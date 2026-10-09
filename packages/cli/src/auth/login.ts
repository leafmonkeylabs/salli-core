/**
 * Signing in, three ways:
 *
 * - browser (default): OAuth 2.1 authorization code + PKCE (S256), with the
 *   browser redirected back to a loopback server on 127.0.0.1, on whatever
 *   port the system gives it (RFC 8252);
 * - device: the device authorization grant (RFC 8628), for a machine with
 *   no browser: approve on another device with a short code. Also what the
 *   browser sign-in falls back to when no browser can open here;
 * - token: a personal access token, used as it is.
 *
 * OAuth tokens are asked for the server's API (`resource` is the
 * `api_resource` from `/v1/meta`): a token issued for MCP is refused by the
 * API. The CLI registers itself with each server once (RFC 7591) and keeps
 * the client_id in the context.
 */
import {
  authMe,
  normalizeServerUrl,
  oauth,
  SalliApiError,
  SalliOAuthError,
  type Meta,
  type OAuthEndpoints,
} from '@leafmonkeylabs/salli-sdk';
import { assertCompatible, type App } from '../app';
import {
  DEFAULT_CONTEXT,
  DEFAULT_SERVER,
  findContext,
  validateContextName,
  type ContextEntry,
} from '../config/config';
import { CliError, ExitCode, IncompatibleServerError, NotSignedInError, UsageError } from '../errors';
import type { OAuthCredentials, StoredCredentials, TokenCredentials } from './credentials';
import { startLoopbackServer } from './loopback';

/** What the CLI registers as (RFC 7591). */
export const CLIENT_METADATA = {
  client_name: 'Salli CLI',
  redirect_uris: ['http://127.0.0.1/callback'],
  grant_types: ['authorization_code', 'refresh_token'],
  token_endpoint_auth_method: 'none',
} as const;

export interface LoginTarget {
  name: string;
  server: string;
  entry: ContextEntry | undefined;
}

/**
 * The context `salli login` signs in to: --context (created if new), else the
 * current one, else "default"; its server from --server, SALLI_SERVER, the
 * context, a prompt, or http://localhost:8000.
 */
export async function resolveLoginTarget(app: App): Promise<LoginTarget> {
  const config = await app.config();
  const name = validateContextName(app.globals.context ?? app.runtime.env.SALLI_CONTEXT ?? config.current_context ?? DEFAULT_CONTEXT);
  const entry = findContext(config, name);
  let server = app.globals.server ?? app.runtime.env.SALLI_SERVER ?? entry?.server;
  if (!server) {
    server = app.prompter.interactive
      ? await app.prompter.text({
          message: 'Which Salli server?',
          initialValue: DEFAULT_SERVER,
          validate: (value) => {
            try {
              normalizeServerUrl(value);
              return undefined;
            } catch (error) {
              return (error as Error).message;
            }
          },
        })
      : DEFAULT_SERVER;
  }
  try {
    return { name, server: normalizeServerUrl(server), entry };
  } catch (error) {
    throw new UsageError((error as Error).message);
  }
}

/** Saves the context (pointing at its server) and makes it the current one. */
export async function saveLoginContext(app: App, target: LoginTarget, changes: Partial<ContextEntry> = {}): Promise<ContextEntry> {
  let saved: ContextEntry | undefined;
  await app.updateConfig((config) => {
    let entry = findContext(config, target.name);
    if (!entry) {
      entry = { name: target.name, server: target.server };
      config.contexts.push(entry);
    }
    if (entry.server !== target.server) {
      // A different server: what was learned about the old one does not apply.
      entry.server = target.server;
      delete entry.client_id;
      delete entry.api_version;
      delete entry.checked_at;
    }
    Object.assign(entry, changes);
    config.current_context = target.name;
    saved = { ...entry };
  });
  target.entry = saved;
  return saved as ContextEntry;
}

