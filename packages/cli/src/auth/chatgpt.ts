/**
 * Sign in with ChatGPT, on this computer, for the Salli server.
 *
 * OpenAI's sign-in returns only to a loopback address, so it runs where the
 * browser is: the CLI listens on 127.0.0.1, sends the browser to OpenAI
 * (PKCE S256, state and nonce, this server's host id), redeems the code,
 * and hands the credential straight to the server, which checks the ID
 * token, keeps it sealed and renews it. The CLI keeps nothing: it never
 * refreshes the tokens, never stores them, and never prints them.
 */
import { aiChatgptConnect, aiChatgptGet, aiHostGet, oauth, SalliOAuthError, type ChatGptConnection, type SalliClient } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, ExitCode } from '../errors';
import { startLoopbackServer } from './loopback';

export const DYNAMIC_CLIENT_ID = 'dynamic_agent_client';
export const CHATGPT_SCOPE = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct';
export const CHATGPT_RESOURCE = 'https://api.openai.com/v1';
export const MANAGE_USAGE_URL = 'https://chatgpt.com/settings/usage';
export const CALLBACK_PATH = '/auth/callback';
const AGAIN = 'salli ai connect chatgpt';

/**
 * OpenAI's sign-in, or (for tests only) a stand-in on this machine named by
 * SALLI_CHATGPT_AUTH_URL: an https URL, or http on 127.0.0.1.
 */
export function chatGptAuthBase(env: Record<string, string | undefined>): string {
  const override = env.SALLI_CHATGPT_AUTH_URL?.trim();
  if (!override) return 'https://auth.openai.com';
  let url: URL;
  try {
    url = new URL(override);
  } catch {
    throw new CliError(`SALLI_CHATGPT_AUTH_URL is not a URL: ${override}`);
  }
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && url.hostname === '127.0.0.1')) {
    throw new CliError('SALLI_CHATGPT_AUTH_URL must be https, or http on 127.0.0.1.');
  }
  return override.replace(/\/+$/, '');
}

export interface AuthorizationRequest {
  base: string;
  /** Sent as `client_id`: the issued one, or `dynamic_agent_client` to register. */
  clientId: string;
  registering: boolean;
  hostId: string;
  redirectUri: string;
  state: string;
  nonce: string;
  codeChallenge: string;
  loginHint?: string | undefined;
  askConsent?: boolean;
}

/** The URL to open in the browser. It never carries an ID token, so it may be shown. */
export function authorizationUrl(r: AuthorizationRequest): string {
  const params = new URLSearchParams({ client_id: r.clientId });
  if (r.registering) params.set('agent_name_hint', 'Salli');
  else if (r.loginHint) params.set('login_hint', r.loginHint);
  params.set('ext_agent_host_id', r.hostId);
  params.set('response_type', 'code');
  params.set('redirect_uri', r.redirectUri);
  params.set('scope', CHATGPT_SCOPE);
  params.set('resource', CHATGPT_RESOURCE);
  params.set('state', r.state);
  params.set('nonce', r.nonce);
  params.set('code_challenge', r.codeChallenge);
  params.set('code_challenge_method', 'S256');
  if (r.askConsent && !r.registering) params.set('prompt', 'consent');
  return `${r.base}/api/accounts/authorize?${params.toString()}`;
}

const failure = (message: string, hint = `Run \`${AGAIN}\` again.`): CliError =>
  new CliError(message, { exitCode: ExitCode.ERROR, kind: 'chatgpt', hint });

/** The client id the callback settles: issued on registration, the same one when signing in again. */
export function callbackClientId(params: URLSearchParams, sent: string, registering: boolean): string {
  const returned = params.get('client_id') ?? '';
  if (registering) {
    if (!returned || returned === DYNAMIC_CLIENT_ID) throw failure('ChatGPT did not finish registering Salli.');
    return returned;
  }
  if (returned && returned !== sent) throw failure('ChatGPT answered for a different registration of Salli, so it was not used.');
  return sent;
}

interface TokenSet {
  access_token: string;
  refresh_token: string;
  id_token: string;
  token_type?: string;
  expires_in?: number;
  scope?: string;
}

