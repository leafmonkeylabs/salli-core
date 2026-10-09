/**
 * An in-process stand-in for a Salli server: the REST routes the CLI uses
 * (fixtures shaped like the Python handlers' responses), problem+json
 * errors, the OAuth endpoints (registration, PKCE authorization with a
 * loopback redirect, device codes, refresh with rotation, revocation), and
 * the agent's SSE stream.
 */
import { createHash, randomBytes } from 'node:crypto';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import {
  ACCOUNTS,
  BALANCE_SHEET,
  ENTRIES,
  FI_SCORE,
  INCOME_STATEMENT,
  REMINDERS,
  STATEMENT_UPLOAD,
  TAGS,
  TRIAL_BALANCE,
  uid,
} from './fixtures';

export interface RecordedRequest {
  method: string;
  path: string;
  query: URLSearchParams;
  headers: http.IncomingHttpHeaders;
  body: string;
  json?: unknown;
  form?: Record<string, string>;
}

export type DeviceStep = 'authorization_pending' | 'slow_down' | 'approve' | 'access_denied' | 'expired_token';

export interface MockOptions {
  apiVersion?: string;
  /** Advertise the device authorization endpoint. Default true. */
  device?: boolean;
  /** Require the exact registered redirect URI (no RFC 8252 port freedom). */
  strictLoopback?: boolean;
  /** Access token lifetime in seconds. Default 3600. */
  accessTokenTtl?: number;
  /** What successive device-code polls answer. Default: pending, then approve. */
  deviceSteps?: DeviceStep[];
  /** Revocation only reads a JSON body (like the server today). */
  revokeJsonOnly?: boolean;
  /** Whether the user approves in the "browser". Default true. */
  consent?: boolean;
}

type Reply = { status: number; body?: unknown; headers?: Record<string, string>; raw?: string };
type Handler = (req: RecordedRequest, params: Record<string, string>, res: http.ServerResponse) => Reply | undefined | Promise<Reply | undefined>;

const clone = <T>(value: T): T => structuredClone(value);
const b64url = (buf: Buffer): string => buf.toString('base64url');

function problem(status: number, title: string, detail?: unknown, type = 'about:blank'): Reply {
  return {
    status,
    body: { type, title, status, detail: detail ?? null },
    headers: { 'Content-Type': 'application/problem+json', 'X-Request-Id': 'req-test-1' },
  };
}

export class MockSalli {
  url = '';
  readonly options: MockOptions;
  readonly requests: RecordedRequest[] = [];
  readonly clients = new Map<string, { redirect_uris: string[]; client_name?: string }>();
  readonly codes = new Map<string, { client_id: string; redirect_uri: string; challenge: string; resource?: string }>();
  readonly accessTokens = new Map<string, { expires_at: number }>();
  readonly refreshTokens = new Map<string, { client_id: string }>();
  readonly revoked: string[] = [];
  readonly pats = new Set<string>(['pat-valid']);
  user: Record<string, unknown> = { user_id: 'user-123' };
  data = {
    accounts: clone(ACCOUNTS),
    entries: clone(ENTRIES),
    reminders: clone(REMINDERS),
    created: [] as unknown[],
    posted: [] as string[][],
    taggings: [] as unknown[],
  };
  /** SSE frames for the next chat turn (each a JSON event). */
  chatEvents: unknown[] = [
    { type: 'token', content: 'Your net worth is ' },
    { type: 'tool_call', name: 'get_balance_sheet', input: {} },
    { type: 'tool_result', name: 'get_balance_sheet', output: { net_worth: '14034.50' } },
    { type: 'token', content: 'USD 14,034.50.' },
    { type: 'done' },
  ];
  resumeEvents: (decision: string) => unknown[] = (decision) => [
    { type: 'token', content: decision === 'approved' ? 'Posted.' : 'Okay, I left it.' },
    { type: 'done' },
  ];
  parseDraft: Record<string, unknown> = {
    entry_type: 'expense',
    amount: '12.50',
    description: 'Lunch',
    debit_account_id: uid(6),
    credit_account_id: uid(1),
    debit_account_hint: null,
    credit_account_hint: null,
    currency: 'USD',
    confidence: 0.92,
  };
  private deviceSteps: DeviceStep[];
  private readonly overrides: Array<{ method: string; pattern: string; handler: Handler }> = [];
  private server: http.Server | undefined;