/** `/v1/meta`, checked for API compatibility. */
export async function serverMeta(app: App, server: string): Promise<Meta> {
  let meta: Meta;
  try {
    meta = await app.client(server, undefined, 15_000).meta();
  } catch (error) {
    if (error instanceof SalliApiError && error.status === 404) {
      throw new IncompatibleServerError(`${server} has no /v1/meta: it is not a Salli server, or one older than this CLI.`);
    }
    throw error;
  }
  assertCompatible(meta, server);
  return meta;
}

async function registerCli(app: App, endpoints: OAuthEndpoints): Promise<string> {
  if (!endpoints.registration_endpoint) {
    throw new CliError('This server does not let clients register, so the CLI cannot sign in with OAuth.', {
      exitCode: ExitCode.NOT_SIGNED_IN,
      kind: 'not-signed-in',
      hint: 'Sign in with a personal access token: `salli login --token <token>`.',
    });
  }
  const client = await oauth.registerClient(
    endpoints.registration_endpoint,
    { ...CLIENT_METADATA, redirect_uris: [...CLIENT_METADATA.redirect_uris], grant_types: [...CLIENT_METADATA.grant_types] },
    { fetch: app.runtime.fetch, signal: app.runtime.signal },
  );
  return client.client_id;
}

/** The client_id registered for this context's server, registering once if needed. */
async function clientIdFor(app: App, target: LoginTarget, endpoints: OAuthEndpoints, fresh = false): Promise<string> {
  const known = target.entry?.server === target.server ? target.entry.client_id : undefined;
  if (known && !fresh) return known;
  const clientId = await registerCli(app, endpoints);
  await saveLoginContext(app, target, { client_id: clientId });
  return clientId;
}

type Preflight = { ok: true } | { ok: false; detail: string };

/**
 * Asks the authorization endpoint whether it accepts this request before
 * the browser does, so a problem (an unknown client after a server reset)
 * is dealt with here rather than shown on a web page while the terminal
 * waits.
 */
async function preflight(app: App, url: string): Promise<Preflight> {
  let response: Response;
  try {
    response = await app.runtime.fetch(url, {
      redirect: 'manual',
      headers: { Accept: 'text/html,application/json' },
      signal: AbortSignal.any([AbortSignal.timeout(15_000), app.runtime.signal]),
    });
  } catch {
    return { ok: true }; // let the browser try
  }
  const text = await response.text().catch(() => '');
  if (response.status < 400) return { ok: true };
  let detail = text.slice(0, 300);
  try {
    const body = JSON.parse(text) as { detail?: unknown; error_description?: unknown };
    if (typeof body.detail === 'string') detail = body.detail;
    else if (typeof body.error_description === 'string') detail = body.error_description;
  } catch {
    // not JSON
  }
  return { ok: false, detail };
}

function oauthCredentials(
  target: LoginTarget,
  endpoints: OAuthEndpoints,
  clientId: string,
  resource: string,
  method: OAuthCredentials['method'],
  tokens: oauth.TokenResponse,
  now: Date,
): OAuthCredentials {
  return {
    kind: 'oauth',
    server: target.server,
    client_id: clientId,
    token_endpoint: endpoints.token_endpoint,
    ...(endpoints.revocation_endpoint ? { revocation_endpoint: endpoints.revocation_endpoint } : {}),
    resource,
    method,
    tokens: oauth.tokensFromResponse(tokens, now.getTime()),
    signed_in_at: now.toISOString(),
  };
}

export interface BrowserLoginOptions {
  /** Open the browser (default), or only print the URL. */
  openBrowser: boolean;
  /** When the browser does not open, throw `NoBrowserError` instead of printing the URL. */
  failWithoutBrowser?: boolean;
  timeoutMs?: number;
}

/** No browser could be opened (so another way to sign in is needed). */
export class NoBrowserError extends Error {
  override readonly name = 'NoBrowserError';
}

