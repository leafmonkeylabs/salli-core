/**
 * A template's answers, from what the person typed to what the API takes
 * (docs/templates.md, "Questions and defaults"): each question's type says
 * how its text is read, and each answer the form can't read is an error at
 * its path, as the server's are (`price`, `mortgages[0].annual_rate`). What
 * is left empty is left out, so the server's default applies and says
 * where it came from. Nothing here computes: amounts and rates stay text.
 */
import type { DecisionTemplate, TemplateQuestion } from '@leafmonkeylabs/salli-sdk';
import { dateInput, nonNegativeAmountInput, positiveAmountInput, rateInput, signedAmountInput, wholeNumberInput } from '../../kit/inputs';
import { labStrings } from '../../lab-strings';

const t = labStrings.templates;

export interface LoanState {
  rate: string;
  term: string;
  label: string;
}

export interface SplitState {
  label: string;
  debts: Record<string, string>;
  invest: string;
}

export type AnswerState = string | string[] | LoanState[] | SplitState[];
export type FormState = Record<string, AnswerState>;
/** Errors by path: `price`, `set_aside[1]`, `mortgages[0].annual_rate`. */
export type Errors = Record<string, string>;

export const LIST_TYPES = new Set(['amounts', 'loans', 'splits']);

export function emptyLoan(): LoanState {
  return { rate: '', term: '', label: '' };
}

export function emptySplit(): SplitState {
  return { label: '', debts: {}, invest: '' };
}

/** The form's starting state: lists at their least, everything else empty. */
export function initialState(template: DecisionTemplate): FormState {
  const state: FormState = {};
  for (const q of template.questions) {
    const least = Math.max(1, q.min_items ?? 1);
    if (q.type === 'amounts') state[q.id] = Array.from({ length: least }, () => '');
    else if (q.type === 'loans') state[q.id] = Array.from({ length: least }, emptyLoan);
    else if (q.type === 'splits') state[q.id] = Array.from({ length: least }, emptySplit);
    else state[q.id] = '';
  }
  return state;
}

/** Whether a question is asked, given what is answered so far (or, unanswered, its default). */
export function applies(q: TemplateQuestion, state: FormState, template: DecisionTemplate): boolean {
  if (!q.when) return true;
  const given = state[q.when.question];
  const other = template.questions.find((x) => x.id === q.when?.question);
  const value = typeof given === 'string' && given.trim() ? given.trim() : other?.default?.value;
  if (value === undefined || value === null || value === '') return false;
  return q.when.equals === null || value === q.when.equals;
}

/** The ids a question takes, as the answers' schema lists them (your own accounts, debts, roles). */
export function allowed(template: DecisionTemplate, path: string[]): string[] | undefined {
  let node: unknown = template.answers_schema;
  for (const key of path) {
    if (typeof node !== 'object' || node === null) return undefined;
    const record = node as Record<string, unknown>;
    node = key === '[]' ? record.items : (record.properties as Record<string, unknown> | undefined)?.[key];
  }
  const values = (node as { enum?: unknown } | undefined)?.enum;
  return Array.isArray(values) ? values.filter((v): v is string => typeof v === 'string') : undefined;
}

/** One answer typed as text, in the form the API takes: the value, or why it can't be read. */
export function readText(q: TemplateQuestion, text: string, locale: string | undefined): { value?: unknown; error?: string } {
  const value = text.trim();
  switch (q.type) {
    case 'amount': {
      const v = positiveAmountInput(value, locale);
      return v === undefined ? { error: t.notAPositiveAmount } : { value: v };
    }
    case 'amount_or_zero':
    case 'number': {
      const v = nonNegativeAmountInput(value, locale);
      return v === undefined ? { error: t.notAnAmount } : { value: v };
    }
    case 'signed_amount': {
      const v = signedAmountInput(value, locale);
      return v === undefined ? { error: t.notASignedAmount } : { value: v };
    }
    case 'rate':
    case 'growth': {
      const v = rateInput(value, locale);
      return v === undefined ? { error: t.notARate } : { value: v };
    }
    case 'months':
    case 'years': {
      const v = wholeNumberInput(value);
      return v === undefined ? { error: t.notAWholeNumber } : { value: v };
    }
    case 'date': {
      const v = dateInput(value);
      return v === undefined ? { error: t.notADate } : { value: v };
    }
    default:
      return { value };
  }
}

