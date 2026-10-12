/**
 * A scenario's changes as forms (docs/scenarios.md, "Changes"): each
 * `salli.scenario/1` change type and its fields, what each field takes, and
 * reading what the person typed into the document the API runs. Amounts
 * and rates stay text; a problem is kept at its path, as Salli's are.
 */
import type { Scenario } from '@leafmonkeylabs/salli-sdk';
import {
  dateInput,
  nonNegativeAmountInput,
  positiveAmountInput,
  rateInput,
  signedAmountInput,
  wholeNumberInput,
} from '../../kit/inputs';
import { labStrings } from '../../lab-strings';

export type ChangeType = NonNullable<Scenario['changes']>[number]['type'];

export type FieldKind = 'signed' | 'positive' | 'fees' | 'date' | 'rate' | 'growth' | 'whole' | 'account' | 'debt' | 'holding' | 'recurring' | 'cadence' | 'text' | 'role';

export interface FieldSpec {
  key: string;
  kind: FieldKind;
  required: boolean;
  /** The label's key in the catalogue, when it isn't the field's own. */
  label?: string;
}

const req = (key: string, kind: FieldKind, label?: string): FieldSpec => ({ key, kind, required: true, ...(label ? { label } : {}) });
const opt = (key: string, kind: FieldKind, label?: string): FieldSpec => ({ key, kind, required: false, ...(label ? { label } : {}) });

/** Each change type's fields, in the order the form asks them. */
export const CHANGE_FIELDS: Record<ChangeType, FieldSpec[]> = {
  one_off: [req('label', 'text'), req('date', 'date'), req('amount', 'signed', 'amountSigned'), opt('account', 'account'), opt('tax_role', 'role')],
  recurring: [
    req('label', 'text'),
    req('amount', 'signed', 'amountSigned'),
    req('cadence', 'cadence'),
    req('start', 'date'),
    opt('end', 'date'),
    opt('account', 'account'),
    opt('real_growth', 'growth'),
    opt('tax_role', 'role'),
  ],
  income_change: [req('label', 'text'), req('monthly', 'signed', 'monthlySigned'), req('from', 'date'), opt('to', 'date'), opt('tax_role', 'role')],
  loan: [req('label', 'text'), req('principal', 'positive'), req('annual_rate', 'rate'), req('term_months', 'whole'), req('start', 'date'), opt('into', 'account')],
  extra_debt_payment: [req('debt', 'debt'), req('monthly', 'positive'), req('from', 'date'), opt('to', 'date'), opt('label', 'text')],
  invest: [req('label', 'text'), req('amount', 'positive'), req('date', 'date'), opt('from', 'account', 'account'), opt('holding', 'holding'), opt('fees', 'fees')],
  sell: [
    req('holding', 'holding'),
    opt('quantity', 'positive'),
    opt('amount', 'positive', 'sellAmount'),
    req('date', 'date'),
    opt('fees', 'fees'),
    opt('into', 'account'),
    opt('tax_role', 'role'),
    opt('label', 'text'),
  ],
  stop_recurring: [req('key', 'recurring'), req('from', 'date'), opt('label', 'text')],
  set_aside: [req('monthly', 'positive'), req('from', 'date'), opt('to', 'date'), opt('label', 'text')],
  asset: [req('label', 'text'), req('price', 'positive'), req('date', 'date'), opt('from', 'account', 'account'), opt('real_growth', 'growth'), opt('selling_costs', 'rate')],
};

export const CHANGE_TYPES = Object.keys(CHANGE_FIELDS) as ChangeType[];

export interface ChangeState {
  id: number;
  type: ChangeType;
  values: Record<string, string>;
}

export interface OptionState {
  id: number;
  label: string;
  changes: ChangeState[];
  /** A document the person loaded, run as written instead of the changes. */
  document?: Record<string, unknown>;
}

const t = labStrings.templates;

