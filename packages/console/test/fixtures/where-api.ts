/**
 * Where you stand's part of the fixture server (MockApi): its reads answer
 * what the real server answered on the golden household (where.ts), and its
 * writes answer what the server answered to the same writes, keeping what
 * they change (lunch posted, then reversed; an assumption set; a reminder
 * done or deleted) so a page reads it back. Only the lunch the fixtures
 * posted can be posted here; a post in dollars answers the dollars entry,
 * one in pounds the server's refusal for want of a rate.
 */
import type {
  AccountOverview,
  CashFlow,
  FiAssumptionsReport,
  FiProjections,
  FiScore,
  JournalEntry,
  Reminder,
  TrialBalance,
} from '@leafmonkeylabs/salli-sdk';
import type { Answer, Recorded } from './api';
import * as home from './home';
import * as where from './where';

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

const NOT_FOUND = { type: '/problems/not-found', title: 'Not found', status: 404, detail: 'Not found' };

export class WhereState {
  entries: JournalEntry[] = clone(where.ENTRIES);
  overviews: AccountOverview[] = clone(where.OVERVIEWS);
  trial: TrialBalance = clone(where.TRIAL_BALANCE);
  reminders: Reminder[] = clone(where.REMINDERS_ALL.reminders);
  score: FiScore = clone(home.FI_SCORE);
  assumptions: FiAssumptionsReport = clone(where.ASSUMPTIONS);
  projections: FiProjections = clone(where.PROJECTIONS);
  /** The cash-flow answer (a test may give one with no full month). */
  cashFlow: CashFlow = clone(where.CASH_FLOW);

  answer(request: Recorded): Answer | undefined {
    const { method, path, search } = request;
    const params = new URLSearchParams(search);
    const body = (): Record<string, unknown> => (request.body ? (JSON.parse(request.body) as Record<string, unknown>) : {});

    if (method === 'GET' && path === '/v1/ledger/trial-balance') return { status: 200, body: this.trial };
    const overview = /^\/v1\/accounts\/([^/]+)\/overview$/.exec(path);
    if (method === 'GET' && overview) {
      const id = decodeURIComponent(overview[1] ?? '');
      const found = this.overviews.find((o) => o.account.id === id);
      return found ? { status: 200, body: found } : { status: 404, body: { ...NOT_FOUND, detail: 'Account not found' } };
    }
    if (method === 'GET' && path === '/v1/entries/') {
      const from = params.get('from_date');
      const to = params.get('to_date');
      return { status: 200, body: this.entries.filter((e) => (!from || e.entry_date >= from) && (!to || e.entry_date <= to)) };
    }
    if (method === 'POST' && path === '/v1/entries/') return this.post(body());
    const entry = /^\/v1\/entries\/([^/]+)(\/provenance|\/reverse)?$/.exec(path);
    if (entry) {
      const id = decodeURIComponent(entry[1] ?? '');
      const found = this.entries.find((e) => e.id === id);
      if (method === 'POST' && entry[2] === '/reverse') return this.reverse(id);
      if (!found) return { status: 404, body: { ...NOT_FOUND, detail: 'Entry not found' } };
      if (method === 'GET' && !entry[2]) return { status: 200, body: found };
      if (method === 'GET' && entry[2] === '/provenance') {
        const provenance = [...where.PROVENANCES, where.LUNCH_PROVENANCE, where.REVERSAL_PROVENANCE].find((p) => p.entry_id === id);
        return provenance ? { status: 200, body: provenance } : { status: 404, body: NOT_FOUND };
      }
    }

    if (method === 'GET' && path === '/v1/insights/forecast') return { status: 200, body: where.FORECAST };
    if (method === 'GET' && path === '/v1/insights/cash-flow') return { status: 200, body: this.cashFlow };
    if (method === 'GET' && path === '/v1/insights/spending') return { status: 200, body: where.SPENDING };

    if (method === 'GET' && path === '/v1/reminders/') {
      const status = params.get('status');
      return { status: 200, body: { reminders: this.reminders.filter((r) => !status || r.status === status) } };
    }
    const reminder = /^\/v1\/reminders\/([^/]+?)(\/done)?$/.exec(path);
    if (reminder && (method === 'PATCH' || method === 'DELETE')) {
      const id = decodeURIComponent(reminder[1] ?? '');
      const found = this.reminders.find((r) => r.id === id);
      if (!found) return { status: 404, body: NOT_FOUND };
      if (method === 'PATCH' && reminder[2]) found.status = 'done';
      if (method === 'DELETE' && !reminder[2]) this.reminders = this.reminders.filter((r) => r.id !== id);
      return { status: 204 };
    }

    if (method === 'GET' && path === '/v1/fi/score') return { status: 200, body: this.score };
    if (method === 'GET' && path === '/v1/fi/assumptions') return { status: 200, body: this.assumptions };
    if (method === 'GET' && path === '/v1/fi/projections') return { status: 200, body: this.projections };
    if (method === 'GET' && path === '/v1/fi/score/history') return { status: 200, body: where.SCORE_HISTORY };
    if (method === 'PATCH' && path === '/v1/fi/assumptions') return this.assume(body());
    return undefined;
  }

