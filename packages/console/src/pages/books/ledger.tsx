/**
 * What the books' pages share: the accounts by id (`accounts.list`), where
 * an account and an entry are, the books' own places, and an entry in one
 * line (its amount and from where to where), as `salli entries list` says
 * it. Nothing here computes: an entry's amount is its one debit's, as
 * posted; an entry of several parts says how many.
 */
import { accountsList, type Account, type JournalEntry, type Posting } from '@leafmonkeylabs/salli-sdk';
import { useMemo } from 'react';
import { useRead } from '../../api';
import { SubNav } from '../../kit/SubNav';
import { whereStrings } from '../../where-strings';

const b = whereStrings.books;

export const BOOKS_PLACES = [
  { to: '/books', label: b.accounts, exact: true },
  { to: '/books/entries', label: b.entries, exact: true },
  { to: '/books/entries/new', label: b.add, exact: true },
] as const;

export function BooksNav() {
  return <SubNav label={b.nav} places={BOOKS_PLACES} />;
}

/** Where an account's page is. */
export function accountPath(id: string): string {
  return `/books/accounts/${encodeURIComponent(id)}`;
}

/** Where an entry's page is. */
export function entryPath(id: string): string {
  return `/books/entries/${encodeURIComponent(id)}`;
}

export interface AccountBook {
  accounts: readonly Account[];
  byId: ReadonlyMap<string, Account>;
  /** "1000 Checking", or the id when the account isn't known. */
  label: (id: string | null | undefined) => string;
  /** "Checking", or the id. */
  name: (id: string | null | undefined) => string;
}

export function accountBook(accounts: readonly Account[]): AccountBook {
  const byId = new Map(accounts.map((a) => [a.id, a]));
  return {
    accounts,
    byId,
    label: (id) => {
      const a = id ? byId.get(id) : undefined;
      return a ? `${a.code} ${a.name}` : (id ?? '');
    },
    name: (id) => (id ? (byId.get(id)?.name ?? id) : ''),
  };
}

/** The chart of accounts, read once and shared by the books' pages. */
export function useAccountBook() {
  const query = useRead('accounts.list', accountsList);
  const book = useMemo(() => (query.data ? accountBook(query.data) : undefined), [query.data]);
  return { query, book };
}

export interface EntryLine {
  /** The amount moved, when one debit carries it all. */
  amount: { amount: string; currency: string } | null;
  /** How many debits there are, when more than one. */
  parts: number;
  /** The accounts money left (credits) and went to (debits). */
  from: string;
  to: string;
}

function side(postings: readonly Posting[], book: AccountBook): string {
  const [first, ...rest] = postings;
  if (!first) return '—';
  return rest.length ? whereStrings.entries.andMore(book.name(first.account_id), rest.length) : book.name(first.account_id);
}

/** An entry in one line, as `salli entries list` shows it. */
export function entryLine(entry: JournalEntry, book: AccountBook): EntryLine {
  const debits = entry.postings.filter((p) => p.direction > 0);
  const credits = entry.postings.filter((p) => p.direction < 0);
  const only = debits.length === 1 ? debits[0] : undefined;
  return {
    amount: only ? { amount: only.amount, currency: only.currency } : null,
    parts: debits.length,
    from: side(credits, book),
    to: side(debits, book),
  };
}

/** The entry that `entry` reverses, from the ledger's own links: the one whose `reversed_by` it is. */
export function reversedOf(entry: JournalEntry, all: readonly JournalEntry[]): JournalEntry | undefined {
  return all.find((other) => other.reversed_by === entry.id);
}

/**
 * The reads a new entry changes: the ledger's own, and every figure built
 * on it (Home's, cash, FI, the baseline). A write refreshes them by name.
 */
export const LEDGER_READS = [
  'entries.list',
  'entries.get',
  'entries.provenance',
  'accounts.overview',
  'ledger.trialBalance',
  'ledger.incomeStatement',
  'reports.balanceSheet',
  'insights.netWorth',
  'insights.safeToSpend',
  'insights.forecast',
  'insights.cashFlow',
  'insights.spending',
  'insights.recurring',
  'insights.signals',
  'fi.score.get',
  'fi.projections',
  'fi.score.history',
  'baseline.get',
];
