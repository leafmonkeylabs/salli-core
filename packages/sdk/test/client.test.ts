import { afterEach, describe, expect, it } from 'vitest';
import { createClient, normalizeServerUrl } from '../src/client';
import { SalliApiError, SalliNetworkError } from '../src/errors';
import { accountsDeactivate, accountsGet, accountsList, entriesCreate, metaGet } from '../src/generated/sdk.gen';
import { rawJsonOf, toJsonText } from '../src/json';
import { sendJson, sendProblem, startServer, type TestServer } from './helpers/server';

let server: TestServer | undefined;

afterEach(async () => {
  await server?.close();
  server = undefined;
});

const account = {
  id: 'acc-1',
  code: '1000',
  name: 'Cash',
  type: 'asset',
  currency: 'USD',
  parent_id: null,
  is_active: true,
  tax_role: null,
};

describe('normalizeServerUrl', () => {
  it('drops a trailing slash, query and fragment', () => {
    expect(normalizeServerUrl('http://localhost:8000/')).toBe('http://localhost:8000');
    expect(normalizeServerUrl(' https://salli.example.com/base/?x=1#y ')).toBe('https://salli.example.com/base');
  });

  it('refuses what is not an http(s) URL', () => {
    expect(() => normalizeServerUrl('localhost:8000')).toThrow(/http/);
    expect(() => normalizeServerUrl('not a url')).toThrow(/Not a server URL/);
  });
});

