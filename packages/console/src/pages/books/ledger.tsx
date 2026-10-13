/**
 * What the books' pages share: the accounts by id (`accounts.list`), where
 * an account and an entry are, the books' own places, and an entry in one
 * line (its amount and from where to where), as `salli entries list` says
 * it. Nothing here computes: an entry's amount is its one debit's, as
 * posted; an entry of several parts says how many.
 */
import { accountsList, amountSign, isAmount, ledgerTrialBalance, type Account, type JournalEntry, type Posting } from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useMemo } from 'react';
import { useRead } from '../../api';
import { AccountChip, Chip } from '../../kit/chips';
import { Icon } from '../../kit/Icon';
import { visibleAmount } from '../../kit/Money';
import { SubNav } from '../../kit/SubNav';
import { useLocale } from '../../preferences';
import { BOOKS_PLACES } from '../../shell/places';
import { whereStrings } from '../../where-strings';

const b = whereStrings.books;

export { BOOKS_PLACES };

export function BooksNav() {
  return <SubNav label={b.nav} places={BOOKS_PLACES} />;
}

/**
 * The books' facts, beside every books page's title: the base currency,
 * how many accounts, and the trial balance's net as Salli computed it
 * (ticked when the server's figure is zero, read from its digits).
 */
export function BooksFacts() {
  const locale = useLocale();
  const accounts = useRead('accounts.list', accountsList);
  const trial = useRead('ledger.trialBalance', ledgerTrialBalance);
  const t = trial.data;
  const zero = t ? isAmount(t.net.trim()) && amountSign(t.net) === 0 : false;
  return (
    <>
      {t ? <Chip mono>{t.currency.toUpperCase()}</Chip> : null}
      {accounts.data ? <Chip>{b.accountsCount(accounts.data.length)}</Chip> : null}
      {t ? (
        <Chip quiet>
          {zero ? <Icon name="check" small /> : null}
          <span title={zero ? b.netsChecked : undefined}>{b.nets(visibleAmount(t.net, t.currency, 'table', { locale }))}</span>
        </Chip>
      ) : null}
    </>
  );
}

/** The books' two actions: importing a statement, and adding an entry. */
export function BooksActions() {
  return (
    <>
      <Link to="/books/imports" className="button button-secondary">
        <Icon name="upload" />
        {b.importStatement}
      </Link>
      <Link to="/books/entries/new" className="button button-primary">
        <Icon name="plus" />
        {b.add}
      </Link>
    </>
  );
}

/** An account as a chip, linked to its page; the id when the account isn't known. */
export function AccountChipOf({ id, book, link = true }: { id: string; book: AccountBook; link?: boolean }) {
  const a = book.byId.get(id);
  if (!a) return <span className="chip chip-id">{id.slice(0, 8)}</span>;
  return <AccountChip code={a.code} name={a.name} type={a.type} typeLabel={b.typeOne[a.type] ?? a.type} {...(link ? { to: accountPath(a.id) } : {})} />;
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
