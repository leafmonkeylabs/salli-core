/**
 * The mock server's tax rule sets (`/v1/tax/schema`, `/v1/tax/rule-sets`):
 * a fictional jurisdiction, XA, with an active version 1 and a version 2 an
 * agent proposed, kept in memory and typed with the SDK's generated types.
 *
 * Its "validator" is a stand-in with fixed rules, not Salli's: a document
 * without `schema` is invalid, one without examples is a draft, an example
 * whose name contains "wrong" fails, and anything else is validated.
 * Activation needs tax:activate, as the real server's does.
 */
import type {
  TaxRuleChange,
  TaxRuleDiff,
  TaxRuleEvaluation,
  TaxRuleExampleResult,
  TaxRuleSet,
  TaxRuleSetVersion,
  TaxRuleSetVersionSummary,
  TaxRuleValidation,
} from '@leafmonkeylabs/salli-sdk';
import { uid } from './fixtures';

type Json = Record<string, unknown>;
type Reply = { status: number; body?: unknown; headers?: Record<string, string> };

export interface TaxRequest {
  method: string;
  path: string;
  query: URLSearchParams;
  json?: unknown;
}

const ACT = { id: 'act', url: 'https://example.org/xa/income-tax-act', title: 'Income Tax Act 2031', retrieved: '2031-02-01' };
const BUDGET = { id: 'budget', url: 'https://example.org/xa/budget-2031', title: 'Budget Statement 2031', retrieved: '2031-03-02' };

/** Version 1: an allowance of 12,000 and two bands. */
export const XA_V1: Json = {
  schema: 'salli.tax/1',
  jurisdiction: { country: 'XA', region: null },
  year: { label: '2031', start: '2031-01-01', end: '2031-12-31' },
  currency: 'USD',
  sources: [ACT],
  roles: [
    { key: 'salary', kind: 'income', label: 'Salary' },
    { key: 'tax_withheld', kind: 'withholding', label: 'Tax withheld' },
  ],
  band_tables: { main: { bands: [{ upto: '40000', rate: '0.20' }, { upto: null, rate: '0.40' }], source: 'act' } },
  blocks: [
    { type: 'relief', key: 'allowance', of: 'role.salary', amount: '12000', source: 'act' },
    { type: 'schedule', key: 'income_tax', of: 'line.allowance.remaining', table: 'main' },
    { type: 'credit', key: 'withholding', of: 'role.tax_withheld', refundable: true },
  ],
  lines: [{ key: 'balance', label: 'Tax less withholding', expr: 'line.income_tax - line.withholding' }],
  result: { net: 'line.balance', round: { mode: 'nearest', unit: '0.01' } },
  examples: [{ name: 'Salary of 30,000', source: 'act', inputs: { salary: '30000' }, expected: { payable: '3600' } }],
};

/** Version 2: the budget raised the allowance to 12,500. */
export const XA_V2: Json = {
  ...XA_V1,
  sources: [ACT, BUDGET],
  blocks: [
    { type: 'relief', key: 'allowance', of: 'role.salary', amount: '12500', source: 'budget' },
    { type: 'schedule', key: 'income_tax', of: 'line.allowance.remaining', table: 'main' },
    { type: 'credit', key: 'withholding', of: 'role.tax_withheld', refundable: true },
  ],
  examples: [
    { name: 'Salary of 30,000', source: 'budget', inputs: { salary: '30000' }, expected: { payable: '3500' } },
    { name: 'Salary of 60,000', source: 'budget', inputs: { salary: '60000' }, expected: { payable: '11000' } },
  ],
};

/** What the review of version 2 against version 1 shows. */
export const XA_V1_TO_V2: TaxRuleChange[] = [
  { path: 'blocks[key=allowance].amount', kind: 'changed', before: '12000', after: '12500', figure: true, source: 'budget' },
  { path: 'blocks[key=allowance].source', kind: 'changed', before: 'act', after: 'budget', figure: false, source: 'budget' },
  { path: 'sources[id=budget]', kind: 'added', before: null, after: BUDGET, figure: false, source: null },
];

const HASH_V1 = 'a1'.repeat(32);
const HASH_V2 = 'b2'.repeat(32);
const AT = '2031-03-05T09:00:00Z';

export class TaxRulesMock {
  readonly sets: TaxRuleSet[] = [];
  readonly versions = new Map<string, TaxRuleSetVersion>();
  /** Bodies of evaluate requests, in order. */
  readonly evaluated: unknown[] = [];
  private seq = 0;

