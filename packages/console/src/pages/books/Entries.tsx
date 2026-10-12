/**
 * The ledger's entries (`entries.list`; `salli entries list`): narrowed by
 * date (the server's `from_date` and `to_date`), by an account they touch
 * and by words in their description (picked from what the server sent, as
 * the CLI's `--account` and `--search` do), newest first. The filters live
 * in the address, so a narrowed list can be reloaded or shared. Each entry
 * says its amount and from where to where; a reversed one, and a reversal,
 * say so.
 */
import { entriesList, type JournalEntry } from '@leafmonkeylabs/salli-sdk';
import { Link, useNavigate, useSearch } from '@tanstack/react-router';
import { useMemo, useState, type FormEvent } from 'react';
import { useRead } from '../../api';
import { displayDate } from '../../kit/dates';
import { Button, Field, SelectField } from '../../kit/forms';
import { dateInput } from '../../kit/inputs';
import { Empty, Grid, Loaded, Page, Panel, Section } from '../../kit/layout';
import { Money } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { BooksNav, entryLine, entryPath, useAccountBook, type AccountBook } from './ledger';

const e = whereStrings.entries;
/** How many a list shows before asking: the latest, as the CLI's tables do. */
const SHOWN = 50;

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

function Filters({ filters, book }: { filters: EntryFilters; book: AccountBook | undefined }) {
  const navigate = useNavigate();
  const [from, setFrom] = useState(filters.from);
  const [to, setTo] = useState(filters.to);
  const [account, setAccount] = useState(filters.account);
  const [q, setQ] = useState(filters.q);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const found: Record<string, string> = {};
    if (from && !dateInput(from)) found.from = e.badDate;
    if (to && !dateInput(to)) found.to = e.badDate;
    if (!found.from && !found.to && from && to && from > to) found.to = e.fromAfterTo;
    setErrors(found);
    if (Object.keys(found).length) return;
    const search = { ...(from ? { from } : {}), ...(to ? { to } : {}), ...(account ? { account } : {}), ...(q.trim() ? { q: q.trim() } : {}) };
    void navigate({ to: '/books/entries', search });
  };
  const clear = (): void => {
    setFrom('');
    setTo('');
    setAccount('');
    setQ('');
    setErrors({});
    void navigate({ to: '/books/entries', search: {} });
  };
  return (
    <form className="form filters" onSubmit={submit} noValidate role="search" aria-label={e.filters}>
      <div className="field-grid">
        <Field label={e.from} type="date" value={from} onChange={setFrom} error={errors.from} />
        <Field label={e.to} type="date" value={to} onChange={setTo} error={errors.to} />
        <SelectField
          label={e.account}
          value={account}
          onChange={setAccount}
          options={[{ value: '', label: e.anyAccount }, ...(book?.accounts ?? []).map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))]}
        />
        <Field label={e.text} value={q} onChange={setQ} />
      </div>
      {Object.keys(errors).length ? (
        <p className="sr-only" role="alert">
          {Object.values(errors).join(' ')}
        </p>
      ) : null}
      <div className="form-actions">
        <Button type="submit">{e.apply}</Button>
        <Button variant="tertiary" onPress={clear}>
          {e.clear}
        </Button>
      </div>
    </form>
  );
}

function List({ entries, book, filters }: { entries: readonly JournalEntry[]; book: AccountBook; filters: EntryFilters }) {
  const locale = useLocale();
  const [all, setAll] = useState(false);
  const reversals = useMemo(() => new Set(entries.flatMap((x) => (x.reversed_by ? [x.reversed_by] : []))), [entries]);
  // Newest first: the server lists them oldest first.
  const found = useMemo(() => narrowed(entries, filters).reverse(), [entries, filters]);
  if (!entries.length) return <Empty>{e.noneAtAll}</Empty>;
  if (!found.length) return <Empty>{e.none}</Empty>;
  const shown = all ? found : found.slice(0, SHOWN);
  return (
    <>
      <p className="section-help" role="status">
        {e.count(found.length)}
      </p>
      <Table<JournalEntry>
        caption={e.title}
        captionHidden
        rows={shown}
        rowKey={(x) => x.id}
        columns={[
          { key: 'date', header: e.date, label: e.date, render: (x) => displayDate(x.entry_date, locale) },
          {
            key: 'what',
            header: e.what,
            label: e.what,
            render: (x) => (
              <>
                <Link to={entryPath(x.id)}>{x.description}</Link>
                {x.reversed_by ? <span className="tag"> {e.reversed}</span> : null}
                {reversals.has(x.id) ? <span className="tag"> {e.reversal}</span> : null}
              </>
            ),
          },
          {
            key: 'amount',
            header: e.amount,
            label: e.amount,
            align: 'end',
            render: (x) => {
              const line = entryLine(x, book);
              return line.amount ? <Money amount={line.amount.amount} currency={line.amount.currency} variant="table" withCode /> : e.parts(line.parts);
            },
          },
          { key: 'from', header: e.fromColumn, label: e.fromColumn, render: (x) => entryLine(x, book).from },
          { key: 'to', header: e.toColumn, label: e.toColumn, render: (x) => entryLine(x, book).to },
        ]}
      />
      {shown.length < found.length ? (
        <div className="form-actions">
          <p className="section-help">{e.showing(shown.length, found.length)}</p>
          <Button variant="secondary" onPress={() => setAll(true)}>
            {e.showAll(found.length)}
          </Button>
        </div>
      ) : null}
    </>
  );
}

export function Entries() {
  const search = useSearch({ strict: false }) as Record<string, unknown>;
  const filters = useMemo(() => filtersOf(search), [search]);
  const { query: accounts, book } = useAccountBook();
  const from = dateInput(filters.from);
  const to = dateInput(filters.to);
  const query = useRead('entries.list', entriesList, { query: { ...(from ? { from_date: from } : {}), ...(to ? { to_date: to } : {}) } });
  return (
    <Page title={e.title} description={e.description}>
      <BooksNav />
      <Grid>
        <Section label={e.filters} full>
          <Panel>
            <Filters key={`${filters.from}|${filters.to}|${filters.account}|${filters.q}`} filters={filters} book={book} />
          </Panel>
        </Section>
        <Section label={e.title} full>
          <Panel>
            <Loaded query={accounts}>
              {() => <Loaded query={query}>{(entries) => (book ? <List entries={entries} book={book} filters={filters} /> : null)}</Loaded>}
            </Loaded>
          </Panel>
        </Section>
      </Grid>
    </Page>
  );
}

export default Entries;