/** Authorization code + PKCE with a loopback redirect. */
export async function browserLogin(app: App, target: LoginTarget, meta: Meta, options: BrowserLoginOptions): Promise<OAuthCredentials> {
  const endpoints = oauth.oauthEndpointsOf(meta);
  const resource = endpoints.api_resource;
  const state = oauth.randomToken(16);
  const loopback = await startLoopbackServer(state);
  try {
    const pkce = await oauth.createPkcePair();
    let clientId = await clientIdFor(app, target, endpoints);
    const urlFor = (id: string): string =>
      oauth.buildAuthorizationUrl({
        authorizationEndpoint: endpoints.authorization_endpoint,
        clientId: id,
        redirectUri: loopback.redirectUri,
        codeChallenge: pkce.challenge,
        state,
        resource,
      });

    let url = urlFor(clientId);
    let check = await preflight(app, url);
    if (!check.ok && /client/i.test(check.detail)) {
      // The server forgot this client (reset, or a different deployment): register again.
      clientId = await clientIdFor(app, target, endpoints, true);
      url = urlFor(clientId);
      check = await preflight(app, url);
    }
    if (!check.ok) {
      throw new CliError(`The server would not start a browser sign-in: ${check.detail}`, {
        exitCode: ExitCode.NOT_SIGNED_IN,
        kind: 'not-signed-in',
        hint: 'Try `salli login --device`, or `salli login --token <token>`.',
      });
    }

    const out = app.out;
    const opened = options.openBrowser ? await app.runtime.openUrl(url) : false;
    if (options.openBrowser && !opened && options.failWithoutBrowser) throw new NoBrowserError('No browser could be opened.');
    out.info(
      opened
        ? `Opening your browser to sign in to ${out.errColors.bold(target.server)}…`
        : `Open this link to sign in to ${out.errColors.bold(target.server)}:`,
    );
    out.info(opened ? out.errColors.dim(`If it does not open, visit: ${url}`) : url);

    const spinner = app.prompter.spinner();
    spinner.start('Waiting for you to approve in the browser');
    let code: string;
    try {
      code = await loopback.waitForCode({ signal: app.runtime.signal, timeoutMs: options.timeoutMs ?? 5 * 60_000 });
    } finally {
      spinner.stop();
    }
    const tokens = await oauth.exchangeAuthorizationCode({
      tokenEndpoint: endpoints.token_endpoint,
      clientId,
      code,
      redirectUri: loopback.redirectUri,
      codeVerifier: pkce.verifier,
      resource,
      fetch: app.runtime.fetch,
      signal: app.runtime.signal,
    });
    return oauthCredentials(target, endpoints, clientId, resource, 'browser', tokens, app.runtime.now());
  } finally {
    await loopback.close();
  }
}

/** The device authorization grant: approve with a code on another device. */
export async function deviceLogin(app: App, target: LoginTarget, meta: Meta): Promise<OAuthCredentials> {
  const endpoints = oauth.oauthEndpointsOf(meta);
  if (!endpoints.device_authorization_endpoint) {
    throw new CliError(`${target.server} does not offer device sign-in.`, {
      exitCode: ExitCode.NOT_SIGNED_IN,
      kind: 'not-signed-in',
      hint: 'Use `salli login` (in a browser on this machine) or `salli login --token <token>`.',
    });
  }
  const resource = endpoints.api_resource;
  let clientId = await clientIdFor(app, target, endpoints);
  const request = (id: string): Promise<oauth.DeviceAuthorization> =>
    oauth.requestDeviceAuthorization({
      deviceAuthorizationEndpoint: endpoints.device_authorization_endpoint,
      clientId: id,
      resource,
      fetch: app.runtime.fetch,
      signal: app.runtime.signal,
    });
  let device: oauth.DeviceAuthorization;
  try {
    device = await request(clientId);
  } catch (error) {
    if (!(error instanceof SalliOAuthError && error.error === 'invalid_client')) throw error;
    clientId = await clientIdFor(app, target, endpoints, true);
    device = await request(clientId);
  }

  const out = app.out;
  const c = out.errColors;
  out.info(`To sign in to ${c.bold(target.server)}, open:`);
  out.info(`  ${c.cyan(device.verification_uri_complete ?? device.verification_uri)}`);
  out.info(`and enter the code ${c.bold(device.user_code)}${device.verification_uri_complete ? ' if asked' : ''}.`);
  const minutes = Math.max(1, Math.round(device.expires_in / 60));
  out.note(`The code expires in ${minutes} minute${minutes === 1 ? '' : 's'}.`);

  const spinner = app.prompter.spinner();
  spinner.start('Waiting for approval');
  try {
    const tokens = await oauth.pollDeviceAuthorization({
      tokenEndpoint: endpoints.token_endpoint,
      clientId,
      device,
      resource,
      fetch: app.runtime.fetch,
      signal: app.runtime.signal,
      onSlowDown: (seconds) => spinner.message(`Waiting for approval (checking every ${seconds}s)`),
    });
    return oauthCredentials(target, endpoints, clientId, resource, 'device', tokens, app.runtime.now());
  } catch (error) {
    if (error instanceof SalliOAuthError) {
      if (error.error === 'access_denied') throw new NotSignedInError('Sign-in was declined.', 'Run `salli login --device` to try again.');
      if (error.error === 'expired_token') throw new NotSignedInError('The sign-in code expired.', 'Run `salli login --device` for a new one.');
    }
    throw error;
  } finally {
    spinner.stop();
  }
}

