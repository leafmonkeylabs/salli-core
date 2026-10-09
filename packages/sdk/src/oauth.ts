/**
 * Signing in to a Salli server: OAuth 2.1 for a public client.
 *
 * The protocol pieces a native client needs, independent of how it shows a
 * browser or stores tokens: dynamic client registration (RFC 7591), PKCE
 * (RFC 7636), the authorization code exchange with resource indicators
 * (RFC 8707), the device authorization grant (RFC 8628), refresh, and
 * revocation (RFC 7009). The endpoints come from `GET /v1/meta`.
 */
import type { Meta } from './generated/types.gen';
import { SalliApiError, SalliNetworkError, SalliOAuthError } from './errors';
import type { TokenProvider } from './client';

/** The sign-in endpoints a server advertises in `/v1/meta`. */
export interface OAuthEndpoints {
  issuer?: string;
  authorization_endpoint: string;
  token_endpoint: string;
  registration_endpoint?: string;
  revocation_endpoint?: string;
  /** RFC 8628. Optional: not every server offers device sign-in. */
  device_authorization_endpoint?: string;
}

/** The OAuth endpoints in a `/v1/meta` response. */
export function oauthEndpointsOf(meta: Meta): OAuthEndpoints {
  return meta.oauth as OAuthEndpoints;
}

/** A token endpoint's successful answer (RFC 6749 §5.1). */
export interface TokenResponse {
  access_token: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
  scope?: string;
  [extension: string]: unknown;
}

/** Tokens as a client keeps them: the expiry as a time, not a duration. */
export interface StoredTokens {
  access_token: string;
  refresh_token?: string;
  /** Seconds since the epoch when the access token expires. */
  expires_at?: number;
  scope?: string;
  token_type?: string;
}

/** Converts a token response to what a client stores. */
export function tokensFromResponse(response: TokenResponse, nowMs: number = Date.now()): StoredTokens {
  const tokens: StoredTokens = { access_token: response.access_token };
  if (response.refresh_token) tokens.refresh_token = response.refresh_token;
  if (typeof response.expires_in === 'number') {
    tokens.expires_at = Math.floor(nowMs / 1000) + response.expires_in;
  }
  if (response.scope) tokens.scope = response.scope;
  if (response.token_type) tokens.token_type = response.token_type;
  return tokens;
}

interface FetchOption {
  fetch?: typeof globalThis.fetch;
  signal?: AbortSignal;
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function send(url: string, init: RequestInit, options: FetchOption): Promise<Response> {
  const fetchImpl = options.fetch ?? globalThis.fetch;
  try {
    return await fetchImpl(url, { ...init, ...(options.signal ? { signal: options.signal } : {}) });
  } catch (error) {
    if ((error as { name?: string } | undefined)?.name === 'AbortError') throw error;
    throw SalliNetworkError.fromFetchError(error, url);
  }
}

/** Raises the error an OAuth endpoint answered with. */
function oauthError(response: Response, body: unknown, url: string): Error {
  if (typeof body === 'object' && body !== null && typeof (body as { error?: unknown }).error === 'string') {
    const b = body as { error: string; error_description?: unknown };
    return new SalliOAuthError(
      b.error,
      typeof b.error_description === 'string' ? b.error_description : undefined,
      response.status,
    );
  }
  return SalliApiError.fromResponse(response, body, new Request(url, { method: 'POST' }));
}

/** POSTs a form to an OAuth endpoint and returns its JSON answer. */
async function postForm(
  url: string,
  params: Record<string, string | undefined>,
  options: FetchOption,
): Promise<Record<string, unknown>> {
  const form = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined) form.set(key, value);
  const response = await send(
    url,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
      body: form.toString(),
    },
    options,
  );
  const body = await readBody(response);
  if (!response.ok) throw oauthError(response, body, url);
  if (typeof body !== 'object' || body === null) {
    throw new SalliOAuthError('invalid_response', `Expected JSON from ${url}`, response.status);
  }
  return body as Record<string, unknown>;
}

