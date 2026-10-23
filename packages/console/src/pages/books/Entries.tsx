/**
 * The ledger's entries (`entries.list`; `salli entries list`): narrowed by
 * date (the server's `from_date` and `to_date`), by an account they touch
 * and by words in their description (picked from what the server sent, as
 * the CLI's `--account` and `--search` do), newest first or oldest. The
 * filters live in the address, so a narrowed list can be reloaded or
 * shared; each shows as a chip that removes it. Each entry says its id,
 * date, amount and from where to where as account chips, its source and
 * whether it is reversed or a reversal; its eye opens it in a sheet beside
 * the list, with its lines and the way to reverse it. Nothing is computed:
 * an entry's amount is its one debit's, as posted; pages count rows.
 */
import { entriesList, type JournalEntry } from '@leafmonkeylabs/salli-sdk';
import { Link, useNavigate, useSearch } from '@tanstack/react-router';
import { useMemo, useRef, useState, type FormEvent } from 'react';
import { useRead } from '../../api';
import { IdChip, Status } from '../../kit/chips';
import { displayDate } from '../../kit/dates';
import { Segmented } from '../../kit/figures';
import { Field, SelectField } from '../../kit/forms';
import { Icon } from '../../kit/Icon';
import { dateInput } from '../../kit/inputs';
import { Blank, Empty, Loaded, Page, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { Pagination, usePages } from '../../kit/Pagination';
import { Popover } from '../../kit/Popover';
import { Table, type Column } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { EntrySheet } from './EntrySheet';
import { AccountChipOf, BooksActions, BooksFacts, BooksNav, entryLine, entryPath, reversedOf, useAccountBook, type AccountBook } from './ledger';

const e = whereStrings.entries;

export interface EntryFilters {
  from: string;
  to: string;
  account: string;
  q: string;
}

/** The filters in the address, as text (the router reads `?q=2026` as a number). */
export function filtersOf(search: Record<string, unknown>): EntryFilters {
  const text = (value: unknown): string => (value === undefined || value === null ? '' : String(value));
  return { from: text(search.from), to: text(search.to), account: text(search.account), q: text(search.q) };
}

/** The entries that touch `account` and have `q` in their description: picked, never computed. */
export function narrowed(entries: readonly JournalEntry[], filters: EntryFilters): JournalEntry[] {
  const needle = filters.q.trim().toLowerCase();
  return entries.filter(
    (entry) =>
      (!filters.account || entry.postings.some((p) => p.account_id === filters.account)) &&
      (!needle || entry.description.toLowerCase().includes(needle)),
  );
}

/** The address's search for `filters`, leaving out what is empty. */
function searchOf(f: EntryFilters): Record<string, string> {
  return { ...(f.from ? { from: f.from } : {}), ...(f.to ? { to: f.to } : {}), ...(f.account ? { account: f.account } : {}), ...(f.q.trim() ? { q: f.q.trim() } : {}) };
}

/** The date and account filters, in a popover: checked, then put in the address. */
function FilterForm({ filters, book, onDone }: { filters: EntryFilters; book: AccountBook | undefined; onDone: () => void }) {
  const navigate = useNavigate();
  const [from, setFrom] = useState(filters.from);
  const [to, setTo] = useState(filters.to);
  const [account, setAccount] = useState(filters.account);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const found: Record<string, string> = {};
    if (from && !dateInput(from)) found.from = e.badDate;
    if (to && !dateInput(to)) found.to = e.badDate;
    if (!found.from && !found.to && from && to && from > to) found.to = e.fromAfterTo;
    setErrors(found);
    if (Object.keys(found).length) return;
    void navigate({ to: '/books/entries', search: searchOf({ ...filters, from, to, account }) });
    onDone();
  };
  return (
    <form className="form" onSubmit={submit} noValidate role="search" aria-label={e.filters}>
      <Field label={e.from} type="date" value={from} onChange={setFrom} error={errors.from} />
      <Field label={e.to} type="date" value={to} onChange={setTo} error={errors.to} />
      <SelectField
        label={e.account}
        value={account}
        onChange={setAccount}
        options={[{ value: '', label: e.anyAccount }, ...(book?.accounts ?? []).map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))]}
      />
      {Object.keys(errors).length ? (
        <p className="sr-only" role="alert">
          {Object.values(errors).join(' ')}
        </p>
      ) : null}
      <div className="popover-actions">
        <button
          type="button"
          className="button-link"
          onClick={() => {
            void navigate({ to: '/books/entries', search: searchOf({ from: '', to: '', account: '', q: filters.q }) });
            onDone();
          }}
        >
          {e.clear}
        </button>
        <button type="submit" className="button button-primary button-small">
          {e.done}
        </button>
      </div>
    </form>
  );
}

