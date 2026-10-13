/**
 * Books, tax and settings' part of the fixture server (MockApi, C4): reads
 * answer what the real server answered (books.ts, tax.ts, settings.ts),
 * and writes answer what it answered to the same writes, keeping what they
 * change so a page reads it back:
 *
 * - imports: the October statement and its queue; an account chosen, two
 *   posted, two discarded; a file with no transactions refused; rules
 *   tested, refused (a pattern that doesn't compile), made and edited;
 * - tax: version 2 activated (the server's step-up answer when a test asks
 *   for it), computed again; version 3 checked and its proposal refused;
 * - settings: a token made (shown once), revoked; MCP switched; a client
 *   revoked; a key saved (one ending other than the person's is refused)
 *   and removed; digest preferences saved.
 */
import type {
  BankStatementList,
  CategorizationRule,
  LlmKeys,
  McpConnection,
  NotificationPreferences,
  PendingStatementTransactions,
  PersonalAccessToken,
  TaxRuleSet,
  TaxRuleSetVersion,
} from '@leafmonkeylabs/salli-sdk';
import type { Answer, Recorded } from './api';
import { MCP_CONNECTIONS, MY_DATA } from './auth';
import * as books from './books';
import * as settings from './settings';
import * as tax from './tax';

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const NOT_FOUND = { type: 'about:blank', title: 'Not Found', status: 404, detail: 'Not found' };

export class BooksState {
  statements: BankStatementList = clone(books.STATEMENTS);
  pending: PendingStatementTransactions = clone(books.PENDING);
  rules: CategorizationRule[] = clone(books.RULES);

  answer(request: Recorded): Answer | undefined {
    const { method, path } = request;
    const body = (): Record<string, unknown> => (request.body ? (JSON.parse(request.body) as Record<string, unknown>) : {});
    if (method === 'GET' && path === '/v1/statements/') return { status: 200, body: this.statements };
    if (method === 'POST' && path === '/v1/statements/upload') {
      // A file with no transactions in it is the server's refusal; any other, the October statement.
      return /Nothing,to,see/.test(request.body) ? { status: 422, body: books.UPLOAD_REFUSED } : { status: 202, body: books.UPLOADED };
    }
    if (method === 'POST' && path === '/v1/statements/categorize') {
      this.pending = clone(books.PENDING_CHOSEN);
      return { status: 200, body: books.CATEGORIZED };
    }
    const statement = /^\/v1\/statements\/([^/]+)(\/post|\/discard)?$/.exec(path);
    if (statement) {
      const id = decodeURIComponent(statement[1] ?? '');
      if (id !== this.pending.statement_id) return { status: 404, body: { ...NOT_FOUND, detail: 'Statement not found' } };
      if (method === 'GET' && !statement[2]) return { status: 200, body: this.pending };
      if (method === 'POST' && statement[2] === '/post') {
        this.pending = clone(books.PENDING_POSTED);
        return { status: 200, body: books.POSTED };
      }
      if (method === 'POST' && statement[2] === '/discard') {
        this.pending = clone(books.PENDING_DISCARDED);
        this.statements = clone(books.STATEMENTS_REVIEWED);
        return { status: 200, body: books.DISCARDED };
      }
    }
    if (method === 'GET' && path === '/v1/bank-connections') return { status: 200, body: books.BANKS };
    if (method === 'GET' && path === '/v1/rules') return { status: 200, body: this.rules };
    if (method === 'GET' && path === '/v1/rules/suggestions') return { status: 200, body: books.SUGGESTIONS };
    if (method === 'POST' && path === '/v1/rules/test') return { status: 200, body: books.RULE_TEST };
    if (method === 'POST' && path === '/v1/rules') {
      const draft = body() as unknown as CategorizationRule;
      if (draft.conditions?.some((c) => c.operator === 'matches' && c.value.includes('('))) return { status: 422, body: books.RULE_REFUSED };
      const made = books.RULES_EDITED.find((r) => r.id === books.RULE_MADE.id);
      this.rules = [...this.rules, { ...clone(made ?? books.RULES_EDITED[0]!), ...draft, id: books.RULE_MADE.id, hits: 0, last_hit_at: null }];
      return { status: 201, body: books.RULE_MADE };
    }
    const rule = /^\/v1\/rules\/([^/]+)$/.exec(path);
    if (rule) {
      const id = decodeURIComponent(rule[1] ?? '');
      const found = this.rules.find((r) => r.id === id);
      if (!found) return { status: 404, body: { ...NOT_FOUND, detail: 'No such rule' } };
      if (method === 'PATCH') {
        Object.assign(found, body());
        return { status: 200, body: { id } };
      }
      if (method === 'DELETE') {
        this.rules = this.rules.filter((r) => r.id !== id);
        return { status: 204 };
      }
    }
    return undefined;
  }
}

