import { afterEach, describe, expect, it } from 'vitest';
import { SalliOAuthError } from '../src/errors';
import {
  buildAuthorizationUrl,
  createOAuthTokenProvider,
  createPkcePair,
  DEVICE_CODE_GRANT,
  exchangeAuthorizationCode,
  pkceChallenge,
  pollDeviceAuthorization,
  registerClient,
  requestDeviceAuthorization,
  revokeToken,
  tokensFromResponse,
  type StoredTokens,
} from '../src/oauth';
import { sendJson, startServer, type TestServer } from './helpers/server';

let server: TestServer | undefined;

afterEach(async () => {
  await server?.close();
  server = undefined;
});

const form = (body: string): Record<string, string> => Object.fromEntries(new URLSearchParams(body));

describe('PKCE', () => {
  it('matches the RFC 7636 example', async () => {
    expect(await pkceChallenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk')).toBe(
      'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM',
    );
  });

  it('makes a fresh 43-character verifier each time', async () => {
    const a = await createPkcePair();
    const b = await createPkcePair();
    expect(a.verifier).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(a.verifier).not.toBe(b.verifier);
    expect(a.challenge).toBe(await pkceChallenge(a.verifier));
    expect(a.method).toBe('S256');
  });
});

describe('buildAuthorizationUrl', () => {
  it('carries PKCE, state and the resource indicator', () => {
    const url = new URL(
      buildAuthorizationUrl({
        authorizationEndpoint: 'https://salli.test/mcp/oauth/authorize',
        clientId: 'cli-1',
        redirectUri: 'http://127.0.0.1:5123/callback',
        codeChallenge: 'chal',
        state: 'st',
        resource: 'https://salli.test/v1',
      }),
    );
    expect(Object.fromEntries(url.searchParams)).toEqual({
      response_type: 'code',
      client_id: 'cli-1',
      redirect_uri: 'http://127.0.0.1:5123/callback',
      code_challenge: 'chal',
      code_challenge_method: 'S256',
      state: 'st',
      resource: 'https://salli.test/v1',
    });
  });
});

describe('registerClient and exchangeAuthorizationCode', () => {
  it('registers as JSON and exchanges the code as a form', async () => {
    server = await startServer((req, res) => {
      if (req.path === '/register') sendJson(res, 201, { client_id: 'cli-1', client_name: 'Salli CLI' });
      else sendJson(res, 200, { access_token: 'at', refresh_token: 'rt', expires_in: 3600, token_type: 'Bearer' });
    });
    const client = await registerClient(`${server.url}/register`, {
      client_name: 'Salli CLI',
      redirect_uris: ['http://127.0.0.1/callback'],
      grant_types: ['authorization_code', 'refresh_token'],
      token_endpoint_auth_method: 'none',
    });
    expect(client.client_id).toBe('cli-1');
    expect(server.requests[0]?.headers['content-type']).toBe('application/json');

    const tokens = await exchangeAuthorizationCode({
      tokenEndpoint: `${server.url}/token`,
      clientId: 'cli-1',
      code: 'code-1',
      redirectUri: 'http://127.0.0.1:5123/callback',
      codeVerifier: 'verifier',
      resource: 'https://salli.test/v1',
    });
    expect(tokens.access_token).toBe('at');
    expect(server.requests[1]?.headers['content-type']).toBe('application/x-www-form-urlencoded');
    expect(form(server.requests[1]?.body ?? '')).toEqual({
      grant_type: 'authorization_code',
      code: 'code-1',
      redirect_uri: 'http://127.0.0.1:5123/callback',
      client_id: 'cli-1',
      code_verifier: 'verifier',
      resource: 'https://salli.test/v1',
    });
  });

  it('raises the OAuth error the token endpoint returns', async () => {
    server = await startServer((req, res) =>
      sendJson(res, 400, { error: 'invalid_grant', error_description: 'PKCE verification failed' }),
    );
    const error = await exchangeAuthorizationCode({
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
      code: 'x',
      redirectUri: 'http://127.0.0.1/callback',
      codeVerifier: 'v',
    }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SalliOAuthError);
    expect((error as SalliOAuthError).error).toBe('invalid_grant');
    expect((error as SalliOAuthError).message).toBe('invalid_grant: PKCE verification failed');
  });
});

