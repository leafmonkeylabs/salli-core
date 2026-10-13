/**
 * The decision lab's part of the fixture server (MockApi): its reads answer
 * what the real server answered on the golden household (lab.ts), and its
 * writes answer what the server answered to the same writes, keeping what
 * they change (a principle added, a decision recorded, a note, a review) so
 * a page reads it back. The answers to a start are by template.
 */
import type { Decision, DecisionSummary, DueReviews, Principle } from '@leafmonkeylabs/salli-sdk';
import type { Answer, Recorded } from './api';
import { REVIEWS_DUE } from './home';
import * as lab from './lab';

const TEMPLATES: Record<string, unknown> = {
  'afford-it': lab.AFFORD_IT,
  'debt-or-invest': lab.DEBT_OR_INVEST,
  windfall: lab.WINDFALL,
  'big-change': lab.BIG_CHANGE,
  borrow: lab.BORROW,
  'emergency-fund': lab.EMERGENCY_FUND,
  'rent-or-buy': lab.RENT_OR_BUY,
};

const STARTS: Record<string, unknown> = {
  'afford-it': lab.AFFORD_IT_START,
  'emergency-fund': lab.EMERGENCY_FUND_START,
  'rent-or-buy': lab.RENT_OR_BUY_START,
};

/** The reads that take no state, by path. */
export const LAB_READS: Record<string, unknown> = {
  '/v1/baseline': lab.BASELINE,
  '/v1/accounts/': lab.ACCOUNTS,
  '/v1/debt/': lab.DEBTS,
  '/v1/portfolio/': lab.HOLDINGS,
  '/v1/insights/recurring': lab.RECURRING,
  '/v1/decisions/templates': lab.TEMPLATES,
  '/v1/principles/figures': lab.FIGURES,
};

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function summary(decision: Decision): DecisionSummary {
  const e = decision.entry;
  return {
    id: decision.id,
    question: e.question,
    chosen: e.chosen,
    currency: e.currency,
    as_of: e.as_of,
    review_on: e.review_on,
    recorded_at: e.recorded_at,
    hash: decision.hash,
    notes: decision.notes.length,
    reviews: decision.reviews.length,
    last_reviewed_at: decision.reviews[decision.reviews.length - 1]?.review.at ?? null,
    status: decision.status,
  };
}

export class LabState {
  principles: Principle[] = clone(lab.PRINCIPLES.principles);
  decisions: Record<string, Decision> = { [lab.DECISION.id]: clone(lab.DECISION), [lab.DECISION_DUE.id]: clone(lab.DECISION_DUE) };
  /** The journal's order: newest first, as the server lists it. */
  order: string[] = lab.DECISIONS.decisions.map((d) => d.id);
  due: DueReviews = clone(REVIEWS_DUE);

  /** Starts without the laptop recorded, so a test can record it. */
  withoutLaptop(): this {
    delete this.decisions[lab.DECISION.id];
    this.order = this.order.filter((id) => id !== lab.DECISION.id);
    return this;
  }