export class TaxState {
  ruleSet: TaxRuleSet = clone(tax.RULE_SET);
  versions: Record<string, TaxRuleSetVersion> = Object.fromEntries([tax.VERSION_1, tax.VERSION_2, tax.VERSION_3].map((v) => [v.id, clone(v)]));
  latest: unknown = clone(tax.LATEST);
  year: unknown = clone(tax.YEAR);
  /** Answer the next activation with the server's step-up problem (the sign-in is older than five minutes). */
  stepUps = 0;

  answer(request: Recorded): Answer | undefined {
    const { method, path, search } = request;
    if (method === 'GET' && path === '/v1/tax/current-year') return { status: 200, body: this.year };
    if (method === 'GET' && path === '/v1/tax/latest') return { status: 200, body: this.latest };
    if (method === 'POST' && path === '/v1/tax/compute') {
      this.latest = { result: clone(tax.COMPUTED) };
      return { status: 200, body: tax.COMPUTED };
    }
    if (method === 'POST' && path === '/v1/tax/explain') return { status: 200, body: tax.EXPLAINED };
    if (method === 'GET' && path === '/v1/tax/rule-sets') return { status: 200, body: [this.ruleSet] };
    const set = /^\/v1\/tax\/rule-sets\/([^/]+)(?:\/(diff)|\/versions\/([^/]+)(?:\/(validate|propose|activate|export))?)?$/.exec(path);
    if (!set) return undefined;
    if (decodeURIComponent(set[1] ?? '') !== this.ruleSet.id) return { status: 404, body: { ...NOT_FOUND, detail: 'Tax rule set not found' } };
    if (method === 'GET' && !set[2] && !set[3]) return { status: 200, body: this.ruleSet };
    if (method === 'GET' && set[2] === 'diff') {
      const to = new URLSearchParams(search).get('to');
      const diff = to === tax.VERSION_3.id ? tax.DIFF_3 : to === tax.VERSION_1.id ? tax.DIFF_1 : tax.DIFF_2;
      return { status: 200, body: diff };
    }
    const id = decodeURIComponent(set[3] ?? '');
    const version = this.versions[id];
    if (!version) return { status: 404, body: { ...NOT_FOUND, detail: 'Version not found' } };
    const action = set[4];
    if (method === 'GET' && !action) return { status: 200, body: version };
    if (method === 'GET' && action === 'export') return { status: 200, body: tax.EXPORT_2 };
    if (method === 'POST' && action === 'validate') {
      if (id === tax.VERSION_3.id) this.versions[id] = clone(tax.VALIDATED_3);
      return { status: 200, body: this.versions[id] };
    }
    if (method === 'POST' && action === 'propose') {
      if (id === tax.VERSION_3.id) return { status: 409, body: tax.PROPOSE_REFUSED };
      return { status: 200, body: version };
    }
    if (method === 'POST' && action === 'activate') {
      if (this.stepUps > 0) {
        this.stepUps -= 1;
        return {
          status: 403,
          body: tax.STEP_UP,
          headers: { 'www-authenticate': 'Bearer error="insufficient_user_authentication", error_description="Sign in again to continue", max_age=300' },
        };
      }
      if (id !== tax.VERSION_2.id) return { status: 409, body: tax.PROPOSE_REFUSED };
      this.versions[id] = clone(tax.ACTIVATED);
      this.versions[tax.VERSION_1.id] = clone(tax.VERSION_1_SUPERSEDED);
      this.ruleSet = clone(tax.RULE_SET_ACTIVATED);
      return { status: 200, body: tax.ACTIVATED };
    }
    return undefined;
  }
}

export class SettingsState {
  tokens: PersonalAccessToken[] = clone(settings.TOKENS);
  keys: LlmKeys = clone(settings.LLM_KEYS);
  mcpEnabled = true;
  connections: McpConnection[] = clone(MCP_CONNECTIONS);
  preferences: NotificationPreferences = clone(settings.PREFERENCES);
  /** Answer the next token asking for tax:activate with the server's step-up problem. */
  stepUps = 0;

