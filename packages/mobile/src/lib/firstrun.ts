/**
 * First run (designs 37 to 41): what the app sends for each step, as pure
 * functions of what was typed. Amounts stay strings; account codes are new
 * ones beside the starter chart's (1100, 1200, 3000, 4100–4600, 5000).
 */
import { normalizeAmountInput } from '@leafmonkeylabs/salli-sdk';

export interface Line {
  name: string;
  amount: string;
  /** For something you own: what kind of money it is. */
  role?: AssetRole;
  /** For something you owe, optional: its yearly rate as typed in percent ("21.9"), and its minimum payment a month. */
  rate?: string;
  minimum?: string;
}

/** Cash is what you spend from; savings you keep, never free to spend; investments grow; other (a home, a car) is none of these. */
export type AssetRole = 'cash' | 'savings' | 'investment' | 'other';
export const ROLES: readonly AssetRole[] = ['cash', 'savings', 'investment', 'other'];

/** A typed amount as a decimal string, or undefined when it isn't one (or is nothing). */
export function amountOf(typed: string): string | undefined {
  const exact = normalizeAmountInput(typed.trim());
  return exact && !/^-?0+(\.0+)?$/.test(exact) ? exact : undefined;
}

/** The lines worth sending: named, with an amount. */
export function filled(lines: readonly Line[]): { name: string; amount: string; role?: AssetRole }[] {
  return lines.flatMap((l) => {
    const amount = amountOf(l.amount);
    return l.name.trim() && amount ? [{ name: l.name.trim(), amount, ...(l.role ? { role: l.role } : {}) }] : [];
  });
}

/** What you owe worth sending: named, with an amount, and a rate and minimum where they read. */
function owedOf(owe: readonly Line[]) {
  return owe.flatMap((l) => {
    const amount = amountOf(l.amount);
    if (!l.name.trim() || !amount) return [];
    const rate = l.rate?.trim() ? fractionOf(l.rate) : undefined;
    const minimum = l.minimum?.trim() ? amountOf(l.minimum) : undefined;
    return [{ name: l.name.trim(), amount, ...(rate ? { rate } : {}), ...(minimum ? { minimum_payment: minimum } : {}) }];
  });
}

/** Whether every line you own that would be sent says what kind it is. */
export function rolesGiven(own: readonly Line[]): boolean {
  return filled(own).every((l) => l.role !== undefined);
}

/** A rate typed in percent ("21.9", "6.4%") as the fraction the server takes ("0.219"), by moving the point: no arithmetic. */
export function fractionOf(percent: string): string | undefined {
  const exact = normalizeAmountInput(percent.trim().replace(/%$/, '').trim());
  if (!exact || exact.startsWith('-')) return undefined;
  const [whole = '0', part = ''] = exact.split('.');
  const digits = whole.padStart(3, '0') + part;
  const fraction = `${digits.slice(0, -2 - part.length)}.${digits.slice(-2 - part.length)}`.replace(/^0+(?=\d)/, '').replace(/\.?0+$/, '');
  return fraction === '' || fraction === '0' ? '0' : fraction;
}

/** Opening balances: what you own from 1500, what you owe from 2500, ten apart; owed ones with their rate and minimum when given. */
export function balancesOf(own: readonly Line[], owe: readonly Line[]) {
  return [
    ...filled(own).map((l, i) => ({ code: String(1500 + i * 10), name: l.name, type: 'asset' as const, amount: l.amount, ...(l.role ? { asset_role: l.role } : {}) })),
    ...owedOf(owe).map((l, i) => ({ code: String(2500 + i * 10), type: 'liability' as const, ...l })),
  ];
}

/**
 * Income sources from 4700, by name only: nothing is booked until you are
 * paid. Paid into the first cash account you own (or the starter bank account).
 */
export function incomesOf(incomes: readonly Line[], own: readonly Line[]) {
  const owned = filled(own);
  const at = owned.findIndex((l) => l.role === 'cash');
  const into = owned[at];
  return incomes
    .map((l) => l.name.trim())
    .filter(Boolean)
    .map((name, i) => ({
      code: String(4700 + i * 10),
      name,
      ...(into ? { deposit_account_code: String(1500 + at * 10), deposit_account_name: into.name } : {}),
    }));
}

/** Goals with a name; an amount and a date when given. */
export function goalsOf(goals: readonly (Line & { date: string })[]) {
  return goals.flatMap((g) => {
    if (!g.name.trim()) return [];
    const amount = amountOf(g.amount);
    const date = /^\d{4}-\d{2}-\d{2}$/.test(g.date.trim()) ? g.date.trim() : /^\d{4}$/.test(g.date.trim()) ? `${g.date.trim()}-12-31` : undefined;
    return [{ name: g.name.trim(), ...(amount ? { target_amount: amount } : {}), ...(date ? { target_date: date } : {}) }];
  });
}

export const HORIZONS = [
  { label: 'Under 3 years', years: 2 },
  { label: '3 to 10 years', years: 5 },
  { label: 'Over 10 years', years: 15 },
] as const;
export const DRAWDOWNS = ['sell_all', 'sell_some', 'hold', 'buy_more'] as const;
export const STABILITY = ['unstable', 'moderate', 'stable'] as const;
export const EXPERIENCE = ['none', 'some', 'experienced'] as const;