  private constructor(options: MockOptions) {
    this.options = options;
    this.deviceSteps = [...(options.deviceSteps ?? ['authorization_pending', 'approve'])];
  }

  static async start(options: MockOptions = {}): Promise<MockSalli> {
    const mock = new MockSalli(options);
    mock.server = http.createServer((req, res) => {
      const chunks: Buffer[] = [];
      req.on('data', (c: Buffer) => chunks.push(c));
      req.on('end', () => {
        mock.handle(req, Buffer.concat(chunks), res).catch((error: unknown) => {
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end(String(error));
        });
      });
    });
    await new Promise<void>((resolve) => mock.server?.listen(0, '127.0.0.1', resolve));
    mock.url = `http://127.0.0.1:${(mock.server.address() as AddressInfo).port}`;
    return mock;
  }

  close(): Promise<void> {
    return new Promise((resolve) => {
      this.server?.closeAllConnections();
      this.server?.close(() => resolve());
    });
  }

  /** Replaces a route's answer for a test. */
  on(method: string, pattern: string, handler: Handler): void {
    this.overrides.unshift({ method, pattern, handler });
  }

  /** Issues a token pair, as a sign-in would. */
  issueTokens(ttl = this.options.accessTokenTtl ?? 3600): { access_token: string; refresh_token: string; expires_in: number } {
    const access = `at-${b64url(randomBytes(9))}`;
    const refresh = `rt-${b64url(randomBytes(9))}`;
    this.accessTokens.set(access, { expires_at: Date.now() / 1000 + ttl });
    this.refreshTokens.set(refresh, { client_id: 'seeded' });
    return { access_token: access, refresh_token: refresh, expires_in: ttl };
  }

  requestsTo(method: string, pathPrefix: string): RecordedRequest[] {
    return this.requests.filter((r) => r.method === method && r.path.startsWith(pathPrefix));
  }

  get meta(): Record<string, unknown> {
    const base = this.url;
    return {
      api_version: this.options.apiVersion ?? '1',
      server_version: '0.1.0',
      extensions: [],
      tax_packs: [{ country: 'LK', year: '2025/26', version: '1', currency: 'LKR', period_start: '2025-04-01', period_end: '2026-03-31' }],
      oauth: {
        issuer: base,
        authorization_endpoint: `${base}/mcp/oauth/authorize`,
        token_endpoint: `${base}/mcp/oauth/token`,
        registration_endpoint: `${base}/mcp/oauth/register`,
        revocation_endpoint: `${base}/mcp/oauth/revoke`,
        ...(this.options.device === false ? {} : { device_authorization_endpoint: `${base}/mcp/oauth/device` }),
      },
      default_currency: 'USD',
    };
  }

  private authorized(req: RecordedRequest): boolean {
    const header = req.headers.authorization ?? '';
    const token = header.startsWith('Bearer ') ? header.slice(7) : '';
    if (this.pats.has(token)) return true;
    const record = this.accessTokens.get(token);
    return !!record && record.expires_at > Date.now() / 1000;
  }

  private async handle(raw: http.IncomingMessage, bodyBuffer: Buffer, res: http.ServerResponse): Promise<void> {
    const url = new URL(raw.url ?? '/', this.url);
    const body = bodyBuffer.toString('utf8');
    const type = raw.headers['content-type'] ?? '';
    const req: RecordedRequest = {
      method: raw.method ?? 'GET',
      path: url.pathname,
      query: url.searchParams,
      headers: raw.headers,
      body,
    };
    if (type.includes('application/json') && body) {
      try {
        req.json = JSON.parse(body);
      } catch {
        // leave unparsed
      }
    }
    if (type.includes('application/x-www-form-urlencoded')) req.form = Object.fromEntries(new URLSearchParams(body));
    this.requests.push(req);

    for (const override of this.overrides) {
      const params = match(override.pattern, req.path);
      if (override.method === req.method && params) {
        const reply = await override.handler(req, params, res);
        if (reply) send(res, reply);
        return;
      }
    }
    const reply = await this.route(req, res);
    if (reply) send(res, reply);
  }

