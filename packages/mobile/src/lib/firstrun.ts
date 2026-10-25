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
}

/** Cash is what you spend from; investments grow; other (a home, a car) is neither. */
export type AssetRole = 'cash' | 'investment' | 'other';
export const ROLES: readonly AssetRole[] = ['cash', 'investment', 'other'];

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

/** Whether every line you own that would be sent says what kind it is. */
export function rolesGiven(own: readonly Line[]): boolean {
  return filled(own).every((l) => l.role !== undefined);
}

/** Opening balances: what you own from 1500, what you owe from 2500, ten apart. */
export function balancesOf(own: readonly Line[], owe: readonly Line[]) {
  return [
    ...filled(own).map((l, i) => ({ code: String(1500 + i * 10), name: l.name, type: 'asset' as const, amount: l.amount, ...(l.role ? { asset_role: l.role } : {}) })),
    ...filled(owe).map((l, i) => ({ code: String(2500 + i * 10), name: l.name, type: 'liability' as const, amount: l.amount })),
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