/**
 * The answers to send, and every problem the form found, by path. A
 * question left empty is left out; a required one with no default is an
 * error, as the server would say.
 */
export function collect(template: DecisionTemplate, state: FormState, locale: string | undefined): { answers: Record<string, unknown>; errors: Errors } {
  const answers: Record<string, unknown> = {};
  const errors: Errors = {};
  for (const q of template.questions) {
    if (!applies(q, state, template)) continue;
    const raw = state[q.id];
    const needed = q.required && q.default === null;
    if (q.type === 'amounts') {
      const items = ((raw as string[] | undefined) ?? []).map((v) => v.trim());
      const values: string[] = [];
      items.forEach((item, i) => {
        if (!item) return;
        const v = nonNegativeAmountInput(item, locale);
        if (v === undefined || /^0*(\.0*)?$/.test(v)) errors[`${q.id}[${i}]`] = t.notAPositiveAmount;
        else values.push(v);
      });
      if (values.length) answers[q.id] = values;
      else if (needed) errors[q.id] = t.needed;
      continue;
    }
    if (q.type === 'loans') {
      const loans = (raw as LoanState[] | undefined) ?? [];
      const out: Array<Record<string, unknown>> = [];
      loans.forEach((loan, i) => {
        if (!loan.rate.trim() && !loan.term.trim() && !loan.label.trim()) return;
        const rate = rateInput(loan.rate, locale);
        const term = wholeNumberInput(loan.term);
        if (rate === undefined) errors[`${q.id}[${i}].annual_rate`] = t.notARate;
        if (term === undefined) errors[`${q.id}[${i}].term_months`] = t.notAWholeNumber;
        if (rate !== undefined && term !== undefined) out.push({ annual_rate: rate, term_months: term, ...(loan.label.trim() ? { label: loan.label.trim() } : {}) });
      });
      if (out.length) answers[q.id] = out;
      else if (needed && !Object.keys(errors).some((k) => k.startsWith(`${q.id}[`))) errors[q.id] = t.needed;
      continue;
    }
    if (q.type === 'splits') {
      const splits = (raw as SplitState[] | undefined) ?? [];
      const out: Array<Record<string, unknown>> = [];
      splits.forEach((split, i) => {
        const debts: Array<{ debt: string; amount: string }> = [];
        for (const [debt, text] of Object.entries(split.debts)) {
          if (!text.trim()) continue;
          const v = positiveAmountInput(text, locale);
          if (v === undefined) errors[`${q.id}[${i}].debts.${debt}`] = t.notAPositiveAmount;
          else debts.push({ debt, amount: v });
        }
        let invest: string | undefined;
        if (split.invest.trim()) {
          invest = positiveAmountInput(split.invest, locale);
          if (invest === undefined) errors[`${q.id}[${i}].invest`] = t.notAPositiveAmount;
        }
        if (!split.label.trim()) {
          if (debts.length || invest) errors[`${q.id}[${i}].label`] = t.needed;
          return;
        }
        out.push({ label: split.label.trim(), debts, ...(invest ? { invest } : {}) });
      });
      if (out.length) answers[q.id] = out;
      const least = q.min_items ?? 1;
      if (out.length < least && (needed || out.length)) errors[q.id] = t.tooFew(least);
      continue;
    }
    const text = typeof raw === 'string' ? raw : '';
    if (!text.trim()) {
      if (needed) errors[q.id] = t.needed;
      continue;
    }
    const read = readText(q, text, locale);
    if (read.error) errors[q.id] = read.error;
    else answers[q.id] = read.value;
  }
  return { answers, errors };
}

/** Salli's problems at their paths in the answers: `["body", "answers", "mortgages", 0, "annual_rate"]` → `mortgages[0].annual_rate`. */
export function answerPath(loc: ReadonlyArray<string | number>): string | undefined {
  const parts = loc[0] === 'body' ? loc.slice(1) : loc;
  if (parts[0] !== 'answers' || parts.length < 2) return undefined;
  return parts
    .slice(1)
    .map((part, i) => (typeof part === 'number' ? `[${part}]` : i === 0 ? part : `.${part}`))
    .join('');
}
