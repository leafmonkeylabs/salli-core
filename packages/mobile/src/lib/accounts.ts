/**
 * Which accounts a picker offers, and in what order: a pure function of the
 * accounts, so it is tested apart from the sheet that draws it.
 */
import type { Account } from '@leafmonkeylabs/salli-sdk';

/** Every kind but equity, in the order "Your other accounts" lists them. */
const KINDS = ['expense', 'income', 'asset', 'liability'] as const;

type Offered = Pick<Account, 'id' | 'name' | 'code' | 'type' | 'is_active'>;

/**
 * The picker's groups: the likely kinds first, each under its own heading,
 * then every other kind but equity under `others` (when given). Narrowed by
 * `words` in the name or code; `except` left out; inactive accounts never.
 */
export function groupsOf<A extends Offered>(
  accounts: readonly A[],
  { likely, typeNames, others, except, words }: { likely: readonly string[]; typeNames: Readonly<Record<string, string>>; others?: string; except?: string | null; words?: string },
): { key: string; label: string; rows: A[] }[] {
  const needle = (words ?? '').trim().toLowerCase();
  const offered = accounts.filter(
    (a) => a.is_active && a.id !== except && a.type !== 'equity' && (!needle || a.name.toLowerCase().includes(needle) || a.code.toLowerCase().includes(needle)),
  );
  return [
    ...likely.map((type) => ({ key: type, label: typeNames[type] ?? type, rows: offered.filter((a) => a.type === type) })),
    ...(others !== undefined ? [{ key: 'others', label: others, rows: offered.filter((a) => !likely.includes(a.type) && (KINDS as readonly string[]).includes(a.type)) }] : []),
  ].filter((g) => g.rows.length);
}

