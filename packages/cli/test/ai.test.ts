import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { authorizationUrl, callbackClientId, chatGptAuthBase, DYNAMIC_CLIENT_ID } from '../src/auth/chatgpt';
import { CliError } from '../src/errors';
import { MockSalli } from './helpers/mock-server';
import { runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
let openai: { url: string; tokenRequests: Array<Record<string, string>>; answer: { status: number; body: unknown }; close: () => Promise<void> };

/** A stand-in for auth.openai.com's token endpoint. */
async function startOpenAiStub(): Promise<typeof openai> {
  const stub = {
    url: '',
    tokenRequests: [] as Array<Record<string, string>>,
    answer: {
      status: 200,
      body: { access_token: 'access-secret', refresh_token: 'refresh-secret', id_token: 'id-token-ok', token_type: 'Bearer', expires_in: 3600, scope: 'openid' } as unknown,
    },
    close: async (): Promise<void> => undefined,
  };
  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c: Buffer) => (body += c.toString()));
    req.on('end', () => {
      if (req.url === '/api/accounts/oauth/token' && req.method === 'POST') {
        stub.tokenRequests.push(Object.fromEntries(new URLSearchParams(body)));
        res.writeHead(stub.answer.status, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(stub.answer.body));
        return;
      }
      res.writeHead(404).end();
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  stub.url = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  stub.close = () => new Promise<void>((resolve) => server.close(() => resolve()));
  return stub;
}

/** A browser that signs in at once: back to the loopback with a code (and an issued client id). */
function browser(answer: (authorize: URL) => Record<string, string>): (url: string) => Promise<boolean> {
  return async (url) => {
    const authorize = new URL(url);
    const back = new URL(authorize.searchParams.get('redirect_uri') ?? '');
    for (const [k, v] of Object.entries(answer(authorize))) back.searchParams.set(k, v);
    void fetch(back).then((r) => r.text());
    return true;
  };
}

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  openai = await startOpenAiStub();
});
afterEach(async () => {
  await mock.close();
  await openai.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, {
    configDir: dir,
    ...options,
    env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', SALLI_CHATGPT_AUTH_URL: openai.url, ...options.env },
  });

describe('the ChatGPT sign-in pieces', () => {
  const request = { base: 'https://auth.openai.com', hostId: 'h1', redirectUri: 'http://127.0.0.1:1455/auth/callback', state: 's', nonce: 'n', codeChallenge: 'c' };

  it('registers with the dynamic client and the agent name, and nothing else', () => {
    const url = new URL(authorizationUrl({ ...request, clientId: DYNAMIC_CLIENT_ID, registering: true, loginHint: 'a@b.c', askConsent: true }));
    expect(url.origin + url.pathname).toBe('https://auth.openai.com/api/accounts/authorize');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      client_id: 'dynamic_agent_client',
      agent_name_hint: 'Salli',
      ext_agent_host_id: 'h1',
      response_type: 'code',
      redirect_uri: 'http://127.0.0.1:1455/auth/callback',
      scope: 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct',
      resource: 'https://api.openai.com/v1',
      state: 's',
      nonce: 'n',
      code_challenge: 'c',
      code_challenge_method: 'S256',
    });
  });

  it('signs in again with the issued client, the login hint, and consent only when asked', () => {
    const url = new URL(authorizationUrl({ ...request, clientId: 'issued-1', registering: false, loginHint: 'a@b.c', askConsent: true }));
    expect(url.searchParams.get('client_id')).toBe('issued-1');
    expect(url.searchParams.get('login_hint')).toBe('a@b.c');
    expect(url.searchParams.get('prompt')).toBe('consent');
    expect(url.searchParams.has('agent_name_hint')).toBe(false);
    expect(url.searchParams.has('id_token_hint')).toBe(false);
  });

  it('takes the client id the callback settles, and refuses the wrong one', () => {
    expect(callbackClientId(new URLSearchParams({ client_id: 'issued-1' }), DYNAMIC_CLIENT_ID, true)).toBe('issued-1');
    expect(() => callbackClientId(new URLSearchParams(), DYNAMIC_CLIENT_ID, true)).toThrow(CliError);
    expect(() => callbackClientId(new URLSearchParams({ client_id: DYNAMIC_CLIENT_ID }), DYNAMIC_CLIENT_ID, true)).toThrow(CliError);
    expect(callbackClientId(new URLSearchParams(), 'issued-1', false)).toBe('issued-1');
    expect(() => callbackClientId(new URLSearchParams({ client_id: 'other' }), 'issued-1', false)).toThrow(/different registration/);
  });

  it('talks to OpenAI unless a stand-in on this machine is named', () => {
    expect(chatGptAuthBase({})).toBe('https://auth.openai.com');
    expect(chatGptAuthBase({ SALLI_CHATGPT_AUTH_URL: 'http://127.0.0.1:9/' })).toBe('http://127.0.0.1:9');
    expect(() => chatGptAuthBase({ SALLI_CHATGPT_AUTH_URL: 'http://evil.example' })).toThrow(CliError);
  });
});