/** Words in the description: kept in the address as they are typed. */
function Search({ filters }: { filters: EntryFilters }) {
  const navigate = useNavigate();
  const [q, setQ] = useState(filters.q);
  return (
    <label className="search">
      <Icon name="search" small />
      <span className="sr-only">{e.search}</span>
      <input
        type="search"
        placeholder={e.search}
        value={q}
        onChange={(event) => {
          setQ(event.target.value);
          void navigate({ to: '/books/entries', search: searchOf({ ...filters, q: event.target.value }), replace: true });
        }}
      />
    </label>
  );
}

type Optional = 'id' | 'source' | 'status';
type Shown = Record<Optional, boolean>;

type Order = 'newest' | 'oldest';

function Toolbar({
  filters,
  book,
  shown,
  setShown,
  order,
  setOrder,
}: {
  filters: EntryFilters;
  book: AccountBook | undefined;
  shown: Shown;
  setShown: (next: Shown) => void;
  order: Order;
  setOrder: (next: Order) => void;
}) {
  const locale = useLocale();
  const navigate = useNavigate();
  const remove = (change: Partial<EntryFilters>): void => void navigate({ to: '/books/entries', search: searchOf({ ...filters, ...change }) });
  const chips: Array<{ key: string; label: string; value: string; clear: Partial<EntryFilters> }> = [];
  if (filters.from || filters.to) {
    const value = [filters.from ? e.since(displayDate(filters.from, locale)) : '', filters.to ? e.until(displayDate(filters.to, locale)) : ''].filter(Boolean).join(' ');
    chips.push({ key: 'date', label: e.date, value, clear: { from: '', to: '' } });
  }
  if (filters.account) chips.push({ key: 'account', label: e.account, value: book?.label(filters.account) ?? filters.account, clear: { account: '' } });
  return (
    <div className="toolbar">
      <Popover
        label={e.filters}
        trigger={(props) => (
          <button {...props} className="button button-dash">
            <Icon name="filter" />
            {e.filtersButton}
            {chips.length ? (
              <>
                <span className="badge" aria-hidden="true">
                  {chips.length}
                </span>
                <span className="sr-only">, {e.filtersOn(chips.length)}</span>
              </>
            ) : null}
          </button>
        )}
      >
        {(close) => <FilterForm filters={filters} book={book} onDone={close} />}
      </Popover>
      {chips.map((chip) => (
        <span key={chip.key} className="filter-chip">
          {chip.label}: <b>{chip.value}</b>
          <button type="button" aria-label={e.remove(chip.label)} onClick={() => remove(chip.clear)}>
            <Icon name="close" small />
          </button>
        </span>
      ))}
      <Search key={filters.q} filters={filters} />
      <Segmented
        label={e.order}
        value={order}
        onChange={setOrder}
        options={[
          { value: 'newest', label: e.newestFirst },
          { value: 'oldest', label: e.oldestFirst },
        ]}
      />
      <span className="toolbar-gap" />
      <Link to="/settings/data" className="button button-line">
        <Icon name="download" />
        {e.export}
      </Link>
      <Popover
        label={e.columns}
        align="end"
        trigger={(props) => (
          <button {...props} className="button button-line">
            <Icon name="columns" />
            {e.columns}
          </button>
        )}
      >
        {() => (
          <>
            {(['id', 'source', 'status'] as const).map((key) => (
              <label key={key} className="check-row">
                <input type="checkbox" checked={shown[key]} onChange={() => setShown({ ...shown, [key]: !shown[key] })} />
                {e.columnNames[key]}
              </label>
            ))}
            <p className="field-help">{e.alwaysShown}</p>
          </>
        )}
      </Popover>
    </div>
  );
}

/**
 * One side of an entry: its first account as a chip, and a button that shows
 * the rest beside it. In place, not in a popover: the table's own scroll
 * would clip a panel.
 */
function Side({ ids, book }: { ids: string[]; book: AccountBook }) {
  const [all, setAll] = useState(false);
  const [first, ...rest] = ids;
  if (!first) return <Blank>{e.noAccount}</Blank>;
  return (
    <span className="chips-inline">
      <AccountChipOf id={first} book={book} />
      {all ? rest.map((id, i) => <AccountChipOf key={`${id}-${i}`} id={id} book={book} />) : null}
      {rest.length ? (
        <button type="button" className="chip chip-more chip-button" aria-expanded={all} onClick={() => setAll(!all)}>
          {all ? e.fewerAccounts : `+${rest.length}`}
          {all ? null : <span className="sr-only">, {e.moreAccounts(rest.length)}</span>}
        </button>
      ) : null}
    </span>
  );
}