async function redeemCode(
  app: App,
  base: string,
  form: { client_id: string; code: string; code_verifier: string; redirect_uri: string },
): Promise<TokenSet> {
  let response: Response;
  try {
    response = await app.runtime.fetch(`${base}/api/accounts/oauth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
      body: new URLSearchParams({ grant_type: 'authorization_code', ...form, resource: CHATGPT_RESOURCE }).toString(),
      signal: AbortSignal.any([AbortSignal.timeout(30_000), app.runtime.signal]),
    });
  } catch (error) {
    if (app.runtime.signal.aborted) throw error;
    throw failure('Could not reach OpenAI to finish signing in.', 'Check your connection, then run `salli ai connect chatgpt` again.');
  }
  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (response.ok) {
    const { access_token, refresh_token, id_token } = body;
    if (typeof access_token !== 'string' || typeof refresh_token !== 'string' || typeof id_token !== 'string') {
      throw failure('ChatGPT’s answer was missing a token, so nothing was connected.');
    }
    return {
      access_token,
      refresh_token,
      id_token,
      ...(typeof body.token_type === 'string' ? { token_type: body.token_type } : {}),
      ...(typeof body.expires_in === 'number' ? { expires_in: body.expires_in } : {}),
      ...(typeof body.scope === 'string' ? { scope: body.scope } : {}),
    };
  }
  if (body.error === 'invalid_grant') throw failure('That sign-in code was already used or has expired.');
  if (response.status >= 500) throw failure(`OpenAI answered ${response.status}.`, 'Try `salli ai connect chatgpt` again in a moment.');
  throw failure('ChatGPT refused the sign-in.');
}

export interface ConnectOptions {
  /** Register a different ChatGPT account than the connected one. */
  newAccount: boolean;
  /** The loopback port the browser returns to. */
  port: number;
  openBrowser: boolean;
  timeoutMs: number;
}

/** Signs in with ChatGPT here and hands the credential to the server. Returns what the server says. */
export async function connectChatGpt(app: App, api: SalliClient, options: ConnectOptions): Promise<ChatGptConnection> {
  const base = chatGptAuthBase(app.runtime.env);
  const [{ ext_agent_host_id: hostId }, status] = await Promise.all([api.call(aiHostGet), api.call(aiChatgptGet)]);
  if (!status.available) {
    throw new CliError('ChatGPT is off on this server.', { hint: 'It needs an encryption key (BYOK_ENCRYPTION_KEYS) and real sign-in.' });
  }
  const issued = status.client_id && status.client_id !== DYNAMIC_CLIENT_ID ? status.client_id : undefined;
  const registering = options.newAccount || !issued;
  const clientId = registering ? DYNAMIC_CLIENT_ID : (issued as string);
  const state = oauth.randomToken(32);
  const nonce = oauth.randomToken(32);
  const pkce = await oauth.createPkcePair();

  let loopback;
  try {
    loopback = await startLoopbackServer(state, { port: options.port, path: CALLBACK_PATH, again: AGAIN });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'EADDRINUSE') {
      throw failure(`Port ${options.port} on 127.0.0.1 is in use.`, 'Close what is using it, or pass --port.');
    }
    throw error;
  }
  try {
    const url = authorizationUrl({
      base,
      clientId,
      registering,
      hostId,
      redirectUri: loopback.redirectUri,
      state,
      nonce,
      codeChallenge: pkce.challenge,
      loginHint: registering ? undefined : (status.email ?? undefined),
      askConsent: status.status === 'needs_consent',
    });
    const out = app.out;
    out.info(`${out.errColors.bold('Continue with ChatGPT')} in your browser to connect your ChatGPT plan to Salli.`);
    out.info(`Salli’s AI requests will then use your ChatGPT plan and count toward its usage limits. Manage usage: ${MANAGE_USAGE_URL}`);
    const opened = options.openBrowser ? await app.runtime.openUrl(url) : false;
    if (!opened) out.info(`Open this link to continue:\n${url}`);

    const spinner = app.prompter.spinner();
    spinner.start('Waiting for you to continue in the browser');
    let params: URLSearchParams;
    try {
      params = await loopback.waitForCallback({ signal: app.runtime.signal, timeoutMs: options.timeoutMs });
    } catch (error) {
      if (error instanceof SalliOAuthError && error.error === 'access_denied') {
        throw failure('Salli was not allowed to use your ChatGPT plan, so nothing was connected.', 'Try again, or add your own API key: `salli llm-keys set openai`.');
      }
      if (error instanceof SalliOAuthError) throw failure(`ChatGPT could not complete the sign-in (${error.error}).`);
      throw error;
    } finally {
      spinner.stop();
    }
    const sentClientId = callbackClientId(params, clientId, registering);
    const code = params.get('code') ?? '';
    const tokens = await redeemCode(app, base, { client_id: sentClientId, code, code_verifier: pkce.verifier, redirect_uri: loopback.redirectUri });
    // Handed over at once; nothing is kept here.
    return await api.call(aiChatgptConnect, { body: { client_id: sentClientId, ...tokens } });
  } finally {
    await loopback.close();
  }
}