function asTokenResponse(body: Record<string, unknown>, url: string): TokenResponse {
  if (typeof body.access_token !== 'string' || !body.access_token) {
    throw new SalliOAuthError('invalid_response', `No access_token in the answer from ${url}`);
  }
  return body as TokenResponse;
}

// ── Dynamic client registration (RFC 7591) ──────────────────────────────────

/** What a client says about itself when registering. */
export interface ClientMetadata {
  client_name?: string;
  redirect_uris: string[];
  grant_types?: string[];
  response_types?: string[];
  token_endpoint_auth_method?: string;
  [field: string]: unknown;
}

export interface RegisteredClient {
  client_id: string;
  [field: string]: unknown;
}

/** Registers a client with the server and returns its `client_id`. */
export async function registerClient(
  registrationEndpoint: string,
  metadata: ClientMetadata,
  options: FetchOption = {},
): Promise<RegisteredClient> {
  const response = await send(
    registrationEndpoint,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(metadata),
    },
    options,
  );
  const body = await readBody(response);
  if (!response.ok) throw oauthError(response, body, registrationEndpoint);
  const clientId = (body as { client_id?: unknown } | undefined)?.client_id;
  if (typeof clientId !== 'string' || !clientId) {
    throw new SalliOAuthError('invalid_response', 'The server registered no client_id');
  }
  return body as RegisteredClient;
}

// ── PKCE (RFC 7636) ──────────────────────────────────────────────────────────

function base64url(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** A random URL-safe string with `bytes` bytes of entropy. */
export function randomToken(bytes = 32): string {
  return base64url(crypto.getRandomValues(new Uint8Array(bytes)));
}

export interface PkcePair {
  verifier: string;
  challenge: string;
  method: 'S256';
}

/** The S256 challenge for a verifier. */
export async function pkceChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(digest));
}

/** A fresh PKCE verifier (43 characters) and its S256 challenge. */
export async function createPkcePair(): Promise<PkcePair> {
  const verifier = randomToken(32);
  return { verifier, challenge: await pkceChallenge(verifier), method: 'S256' };
}

// ── Authorization code grant ─────────────────────────────────────────────────

export interface AuthorizationUrlParams {
  authorizationEndpoint: string;
  clientId: string;
  redirectUri: string;
  codeChallenge: string;
  state: string;
  /** RFC 8707: the API the token is for, e.g. `https://salli.example.com/v1`. */
  resource?: string;
  scope?: string;
}

/** The URL to send the user's browser to. */
export function buildAuthorizationUrl(params: AuthorizationUrlParams): string {
  const url = new URL(params.authorizationEndpoint);
  url.searchParams.set('response_type', 'code');
  url.searchParams.set('client_id', params.clientId);
  url.searchParams.set('redirect_uri', params.redirectUri);
  url.searchParams.set('code_challenge', params.codeChallenge);
  url.searchParams.set('code_challenge_method', 'S256');
  url.searchParams.set('state', params.state);
  if (params.resource) url.searchParams.set('resource', params.resource);
  if (params.scope) url.searchParams.set('scope', params.scope);
  return url.toString();
}

export interface CodeExchangeParams extends FetchOption {
  tokenEndpoint: string;
  clientId: string;
  code: string;
  redirectUri: string;
  codeVerifier: string;
  resource?: string;
}

/** Exchanges an authorization code (and its PKCE verifier) for tokens. */
export async function exchangeAuthorizationCode(params: CodeExchangeParams): Promise<TokenResponse> {
  const body = await postForm(
    params.tokenEndpoint,
    {
      grant_type: 'authorization_code',
      code: params.code,
      redirect_uri: params.redirectUri,
      client_id: params.clientId,
      code_verifier: params.codeVerifier,
      resource: params.resource,
    },
    params,
  );
  return asTokenResponse(body, params.tokenEndpoint);
}

export interface RefreshParams extends FetchOption {
  tokenEndpoint: string;
  clientId: string;
  refreshToken: string;
  resource?: string;
}