  constructor() {
    const set: TaxRuleSet = {
      id: uid(1501),
      country: 'XA',
      region: null,
      year_label: '2031',
      name: 'XA 2031',
      active_version_id: uid(1511),
      created_at: '2031-02-01T09:00:00Z',
      updated_at: AT,
      versions: [],
    };
    this.sets.push(set);
    this.store(
      this.version(set, 1, XA_V1, { id: uid(1511), status: 'active', author_kind: 'user', author_name: 'Salli CLI', change_note: null, content_hash: HASH_V1, activated_at: '2031-02-02T09:00:00Z' }),
    );
    this.store(
      this.version(set, 2, XA_V2, {
        id: uid(1512),
        status: 'proposed',
        author_kind: 'agent',
        author_name: 'Claude',
        change_note: 'Allowance raised to 12,500 by the 2031 budget',
        content_hash: HASH_V2,
        proposed_at: AT,
      }),
    );
  }

  /** The stand-in validator: see the module comment. */
  static validate(document: Json): TaxRuleValidation {
    const base = { content_hash: null, validated_at: AT, warnings: [], examples: [] as TaxRuleExampleResult[] };
    if (document.schema !== 'salli.tax/1') {
      return { ...base, ok: false, errors: [{ path: 'schema', message: 'Field required', snippet: null }] };
    }
    const examples = (Array.isArray(document.examples) ? document.examples : []) as Array<{ name: string; expected?: { payable?: string } }>;
    const results: TaxRuleExampleResult[] = examples.map((e) =>
      e.name.includes('wrong')
        ? {
            name: e.name,
            passed: false,
            error: null,
            mismatches: [
              {
                key: 'payable',
                expected: e.expected?.payable ?? '0',
                got: '3600',
                expr: 'line.balance',
                message: `payable: expected ${e.expected?.payable ?? '0'}, got 3600 (from line.balance)`,
              },
              {
                key: 'allowance.remaining',
                expected: '17500',
                got: '18000',
                expr: 'max(0, role.salary - line.allowance)',
                message: 'allowance.remaining: expected 17500, got 18000 (from max(0, role.salary - line.allowance))',
              },
            ],
          }
        : { name: e.name, passed: true, error: null, mismatches: [] },
    );
    return {
      ...base,
      ok: results.length > 0 && results.every((r) => r.passed),
      content_hash: 'c3'.repeat(32),
      errors: [],
      warnings: [{ path: 'roles[1]', message: "Role 'tax_withheld' is never used", snippet: null }],
      examples: results,
    };
  }

  private version(set: TaxRuleSet, n: number, document: Json, fields: Partial<TaxRuleSetVersion>): TaxRuleSetVersion {
    const validation = TaxRulesMock.validate(document);
    return {
      id: uid(1600 + ++this.seq),
      rule_set_id: set.id,
      version: n,
      status: validation.errors.length ? 'invalid' : validation.ok ? 'validated' : 'draft',
      content_hash: validation.content_hash,
      author_kind: 'user',
      author_name: null,
      change_note: null,
      created_at: AT,
      proposed_at: null,
      activated_at: null,
      superseded_at: null,
      document,
      validation,
      ...fields,
    };
  }

  private store(version: TaxRuleSetVersion): TaxRuleSetVersion {
    this.versions.set(version.id, version);
    const set = this.sets.find((s) => s.id === version.rule_set_id);
    if (set) set.versions = [...set.versions.filter((v) => v.id !== version.id), summary(version)].sort((a, b) => a.version - b.version);
    return version;
  }

  private versionsOf(set: TaxRuleSet): TaxRuleSetVersion[] {
    return set.versions.map((v) => this.versions.get(v.id)).filter((v): v is TaxRuleSetVersion => v !== undefined);
  }

  /** Reads a document as the API does: JSON text, read strictly, or JSON. */
  private static read(input: unknown): Json | Reply {
    let document = input;
    if (typeof input === 'string') {
      try {
        document = JSON.parse(input);
      } catch {
        return problem(422, 'This is not a rule set Salli can read: $: Not valid JSON', '/problems/invalid-rule-set');
      }
    }
    if (typeof document !== 'object' || document === null || Array.isArray(document)) {
      return problem(422, 'This is not a rule set Salli can read: $: Not a JSON object', '/problems/invalid-rule-set');
    }
    return document as Json;
  }

  private add(set: TaxRuleSet, document: Json, note: string | null | undefined, status?: TaxRuleSetVersion['status']): TaxRuleSetVersion {
    const n = Math.max(0, ...set.versions.map((v) => v.version)) + 1;
    const version = this.version(set, n, document, { change_note: note ?? null });
    if (status) version.status = status;
    return this.store(version);
  }