  /** Lunch, the dollars, or the pounds Salli has no rate for: what the server answered to each. */
  private post(body: Record<string, unknown>): Answer {
    const postings = (body.postings as Array<{ currency?: string; fx_rate?: string }> | undefined) ?? [];
    const currency = postings[0]?.currency;
    if (currency === 'GBP' && !postings[0]?.fx_rate) return { status: 422, body: where.NO_RATE };
    if (currency === 'USD') {
      this.entries.push(clone(where.DOLLARS));
      return { status: 201, body: where.DOLLARS_POSTED };
    }
    const lunch = clone(where.LUNCH);
    lunch.description = String(body.description ?? lunch.description);
    this.entries.push(lunch);
    this.trial = clone(where.TRIAL_BALANCE_POSTED);
    this.replaceOverview(where.CHECKING_POSTED);
    return { status: 201, body: where.POSTED };
  }

  private reverse(id: string): Answer {
    const found = this.entries.find((e) => e.id === id);
    if (!found) return { status: 404, body: { ...NOT_FOUND, detail: `Entry ${id} not found` } };
    if (found.reversed_by) return { status: 400, body: where.REVERSE_REFUSED };
    if (id !== where.LUNCH.id) return { status: 404, body: { ...NOT_FOUND, detail: 'Only lunch can be reversed here' } };
    found.reversed_by = where.LUNCH_REVERSED.reversed_by;
    this.entries.push(clone(where.REVERSAL));
    this.trial = clone(where.TRIAL_BALANCE_REVERSED);
    this.replaceOverview(where.CHECKING_REVERSED);
    return { status: 201, body: where.REVERSED };
  }

  private replaceOverview(next: AccountOverview): void {
    this.overviews = this.overviews.map((o) => (o.account.id === next.account.id ? clone(next) : o));
  }

  /** The real return set (or a refused rate), or every one cleared back to the household's own. */
  private assume(body: Record<string, unknown>): Answer {
    const real = body.real_return as { value?: string } | null | undefined;
    if (real && real.value === '0.6') return { status: 422, body: where.ASSUMPTION_REFUSED };
    if (Object.values(body).every((v) => v === null)) {
      this.assumptions = clone(where.ASSUMPTIONS);
      this.score = clone(home.FI_SCORE);
      this.projections = clone(where.PROJECTIONS);
      return { status: 200, body: this.assumptions };
    }
    this.assumptions = clone(where.ASSUMPTION_SET);
    this.score = clone(where.FI_SCORE_SET);
    this.projections = clone(where.PROJECTIONS_SET);
    return { status: 200, body: this.assumptions };
  }
}