/** One field's text, as the API takes it, or why it can't be read. */
export function readField(kind: FieldKind, text: string, locale: string | undefined): { value?: unknown; error?: string } {
  const value = text.trim();
  switch (kind) {
    case 'signed': {
      const v = signedAmountInput(value, locale);
      return v === undefined ? { error: t.notASignedAmount } : { value: v };
    }
    case 'positive': {
      const v = positiveAmountInput(value, locale);
      return v === undefined ? { error: t.notAPositiveAmount } : { value: v };
    }
    case 'fees': {
      const v = nonNegativeAmountInput(value, locale);
      return v === undefined ? { error: t.notAnAmount } : { value: v };
    }
    case 'rate':
    case 'growth': {
      const v = rateInput(value, locale);
      return v === undefined ? { error: t.notARate } : { value: v };
    }
    case 'whole': {
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

/** Problems, by path: `0.label`, `1.changes.2.amount`, `horizon_years`. */
export type ScenarioErrors = Record<string, string>;

/** An option's document, and every problem the form found in it. */
export function buildOption(
  option: OptionState,
  index: number,
  shared: { horizon: number | undefined; asOf: string | undefined },
  locale: string | undefined,
): { doc: Scenario; errors: ScenarioErrors } {
  const errors: ScenarioErrors = {};
  if (option.document) {
    const doc = { ...option.document } as Record<string, unknown>;
    if (option.label.trim()) doc.label = option.label.trim();
    return { doc: doc as unknown as Scenario, errors };
  }
  const changes = option.changes.map((change, j) => {
    const out: Record<string, unknown> = { type: change.type };
    for (const spec of CHANGE_FIELDS[change.type]) {
      const text = change.values[spec.key] ?? '';
      const path = `${index}.changes.${j}.${spec.key}`;
      if (!text.trim()) {
        if (spec.required) errors[path] = t.needed;
        continue;
      }
      const read = readField(spec.kind, text, locale);
      if (read.error) errors[path] = read.error;
      else out[spec.key] = read.value;
    }
    if (change.type === 'sell' && !out.quantity && !out.amount && !errors[`${index}.changes.${j}.quantity`]) {
      errors[`${index}.changes.${j}.quantity`] = labStrings.scenarios.oneOfQuantity;
    }
    return out;
  });
  const doc = {
    schema: 'salli.scenario/1',
    label: option.label.trim() || labStrings.scenarios.option(index + 1),
    ...(shared.horizon !== undefined ? { horizon_years: shared.horizon } : {}),
    ...(shared.asOf ? { as_of: shared.asOf } : {}),
    changes,
  };
  return { doc: doc as unknown as Scenario, errors };
}

/**
 * Salli's problems with a run or a comparison, at their place in the form:
 * `["body", "changes", 0, "one_off", "amount"]` (a run) or
 * `["body", "options", 1, "changes", 0, "amount"]` (a comparison).
 */
export function scenarioErrors(detail: unknown, compared: boolean): ScenarioErrors {
  const out: ScenarioErrors = {};
  if (!Array.isArray(detail)) return out;
  for (const item of detail as Array<{ loc?: unknown; msg?: unknown }>) {
    if (!Array.isArray(item.loc) || typeof item.msg !== 'string') continue;
    let loc = (item.loc as Array<string | number>).slice(item.loc[0] === 'body' ? 1 : 0);
    let option = 0;
    if (compared) {
      if (loc[0] !== 'options' || typeof loc[1] !== 'number') continue;
      option = loc[1];
      loc = loc.slice(2);
    }
    let key: string;
    if (loc[0] === 'changes' && typeof loc[1] === 'number') {
      const field = [...loc.slice(2)].reverse().find((p): p is string => typeof p === 'string' && !(CHANGE_TYPES as string[]).includes(p));
      key = `${option}.changes.${loc[1]}${field ? `.${field}` : ''}`;
    } else if (loc[0] === 'horizon_years' || loc[0] === 'as_of') {
      key = String(loc[0]);
    } else {
      key = `${option}.${loc.map(String).join('.')}`;
    }
    if (!(key in out)) out[key] = item.msg;
  }
  return out;
}