  answer(request: Recorded): Answer | undefined {
    const { method, path } = request;
    const body = (): Record<string, unknown> => (request.body ? (JSON.parse(request.body) as Record<string, unknown>) : {});
    if (method === 'GET' && path === '/v1/tokens') return { status: 200, body: this.tokens };
    if (method === 'POST' && path === '/v1/tokens') {
      const asked = body() as { name?: string; permissions?: string[] };
      if (!asked.name) return { status: 422, body: settings.TOKEN_REFUSED };
      if (asked.permissions?.includes('tax:activate') && this.stepUps > 0) {
        this.stepUps -= 1;
        return { status: 403, body: settings.TOKEN_STEP_UP };
      }
      const made = { ...clone(settings.TOKEN_MADE), name: asked.name, permissions: (asked.permissions ?? []) as PersonalAccessToken['permissions'] };
      const { token: _secret, ...listed } = made;
      this.tokens = [listed, ...this.tokens];
      return { status: 201, body: made };
    }
    const token = /^\/v1\/tokens\/([^/]+)$/.exec(path);
    if (method === 'DELETE' && token) {
      const id = decodeURIComponent(token[1] ?? '');
      if (!this.tokens.some((x) => x.id === id)) return { status: 404, body: { ...NOT_FOUND, detail: 'No such token' } };
      this.tokens = this.tokens.filter((x) => x.id !== id);
      return { status: 204 };
    }
    if (method === 'GET' && path === '/v1/llm-keys') return { status: 200, body: this.keys };
    if (method === 'GET' && path === '/v1/ai/settings') return { status: 200, body: settings.AI_SETTINGS };
    const key = /^\/v1\/llm-keys\/(anthropic|openai)$/.exec(path);
    if (key) {
      const provider = key[1] ?? '';
      if (method === 'PUT') {
        // The provider refuses any key but the person's own (the fixtures' check).
        if (provider === 'openai') return { status: 400, body: settings.KEY_REFUSED };
        const given = String(body().key ?? '');
        this.keys = { ...this.keys, keys: [...this.keys.keys.filter((k) => k.provider !== provider), { provider, last4: given.slice(-4), validated_at: '2026-10-11T10:00:00+00:00', readable: true }] };
        return { status: 204 };
      }
      if (method === 'DELETE') {
        if (!this.keys.keys.some((k) => k.provider === provider)) return { status: 404, body: { ...NOT_FOUND, detail: 'No key stored' } };
        this.keys = { ...this.keys, keys: this.keys.keys.filter((k) => k.provider !== provider) };
        return { status: 204 };
      }
    }
    if (method === 'GET' && path === '/v1/mcp/connections/enabled') return { status: 200, body: { enabled: this.mcpEnabled } };
    if (method === 'PUT' && path === '/v1/mcp/connections/enabled') {
      this.mcpEnabled = Boolean(body().enabled);
      return { status: 204 };
    }
    if (method === 'GET' && path === '/v1/mcp/connections/') return { status: 200, body: { connections: this.connections } };
    const connection = /^\/v1\/mcp\/connections\/([^/]+)$/.exec(path);
    if (method === 'DELETE' && connection) {
      const id = decodeURIComponent(connection[1] ?? '');
      if (!this.connections.some((c) => c.token_id === id)) return { status: 404, body: { ...NOT_FOUND, detail: 'connection not found' } };
      this.connections = this.connections.filter((c) => c.token_id !== id);
      return { status: 204 };
    }
    if (method === 'GET' && path === '/v1/notifications/preferences') return { status: 200, body: this.preferences };
    if (method === 'PATCH' && path === '/v1/notifications/preferences') {
      const changes = body() as Partial<NotificationPreferences>;
      this.preferences = changes.cadence === 'monthly' ? { ...clone(settings.PREFERENCES_SAVED), ...changes } : { ...this.preferences, ...changes };
      return { status: 200, body: this.preferences };
    }
    if (method === 'GET' && path === '/v1/notifications/preview') return { status: 200, body: settings.PREVIEW };
    if (method === 'GET' && path === '/v1/notifications/deliveries') return { status: 200, body: settings.DELIVERIES };
    if (method === 'GET' && path === '/v1/export/beancount') return { status: 200, text: settings.BEANCOUNT };
    if (method === 'GET' && path === '/v1/export/hledger') return { status: 200, text: settings.HLEDGER };
    if (method === 'GET' && path === '/v1/onboarding/export') return { status: 200, body: MY_DATA };
    return undefined;
  }
}
