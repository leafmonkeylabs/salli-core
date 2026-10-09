/**
 * An in-process stand-in for a Salli server: the REST routes the CLI uses
 * (fixtures typed with the SDK's generated response types), problem+json
 * errors, the OAuth endpoints (registration, PKCE authorization with a
 * loopback redirect on any port, device codes, refresh with rotation,
 * revocation), and the agent's SSE stream.
 */
import { createHash, randomBytes } from 'node:crypto';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import type {
  Account,
  AgentDocument,
  CategorizationRule,
  EntryProvenance,
  McpConnection,
  Meta,
  PersonalAccessToken,
  Profile,
  PurchaseImpact,
  RuleDraft,
  RuleSuggestion,
  RuleTestResult,
  RuleUpdate,
  TaxPack,
} from '@leafmonkeylabs/salli-sdk';
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
  /** Whether the user approves in the "browser". Default true. */
  consent?: boolean;
  /** The resource indicator for the REST API. Default: `<url>/v1`. */
  apiResource?: string;
  /** Answer an upload with the transactions' ids (the server today sends them empty). */
  uploadIds?: boolean;
}

type Reply = { status: number; body?: unknown; headers?: Record<string, string>; raw?: string };
type Handler = (req: RecordedRequest, params: Record<string, string>, res: http.ServerResponse) => Reply | undefined | Promise<Reply | undefined>;