  private async route(req: RecordedRequest, res: http.ServerResponse): Promise<Reply | undefined> {
    const { method, path } = req;
    if (method === 'GET' && path === '/v1/meta') return { status: 200, body: this.meta };
    if (path.startsWith('/mcp/oauth/')) return this.oauth(req);
    if (!path.startsWith('/v1/')) return problem(404, 'Not Found', 'Not Found');
    if (!this.authorized(req)) return problem(401, 'Unauthorized', 'Could not validate token');

    const p = (pattern: string): Record<string, string> | undefined => match(pattern, path);
    let params: Record<string, string> | undefined;

    if (method === 'GET' && path === '/v1/auth/me') return { status: 200, body: this.user };

    // accounts
    if (method === 'GET' && path === '/v1/accounts/') return { status: 200, body: this.data.accounts };
    if (method === 'POST' && path === '/v1/accounts/') {
      const input = req.json as Record<string, unknown>;
      if (!input?.code || !input?.name || !input?.type) {
        return problem(422, 'Request validation failed', [{ loc: ['body', 'code'], msg: 'Field required', type: 'missing' }], '/problems/validation');
      }
      const id = uid(1000 + this.data.accounts.length);
      this.data.accounts.push({
        id,
        code: String(input.code),
        name: String(input.name),
        type: String(input.type),
        currency: String(input.currency ?? 'USD'),
        parent_id: (input.parent_id as string | null) ?? null,
        is_active: true,
        tax_role: (input.tax_role as string | null) ?? null,
      });
      return { status: 201, body: { id } };
    }
    if ((params = p('/v1/accounts/{id}/overview')) && method === 'GET') {
      const account = this.data.accounts.find((a) => a.id === params?.id);
      if (!account) return problem(404, 'Not Found', 'Account not found');
      return {
        status: 200,
        body: {
          account,
          base_currency: 'USD',
          current_balance: account.currency === 'EUR' ? '2200.00' : '12784.50',
          balance: account.currency === 'EUR' ? '2000.00' : '12784.50',
          transactions: [
            { entry_id: uid(201), entry_date: '2026-10-01', description: 'October salary', source: 'manual', external_ref: null, running_balance: '14584.50', running_balance_native: '14584.50' },
            { entry_id: uid(202), entry_date: '2026-10-03', description: 'Rent for October', source: 'manual', external_ref: null, running_balance: '12784.50', running_balance_native: '12784.50' },
          ],
        },
      };
    }
    if ((params = p('/v1/accounts/{id}/reactivate')) && method === 'POST') {
      const account = this.data.accounts.find((a) => a.id === params?.id);
      if (!account) return problem(404, 'Not Found', `Not found: '${params.id}'`, '/problems/not-found');
      account.is_active = true;
      return { status: 200, body: { id: account.id, is_active: true } };
    }
    if ((params = p('/v1/accounts/{id}'))) {
      const account = this.data.accounts.find((a) => a.id === params?.id);
      if (!account) return problem(404, 'Not Found', 'Account not found');
      if (method === 'GET') return { status: 200, body: account };
      if (method === 'PATCH') {
        Object.assign(account, req.json);
        return { status: 200, body: { id: account.id } };
      }
      if (method === 'DELETE') {
        account.is_active = false;
        return { status: 204 };
      }
    }

    // entries
    if (method === 'POST' && path === '/v1/entries/parse') {
      return { status: 200, body: { ...this.parseDraft } };
    }
    if (method === 'GET' && path === '/v1/entries/') {
      const from = req.query.get('from_date');
      const to = req.query.get('to_date');
      const list = this.data.entries.filter((e) => (!from || e.entry_date >= from) && (!to || e.entry_date <= to));
      return { status: 200, body: list };
    }
    if (method === 'POST' && path === '/v1/entries/') {
      const input = req.json as { postings?: Array<{ currency?: string; fx_rate?: string }> };
      const foreign = input.postings?.find((x) => x.currency && x.currency !== 'USD' && !x.fx_rate);
      if (foreign) {
        return problem(422, 'No exchange rate', `No ${foreign.currency}→USD rate for that date. Send the exchange rate (fx_rate) with the amount.`, '/problems/fx-rate-unavailable');
      }
      this.data.created.push(req.json);
      return { status: 201, body: { id: uid(2000 + this.data.created.length) } };
    }
    if ((params = p('/v1/entries/postings/{id}/tags')) && method === 'PUT') {
      this.data.taggings.push({ posting: params.id, ...(req.json as object) });
      return { status: 204 };
    }
    if ((params = p('/v1/entries/{id}/provenance')) && method === 'GET') {
      const entry = this.data.entries.find((e) => e.id === params?.id);
      if (!entry) return problem(404, 'Not Found', 'Entry not found');
      return {
        status: 200,
        body: {
          entry_id: entry.id,
          entry_date: entry.entry_date,
          description: entry.description,
          source: entry.source,
          external_ref: entry.external_ref,
          statement:
            entry.source === 'statement'
              ? {
                  parsed_transaction_id: uid(901),
                  raw_description: 'SUPERMARKET 123',
                  raw_amount: '412.35',
                  raw_date: '2026-10-05',
                  bank_ref: 'REF9',
                  statement: { id: uid(801), bank: 'Acme Bank', period_start: '2026-10-01', period_end: '2026-10-31' },
                }
              : null,
          receipt: null,
        },
      };
    }
    if ((params = p('/v1/entries/{id}/reverse')) && method === 'POST') {
      const entry = this.data.entries.find((e) => e.id === params?.id);
      if (!entry) return problem(404, 'Not Found', 'Entry not found');
      if (entry.reversed_by) return problem(400, 'Bad Request', 'Entry is already reversed');
      entry.reversed_by = uid(3000);
      return { status: 201, body: { id: uid(3000) } };
    }
    if ((params = p('/v1/entries/{id}')) && method === 'GET') {
      const entry = this.data.entries.find((e) => e.id === params?.id);
      return entry ? { status: 200, body: entry } : problem(404, 'Not Found', 'Entry not found');
    }

    // ledger, tags, reports
    if (method === 'GET' && path === '/v1/ledger/trial-balance') return { status: 200, body: TRIAL_BALANCE };
    if (method === 'GET' && path === '/v1/ledger/income-statement') {
      const from = req.query.get('from_date');
      const to = req.query.get('to_date');
      if (!from || !to) {
        return problem(422, 'Request validation failed', [{ loc: ['query', 'from_date'], msg: 'Field required', type: 'missing' }], '/problems/validation');
      }
      return { status: 200, body: INCOME_STATEMENT(from, to) };
    }
    if (method === 'GET' && path === '/v1/tags/') {
      const kind = req.query.get('kind');
      return { status: 200, body: { tags: kind ? TAGS.filter((t) => t.kind === kind) : TAGS } };
    }
    if (method === 'GET' && path === '/v1/reports/balance-sheet') return { status: 200, body: BALANCE_SHEET };
    if (method === 'GET' && path === '/v1/reports/net-worth') {
      return {
        status: 200,
        body: {
          currency: 'USD',
          current_net_worth: '14034.50',
          as_of: '2026-10-09T08:00:00+00:00',
          trend: [
            { date: '2026-08-01T08:00:00+00:00', net_worth: '9500.00' },
            { date: '2026-09-01T08:00:00+00:00', net_worth: '11250.00' },
            { date: '2026-10-09T08:00:00+00:00', net_worth: '14034.50' },
          ],
        },
      };
    }
    if ((params = p('/v1/reports/{type}/export')) && method === 'GET') {
      return { status: 200, raw: 'Type,Code,Account,Balance\r\nasset,1000,Cash,250.00\r\n', headers: { 'Content-Type': 'text/csv' } };
    }

    // FI
    if (method === 'GET' && path === '/v1/fi/score') return { status: 200, body: FI_SCORE };

    // reminders
    if (method === 'GET' && path === '/v1/reminders/') {
      const status = req.query.get('status');
      return { status: 200, body: { reminders: this.data.reminders.filter((r) => !status || r.status === status) } };
    }

    // statements
    if (method === 'POST' && path === '/v1/statements/upload') {
      if (!(req.headers['content-type'] ?? '').startsWith('multipart/form-data')) return problem(422, 'Request validation failed', 'file required');
      return { status: 202, body: clone(STATEMENT_UPLOAD) };
    }
    if (method === 'GET' && path === '/v1/statements/') {
      return {
        status: 200,
        body: { statements: [{ id: uid(801), bank: 'Acme Bank', period_start: '2026-09-01', period_end: '2026-09-30', status: 'parsed', created_at: '2026-10-02T10:00:00+00:00' }] },
      };
    }
    if ((params = p('/v1/statements/{id}/post')) && method === 'POST') {
      const ids = (req.json as { approved_ids: string[] }).approved_ids;
      this.data.posted.push(ids);
      return { status: 200, body: { posted: ids.length, entry_ids: ids.map((_, i) => uid(4000 + i)) } };
    }
    if ((params = p('/v1/statements/{id}')) && method === 'GET') {
      return { status: 200, body: { statement_id: params.id, transactions: clone(STATEMENT_UPLOAD.transactions) } };
    }

    // agent
    if (method === 'POST' && (path === '/v1/agent/chat' || path === '/v1/agent/resume')) {
      const events = path === '/v1/agent/chat' ? this.chatEvents : this.resumeEvents(String((req.json as { decision?: string }).decision));
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' });
      for (const event of events) res.write(`data: ${JSON.stringify(event)}\n\n`);
      res.end();
      return undefined;
    }

    return problem(404, 'Not Found', 'Not Found');
  }