describe('salli ai', () => {
  it('shows the provider in use and the ChatGPT connection', async () => {
    expect((await run(['ai', 'status'])).stdout).toMatchInlineSnapshot(`
      "AI provider    auto → anthropic (yours)
      Your API keys  anthropic
      ChatGPT        not connected
      "
    `);
    const json = JSON.parse((await run(['ai', 'status', '--json'])).stdout);
    expect(Object.keys(json)).toEqual(['settings', 'chatgpt']);
  });

  it('chooses the provider and the models', async () => {
    expect((await run(['ai', 'use', 'openai'])).stderr).toContain('AI provider set to openai');
    expect((await run(['ai', 'use', 'gemini'])).code).toBe(2);
    expect((await run(['ai', 'models', 'openai'])).stdout).toContain('gpt-5-mini');
    await run(['ai', 'set-models', 'openai', '--fast', 'gpt-5-mini']);
    expect(mock.data.bodies.find((b) => b.path === '/v1/ai/models/openai')?.body).toEqual({ fast: 'gpt-5-mini', best: null });
    expect((await run(['ai', 'host'])).stdout).toBe('host-e2e-1\n');
  });

  it('connects ChatGPT: registers, redeems the code here, hands the tokens to the server, prints none', async () => {
    let authorize: URL | undefined;
    const result = await run(['ai', 'connect', 'chatgpt', '--port', '0'], {
      openUrl: browser((url) => {
        authorize = url;
        return { code: 'code-1', state: url.searchParams.get('state') ?? '', client_id: 'issued-1' };
      }),
    });
    expect(result.code).toBe(0);
    expect(authorize?.searchParams.get('client_id')).toBe('dynamic_agent_client');
    expect(authorize?.searchParams.get('ext_agent_host_id')).toBe('host-e2e-1');
    expect(authorize?.searchParams.get('redirect_uri')).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/auth\/callback$/);
    expect(openai.tokenRequests).toEqual([
      {
        grant_type: 'authorization_code',
        client_id: 'issued-1',
        code: 'code-1',
        code_verifier: expect.stringMatching(/^[A-Za-z0-9_-]{43,128}$/),
        redirect_uri: authorize?.searchParams.get('redirect_uri'),
        resource: 'https://api.openai.com/v1',
      },
    ]);
    expect(mock.data.bodies.find((b) => b.path === '/v1/ai/connections/chatgpt')?.body).toEqual({
      client_id: 'issued-1',
      access_token: 'access-secret',
      refresh_token: 'refresh-secret',
      id_token: 'id-token-ok',
      token_type: 'Bearer',
      expires_in: 3600,
      scope: 'openid',
    });
    expect(result.stderr).toContain('Continue with ChatGPT');
    expect(result.stderr).toContain('count toward its usage limits');
    expect(result.stderr).toContain('You’re using your ChatGPT plan.');
    expect(result.stderr).toContain('https://chatgpt.com/settings/usage');
    expect(result.stdout + result.stderr).not.toMatch(/access-secret|refresh-secret|id-token-ok/);
  });

  it('signs in again with the issued client, and stops when the plan is declined', async () => {
    mock.data.ai.chatgpt = { ...mock.data.ai.chatgpt, status: 'needs_consent', client_id: 'issued-1', email: 'ada@example.com' };
    let authorize: URL | undefined;
    const again = await run(['ai', 'connect', 'chatgpt', '--port', '0'], {
      openUrl: browser((url) => {
        authorize = url;
        return { code: 'code-2', state: url.searchParams.get('state') ?? '' };
      }),
    });
    expect(again.code).toBe(0);
    expect(authorize?.searchParams.get('login_hint')).toBe('ada@example.com');
    expect(authorize?.searchParams.get('prompt')).toBe('consent');
    expect(again.stderr).toContain('Connected to ChatGPT as ada@example.com.');

    const declined = await run(['ai', 'connect', 'chatgpt', '--port', '0'], {
      openUrl: browser((url) => ({ error: 'access_denied', state: url.searchParams.get('state') ?? '' })),
    });
    expect(declined.code).toBe(1);
    expect(declined.stderr).toContain('nothing was connected');
    expect(openai.tokenRequests).toHaveLength(1);
  });

  it('refuses a callback with the wrong state, and starts over on invalid_grant', async () => {
    const forged = await run(['ai', 'connect', 'chatgpt', '--port', '0'], { openUrl: browser(() => ({ code: 'x', state: 'forged', client_id: 'issued-1' })) });
    expect(forged.code).toBe(3);
    expect(forged.stderr).toContain('different state');
    expect(openai.tokenRequests).toHaveLength(0);

    openai.answer = { status: 400, body: { error: 'invalid_grant' } };
    const stale = await run(['ai', 'connect', 'chatgpt', '--port', '0'], {
      openUrl: browser((url) => ({ code: 'old', state: url.searchParams.get('state') ?? '', client_id: 'issued-1' })),
    });
    expect(stale.code).toBe(1);
    expect(stale.stderr).toContain('already used or has expired');
    expect(stale.stderr).toContain('salli ai connect chatgpt');
  });

  it('shows the server’s refusal of the credential, with its message', async () => {
    openai.answer = { status: 200, body: { access_token: 'a', refresh_token: 'r', id_token: 'expired' } };
    const result = await run(['ai', 'connect', 'chatgpt', '--port', '0'], {
      openUrl: browser((url) => ({ code: 'c', state: url.searchParams.get('state') ?? '', client_id: 'issued-1' })),
    });
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('The ID token could not be verified.');
  });

  it('disconnects, and says when there is nothing to disconnect', async () => {
    expect((await run(['ai', 'disconnect', 'chatgpt'])).code).toBe(1);
    mock.data.ai.chatgpt = { ...mock.data.ai.chatgpt, status: 'active', connected: true };
    expect((await run(['ai', 'disconnect', 'chatgpt'])).stderr).toContain('Disconnected from ChatGPT.');
    expect((await run(['ai', 'disconnect', 'claude'])).code).toBe(2);
  });

  it('stores an OpenAI key from stdin', async () => {
    expect((await run(['llm-keys', 'set', 'openai'], { stdin: 'sk-example\n' })).code).toBe(0);
    expect(mock.requestsTo('PUT', '/v1/llm-keys/openai')[0]?.json).toEqual({ key: 'sk-example' });
    expect((await run(['llm-keys', 'set', 'chatgpt'], { stdin: 'x' })).code).toBe(2);
  });
});