const clone = <T>(value: T): T => structuredClone(value);
/** When a stored record was made and last changed. */
const STAMPS = { created_at: '2026-09-01T09:00:00+00:00', updated_at: '2026-09-01T09:00:00+00:00' };
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
  user: { user_id: string; email: string | null } = { user_id: 'user-123', email: null };
  data = {
    accounts: clone(ACCOUNTS),
    entries: clone(ENTRIES),
    reminders: clone(REMINDERS),
    created: [] as unknown[],
    posted: [] as string[][],
    taggings: [] as unknown[],
    /** Simple collections, by API path (budgets, debts, holdings…). */
    collections: {
      '/v1/budget/': [
        {
          id: uid(401),
          period_start: '2026-10-01',
          period_end: '2026-10-31',
          currency: 'USD',
          lines: [
            { account_id: uid(6), limit_amount: '400.00' },
            { account_id: uid(7), limit_amount: '1800.00' },
          ],
          ...STAMPS,
        },
      ],
      '/v1/debt/': [
        { id: uid(411), name: 'Credit card', currency: 'USD', principal: '1200.00', apr: '0.2399', minimum_payment: '35.00', is_active: true, ...STAMPS },
        { id: uid(412), name: 'Car loan', currency: 'USD', principal: '8400.00', apr: '0.069', minimum_payment: '310.00', is_active: true, ...STAMPS },
      ],
      '/v1/portfolio/': [
        { id: uid(421), symbol: 'VTI', name: 'Total Stock Market', asset_class: 'equity', currency: 'USD', cost_basis: '9000.00', current_value: '11250.40', is_active: true, ...STAMPS },
        { id: uid(422), symbol: 'BND', name: 'Total Bond Market', asset_class: 'bond', currency: 'USD', cost_basis: '3000.00', current_value: '2890.10', is_active: true, ...STAMPS },
      ],
      '/v1/subscriptions/': [
        { id: uid(431), name: 'Streaming', amount: '15.99', currency: 'USD', frequency: 'monthly', next_due_date: '2026-10-20', account_id: null, grace_days: 5, amount_tolerance_pct: '0.05', is_active: true, ...STAMPS },
      ],
      '/v1/insurance/policies': [
        { id: uid(441), name: 'Term life', policy_type: 'life', provider: 'Acme Life', currency: 'USD', coverage_amount: '500000.00', premium_amount: '42.00', premium_frequency: 'monthly', expiry_date: '2046-01-01', is_active: true, ...STAMPS },
      ],
      '/v1/fi/goals': [
        { id: uid(451), name: 'Emergency fund', kind: 'emergency_fund', currency: 'USD', target_amount: '15000.00', current_amount: '9000.00', allocated_amount: '9000.00', shortfall: '0.00', target_date: '2027-06-30', priority: 1, progress: 0.6, created_at: '2026-01-01T00:00:00+00:00' },
      ],
      '/v1/documents/': [
        {
          id: uid(461),
          user_id: 'user-123',
          title: 'Receipt.pdf',
          content: 'Thank you for shopping',
          storage_key: 'user-123/receipt.pdf',
          mime_type: 'application/pdf',
          tags: ['receipt'],
          source: 'upload',
          namespace: 'documents',
          slug: null,
          description: null,
          created_at: '2026-10-02T00:00:00+00:00',
          updated_at: '2026-10-02T00:00:00+00:00',
        } satisfies AgentDocument,
      ],
    } as Record<string, Array<Record<string, unknown> & { id: string }>>,
    connections: [
      { token_id: uid(471), client_id: 'client-claude', client_name: 'Claude', scope: '', connected_at: '2026-10-01T00:00:00+00:00' },
    ] as McpConnection[],
    rules: [
      {
        id: uid(601),
        name: 'Groceries',
        conditions: [{ field: 'description', operator: 'contains', value: 'groceries' }],
        actions: { account_id: uid(6), category: 'groceries' },
        priority: 100,
        match_all: true,
        enabled: true,
        hits: 3,
        last_hit_at: '2026-10-05T09:00:00Z',
        created_at: '2026-09-01T09:00:00Z',
        updated_at: '2026-09-01T09:00:00Z',
      },
    ] as CategorizationRule[],
    tokens: [
      { id: uid(701), name: 'backup job', prefix: 'salli_pat_bk7Q', created_at: '2026-09-01T09:00:00Z', expires_at: null, last_used_at: '2026-10-08T03:00:00Z' },
    ] as PersonalAccessToken[],
    bodies: [] as Array<{ method: string; path: string; body: unknown }>,
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

  get meta(): Meta {
    const base = this.url;
    const meta: Meta = {
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
        device_authorization_endpoint: `${base}/mcp/oauth/device_authorization`,
        api_resource: this.options.apiResource ?? `${base}/v1`,
        device_verification_uri: `${base}/mcp/oauth/device`,
      },
      default_currency: 'USD',
    };
    if (this.options.device === false) {
      // A server from before device sign-in.
      const { device_authorization_endpoint: _endpoint, device_verification_uri: _page, ...oauth } = meta.oauth;
      return { ...meta, oauth: oauth as Meta['oauth'] };
    }
    return meta;
  }

  /** The bearer token of a request. */
  private tokenOf(req: RecordedRequest): string {
    const header = req.headers.authorization ?? '';
    return header.startsWith('Bearer ') ? header.slice(7) : '';
  }

  private authorized(req: RecordedRequest): boolean {
    const token = this.tokenOf(req);
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

    if (method === 'GET' && path === '/v1/auth/me') {
      return { status: 200, body: { ...this.user, method: this.pats.has(this.tokenOf(req)) ? 'pat' : 'oauth' } };
    }

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
        type: String(input.type) as Account['type'],
        currency: String(input.currency ?? 'USD'),
        parent_id: (input.parent_id as string | null) ?? null,
        is_active: true,
        tax_role: (input.tax_role as Account['tax_role']) ?? null,
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
      const provenance: EntryProvenance = {
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
                currency: 'USD',
                raw_date: '2026-10-05',
                bank_ref: 'REF9',
                statement: {
                  id: uid(801),
                  bank: 'Acme Bank',
                  period_start: '2026-10-01',
                  period_end: '2026-10-31',
                  storage_key: 'user-123/statement.pdf',
                  status: 'posted',
                  created_at: '2026-10-06T09:00:00+00:00',
                },
              }
            : null,
        receipt: null,
        possible_subscriptions: [],
      };
      return { status: 200, body: provenance };
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

    // Collections: list, get, create, update, delete.
    const collection = this.collectionRoute(req);
    if (collection) return collection;

    // FI
    if (method === 'GET' && path === '/v1/fi/score') return { status: 200, body: FI_SCORE };
    if (method === 'POST' && path === '/v1/fi/score/recompute') return { status: 200, body: FI_SCORE };
    if (method === 'GET' && path === '/v1/fi/projections') {
      return {
        status: 200,
        body: {
          currency: 'USD',
          points: [
            { year: 2027, conservative: '30000.00', base: '32000.00', growth: '34000.00' },
            { year: 2028, conservative: '48000.00', base: '52000.00', growth: '57000.00' },
          ],
          fi_number: '663705.00',
          swr: '0.04',
          fire_year_conservative: 19,
          fire_year_base: 14,
          fire_year_growth: 11,
          current_portfolio: '12834.50',
          real_returns: { conservative: '0.02', base: '0.035', growth: '0.05' },
          expected_inflation: '0.05',
        },
      };
    }
    if (method === 'POST' && path === '/v1/fi/simulate-purchase') {
      this.data.bodies.push({ method, path, body: req.json });
      const impact: PurchaseImpact = {
        amount: (req.json as { amount: string }).amount,
        currency: 'USD',
        fi_number: '663705.00',
        fi_asset_base_before: '12834.50',
        monthly_surplus: '2787.65',
        baseline_months_to_fi: 168,
        payable_from_liquid: true,
        emergency_months_before: '5.8',
        emergency_months_after_cash: '4.7',
        emergency_fund_target_months: 6,
        options: [
          { key: 'cash', label: 'Pay cash', total_cost: '2400.00', interest_cost: '0.00', monthly_payment: null, term_months: null, months_to_fi: 169, months_delay: 1, exceeds_monthly_surplus: false },
          { key: 'installments', label: 'Pay over 12 months', total_cost: '2616.00', interest_cost: '216.00', monthly_payment: '218.00', term_months: 12, months_to_fi: 170, months_delay: 2, exceeds_monthly_surplus: false },
        ],
        cheapest_option_key: 'cash',
        data_as_of: '2026-10-06',
        is_stale: false,
        stale_after_days: 30,
        real_return_used: '0.035',
        swr: '0.04',
      };
      return { status: 200, body: impact };
    }
    if (method === 'GET' && path === '/v1/debt/payoff-plan') {
      return {
        status: 200,
        body: {
          strategy: req.query.get('strategy') ?? 'avalanche',
          currency: 'USD',
          months_to_payoff: 26,
          total_interest_paid: '845.12',
          schedule: [
            { month: 1, debt_name: 'Credit card', payment: '135.00', principal_paid: '111.01', interest_paid: '23.99', remaining_balance: '1088.99' },
            { month: 1, debt_name: 'Car loan', payment: '310.00', principal_paid: '261.70', interest_paid: '48.30', remaining_balance: '8138.30' },
          ],
        },
      };
    }
    if (method === 'GET' && path === '/v1/portfolio/summary') {
      return {
        status: 200,
        body: {
          currency: 'USD',
          total_value: '14140.50',
          total_cost_basis: '12000.00',
          total_gain: '2140.50',
          total_gain_pct: '0.178375',
          allocation: [
            { asset_class: 'equity', current_value: '11250.40', pct_of_portfolio: '0.7956' },
            { asset_class: 'bond', current_value: '2890.10', pct_of_portfolio: '0.2044' },
          ],
          alerts: req.query.getAll('target').length ? [{ asset_class: 'equity', current_pct: '0.7956', target_pct: '0.6', drift_pct: '0.1956' }] : [],
        },
      };
    }
    if (method === 'GET' && path === '/v1/insurance/report') {
      return {
        status: 200,
        body: {
          currency: 'USD',
          lines: [{ policy_type: 'life', target_amount: '750000.00', actual_coverage: '500000.00', gap: '250000.00' }],
          missing_types: ['health'],
          expiring_soon: [],
        },
      };
    }
    if (method === 'PUT' && path === '/v1/insurance/targets') {
      this.data.bodies.push({ method, path, body: req.json });
      return { status: 200, body: { id: uid(481) } };
    }
    if (method === 'GET' && path === '/v1/reports/goal-progress') {
      return { status: 200, body: { goals: this.data.collections['/v1/fi/goals'], completed_count: 0, in_progress_count: 1 } };
    }
    if (method === 'GET' && path === '/v1/onboarding/profile') {
      const profile: Profile = {
        id: 'user-123',
        email: null,
        display_name: 'Ada',
        base_currency: 'USD',
        date_of_birth: '1990-04-01',
        dependents_count: 0,
        employment_status: null,
        residency_status: 'resident',
        employer: null,
        employment_type: null,
        ird_number: null,
        risk_score: null,
        risk_category: null,
        life_stage: null,
        mcp_enabled: true,
        daily_briefing_enabled: false,
        preferred_model: null,
      };
      return { status: 200, body: profile };
    }
    if (method === 'PATCH' && path === '/v1/onboarding/profile') {
      this.data.bodies.push({ method, path, body: req.json });
      if ((req.json as { base_currency?: string }).base_currency === 'EUR') {
        return problem(409, 'Base currency is fixed', 'Your ledger already has amounts in USD.', '/problems/base-currency-locked');
      }
      return { status: 200, body: { updated: true } };
    }
    if (method === 'GET' && path === '/v1/onboarding/export') return { status: 200, raw: '{"profile": {"display_name": "Ada"}, "progress": 0.0}', headers: { 'Content-Type': 'application/json' } };
    if (method === 'GET' && path === '/v1/tax/packs') {
      const pack: TaxPack = {
        country: 'LK',
        year: '2025/26',
        version: '1',
        currency: 'LKR',
        period_start: '2025-04-01',
        period_end: '2026-03-31',
        personal_relief: '1800000.00',
        return_due: '11-30',
        set_due: '09-30',
        installments: ['08-15', '11-15', '02-15'],
        final_installment_due: '05-15',
      };
      return { status: 200, body: [pack] };
    }
    if (method === 'POST' && path === '/v1/tax/compute') {
      return {
        status: 200,
        body: {
          pack_country: 'LK', pack_year: '2025/26', pack_version: '1', currency: 'LKR',
          gross_income: '6000000.00', foreign_service_income: '0.00', regular_income: '6000000.00', personal_relief_applied: '1800000.00',
          qp_deduction: '0.00', taxable_income: '4200000.00', fsi_tax: '0.00', tax_before_credits: '540000.00',
          apit_credit: '400000.00', ait_credit: '0.00', foreign_tax_credit: '0.00', total_credits: '400000.00',
          tax_payable: '140000.00', refund_due: '0.00', rounding: 'nearest_rupee',
          band_workings: [
            { band: 'LKR 0 – LKR 1,000,000', rate: '6%', from_amount: '0', to_amount: '1000000', rate_fraction: '0.06', taxable_in_band: '1000000.00', tax: '60000.00' },
            { band: 'LKR 1,000,000 – LKR 1,500,000', rate: '18%', from_amount: '1000000', to_amount: '1500000', rate_fraction: '0.18', taxable_in_band: '500000.00', tax: '90000.00' },
          ],
        },
      };
    }
    if (method === 'GET' && path === '/v1/llm-keys') return { status: 200, body: { available: true, keys: [{ provider: 'anthropic', last4: 'Ab12', validated_at: '2026-10-01T00:00:00+00:00', readable: true }] } };
    if (method === 'PUT' && path === '/v1/llm-keys/anthropic') {
      this.data.bodies.push({ method, path, body: req.json });
      return { status: 204 };
    }
    if (method === 'GET' && path === '/v1/mcp/connections/enabled') return { status: 200, body: { enabled: true } };
    if (method === 'GET' && path === '/v1/mcp/connections/') return { status: 200, body: { connections: this.data.connections } };
    if ((params = p('/v1/mcp/connections/{id}')) && method === 'DELETE') {
      const index = this.data.connections.findIndex((c) => c.token_id === params?.id);
      if (index < 0) return problem(404, 'Not Found', 'connection not found', '/problems/not-found');
      this.data.connections.splice(index, 1);
      return { status: 204 };
    }
    if (method === 'PUT' && path === '/v1/mcp/connections/enabled') {
      this.data.bodies.push({ method, path, body: req.json });
      return { status: 204 };
    }
    if (method === 'GET' && path === '/v1/advisor/reports/latest') return { status: 200, body: {} };

    // rules, tokens, plain-text exports
    const rules = this.rulesRoute(req);
    if (rules) return rules;
    const tokens = this.tokensRoute(req);
    if (tokens) return tokens;
    if (method === 'GET' && (path === '/v1/export/beancount' || path === '/v1/export/hledger')) {
      const text = path.endsWith('beancount')
        ? '2026-01-01 open Assets:Cash USD\n\n2026-10-01 * "October salary"\n  Assets:Checking  5000.00 USD\n  Income:Salary  -5000.00 USD\n'
        : '2026-10-01 October salary\n    assets:checking    5000.00 USD\n    income:salary    -5000.00 USD\n';
      return { status: 200, raw: text, headers: { 'Content-Type': 'text/plain; charset=utf-8' } };
    }

    // reminders
    if (method === 'GET' && path === '/v1/reminders/') {
      const status = req.query.get('status');
      return { status: 200, body: { reminders: this.data.reminders.filter((r) => !status || r.status === status) } };
    }

    // statements
    if (method === 'POST' && path === '/v1/statements/upload') {
      if (!(req.headers['content-type'] ?? '').startsWith('multipart/form-data')) return problem(422, 'Request validation failed', 'file required');
      const upload = clone(STATEMENT_UPLOAD);
      if (!this.options.uploadIds) for (const t of upload.transactions) t.id = '';
      return { status: 202, body: upload };
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
    if (method === 'POST' && path === '/v1/agent/files') {
      const name = /filename="([^"]+)"/.exec(req.body)?.[1] ?? 'attachment';
      return { status: 200, body: { file_ref: `ref-${name}`, name, size: req.body.length, mime_type: 'application/pdf' } };
    }
    if (method === 'POST' && (path === '/v1/agent/chat' || path === '/v1/agent/resume')) {
      const events = path === '/v1/agent/chat' ? this.chatEvents : this.resumeEvents(String((req.json as { decision?: string }).decision));
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' });
      for (const event of events) res.write(`data: ${JSON.stringify(event)}\n\n`);
      res.end();
      return undefined;
    }

    return problem(404, 'Not Found', 'Not Found');
  }

  /** The categorization rules: CRUD, a test against booked entries, and suggestions. */
  private rulesRoute(req: RecordedRequest): Reply | undefined {
    const { method, path } = req;
    const rules = this.data.rules;
    const invalid = (detail: string): Reply => problem(422, 'Unprocessable Entity', detail, '/problems/unprocessable');
    const hasAction = (actions: RuleDraft['actions'] | null | undefined): boolean =>
      !!actions && Object.values(actions).some((v) => v !== null && v !== undefined && v !== '');
    if (path === '/v1/rules' && method === 'GET') return { status: 200, body: rules };
    if (path === '/v1/rules' && method === 'POST') {
      const draft = req.json as RuleDraft;
      this.data.bodies.push({ method, path, body: draft });
      if (!hasAction(draft.actions)) return invalid('A rule needs to do something: set an account, a tag, or a description');
      const id = uid(600 + rules.length + 10);
      rules.push({ priority: 100, match_all: true, enabled: true, ...draft, id, hits: 0, last_hit_at: null, created_at: '2026-10-09T10:00:00Z', updated_at: '2026-10-09T10:00:00Z' });
      return { status: 201, body: { id } };
    }
    if (path === '/v1/rules/test' && method === 'POST') {
      const draft = req.json as RuleDraft;
      this.data.bodies.push({ method, path, body: draft });
      if (!hasAction(draft.actions)) return invalid('A rule needs to do something: set an account, a tag, or a description');
      const needles = draft.conditions.filter((c) => c.field === 'description').map((c) => c.value.toLowerCase());
      const matches = this.data.entries
        .filter((e) => needles.some((n) => e.description.toLowerCase().includes(n)))
        .map((e) => {
          const debit = e.postings.find((x) => x.direction > 0);
          return { entry_id: e.id, entry_date: e.entry_date, description: e.description, amount: debit?.amount ?? '0', currency: debit?.currency ?? 'USD', direction: 'out' as const, account_id: debit?.account_id ?? '' };
        });
      const result: RuleTestResult = {
        total: matches.length,
        agreeing: matches.filter((m) => m.account_id === draft.actions.account_id).length,
        matches,
      };
      return { status: 200, body: result };
    }
    if (path === '/v1/rules/suggestions' && method === 'GET') {
      const suggestion: RuleSuggestion = {
        name: 'Rent',
        conditions: [{ field: 'description', operator: 'contains', value: "landlord's rent" }],
        actions: { account_id: uid(7) },
        priority: 100,
        match_all: true,
        enabled: true,
        support: 4,
        agreement: 4,
        examples: ['Rent for October'],
      };
      return { status: 200, body: [suggestion] };
    }
    const params = match('/v1/rules/{id}', path);
    if (!params) return undefined;
    const rule = rules.find((r) => r.id === params.id);
    if (!rule) return problem(404, 'Not Found', 'No such rule', '/problems/not-found');
    if (method === 'GET') return { status: 200, body: rule };
    if (method === 'PATCH') {
      const update = req.json as RuleUpdate;
      this.data.bodies.push({ method, path, body: update });
      const changes = Object.fromEntries(Object.entries(update).filter(([, v]) => v !== null && v !== undefined));
      Object.assign(rule, changes);
      return { status: 200, body: { id: rule.id } };
    }
    if (method === 'DELETE') {
      rules.splice(rules.indexOf(rule), 1);
      return { status: 204 };
    }
    return undefined;
  }

  /** Personal access tokens: a new one works at once, a revoked one never again. */
  private tokensRoute(req: RecordedRequest): Reply | undefined {
    const { method, path } = req;
    if (path === '/v1/tokens' && method === 'GET') return { status: 200, body: this.data.tokens };
    if (path === '/v1/tokens' && method === 'POST') {
      const input = req.json as { name?: string; expires_in_days?: number | null };
      if (!input?.name) return problem(422, 'Request validation failed', [{ loc: ['body', 'name'], msg: 'Field required', type: 'missing' }], '/problems/validation');
      const token = `salli_pat_${b64url(randomBytes(18))}`;
      const created: PersonalAccessToken = {
        id: uid(700 + this.data.tokens.length + 10),
        name: input.name,
        prefix: token.slice(0, 14),
        created_at: '2026-10-09T10:00:00Z',
        expires_at: input.expires_in_days ? '2027-01-07T10:00:00Z' : null,
        last_used_at: null,
      };
      this.data.tokens.push(created);
      this.pats.add(token);
      return { status: 201, body: { ...created, token } };
    }
    const params = match('/v1/tokens/{id}', path);
    if (params && method === 'DELETE') {
      const index = this.data.tokens.findIndex((t) => t.id === params.id);
      if (index < 0) return problem(404, 'Not Found', 'No such token', '/problems/not-found');
      const [removed] = this.data.tokens.splice(index, 1);
      for (const pat of [...this.pats]) if (removed && pat.startsWith(removed.prefix)) this.pats.delete(pat);
      return { status: 204 };
    }
    return undefined;
  }

  /** Generic CRUD over `data.collections` (POST, GET, PATCH, DELETE). */
  private collectionRoute(req: RecordedRequest): Reply | undefined {
    for (const [base, items] of Object.entries(this.data.collections)) {
      const root = base.endsWith('/') ? base : `${base}/`;
      if (req.path === base || req.path === root) {
        if (req.method === 'GET') {
          const key = base.split('/').filter(Boolean).pop() ?? 'items';
          const name = { budget: 'budgets', debt: 'debts', portfolio: 'holdings', policies: 'policies', goals: 'goals' }[key] ?? key;
          const activeOnly = req.query.get('active_only') !== 'false';
          return { status: 200, body: { [name]: items.filter((i) => !activeOnly || i.is_active !== false), ...(key === 'documents' ? { count: items.length } : {}) } };
        }
        if (req.method === 'POST') {
          this.data.bodies.push({ method: req.method, path: req.path, body: req.json });
          const id = uid(5000 + items.length);
          items.push({ id, ...(req.json as object) });
          return { status: 201, body: { id } };
        }
      }
      if (req.path.startsWith(root) && req.path.length > root.length) {
        const rest = req.path.slice(root.length).split('/');
        const item = items.find((i) => i.id === rest[0]);
        if (!item) continue;
        if (rest.length === 1 && req.method === 'GET') return { status: 200, body: item };
        if (rest.length === 1 && req.method === 'PATCH') {
          this.data.bodies.push({ method: req.method, path: req.path, body: req.json });
          Object.assign(item, req.json);
          return { status: 200, body: { updated: true } };
        }
        if (rest.length === 1 && req.method === 'DELETE') {
          items.splice(items.indexOf(item), 1);
          return { status: 204 };
        }
        if (rest[1] === 'summary' && req.method === 'GET') {
          return {
            status: 200,
            body: {
              id: item.id, period_start: item.period_start, period_end: item.period_end, currency: 'USD',
              total_limit: '2200.00', total_actual: '2212.35', total_variance: '-12.35',
              lines: [
                { account_id: uid(6), category: 'Groceries', limit_amount: '400.00', actual_amount: '412.35', variance: '-12.35' },
                { account_id: uid(7), category: 'Rent', limit_amount: '1800.00', actual_amount: '1800.00', variance: '0.00' },
              ],
            },
          };
        }
        if (rest[1] === 'allocations') {
          if (req.method === 'PUT') {
            this.data.bodies.push({ method: req.method, path: req.path, body: req.json });
            return { status: 200, body: { updated: true } };
          }
          return { status: 200, body: { allocations: [{ goal_id: item.id, account_id: uid(2), currency: 'USD', allocated_amount: '9000.00' }] } };
        }
      }
    }
    return undefined;
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
    if (method === 'POST' && path === '/mcp/oauth/device_authorization') {
      const clientId = req.form?.client_id ?? '';
      if (!this.clients.has(clientId)) return { status: 400, body: { error: 'invalid_client', error_description: 'unknown client_id' } };
      return {
        status: 200,
        body: {
          device_code: 'dev-code-1',
          user_code: 'WDJB-MJHT',
          verification_uri: `${this.url}/mcp/oauth/device`,
          verification_uri_complete: `${this.url}/mcp/oauth/device?user_code=WDJB-MJHT`,
          expires_in: 600,
          // Seconds in the real thing (5); a hundredth here, so tests do not wait.
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