  route(req: TaxRequest, permissions: readonly string[]): Reply | undefined {
    const { method, path } = req;
    if (method === 'GET' && path === '/v1/tax/schema') {
      return { status: 200, body: { $schema: 'https://json-schema.org/draft/2020-12/schema', title: 'Salli tax rule set', type: 'object', required: ['schema', 'jurisdiction', 'year', 'currency', 'result'] } };
    }
    if (!path.startsWith('/v1/tax/rule-sets')) return undefined;
    const parts = path.slice('/v1/tax/rule-sets'.length).split('/').filter(Boolean);
    const body = (req.json ?? {}) as { document?: unknown; note?: string | null; url?: string };

    if (parts.length === 0) {
      if (method === 'GET') return { status: 200, body: this.sets };
      if (method === 'POST') {
        const document = TaxRulesMock.read(body.document);
        if ('status' in document && typeof document.status === 'number') return document as Reply;
        const doc = document as Json;
        const country = (doc.jurisdiction as { country?: string } | undefined)?.country;
        const year = (doc.year as { label?: string } | undefined)?.label;
        if (!country || !year) return problem(422, "This is not a rule set Salli can read: jurisdiction.country: can't be read", '/problems/invalid-rule-set');
        const existing = this.sets.find((s) => s.country === country && s.year_label === year);
        if (existing) return problem(409, `You already have a rule set for ${country} ${year} (${existing.id}): add a version to it instead.`, '/problems/rule-set-exists');
        const set: TaxRuleSet = { id: uid(1700 + this.sets.length), country, region: null, year_label: year, name: `${country} ${year}`, active_version_id: null, created_at: AT, updated_at: AT, versions: [] };
        this.sets.push(set);
        return { status: 201, body: this.add(set, doc, body.note) };
      }
    }
    if (parts[0] === 'import' && parts.length === 1 && method === 'POST') {
      let doc: Json;
      if (body.url !== undefined) {
        if (!body.url.startsWith('https://')) return problem(422, 'Only https URLs can be imported', '/problems/fetch-refused');
        doc = { ...XA_V2, examples: [] };
      } else {
        const document = TaxRulesMock.read(body.document);
        if ('status' in document && typeof document.status === 'number') return document as Reply;
        doc = document as Json;
      }
      const set = this.sets.find((s) => s.country === (doc.jurisdiction as { country?: string })?.country) ?? this.sets[0];
      if (!set) return problem(500, 'no set');
      const version = this.add(set, doc, body.note ?? (body.url ? `Imported from ${body.url}` : null));
      if (version.status === 'validated') version.status = 'draft'; // an import lands as a draft
      return { status: 201, body: this.store(version) };
    }

    const set = this.sets.find((s) => s.id === parts[0]);
    if (!set) return problem(404, 'Tax rule set not found', '/problems/not-found');
    if (parts.length === 1 && method === 'GET') return { status: 200, body: set };
    if (parts[1] === 'diff' && method === 'GET') {
      const to = this.versions.get(req.query.get('to') ?? '');
      if (!to || to.rule_set_id !== set.id) return problem(404, 'Tax rule set version not found', '/problems/not-found');
      const fromId = req.query.get('from') ?? set.active_version_id;
      const from = fromId ? this.versions.get(fromId) : undefined;
      if (fromId && !from) return problem(404, 'Tax rule set version not found', '/problems/not-found');
      let changes: TaxRuleChange[];
      if (from?.id === uid(1511) && to.id === uid(1512)) changes = XA_V1_TO_V2;
      else if (!from) changes = [{ path: '$', kind: 'added', before: null, after: null, figure: false, source: null }];
      else changes = JSON.stringify(from.document) === JSON.stringify(to.document) ? [] : [{ path: 'blocks[key=allowance].amount', kind: 'changed', before: '12000', after: '12500', figure: true, source: 'budget' }];
      const sources = Object.fromEntries(((to.document.sources ?? []) as Array<{ id: string }>).map((s) => [s.id, s]));
      const diff: TaxRuleDiff = { rule_set_id: set.id, from: from ? summary(from) : null, to: summary(to), changes, sources: sources as TaxRuleDiff['sources'], examples: to.validation.examples, validation_ok: to.validation.ok };
      return { status: 200, body: diff };
    }
    if (parts[1] !== 'versions') return problem(404, 'Not Found');
    if (parts.length === 2 && method === 'POST') {
      const document = TaxRulesMock.read(body.document);
      if ('status' in document && typeof document.status === 'number') return document as Reply;
      return { status: 201, body: this.add(set, document as Json, body.note) };
    }
    const version = this.versions.get(parts[2] ?? '');
    if (!version || version.rule_set_id !== set.id) return problem(404, 'Tax rule set version not found', '/problems/not-found');
    const action = parts[3];
    if (action === undefined && method === 'GET') return { status: 200, body: version };
    if (action === 'validate' && method === 'POST') {
      version.validation = TaxRulesMock.validate(version.document);
      if (['draft', 'invalid', 'validated'].includes(version.status)) {
        version.status = version.validation.errors.length ? 'invalid' : version.validation.ok ? 'validated' : 'draft';
      }
      return { status: 200, body: this.store(version) };
    }
    if (action === 'propose' && method === 'POST') {
      if (!version.validation.ok) return problem(409, `Version ${version.version} can't be proposed: its worked examples don't all pass`, '/problems/rule-set-state');
      version.status = 'proposed';
      version.proposed_at = AT;
      return { status: 200, body: this.store(version) };
    }
    if (action === 'activate' && method === 'POST') {
      if (!permissions.includes('tax:activate')) {
        return problem(403, "This sign-in doesn't hold tax:activate. Only your own sign-in to Salli (the app, or the salli CLI) can do this, or a personal access token you made with it; AI connectors and other applications never can.", '/problems/permission');
      }
      if (!version.validation.ok) return problem(409, `Version ${version.version} can't be activated: its worked examples don't all pass`, '/problems/rule-set-state');
      for (const other of this.versionsOf(set)) {
        if (other.status === 'active' && other.id !== version.id) this.store({ ...other, status: 'superseded', superseded_at: AT });
      }
      version.status = 'active';
      version.activated_at = AT;
      set.active_version_id = version.id;
      return { status: 200, body: this.store(version) };
    }
    if (action === 'export' && method === 'GET') {
      const text = `${JSON.stringify(version.document)}`;
      return { status: 200, body: { filename: `xa-2031-v${version.version}.salli-tax.json`, content_hash: version.content_hash, canonical: version.content_hash !== null, text } };
    }
    if (action === 'evaluate' && method === 'POST') {
      this.evaluated.push(req.json ?? null);
      const answers = ((req.json ?? {}) as { answers?: Record<string, unknown> }).answers ?? {};
      const evaluation: TaxRuleEvaluation = {
        version: summary(version),
        validated: version.validation.ok,
        country: set.country,
        region: null,
        year: set.year_label,
        period_start: '2031-01-01',
        period_end: '2031-12-31',
        currency: 'USD',
        base_currency: 'USD',
        content_hash: version.content_hash ?? '',
        roles: [
          { key: 'salary', kind: 'income', label: 'Salary', total: '60000.00', postings: 12 },
          { key: 'tax_withheld', kind: 'withholding', label: 'Tax withheld', total: '12000.00', postings: 12 },
        ],
        rates: [],
        lines: [
          { key: 'allowance', label: 'Allowance', amount: '12500', expr: 'min(12500, max(0, role.salary))', source: 'budget', refundable: null },
          { key: 'allowance.remaining', label: 'Allowance (remaining)', amount: '47500.00', expr: 'max(0, role.salary - line.allowance)', source: 'budget', refundable: null },
          { key: 'income_tax', label: 'Income tax', amount: '11000.000', expr: 'line.income_tax.band_1.tax + line.income_tax.band_2.tax', source: 'act', refundable: null },
          { key: 'withholding', label: 'Tax withheld', amount: '12000.00', expr: 'role.tax_withheld', source: null, refundable: true },
          { key: 'balance', label: 'Tax less withholding', amount: '-1000.000', expr: 'line.income_tax - line.withholding', source: null, refundable: null },
        ],
        net: '-1000.00',
        net_expr: 'line.balance',
        tax_payable: '0.00',
        refund_due: '1000.00',
        forms: [],
        warnings: Object.keys(answers).length ? [`Answers used: ${Object.keys(answers).sort().join(', ')}`] : [],
        provenance: 'Computed from rules you or your agent entered (XA 2031, version 2). Salli does not vouch for them.',
      };
      return { status: 200, body: evaluation };
    }
    return problem(404, 'Not Found');
  }
}

function summary(version: TaxRuleSetVersion): TaxRuleSetVersionSummary {
  const { document: _document, validation: _validation, ...rest } = version;
  return rest;
}

function problem(status: number, detail: string, type = 'about:blank'): Reply {
  const titles: Record<number, string> = { 403: 'Forbidden', 404: 'Not Found', 409: 'Conflict', 422: 'Unprocessable Content', 500: 'Error' };
  return {
    status,
    body: { type, title: titles[status] ?? 'Error', status, detail },
    headers: { 'Content-Type': 'application/problem+json', 'X-Request-Id': 'req-test-1' },
  };
}
