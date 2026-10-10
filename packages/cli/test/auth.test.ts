import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli, type MockOptions } from './helpers/mock-server';
import { closedServerUrl, runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;

async function startMock(options: MockOptions = {}): Promise<MockSalli> {
  mock = await MockSalli.start(options);
  return mock;
}

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await mock?.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) => runCli(args, { configDir: dir, ...options });

async function credentials(): Promise<Record<string, { kind: string; tokens?: Record<string, unknown>; client_id?: string; method?: string; server?: string; token?: string }>> {
  const raw = JSON.parse(await readFile(join(dir, 'credentials.json'), 'utf8')) as Record<string, string>;
  return Object.fromEntries(Object.entries(raw).map(([name, secret]) => [name, JSON.parse(secret)])) as never;
}

async function config(): Promise<{ current_context: string; contexts: Array<Record<string, string>> }> {
  return JSON.parse(await readFile(join(dir, 'config.json'), 'utf8')) as never;
}

describe('salli login (browser, PKCE, loopback)', () => {
  it('signs in as the server’s own CLI client, without registering one', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url]);
    expect(result.code).toBe(0);
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(0);

    const authorize = new URL(result.opened[0] ?? '');
    expect(authorize.searchParams.get('client_id')).toBe('salli-cli');
    expect(authorize.searchParams.get('redirect_uri')).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/callback$/);
    expect(mock.requestsTo('POST', '/mcp/oauth/token')[0]?.form).toMatchObject({ grant_type: 'authorization_code', client_id: 'salli-cli' });
    expect((await credentials()).default).toMatchObject({ kind: 'oauth', method: 'browser', client_id: 'salli-cli' });
    // Nothing registered, so nothing to remember about a registration.
    expect((await config()).contexts[0]?.client_id).toBeUndefined();

    // That sign-in may activate tax rule sets; the server says so.
    const me = JSON.parse((await run(['whoami', '--json'])).stdout) as { permissions: string[] };
    expect(me.permissions).toEqual(['tax:activate']);
  });

  it('uses the CLI’s client over a registration saved from before', async () => {
    await startMock({ cliClient: false });
    expect((await run(['login', '--server', mock.url])).code).toBe(0);
    expect((await config()).contexts[0]?.client_id).toBe('client-1');
    await mock.close();
    // The same server, upgraded: it now names the CLI's own client.
    const upgraded = await MockSalli.start();
    try {
      const again = await run(['login', '--server', upgraded.url]);
      expect(again.code).toBe(0);
      expect(upgraded.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(0);
      expect((await credentials()).default?.client_id).toBe('salli-cli');
    } finally {
      await upgraded.close();
    }
  });

  it('never swaps the CLI’s own client for a registered one', async () => {
    await startMock();
    mock.clients.delete('salli-cli'); // advertised, but the server does not know it (unmigrated)
    const result = await run(['login', '--server', mock.url]);
    expect(result.code).toBe(3);
    expect(result.opened).toEqual([]);
    expect(result.stderr).toContain('names "salli-cli" as the CLI’s client, but does not know it');
    expect(result.stderr).toContain('salli-server db upgrade');
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(0);
  });

  it('on a server that names no CLI client, registers once, signs in through the loopback redirect and stores the tokens', async () => {
    await startMock({ cliClient: false });
    const result = await run(['login', '--server', mock.url]);
    expect(result.stderr).toContain(`Signed in to ${mock.url} as user-123 (context "default")`);
    expect(result.code).toBe(0);

    // Registered exactly as RFC 7591 asks, with the loopback redirect.
    const [registration] = mock.requestsTo('POST', '/mcp/oauth/register');
    expect(registration?.json).toEqual({
      client_name: 'Salli CLI',
      redirect_uris: ['http://127.0.0.1/callback'],
      grant_types: ['authorization_code', 'refresh_token'],
      token_endpoint_auth_method: 'none',
    });

    // The browser was sent to the authorization endpoint with PKCE, state and the resource.
    expect(result.opened).toHaveLength(1);
    const authorize = new URL(result.opened[0] ?? '');
    expect(authorize.pathname).toBe('/mcp/oauth/authorize');
    expect(authorize.searchParams.get('client_id')).toBe('client-1');
    expect(authorize.searchParams.get('code_challenge_method')).toBe('S256');
    expect(authorize.searchParams.get('resource')).toBe(`${mock.url}/v1`);
    expect(authorize.searchParams.get('redirect_uri')).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/callback$/);
    expect(authorize.searchParams.get('state')).toMatch(/^[A-Za-z0-9_-]{22}$/);

    // The code was exchanged with its verifier, form-encoded.
    const [exchange] = mock.requestsTo('POST', '/mcp/oauth/token');
    expect(exchange?.headers['content-type']).toBe('application/x-www-form-urlencoded');
    expect(exchange?.form).toMatchObject({
      grant_type: 'authorization_code',
      client_id: 'client-1',
      redirect_uri: authorize.searchParams.get('redirect_uri'),
      resource: `${mock.url}/v1`,
    });

    const stored = (await credentials()).default;
    expect(stored).toMatchObject({ kind: 'oauth', method: 'browser', client_id: 'client-1', server: mock.url });
    expect(typeof stored?.tokens?.access_token).toBe('string');
    expect(typeof stored?.tokens?.expires_at).toBe('number');
    expect(await config()).toMatchObject({
      current_context: 'default',
      contexts: [{ name: 'default', server: mock.url, client_id: 'client-1', api_version: '1' }],
    });

    // A second login reuses the registration.
    expect((await run(['login'])).code).toBe(0);
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(1);
  });

  it('prints JSON with --json', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url, '--context', 'home', '--json']);
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual({
      context: 'home',
      server: mock.url,
      method: 'browser',
      user: { user_id: 'user-123', email: null, method: 'oauth', permissions: ['tax:activate'] },
    });
  });

  it('only prints the link with --no-browser', async () => {
    await startMock();
    const pending = run(['login', '--server', mock.url, '--no-browser'], {
      openUrl: async () => true,
    });
    // The CLI prints the link on stderr; follow it as the user would.
    const started = Date.now();
    while (Date.now() - started < 5000) {
      const authorize = mock.requestsTo('GET', '/mcp/oauth/authorize');
      if (authorize.length > 0) break;
      await new Promise((r) => setTimeout(r, 20));
    }
    // The preflight request carries the full URL.
    const preflight = mock.requestsTo('GET', '/mcp/oauth/authorize')[0];
    const link = `${mock.url}${preflight?.path}?${preflight?.query.toString()}`;
    await fetch(link, { redirect: 'follow' }).then((r) => r.text());
    const result = await pending;
    expect(result.opened).toEqual([]);
    expect(result.stderr).toContain('Open this link to sign in');
    expect(result.code).toBe(0);
  });

  it('asks for tokens for the API resource the server names', async () => {
    await startMock({ apiResource: 'https://api.example.com/v1' });
    const result = await run(['login', '--server', mock.url]);
    expect(result.code).toBe(0);
    expect(new URL(result.opened[0] ?? '').searchParams.get('resource')).toBe('https://api.example.com/v1');
    expect(mock.requestsTo('POST', '/mcp/oauth/token')[0]?.form?.resource).toBe('https://api.example.com/v1');
  });

  it('reports what the server refuses before opening a browser', async () => {
    await startMock({ strictLoopback: true });
    const result = await run(['login', '--server', mock.url]);
    expect(result.code).toBe(3);
    expect(result.opened).toEqual([]);
    expect(result.stderr).toContain('redirect_uri does not match a registered value');
    expect(result.stderr).toContain('salli login --device');
  });

  it('signs in with a code instead where no browser can open', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url], { browser: false });
    expect(result.code).toBe(0);
    expect(result.opened).toEqual([]);
    expect(result.stderr).toContain('No browser here');
    expect(result.stderr).toContain('WDJB-MJHT');
    expect(mock.requestsTo('POST', '/mcp/oauth/device_authorization')[0]?.form).toMatchObject({ client_id: 'salli-cli', resource: `${mock.url}/v1` });
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(0);
    expect((await credentials()).default).toMatchObject({ kind: 'oauth', method: 'device' });
  });

  it('signs in with a code instead when the browser does not open', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url], { openUrl: async () => false });
    expect(result.code).toBe(0);
    expect(result.opened).toHaveLength(1);
    expect(result.stderr).toContain('No browser opened');
    expect((await credentials()).default).toMatchObject({ kind: 'oauth', method: 'device' });
  });

  it('prints the link for a server without device sign-in, when the browser does not open', async () => {
    await startMock({ device: false });
    const pending = run(['login', '--server', mock.url], { openUrl: async () => false });
    const started = Date.now();
    while (Date.now() - started < 5000 && mock.requestsTo('GET', '/mcp/oauth/authorize').length === 0) {
      await new Promise((r) => setTimeout(r, 20));
    }
    const preflight = mock.requestsTo('GET', '/mcp/oauth/authorize')[0];
    await fetch(`${mock.url}${preflight?.path}?${preflight?.query.toString()}`, { redirect: 'follow' }).then((r) => r.text());
    const result = await pending;
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Open this link to sign in');
    expect((await credentials()).default).toMatchObject({ kind: 'oauth', method: 'browser' });
  });

  it('registers again when the server has forgotten the client it registered', async () => {
    await startMock({ cliClient: false });
    expect((await run(['login', '--server', mock.url])).code).toBe(0);
    mock.clients.clear(); // e.g. the server's database was reset
    const again = await run(['login']);
    expect(again.code).toBe(0);
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(2);
    expect((await config()).contexts[0]?.client_id).toBe('client-1');
  });

  it('exits 3 when the user declines', async () => {
    await startMock({ consent: false });
    const result = await run(['login', '--server', mock.url]);
    expect(result.code).toBe(3);
    expect(result.stderr).toContain('access_denied');
  });

  it('refuses a server that speaks another API version (exit 6)', async () => {
    await startMock({ apiVersion: '2' });
    const result = await run(['login', '--server', mock.url]);
    expect(result.code).toBe(6);
    expect(result.stderr).toContain('speaks API version 2');
  });

  it('exits 7 when the server is unreachable', async () => {
    const closed = await closedServerUrl();
    const result = await run(['login', '--server', closed]);
    expect(result.code).toBe(7);
    expect(result.stderr).toContain(`Could not reach ${closed} (connection refused)`);
  });
});