  private oauth(req: RecordedRequest): Reply {
    const { method, path } = req;
    if (method === 'POST' && path === '/mcp/oauth/register') {
      const input = req.json as { client_name?: string; redirect_uris?: string[] };
      if (!input?.redirect_uris?.length) return problem(400, 'Bad Request', 'redirect_uris must be a non-empty list');
      const clientId = `client-${this.clients.size + 1}`;
      this.clients.set(clientId, { redirect_uris: input.redirect_uris, ...(input.client_name ? { client_name: input.client_name } : {}) });
      return {
        status: 201,
        body: { client_id: clientId, client_name: input.client_name, redirect_uris: input.redirect_uris, token_endpoint_auth_method: 'none', grant_types: ['authorization_code', 'refresh_token'], response_types: ['code'] },
      };
    }
    if (method === 'GET' && path === '/mcp/oauth/authorize') {
      const q = req.query;
      const client = this.clients.get(q.get('client_id') ?? '');
      if (!client) return problem(400, 'Bad Request', 'unknown client_id');
      const redirect = q.get('redirect_uri') ?? '';
      if (!this.redirectAllowed(client.redirect_uris, redirect)) {
        return problem(400, 'Bad Request', 'redirect_uri does not match a registered value for this client');
      }
      if (q.get('code_challenge_method') !== 'S256' || !q.get('code_challenge')) return problem(400, 'Bad Request', 'code_challenge_method must be S256');
      const target = new URL(redirect);
      if (this.options.consent === false) {
        target.searchParams.set('error', 'access_denied');
      } else {
        const code = `code-${b64url(randomBytes(9))}`;
        this.codes.set(code, {
          client_id: q.get('client_id') ?? '',
          redirect_uri: redirect,
          challenge: q.get('code_challenge') ?? '',
          ...(q.get('resource') ? { resource: q.get('resource') ?? '' } : {}),
        });
        target.searchParams.set('code', code);
      }
      if (q.get('state')) target.searchParams.set('state', q.get('state') ?? '');
      return { status: 302, headers: { Location: target.toString() } };
    }
    if (method === 'POST' && path === '/mcp/oauth/device') {
      const clientId = req.form?.client_id ?? '';
      if (!this.clients.has(clientId)) return { status: 401, body: { error: 'invalid_client' } };
      return {
        status: 200,
        body: {
          device_code: 'dev-code-1',
          user_code: 'WDJB-MJHT',
          verification_uri: `${this.url}/device`,
          verification_uri_complete: `${this.url}/device?user_code=WDJB-MJHT`,
          expires_in: 600,
          interval: 0.01,
        },
      };
    }
    if (method === 'POST' && path === '/mcp/oauth/token') {
      const form = req.form ?? {};
      const oauthError = (error: string, description?: string): Reply => ({
        status: 400,
        body: { error, ...(description ? { error_description: description } : {}) },
      });
      if (form.grant_type === 'authorization_code') {
        const record = this.codes.get(form.code ?? '');
        if (!record) return oauthError('invalid_grant', 'invalid or expired authorization code');
        if (record.client_id !== form.client_id || record.redirect_uri !== form.redirect_uri) return oauthError('invalid_grant', 'client_id/redirect_uri mismatch');
        const computed = createHash('sha256').update(form.code_verifier ?? '').digest('base64url');
        if (computed !== record.challenge) return oauthError('invalid_grant', 'PKCE verification failed');
        this.codes.delete(form.code ?? '');
        return { status: 200, body: { ...this.issueTokens(), token_type: 'Bearer', scope: '' } };
      }
      if (form.grant_type === 'refresh_token') {
        if (!this.refreshTokens.has(form.refresh_token ?? '')) return oauthError('invalid_grant', 'invalid or expired refresh token');
        this.refreshTokens.delete(form.refresh_token ?? '');
        return { status: 200, body: { ...this.issueTokens(), token_type: 'Bearer', scope: '' } };
      }
      if (form.grant_type === 'urn:ietf:params:oauth:grant-type:device_code') {
        const step = this.deviceSteps.shift() ?? 'approve';
        if (step === 'approve') return { status: 200, body: { ...this.issueTokens(), token_type: 'Bearer' } };
        return oauthError(step);
      }
      return oauthError('unsupported_grant_type', form.grant_type);
    }
    if (method === 'POST' && path === '/mcp/oauth/revoke') {
      const isJson = (req.headers['content-type'] ?? '').includes('application/json');
      if (this.options.revokeJsonOnly && !isJson) {
        return problem(422, 'Request validation failed', [{ loc: ['body'], msg: 'Input should be a valid dictionary', type: 'model_attributes_type' }], '/problems/validation');
      }
      const token = isJson ? (req.json as { token?: string }).token : req.form?.token;
      if (token) {
        this.revoked.push(token);
        this.accessTokens.delete(token);
        this.refreshTokens.delete(token);
      }
      return { status: 200, body: {} };
    }
    return problem(404, 'Not Found', 'Not Found');
  }