function List({ entries, book, filters, shown, order }: { entries: readonly JournalEntry[]; book: AccountBook; filters: EntryFilters; shown: Shown; order: Order }) {
  const locale = useLocale();
  const oldest = order === 'oldest';
  const [open, setOpen] = useState<string | null>(null);
  const eyes = useRef(new Map<string, HTMLButtonElement>());
  const reversals = useMemo(() => new Set(entries.flatMap((x) => (x.reversed_by ? [x.reversed_by] : []))), [entries]);
  // The server lists them oldest first.
  const found = useMemo(() => {
    const picked = narrowed(entries, filters);
    return oldest ? picked : picked.reverse();
  }, [entries, filters, oldest]);
  const paged = usePages(found);
  const opened = open ? entries.find((x) => x.id === open) : undefined;
  if (!entries.length) return <Empty>{e.noneAtAll}</Empty>;

  // The amount column's currency, when every amount on the page shares one.
  const codes = new Set(paged.shown.flatMap((x) => {
    const amount = entryLine(x, book).amount;
    return amount ? [amount.currency.toUpperCase()] : [];
  }));
  const code = codes.size === 1 ? [...codes][0] : undefined;
  const close = (): void => {
    const id = open;
    setOpen(null);
    if (id) eyes.current.get(id)?.focus();
  };
  const columns: Array<Column<JournalEntry> | false> = [
    shown.id && { key: 'id', header: e.id, label: e.id, className: 'cell-tight', render: (x) => <IdChip id={x.id} /> },
    {
      key: 'date',
      header: e.date,
      sort: oldest ? 'ascending' : 'descending',
      label: e.date,
      className: 'cell-tight',
      render: (x) => displayDate(x.entry_date, locale),
    },
    { key: 'what', header: e.what, label: e.what, className: 'cell-description', render: (x) => <Link to={entryPath(x.id)}>{x.description}</Link> },
    { key: 'from', header: e.fromColumn, label: e.fromColumn, render: (x) => <Side ids={x.postings.filter((p) => p.direction < 0).map((p) => p.account_id)} book={book} /> },
    { key: 'to', header: e.toColumn, label: e.toColumn, render: (x) => <Side ids={x.postings.filter((p) => p.direction > 0).map((p) => p.account_id)} book={book} /> },
    {
      key: 'amount',
      header: code ? e.amountIn(code) : e.amount,
      label: code ? e.amountIn(code) : e.amount,
      align: 'end',
      render: (x) => {
        const line = entryLine(x, book);
        return line.amount ? <Money amount={line.amount.amount} currency={line.amount.currency} variant="table" withCode={!code} /> : e.parts(line.parts);
      },
    },
    shown.source && { key: 'source', header: e.source, label: e.source, className: 'cell-tight muted', render: (x) => e.sourceShort[x.source] ?? x.source },
    shown.status && {
      key: 'status',
      header: e.status,
      label: e.status,
      className: 'cell-tight',
      render: (x) =>
        x.reversed_by ? <Status kind="reversed">{e.reversed}</Status> : reversals.has(x.id) ? <Status kind="reversal">{e.reversal}</Status> : <Status kind="posted">{e.posted}</Status>,
    },
    {
      key: 'open',
      header: <span className="sr-only">{e.sheet}</span>,
      label: e.sheet,
      className: 'cell-tight',
      render: (x) => (
        <button
          type="button"
          className="icon-button icon-button-small"
          ref={(el) => {
            if (el) eyes.current.set(x.id, el);
            else eyes.current.delete(x.id);
          }}
          aria-pressed={open === x.id}
          aria-label={open === x.id ? e.close(x.description) : e.open(x.description)}
          onClick={() => setOpen(open === x.id ? null : x.id)}
        >
          <Icon name="eye" small />
        </button>
      ),
    },
  ];
  return (
    <>
      {found.length ? (
        <Table<JournalEntry>
          caption={e.title}
          captionHidden
          rows={paged.shown}
          rowKey={(x) => x.id}
          selected={(x) => x.id === open}
          columns={columns.filter((c): c is Column<JournalEntry> => Boolean(c))}
        />
      ) : (
        <Empty>{e.none}</Empty>
      )}
      <Pagination paged={paged} noun={e.nounOf} />
      {opened ? <EntrySheet key={opened.id} entry={opened} original={reversedOf(opened, entries)} book={book} onClose={close} /> : null}
    </>
  );
}

export function Entries() {
  const search = useSearch({ strict: false }) as Record<string, unknown>;
  const filters = useMemo(() => filtersOf(search), [search]);
  const [shown, setShown] = useState<Shown>({ id: true, source: true, status: true });
  const [order, setOrder] = useState<Order>('newest');
  const { query: accounts, book } = useAccountBook();
  const from = dateInput(filters.from);
  const to = dateInput(filters.to);
  const query = useRead('entries.list', entriesList, { query: { ...(from ? { from_date: from } : {}), ...(to ? { to_date: to } : {}) } });
  return (
    <Page title={e.title} description={e.description} facts={<BooksFacts />} actions={<BooksActions />}>
      <BooksNav />
      <Section label={e.title} className="with-sheet">
        <Toolbar filters={filters} book={book} shown={shown} setShown={setShown} order={order} setOrder={setOrder} />
        <p className="section-help">{e.exportHelp}</p>
        <Loaded query={accounts}>
          {() => <Loaded query={query}>{(entries) => (book ? <List entries={entries} book={book} filters={filters} shown={shown} order={order} /> : null)}</Loaded>}
        </Loaded>
      </Section>
    </Page>
  );
}

export default Entries;