describe('salli login --device', () => {
  it('shows the code and polls until approved', async () => {
    await startMock({ deviceSteps: ['authorization_pending', 'authorization_pending', 'approve'] });
    const result = await run(['login', '--device', '--server', mock.url]);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('WDJB-MJHT');
    expect(result.stderr).toContain(`${mock.url}/mcp/oauth/device?user_code=WDJB-MJHT`);
    expect(result.opened).toEqual([]);
    const polls = mock.requestsTo('POST', '/mcp/oauth/token');
    expect(polls).toHaveLength(3);
    expect(polls[0]?.form).toMatchObject({
      grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
      device_code: 'dev-code-1',
      client_id: 'salli-cli',
    });
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(0);
    expect((await credentials()).default).toMatchObject({ kind: 'oauth', method: 'device', client_id: 'salli-cli' });
  });

  it('registers for the device flow on a server that names no CLI client', async () => {
    await startMock({ cliClient: false });
    const result = await run(['login', '--device', '--server', mock.url]);
    expect(result.code).toBe(0);
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(1);
    expect(mock.requestsTo('POST', '/mcp/oauth/device_authorization')[0]?.form).toMatchObject({ client_id: 'client-1' });
  });

  it('exits 3 when the sign-in is declined or the code expires', async () => {
    await startMock({ deviceSteps: ['access_denied'] });
    const denied = await run(['login', '--device', '--server', mock.url]);
    expect(denied.code).toBe(3);
    expect(denied.stderr).toContain('Sign-in was declined');
    await mock.close();

    await startMock({ deviceSteps: ['authorization_pending', 'expired_token'] });
    const expired = await run(['login', '--device', '--server', mock.url]);
    expect(expired.code).toBe(3);
    expect(expired.stderr).toContain('The sign-in code expired');
  });

  it('says so when the server has no device endpoint', async () => {
    await startMock({ device: false });
    const result = await run(['login', '--device', '--server', mock.url]);
    expect(result.code).toBe(3);
    expect(result.stderr).toContain('does not offer device sign-in');
  });
});

