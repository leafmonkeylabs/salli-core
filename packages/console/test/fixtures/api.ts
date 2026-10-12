/**
 * A Salli server made of fixtures, for the component tests (as a `fetch`)
 * and the visual and accessibility runs (behind Playwright's `page.route`).
 * Home's reads answer what the real server answers on the golden household
 * (home.ts), the decision lab's (lab-api.ts) and where you stand's
 * (where-api.ts) likewise; the sign-in answers as Salli's OAuth endpoints do.
 */
import type { NotificationPreferences, Profile } from '@leafmonkeylabs/salli-sdk';
import { ME, metaAt, ORIGIN, PROFILE, SIGN_INS } from './auth';
import * as home from './home';
import { LabState } from './lab-api';
import { WhereState } from './where-api';

export interface Answer {
  status: number;
  body?: unknown;
  /** A body that is text, not JSON (Markdown). */
  text?: string;
  headers?: Record<string, string>;
}

export interface Recorded {
  method: string;
  path: string;
  search: string;
  body: string;
  authorization: string | null;
}

type Override = (request: Recorded) => Answer | undefined;

export const PREFERENCES: NotificationPreferences = {
  enabled: false,
  cadence: 'weekly',
  weekday: 'monday',
  hour: 8,
  items: ['decision_review_due', 'reminder_due', 'filing_deadline', 'cash_below_zero_ahead'],
  time_zone: 'Europe/Lisbon',
  next_at: null,
  sender_enabled: false,
};

/**
 * The reads Home makes, by path, but its reminders: those are where you
 * stand's (where-api.ts), which answers Home's `?status=pending` with the
 * same three and Attention with the one done as well.
 */
export const HOME_READS: Record<string, unknown> = {
  '/v1/reports/balance-sheet': home.BALANCE_SHEET,
  '/v1/ledger/income-statement': home.INCOME_STATEMENT,
  '/v1/fi/score': home.FI_SCORE,
  '/v1/insights/safe-to-spend': home.SAFE_TO_SPEND,
  '/v1/insights/signals': home.SIGNALS,
  '/v1/decisions/reviews': home.REVIEWS_DUE,
  '/v1/insights/net-worth': home.NET_WORTH,
};

export class MockApi {
  /** The server's public URL (SALLI_PUBLIC_URL), which /v1/meta names. */
  readonly origin: string;
  requests: Recorded[] = [];
  overrides: Override[] = [];
  extensions: string[] = [];
  me = ME;
  profile: Profile = { ...PROFILE };
  signIns = [...SIGN_INS];
  reads: Record<string, unknown> = { ...HOME_READS };
  /** The decision lab's reads and writes (lab-api.ts). */
  lab = new LabState();
  /** Where you stand's reads and writes (where-api.ts): the books, cash, attention, FI. */
  where = new WhereState();
  issued = 0;

  constructor(origin: string = ORIGIN) {
    this.origin = origin;
  }

  /** Answers one request, or undefined for a path it doesn't know. */
  answer(request: Recorded): Answer | undefined {
    this.requests.push(request);
    for (const override of this.overrides) {
      const answer = override(request);
      if (answer) return answer;
    }
    const { method, path } = request;
    if (method === 'GET' && path === '/v1/meta') return { status: 200, body: metaAt(this.origin, this.extensions) };
    if (method === 'POST' && path === '/mcp/oauth/token') {
      this.issued += 1;
      return {
        status: 200,
        body: { access_token: `at-${this.issued}`, token_type: 'Bearer', expires_in: 3600, refresh_token: `rt-${this.issued}`, scope: '' },
      };
    }
    if (method === 'POST' && path === '/mcp/oauth/revoke') return { status: 200, body: {} };
    if (!request.authorization) return { status: 401, body: problem(401, 'Not signed in') };
    if (method === 'GET' && path === '/v1/auth/me') return { status: 200, body: this.me };
    if (method === 'GET' && path in this.reads) return { status: 200, body: this.reads[path] };
    const stands = this.where.answer(request);
    // An assumption set changes the FI score, which Home reads too.
    if (stands && method === 'PATCH' && path === '/v1/fi/assumptions' && stands.status === 200) this.reads['/v1/fi/score'] = this.where.score;
    if (stands) return stands;
    if (method === 'GET' && path === '/v1/onboarding/profile') return { status: 200, body: this.profile };
    if (method === 'PATCH' && path === '/v1/onboarding/profile') {
      this.profile = { ...this.profile, ...(JSON.parse(request.body) as Partial<Profile>) };
      return { status: 200, body: this.profile };
    }
    if (method === 'PATCH' && path === '/v1/notifications/preferences') {
      const changes = JSON.parse(request.body) as { time_zone?: string };
      if (changes.time_zone) this.profile = { ...this.profile, time_zone: changes.time_zone };
      return { status: 200, body: { ...PREFERENCES, ...changes } };
    }
    if (method === 'GET' && path === '/v1/auth/sign-ins') return { status: 200, body: this.signIns };
    const revoke = /^\/v1\/auth\/sign-ins\/([^/]+)$/.exec(path);
    if (method === 'DELETE' && revoke) {
      this.signIns = this.signIns.filter((s) => s.id !== decodeURIComponent(revoke[1] ?? ''));
      return { status: 204 };
    }
    const answered = this.lab.answer(request);
    // A review changes what is due, which Home reads too.
    if (answered && method === 'POST' && /\/review$/.test(path)) this.reads['/v1/decisions/reviews'] = this.lab.due;
    return answered;
  }

  /** The requests to `path`. */
  to(path: string, method?: string): Recorded[] {
    return this.requests.filter((r) => r.path === path && (!method || r.method === method));
  }

  /** As a `fetch`, for the component tests. */
  fetch = async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    const body = request.method === 'GET' || request.method === 'HEAD' ? '' : await request.text();
    const recorded: Recorded = {
      method: request.method,
      path: url.pathname,
      search: url.search,
      body,
      authorization: request.headers.get('authorization'),
    };
    const answer = this.answer(recorded) ?? { status: 404, body: problem(404, 'Not Found') };
    if (answer.text !== undefined) return new Response(answer.text, { status: answer.status, headers: { 'content-type': 'text/plain', ...answer.headers } });
    const json = answer.body !== undefined && answer.status !== 204;
    const isProblem = answer.status >= 400 && json && typeof answer.body === 'object' && answer.body !== null && 'type' in answer.body;
    return new Response(json ? JSON.stringify(answer.body) : null, {
      status: answer.status,
      headers: { 'content-type': isProblem ? 'application/problem+json' : 'application/json', ...answer.headers },
    });
  };
}

export function problem(status: number, title: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { type: status === 404 ? 'about:blank' : `/problems/${title.toLowerCase().replace(/\s+/g, '-')}`, title, status, detail: title, ...extra };
}

/** Salli's answer when the password must be entered again (RFC 9470), as main.py's handler writes it. */
export const STEP_UP = {
  status: 403,
  body: {
    type: '/problems/step-up-required',
    title: 'Sign in again',
    status: 403,
    detail: "tax:activate needs your password, entered in the last 5 minutes. Sign in again on Salli's sign-in page, then try again.",
    max_age: 300,
  },
  headers: {
    'www-authenticate': 'Bearer error="insufficient_user_authentication", error_description="Sign in again to continue", max_age=300',
  },
} satisfies Answer;