/** Trades a refresh token for new tokens. The server may rotate the refresh token. */
export async function refreshAccessToken(params: RefreshParams): Promise<TokenResponse> {
  const body = await postForm(
    params.tokenEndpoint,
    {
      grant_type: 'refresh_token',
      refresh_token: params.refreshToken,
      client_id: params.clientId,
      resource: params.resource,
    },
    params,
  );
  return asTokenResponse(body, params.tokenEndpoint);
}

// ── Device authorization grant (RFC 8628) ────────────────────────────────────

export const DEVICE_CODE_GRANT = 'urn:ietf:params:oauth:grant-type:device_code';

export interface DeviceAuthorization {
  device_code: string;
  user_code: string;
  verification_uri: string;
  verification_uri_complete?: string;
  /** Seconds until the codes expire. */
  expires_in: number;
  /** Seconds to wait between polls. Default 5. */
  interval?: number;
}

export interface DeviceAuthorizationParams extends FetchOption {
  deviceAuthorizationEndpoint: string;
  clientId: string;
  scope?: string;
  resource?: string;
}

/** Starts a device sign-in: returns the code the user enters, and where. */
export async function requestDeviceAuthorization(
  params: DeviceAuthorizationParams,
): Promise<DeviceAuthorization> {
  const body = await postForm(
    params.deviceAuthorizationEndpoint,
    { client_id: params.clientId, scope: params.scope, resource: params.resource },
    params,
  );
  if (typeof body.device_code !== 'string' || typeof body.user_code !== 'string') {
    throw new SalliOAuthError('invalid_response', 'The device authorization answer had no codes');
  }
  if (typeof body.verification_uri !== 'string') {
    throw new SalliOAuthError('invalid_response', 'The device authorization answer had no verification_uri');
  }
  return {
    device_code: body.device_code,
    user_code: body.user_code,
    verification_uri: body.verification_uri,
    ...(typeof body.verification_uri_complete === 'string'
      ? { verification_uri_complete: body.verification_uri_complete }
      : {}),
    expires_in: typeof body.expires_in === 'number' ? body.expires_in : 600,
    ...(typeof body.interval === 'number' ? { interval: body.interval } : {}),
  };
}

export interface DevicePollParams extends FetchOption {
  tokenEndpoint: string;
  clientId: string;
  device: DeviceAuthorization;
  resource?: string;
  /** Told when the server asks to slow down, with the new interval in seconds. */
  onSlowDown?: (intervalSeconds: number) => void;
  /** For tests: how to wait, and what time it is. */
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
  now?: () => number;
}

function sleepFor(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = (): void => {
      clearTimeout(timer);
      reject(signal?.reason);
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/**
 * Polls the token endpoint until the user approves the device sign-in.
 * Waits `interval` between polls, five seconds longer after each
 * `slow_down`, keeps going on `authorization_pending`, and throws
 * `SalliOAuthError` on `access_denied`, `expired_token`, or when the codes
 * expire.
 */
export async function pollDeviceAuthorization(params: DevicePollParams): Promise<TokenResponse> {
  const sleep = params.sleep ?? sleepFor;
  const now = params.now ?? Date.now;
  const deadline = now() + params.device.expires_in * 1000;
  let interval = params.device.interval ?? 5;
  for (;;) {
    await sleep(interval * 1000, params.signal);
    if (now() >= deadline) {
      throw new SalliOAuthError('expired_token', 'The sign-in code expired before it was approved.');
    }
    try {
      const body = await postForm(
        params.tokenEndpoint,
        {
          grant_type: DEVICE_CODE_GRANT,
          device_code: params.device.device_code,
          client_id: params.clientId,
          resource: params.resource,
        },
        params,
      );
      return asTokenResponse(body, params.tokenEndpoint);
    } catch (error) {
      if (error instanceof SalliOAuthError && error.error === 'authorization_pending') continue;
      if (error instanceof SalliOAuthError && error.error === 'slow_down') {
        interval += 5;
        params.onSlowDown?.(interval);
        continue;
      }
      throw error;
    }
  }
}

// ── Revocation (RFC 7009) ────────────────────────────────────────────────────

export interface RevokeParams extends FetchOption {
  revocationEndpoint: string;
  token: string;
  tokenTypeHint?: 'access_token' | 'refresh_token';
  clientId?: string;
}

/**
 * Revokes a token. Sent form-encoded as RFC 7009 says; a server that only
 * reads a JSON body answers that with 422, so it is retried once as JSON.
 */
export async function revokeToken(params: RevokeParams): Promise<void> {
  const fields: Record<string, string> = { token: params.token };
  if (params.tokenTypeHint) fields.token_type_hint = params.tokenTypeHint;
  if (params.clientId) fields.client_id = params.clientId;

  let response = await send(
    params.revocationEndpoint,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json' },
      body: new URLSearchParams(fields).toString(),
    },
    params,
  );
  if (response.status === 422 || response.status === 415) {
    await response.body?.cancel().catch(() => undefined);
    response = await send(
      params.revocationEndpoint,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(fields),
      },
      params,
    );
  }
  const body = await readBody(response);
  if (!response.ok) throw oauthError(response, body, params.revocationEndpoint);
}