describe('salli login --token', () => {
  it('checks the token and stores it as given', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url, '--token', 'pat-valid']);
    expect(result.code).toBe(0);
    expect((await credentials()).default).toMatchObject({ kind: 'token', token: 'pat-valid', server: mock.url });
    expect(mock.requestsTo('POST', '/mcp/oauth/register')).toHaveLength(0);
  });

  it('reads the token from stdin with -', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url, '--token', '-'], { stdin: 'pat-valid\n' });
    expect(result.code).toBe(0);
    expect((await credentials()).default?.token).toBe('pat-valid');
  });

  it('refuses a token the server does not accept', async () => {
    await startMock();
    const result = await run(['login', '--server', mock.url, '--token', 'nope']);
    expect(result.code).toBe(3);
    expect(result.stderr).toContain('did not accept that token');
  });
});

describe('using the stored sign-in', () => {
  it('whoami prints the API JSON exactly', async () => {
    await startMock();
    await run(['login', '--server', mock.url, '--token', 'pat-valid']);
    const result = await run(['whoami', '--json']);
    expect(result.code).toBe(0);
    expect(result.stdout).toBe('{\n  "user_id": "user-123",\n  "email": null,\n  "method": "pat",\n  "permissions": []\n}\n');
    mock.user.email = 'ada@example.com';
    const human = await run(['whoami']);
    expect(human.stdout).toContain('ada@example.com');
    expect(human.stdout).toContain('user-123');
    expect(human.stdout).toContain('access token');
    expect(human.stdout).toContain('a personal access token');
    expect(human.stdout).toMatch(/May also\s+nothing more/);
  });

  it('refreshes an expired access token once and retries', async () => {
    await startMock({ accessTokenTtl: 1 });
    expect((await run(['login', '--server', mock.url])).code).toBe(0);
    const before = (await credentials()).default?.tokens;
    // The server expires the token; the CLI still thinks it is valid.
    mock.accessTokens.clear();
    const result = await run(['whoami', '--json']);
    expect(result.code).toBe(0);
    const refreshes = mock.requestsTo('POST', '/mcp/oauth/token').filter((r) => r.form?.grant_type === 'refresh_token');
    expect(refreshes).toHaveLength(1);
    expect(refreshes[0]?.form).toMatchObject({ refresh_token: before?.refresh_token, client_id: 'salli-cli', resource: `${mock.url}/v1` });
    const after = (await credentials()).default?.tokens;
    expect(after?.access_token).not.toBe(before?.access_token);
    expect(after?.refresh_token).not.toBe(before?.refresh_token);
  });

  it('exits 3 when the session can no longer be refreshed', async () => {
    await startMock();
    await run(['login', '--server', mock.url]);
    mock.accessTokens.clear();
    mock.refreshTokens.clear();
    const result = await run(['whoami']);
    expect(result.code).toBe(3);
    expect(result.stderr).toContain('Not signed in, or your session has expired.');
    expect(result.stderr).toContain('salli login');
  });

  it('uses SALLI_TOKEN over what is stored', async () => {
    await startMock();
    const result = await run(['whoami', '--json'], { env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid' } });
    expect(result.code).toBe(0);
    expect(mock.requestsTo('GET', '/v1/auth/me')[0]?.headers.authorization).toBe('Bearer pat-valid');
  });

  it('never sends a stored token to a different server', async () => {
    await startMock();
    await run(['login', '--server', mock.url, '--token', 'pat-valid']);
    const other = await MockSalli.start();
    try {
      const result = await run(['--server', other.url, 'whoami']);
      expect(result.code).toBe(3);
      expect(result.stderr).toContain(`You are signed in to ${mock.url}`);
      expect(other.requests.filter((r) => r.headers.authorization)).toHaveLength(0);
    } finally {
      await other.close();
    }
  });

  it('exits 3 with a hint when nobody is signed in', async () => {
    const result = await run(['whoami']);
    expect(result.code).toBe(3);
    expect(result.stderr).toContain('Not signed in to http://localhost:8000');
    const json = await run(['whoami', '--json']);
    expect(JSON.parse(json.stderr)).toMatchObject({ type: '/problems/cli/not-signed-in', exit_code: 3 });
  });
});

describe('salli logout', () => {
  it('revokes the refresh and access tokens, then forgets them', async () => {
    await startMock();
    await run(['login', '--server', mock.url]);
    const tokens = (await credentials()).default?.tokens;
    const result = await run(['logout']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain(`Signed out of ${mock.url}`);
    expect(mock.revoked).toEqual([tokens?.refresh_token, tokens?.access_token]);
    expect(mock.requestsTo('POST', '/mcp/oauth/revoke')[0]?.form).toMatchObject({ token_type_hint: 'refresh_token', client_id: 'salli-cli' });
    expect((await credentials()).default).toBeUndefined();
    expect((await run(['whoami'])).code).toBe(3);
  });

  it('is fine when already signed out', async () => {
    const result = await run(['logout']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Not signed in');
  });
});