export interface InteractiveLoginOptions {
  /** --device: the device flow, whatever else is possible. */
  device: boolean;
  /** False for --no-browser: print the link to open rather than opening it. */
  openBrowser: boolean;
}

/**
 * Signs in with the browser when one can open here, and otherwise (or with
 * --device) with a code approved on another device.
 */
export async function interactiveLogin(app: App, target: LoginTarget, meta: Meta, options: InteractiveLoginOptions): Promise<OAuthCredentials> {
  if (options.device) return deviceLogin(app, target, meta);
  const deviceOffered = Boolean(oauth.oauthEndpointsOf(meta).device_authorization_endpoint);
  if (options.openBrowser && deviceOffered && !app.runtime.canOpenBrowser()) {
    app.out.note('No browser here, so sign in with a code on another device (or pass --no-browser for a link to open).');
    return deviceLogin(app, target, meta);
  }
  try {
    return await browserLogin(app, target, meta, { openBrowser: options.openBrowser, failWithoutBrowser: deviceOffered });
  } catch (error) {
    if (!(error instanceof NoBrowserError)) throw error;
    app.out.note('No browser opened, so sign in with a code instead.');
    return deviceLogin(app, target, meta);
  }
}

/** A personal access token: checked against the server, then kept as it is. */
export async function tokenLogin(app: App, target: LoginTarget, token: string): Promise<TokenCredentials> {
  const trimmed = token.trim();
  if (!trimmed) throw new UsageError('The token is empty.');
  try {
    await app.client(target.server, { getToken: () => trimmed }).call(authMe);
  } catch (error) {
    if (error instanceof SalliApiError && error.status === 401) {
      throw new NotSignedInError(`${target.server} did not accept that token.`, 'Check it has not expired or been revoked.');
    }
    throw error;
  }
  return { kind: 'token', server: target.server, token: trimmed, signed_in_at: app.runtime.now().toISOString() };
}

/**
 * Revokes stored OAuth tokens (refresh first, then access). Best effort:
 * returns what went wrong rather than throwing, since signing out locally
 * should not depend on the server.
 */
export async function revokeCredentials(app: App, credentials: StoredCredentials): Promise<{ revoked: boolean; problem?: string }> {
  if (credentials.kind !== 'oauth' || !credentials.revocation_endpoint) return { revoked: false };
  const tokens = [
    credentials.tokens.refresh_token ? { token: credentials.tokens.refresh_token, hint: 'refresh_token' as const } : undefined,
    { token: credentials.tokens.access_token, hint: 'access_token' as const },
  ].filter((t) => t !== undefined);
  try {
    for (const { token, hint } of tokens) {
      await oauth.revokeToken({
        revocationEndpoint: credentials.revocation_endpoint,
        token,
        tokenTypeHint: hint,
        clientId: credentials.client_id,
        fetch: app.runtime.fetch,
      });
    }
    return { revoked: true };
  } catch (error) {
    return { revoked: false, problem: (error as Error).message };
  }
}