describe('device authorization', () => {
  it('polls through pending and slow_down until approved', async () => {
    let polls = 0;
    server = await startServer((req, res) => {
      if (req.path === '/device') {
        sendJson(res, 200, {
          device_code: 'dev-1',
          user_code: 'WDJB-MJHT',
          verification_uri: 'https://salli.test/device',
          verification_uri_complete: 'https://salli.test/device?user_code=WDJB-MJHT',
          expires_in: 600,
          interval: 5,
        });
        return;
      }
      polls += 1;
      if (polls === 1) sendJson(res, 400, { error: 'authorization_pending' });
      else if (polls === 2) sendJson(res, 400, { error: 'slow_down' });
      else sendJson(res, 200, { access_token: 'at', refresh_token: 'rt', expires_in: 3600 });
    });
    const device = await requestDeviceAuthorization({
      deviceAuthorizationEndpoint: `${server.url}/device`,
      clientId: 'cli-1',
    });
    expect(device.user_code).toBe('WDJB-MJHT');
    expect(form(server.requests[0]?.body ?? '')).toEqual({ client_id: 'cli-1' });

    const waits: number[] = [];
    const slowedTo: number[] = [];
    const tokens = await pollDeviceAuthorization({
      tokenEndpoint: `${server.url}/token`,
      clientId: 'cli-1',
      device,
      sleep: async (ms) => {
        waits.push(ms);
      },
      onSlowDown: (interval) => slowedTo.push(interval),
    });
    expect(tokens.access_token).toBe('at');
    expect(waits).toEqual([5000, 5000, 10000]);
    expect(slowedTo).toEqual([10]);
    expect(form(server.requests[1]?.body ?? '')).toEqual({
      grant_type: DEVICE_CODE_GRANT,
      device_code: 'dev-1',
      client_id: 'cli-1',
    });
  });

  it('stops on access_denied', async () => {
    server = await startServer((req, res) => sendJson(res, 400, { error: 'access_denied' }));
    const error = await pollDeviceAuthorization({
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
      device: { device_code: 'd', user_code: 'u', verification_uri: 'v', expires_in: 600 },
      sleep: async () => undefined,
    }).catch((e: unknown) => e);
    expect((error as SalliOAuthError).error).toBe('access_denied');
  });

  it('gives up when the code expires', async () => {
    server = await startServer((req, res) => sendJson(res, 400, { error: 'authorization_pending' }));
    let clock = 0;
    const error = await pollDeviceAuthorization({
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
      device: { device_code: 'd', user_code: 'u', verification_uri: 'v', expires_in: 12, interval: 5 },
      now: () => clock,
      sleep: async (ms) => {
        clock += ms;
      },
    }).catch((e: unknown) => e);
    expect((error as SalliOAuthError).error).toBe('expired_token');
    expect(server.requests).toHaveLength(2);
  });

  it('honours expired_token from the server', async () => {
    server = await startServer((req, res) => sendJson(res, 400, { error: 'expired_token' }));
    const error = await pollDeviceAuthorization({
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
      device: { device_code: 'd', user_code: 'u', verification_uri: 'v', expires_in: 600 },
      sleep: async () => undefined,
    }).catch((e: unknown) => e);
    expect((error as SalliOAuthError).error).toBe('expired_token');
  });
});

describe('revokeToken', () => {
  it('sends the RFC 7009 form', async () => {
    server = await startServer((req, res) => sendJson(res, 200, {}));
    await revokeToken({ revocationEndpoint: `${server.url}/revoke`, token: 'rt', tokenTypeHint: 'refresh_token', clientId: 'c' });
    expect(form(server.requests[0]?.body ?? '')).toEqual({ token: 'rt', token_type_hint: 'refresh_token', client_id: 'c' });
  });
});

describe('createOAuthTokenProvider', () => {
  const tokenServer = async (respond: (body: Record<string, string>) => [number, unknown]): Promise<TestServer> =>
    startServer((req, res) => {
      const [status, body] = respond(form(req.body));
      sendJson(res, status, body);
    });

  it('refreshes ahead of expiry and saves the rotated tokens', async () => {
    server = await tokenServer((body) => [200, { access_token: `new-${body.refresh_token}`, refresh_token: 'rt-2', expires_in: 3600 }]);
    const saved: StoredTokens[] = [];
    const now = 1_000_000_000_000;
    const provider = createOAuthTokenProvider({
      tokens: { access_token: 'old', refresh_token: 'rt-1', expires_at: now / 1000 + 30 },
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
      resource: 'http://salli.test/v1',
      save: (t) => {
        saved.push(t);
      },
      now: () => now,
    });
    expect(await provider.getToken()).toBe('new-rt-1');
    expect(saved).toEqual([{ access_token: 'new-rt-1', refresh_token: 'rt-2', expires_at: now / 1000 + 3600 }]);
    expect(form(server.requests[0]?.body ?? '')).toEqual({
      grant_type: 'refresh_token',
      refresh_token: 'rt-1',
      client_id: 'c',
      resource: 'http://salli.test/v1',
    });
  });

  it('keeps the refresh token when the server does not rotate it', async () => {
    server = await tokenServer(() => [200, { access_token: 'new', expires_in: 60 }]);
    const provider = createOAuthTokenProvider({
      tokens: { access_token: 'old', refresh_token: 'rt-1' },
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
    });
    expect(await provider.refresh('old')).toBe('new');
    expect(provider.tokens.refresh_token).toBe('rt-1');
  });

  it('does not refresh for a token that is no longer current', async () => {
    server = await tokenServer(() => [200, { access_token: 'x' }]);
    const provider = createOAuthTokenProvider({
      tokens: { access_token: 'current', refresh_token: 'rt' },
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
    });
    expect(await provider.refresh('older')).toBe('current');
    expect(server.requests).toHaveLength(0);
  });

  it('uses tokens another process already refreshed', async () => {
    server = await tokenServer(() => [200, { access_token: 'x' }]);
    const provider = createOAuthTokenProvider({
      tokens: { access_token: 'old', refresh_token: 'rt-1' },
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
      reload: () => ({ access_token: 'from-store', refresh_token: 'rt-2' }),
    });
    expect(await provider.refresh('old')).toBe('from-store');
    expect(server.requests).toHaveLength(0);
  });

  it('gives up quietly when the refresh token is refused', async () => {
    server = await tokenServer(() => [400, { error: 'invalid_grant' }]);
    const provider = createOAuthTokenProvider({
      tokens: { access_token: 'old', refresh_token: 'rt' },
      tokenEndpoint: `${server.url}/token`,
      clientId: 'c',
    });
    expect(await provider.refresh('old')).toBeUndefined();
    expect(await provider.refresh('old')).toBeUndefined();
    expect(server.requests).toHaveLength(1);
  });
});

describe('tokensFromResponse', () => {
  it('turns expires_in into an expiry time', () => {
    expect(tokensFromResponse({ access_token: 'a', expires_in: 60, token_type: 'Bearer' }, 10_000)).toEqual({
      access_token: 'a',
      expires_at: 70,
      token_type: 'Bearer',
    });
  });
});