  answer(request: Recorded): Answer | undefined {
    const { method, path } = request;
    const body = (): Record<string, unknown> => (request.body ? (JSON.parse(request.body) as Record<string, unknown>) : {});
    if (method === 'GET' && path in LAB_READS) return { status: 200, body: LAB_READS[path] };
    const template = /^\/v1\/decisions\/templates\/([^/]+)$/.exec(path);
    if (method === 'GET' && template) {
      const found = TEMPLATES[decodeURIComponent(template[1] ?? '')];
      return found ? { status: 200, body: found } : undefined;
    }
    if (method === 'POST' && path === '/v1/decisions/start') {
      const id = String(body().template ?? '');
      const found = STARTS[id];
      return found ? { status: 200, body: found } : { status: 422, body: lab.START_REFUSED };
    }
    if (method === 'POST' && path === '/v1/scenarios/run') return { status: 200, body: lab.SCENARIO_RUN };
    if (method === 'POST' && path === '/v1/scenarios/compare') return { status: 200, body: lab.SCENARIO_COMPARISON };
    if (method === 'POST' && path === '/v1/principles/check') {
      const options = (body().options as unknown[] | undefined) ?? [];
      return { status: 200, body: options.length ? lab.PRINCIPLE_CHECK : lab.BASELINE_CHECK };
    }
    if (method === 'GET' && path === '/v1/principles') {
      const all = /include_archived=true/.test(request.search);
      return { status: 200, body: { principles: this.principles.filter((p) => all || p.status === 'active') } };
    }
    if (method === 'POST' && path === '/v1/principles') {
      const added = { ...clone(lab.PRINCIPLE_ADDED), ...pick(body(), ['label', 'check', 'account', 'note']) };
      this.principles.push(added);
      return { status: 201, body: added };
    }
    const principle = /^\/v1\/principles\/([^/]+)(\/archive)?$/.exec(path);
    if (principle) {
      const id = decodeURIComponent(principle[1] ?? '');
      const found = this.principles.find((p) => p.id === id);
      if (!found) return { status: 404, body: { type: 'about:blank', title: 'Not Found', status: 404 } };
      if (method === 'PATCH' && !principle[2]) {
        Object.assign(found, pick(body(), ['label', 'check', 'account', 'note']), { version: found.version + 1 });
        return { status: 200, body: found };
      }
      if (method === 'POST' && principle[2]) {
        Object.assign(found, { status: 'archived', archived_at: lab.PRINCIPLE_EDITED.updated_at });
        return { status: 200, body: found };
      }
    }
    if (method === 'GET' && path === '/v1/decisions') return { status: 200, body: { decisions: this.order.flatMap((id) => (this.decisions[id] ? [summary(this.decisions[id])] : [])) } };
    if (method === 'GET' && path === '/v1/decisions/reviews') return { status: 200, body: this.due };
    if (method === 'GET' && path === '/v1/decisions/export') return { status: 200, body: lab.JOURNAL };
    if (method === 'GET' && path === '/v1/decisions/export/markdown') return { status: 200, text: lab.JOURNAL_MARKDOWN, headers: { 'content-type': 'text/markdown; charset=utf-8' } };
    if (method === 'POST' && path === '/v1/decisions') {
      const recorded = clone(lab.RECORDED);
      recorded.entry.question = String(body().question ?? recorded.entry.question);
      this.decisions[recorded.id] = recorded;
      if (!this.order.includes(recorded.id)) this.order.unshift(recorded.id);
      return { status: 201, body: recorded };
    }
    const decision = /^\/v1\/decisions\/([^/]+)(\/notes|\/review|\/markdown)?$/.exec(path);
    if (decision) {
      const id = decodeURIComponent(decision[1] ?? '');
      const found = this.decisions[id];
      if (!found) return { status: 404, body: { type: '/problems/not-found', title: 'Not found', status: 404, detail: `No decision ${id}` } };
      if (method === 'GET' && !decision[2]) return { status: 200, body: found };
      if (method === 'GET' && decision[2] === '/markdown') return { status: 200, text: lab.JOURNAL_MARKDOWN, headers: { 'content-type': 'text/markdown; charset=utf-8' } };
      if (method === 'POST' && decision[2] === '/notes') {
        const note = clone(lab.NOTE);
        note.note.text = String(body().text ?? note.note.text);
        note.note.decision_id = id;
        found.notes.push(note);
        return { status: 201, body: note };
      }
      if (method === 'POST' && decision[2] === '/review') {
        const reviewed = clone(lab.REVIEWED);
        reviewed.review.reflection = String(body().reflection ?? reviewed.review.reflection);
        found.reviews.push(reviewed);
        found.status = 'reviewed';
        this.due = { ...this.due, reviews: this.due.reviews.filter((r) => r.id !== id) };
        return { status: 201, body: reviewed };
      }
    }
    return undefined;
  }
}

function pick(source: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  return Object.fromEntries(keys.filter((k) => k in source).map((k) => [k, source[k]]));
}