describe('createClient', () => {
  it('sends the bearer token and returns the data', async () => {
    server = await startServer((req, res) => sendJson(res, 200, [account]));
    const salli = createClient({ server: server.url, auth: 'tok-1', userAgent: 'salli-test/1' });
    const accounts = await salli.call(accountsList);
    expect(accounts).toEqual([account]);
    expect(server.requests[0]?.path).toBe('/v1/accounts/');
    expect(server.requests[0]?.headers.authorization).toBe('Bearer tok-1');
    expect(server.requests[0]?.headers['user-agent']).toBe('salli-test/1');
  });

  it('fills path parameters and sends JSON bodies', async () => {
    server = await startServer((req, res) =>
      req.method === 'GET' ? sendJson(res, 200, account) : sendJson(res, 201, { id: 'entry-1' }),
    );
    const salli = createClient({ server: server.url, auth: 'tok' });
    await salli.call(accountsGet, { path: { account_id: 'acc-1' } });
    expect(server.requests[0]?.path).toBe('/v1/accounts/acc-1');

    const created = await salli.call(entriesCreate, {
      body: {
        entry_date: '2026-10-01',
        description: 'Lunch',
        postings: [
          { account_id: 'exp', direction: 1, amount: '12.50' },
          { account_id: 'cash', direction: -1, amount: '12.50' },
        ],
      },
    });
    expect(created).toEqual({ id: 'entry-1' });
    expect(JSON.parse(server.requests[1]?.body ?? '{}')).toMatchObject({
      postings: [{ amount: '12.50' }, { amount: '12.50' }],
    });
  });

  it('keeps the JSON text it received, numbers exactly as written', async () => {
    server = await startServer((req, res) => sendJson(res, 200, '{"confidence": 0.0, "amount": "1.10"}'));
    const salli = createClient({ server: server.url, auth: 'tok' });
    const data = await salli.call(accountsList);
    expect(rawJsonOf(data)).toBe('{"confidence": 0.0, "amount": "1.10"}');
    expect(toJsonText(data)).toBe('{\n  "confidence": 0.0,\n  "amount": "1.10"\n}');
    // The raw text is not part of the value itself.
    expect(Object.keys(data as object)).toEqual(['confidence', 'amount']);
  });

  it('treats 204 as success with nothing to return', async () => {
    server = await startServer((req, res) => {
      res.writeHead(204);
      res.end();
    });
    const salli = createClient({ server: server.url, auth: 'tok' });
    await expect(salli.call(accountsDeactivate, { path: { account_id: 'acc-1' } })).resolves.toBeUndefined();
  });

  it('throws SalliApiError with the problem details', async () => {
    server = await startServer((req, res) =>
      sendProblem(res, 404, { title: 'Not Found', detail: 'Account not found' }),
    );
    const salli = createClient({ server: server.url, auth: 'tok' });
    const error = await salli.call(accountsGet, { path: { account_id: 'nope' } }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SalliApiError);
    expect((error as SalliApiError).status).toBe(404);
    expect((error as SalliApiError).message).toBe('Not Found: Account not found');
    expect((error as SalliApiError).method).toBe('GET');
  });

  it('refreshes once on 401 and retries with the new token', async () => {
    server = await startServer((req, res) => {
      if (req.headers.authorization === 'Bearer fresh') sendJson(res, 200, [account]);
      else sendProblem(res, 401, { title: 'Unauthorized', detail: 'Could not validate token' });
    });
    const refreshedWith: Array<string | undefined> = [];
    const salli = createClient({
      server: server.url,
      auth: {
        getToken: () => 'stale',
        refresh: async (failed) => {
          refreshedWith.push(failed);
          return 'fresh';
        },
      },
    });
    await expect(salli.call(accountsList)).resolves.toEqual([account]);
    expect(refreshedWith).toEqual(['stale']);
    expect(server.requests.map((r) => r.headers.authorization)).toEqual(['Bearer stale', 'Bearer fresh']);
  });

  it('retries a POST with its body intact', async () => {
    server = await startServer((req, res) => {
      if (req.headers.authorization === 'Bearer fresh') sendJson(res, 201, { id: 'e-1' });
      else sendProblem(res, 401, { title: 'Unauthorized' });
    });
    const salli = createClient({
      server: server.url,
      auth: { getToken: () => 'stale', refresh: async () => 'fresh' },
    });
    await salli.call(entriesCreate, {
      body: { entry_date: '2026-10-01', description: 'x', postings: [] },
    });
    expect(server.requests[1]?.body).toBe(server.requests[0]?.body);
    expect(JSON.parse(server.requests[1]?.body ?? '{}')).toMatchObject({ description: 'x' });
  });

  it('lets the 401 stand when the refresh fails, and retries only once', async () => {
    server = await startServer((req, res) => sendProblem(res, 401, { title: 'Unauthorized' }));
    let refreshes = 0;
    const salli = createClient({
      server: server.url,
      auth: {
        getToken: () => 'stale',
        refresh: async () => {
          refreshes += 1;
          return refreshes === 1 ? 'also-bad' : undefined;
        },
      },
    });
    const error = await salli.call(accountsList).catch((e: unknown) => e);
    expect((error as SalliApiError).status).toBe(401);
    expect(refreshes).toBe(1);
    expect(server.requests).toHaveLength(2);
  });

  it('refreshes once for many requests refused together', async () => {
    server = await startServer((req, res) => {
      if (req.headers.authorization === 'Bearer fresh') sendJson(res, 200, []);
      else setTimeout(() => sendProblem(res, 401, { title: 'Unauthorized' }), 20);
    });
    let refreshes = 0;
    const salli = createClient({
      server: server.url,
      auth: {
        getToken: () => 'stale',
        refresh: async () => {
          refreshes += 1;
          await new Promise((r) => setTimeout(r, 30));
          return 'fresh';
        },
      },
    });
    await Promise.all([salli.call(accountsList), salli.call(accountsList), salli.call(accountsList)]);
    expect(refreshes).toBe(1);
  });

  it('sends no Authorization header without auth', async () => {
    server = await startServer((req, res) =>
      sendJson(res, 200, { api_version: '1', server_version: '0.1.0', extensions: [], tax_packs: [], oauth: {}, default_currency: 'USD' }),
    );
    const salli = createClient({ server: server.url });
    const meta = await salli.call(metaGet);
    expect(meta.api_version).toBe('1');
    expect(server.requests[0]?.headers.authorization).toBeUndefined();
  });

  it('turns a refused connection into SalliNetworkError', async () => {
    const closed = await startServer(() => undefined);
    const url = closed.url;
    await closed.close();
    const salli = createClient({ server: url, auth: 'tok' });
    const error = await salli.call(accountsList).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SalliNetworkError);
    expect((error as SalliNetworkError).message).toMatch(/Could not reach http:\/\/127\.0\.0\.1:\d+ \(connection refused\)/);
  });

  it('gives up on a server that does not answer', async () => {
    server = await startServer(() => undefined); // never responds
    const salli = createClient({ server: server.url, auth: 'tok', timeoutMs: 100 });
    const error = await salli.call(accountsList).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SalliNetworkError);
    expect((error as SalliNetworkError).code).toBe('ETIMEDOUT');
  });

  it('ends every request with the reason its client-wide signal was aborted for', async () => {
    server = await startServer(() => undefined);
    const controller = new AbortController();
    const salli = createClient({ server: server.url, auth: 'tok', signal: controller.signal });
    const pending = salli.call(accountsList);
    const reason = new Error('interrupted by the user');
    setTimeout(() => controller.abort(reason), 20);
    await expect(pending).rejects.toBe(reason);
    // Already aborted: nothing is sent.
    const before = server.requests.length;
    await expect(salli.call(accountsList)).rejects.toBe(reason);
    expect(server.requests.length).toBe(before);
  });

  it('passes a caller abort through untouched', async () => {
    server = await startServer(() => undefined);
    const salli = createClient({ server: server.url, auth: 'tok' });
    const controller = new AbortController();
    const pending = salli.call(accountsList, { signal: controller.signal });
    setTimeout(() => controller.abort(), 20);
    const error = await pending.catch((e: unknown) => e);
    expect((error as Error).name).toBe('AbortError');
  });
});