// ── Tokens that refresh themselves ───────────────────────────────────────────

export interface OAuthTokenProviderOptions {
  tokens: StoredTokens;
  tokenEndpoint: string;
  clientId: string;
  resource?: string;
  /** Persists tokens after a refresh. */
  save?: (tokens: StoredTokens) => void | Promise<void>;
  /**
   * Reads the stored tokens again before refreshing, in case another process
   * already did (refresh tokens rotate, so refreshing twice fails).
   */
  reload?: () => StoredTokens | undefined | Promise<StoredTokens | undefined>;
  fetch?: typeof globalThis.fetch;
  /** Refresh this many seconds before the access token expires. Default 60. */
  refreshMarginSeconds?: number;
  now?: () => number;
}

export interface OAuthTokenProvider extends TokenProvider {
  /** The tokens currently in use. */
  readonly tokens: StoredTokens;
  refresh(failedToken: string | undefined): Promise<string | undefined>;
}

/**
 * A token provider for OAuth tokens: refreshes ahead of expiry and once on
 * a 401, one refresh at a time, keeping the refresh token when the server
 * does not rotate it.
 */
export function createOAuthTokenProvider(options: OAuthTokenProviderOptions): OAuthTokenProvider {
  let tokens = options.tokens;
  let inflight: Promise<string | undefined> | undefined;
  let refreshFailed = false;
  const now = options.now ?? Date.now;
  const margin = options.refreshMarginSeconds ?? 60;

  const doRefresh = async (): Promise<string | undefined> => {
    if (options.reload) {
      const latest = await options.reload();
      if (latest && latest.access_token !== tokens.access_token) {
        tokens = latest;
        if (!expiringSoon()) return tokens.access_token;
      }
    }
    if (!tokens.refresh_token) return undefined;
    try {
      const response = await refreshAccessToken({
        tokenEndpoint: options.tokenEndpoint,
        clientId: options.clientId,
        refreshToken: tokens.refresh_token,
        ...(options.resource ? { resource: options.resource } : {}),
        ...(options.fetch ? { fetch: options.fetch } : {}),
      });
      const next = tokensFromResponse(response, now());
      if (!next.refresh_token && tokens.refresh_token) next.refresh_token = tokens.refresh_token;
      tokens = next;
      await options.save?.(tokens);
      return tokens.access_token;
    } catch (error) {
      if (error instanceof SalliOAuthError) {
        refreshFailed = true;
        return undefined;
      }
      throw error;
    }
  };

  const refreshOnce = (): Promise<string | undefined> => {
    inflight ??= doRefresh().finally(() => {
      inflight = undefined;
    });
    return inflight;
  };

  function expiringSoon(): boolean {
    return tokens.expires_at !== undefined && now() / 1000 >= tokens.expires_at - margin;
  }

  return {
    get tokens() {
      return tokens;
    },
    async getToken() {
      if (expiringSoon() && tokens.refresh_token && !refreshFailed) await refreshOnce();
      return tokens.access_token;
    },
    async refresh(failedToken) {
      if (failedToken !== undefined && failedToken !== tokens.access_token) return tokens.access_token;
      if (refreshFailed) return undefined;
      return refreshOnce();
    },
  };
}