  /** RFC 8252 §7.3: a registered loopback URI matches on any port. */
  private redirectAllowed(registered: string[], redirect: string): boolean {
    if (registered.includes(redirect)) return true;
    if (this.options.strictLoopback) return false;
    let target: URL;
    try {
      target = new URL(redirect);
    } catch {
      return false;
    }
    return registered.some((r) => {
      const u = new URL(r);
      return u.hostname === '127.0.0.1' && target.hostname === '127.0.0.1' && u.pathname === target.pathname && u.protocol === target.protocol;
    });
  }
}

function match(pattern: string, path: string): Record<string, string> | undefined {
  const want = pattern.split('/');
  const got = path.split('/');
  if (want.length !== got.length) return undefined;
  const params: Record<string, string> = {};
  for (let i = 0; i < want.length; i += 1) {
    const w = want[i] ?? '';
    const g = got[i] ?? '';
    if (w.startsWith('{') && w.endsWith('}')) {
      if (!g) return undefined;
      params[w.slice(1, -1)] = decodeURIComponent(g);
    } else if (w !== g) {
      return undefined;
    }
  }
  return params;
}

function send(res: http.ServerResponse, reply: Reply): void {
  const headers: Record<string, string> = { ...(reply.headers ?? {}) };
  if (reply.raw !== undefined) {
    res.writeHead(reply.status, headers);
    res.end(reply.raw);
    return;
  }
  if (reply.body === undefined) {
    res.writeHead(reply.status, headers);
    res.end();
    return;
  }
  headers['Content-Type'] ??= 'application/json';
  res.writeHead(reply.status, headers);
  res.end(JSON.stringify(reply.body));
}
