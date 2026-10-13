/**
 * An account (`accounts.overview`; `salli accounts show`): key figures
 * (its balance in its own currency and, for one held in another, in your
 * base currency at the rates its entries recorded; how many entries; the
 * latest); its balance after each day with an entry, drawn, over a range
 * picked by date; its details; and its entries, newest first, each with
 * the balance after it, a page at a time. Every figure is the server's
 * running balance; the console counts entries and picks dates, nothing
 * more.
 */
import { accountsOverview, type AccountActivity, type AccountOverview } from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { useRead } from '../../api';
import { LineChart } from '../../kit/chart/LineChart';
import { firstInMonthTicks } from '../../kit/chart/ticks';
import { Chip, IdChip, TypeMark } from '../../kit/chips';
import { displayDate, displayMonth, isoDate } from '../../kit/dates';
import { KeyFigure, KeyFigures, Segmented } from '../../kit/figures';
import { Empty, Grid, Loaded, Page, Panel, Provenance, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { Pagination, usePages } from '../../kit/Pagination';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { BooksActions, BooksNav, entryPath } from './ledger';

const a = whereStrings.account;
const b = whereStrings.books;

/** Which running balance the page shows: the account's own currency when every one is known, else the base. */
function shownIn(o: AccountOverview): { native: boolean; code: string } {
  const foreign = o.account.currency.toUpperCase() !== o.base_currency.toUpperCase();
  const native = foreign && o.transactions.every((t) => t.running_balance_native !== null);
  return { native, code: (native ? o.account.currency : o.base_currency).toUpperCase() };
}

/** The balance after each day with an entry: the last entry's running balance that day, as the server gave it. */
function lastOfEachDay(transactions: readonly AccountActivity[], native: boolean): Array<{ date: string; balance: string }> {
  const days: Array<{ date: string; balance: string }> = [];
  for (const t of transactions) {
    const balance = (native ? t.running_balance_native : t.running_balance) ?? '0';
    const last = days[days.length - 1];
    if (last && last.date === t.entry_date) last.balance = balance;
    else days.push({ date: t.entry_date, balance });
  }
  return days;
}

type Range = 'd90' | 'm6' | 'all';

/** The first day a range shows, counted back from today: dates only, never money. */
function rangeStart(range: Range, today: Date): string {
  if (range === 'd90') return isoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 90));
  if (range === 'm6') return isoDate(new Date(today.getFullYear(), today.getMonth() - 6, today.getDate()));
  return '';
}

function OverTime({ overview, range }: { overview: AccountOverview; range: Range }) {
  const locale = useLocale();
  const { native, code } = shownIn(overview);
  const all = useMemo(() => lastOfEachDay(overview.transactions, native), [overview, native]);
  const start = rangeStart(range, new Date());
  const days = useMemo(() => all.filter((d) => d.date >= start), [all, start]);
  if (!all.length) return <Empty>{a.noEntries}</Empty>;
  if (all.length < 2) return <Empty>{a.onlyOne}</Empty>;
  const first = days[0];
  const last = days[days.length - 1];
  if (!first || !last || days.length < 2) return <Empty>{a.rangeEmpty}</Empty>;
  const dates = days.map((d) => d.date);
  const caption = a.overTimeCaption(overview.account.name, displayDate(first.date, locale), displayDate(last.date, locale), visibleAmount(last.balance, code, 'prose', { locale }));
  return (
    <LineChart
      caption={caption}
      currency={code}
      at={dates.map((d) => displayMonth(d.slice(0, 7), locale))}
      days={dates}
      ticks={{ wide: firstInMonthTicks(dates, 1), narrow: firstInMonthTicks(dates, 3) }}
      series={[{ label: overview.account.name, values: days.map((d) => d.balance) }]}
      step
      zero
      shortfall={false}
      figures={
        <Table
          caption={caption}
          captionHidden
          rows={days}
          rowKey={(d) => d.date}
          columns={[
            { key: 'date', header: a.date, label: a.date, render: (d) => displayDate(d.date, locale) },
            { key: 'balance', header: a.after(code), label: a.after(code), align: 'end', render: (d) => <Money amount={d.balance} currency={code} variant="table" /> },
          ]}
        />
      }
    />
  );
}

function Entries({ overview }: { overview: AccountOverview }) {
  const locale = useLocale();
  const { native, code } = shownIn(overview);
  const rows = useMemo(() => [...overview.transactions].reverse(), [overview]);
  const paged = usePages(rows);
  if (!rows.length) return <Empty>{a.noEntries}</Empty>;
  return (
    <>
      <p className="section-help">{a.entriesHelp}</p>
      <Table<AccountActivity>
        caption={a.entries}
        captionHidden
        rows={paged.shown}
        rowKey={(t) => t.entry_id}
        columns={[
          { key: 'id', header: a.entry, label: a.entry, className: 'cell-tight', render: (t) => <IdChip id={t.entry_id} /> },
          { key: 'date', header: a.date, label: a.date, className: 'cell-tight', render: (t) => displayDate(t.entry_date, locale) },
          { key: 'what', header: whereStrings.entries.what, label: whereStrings.entries.what, className: 'cell-description', render: (t) => <Link to={entryPath(t.entry_id)}>{t.description}</Link> },
          { key: 'source', header: a.source, label: a.source, className: 'cell-tight muted', render: (t) => whereStrings.entries.sourceShort[t.source] ?? t.source },
          {
            key: 'after',
            header: a.after(code),
            label: a.after(code),
            align: 'end',
            render: (t) => <Money amount={native ? t.running_balance_native : t.running_balance} currency={code} variant="table" />,
          },
        ]}
      />
      <Pagination paged={paged} noun={a.entriesCount} />
    </>
  );
}

/** The account's balance, in its own currency and the base, how many entries, and the latest. */
function Figures({ overview }: { overview: AccountOverview }) {
  const locale = useLocale();
  const o = overview;
  const account = o.account;
  const base = o.base_currency.toUpperCase();
  const foreign = account.currency.toUpperCase() !== base;
  const first = o.transactions[0];
  const latest = o.transactions[o.transactions.length - 1];
  return (
    <KeyFigures>
      <KeyFigure label={a.balance}>
        {foreign ? (
          o.balance === null ? (
            <span className="figure-note">{a.nativeUnknown(account.currency)}</span>
          ) : (
            <Money amount={o.balance} currency={account.currency} variant="figure" />
          )
        ) : (
          <Money amount={o.current_balance} currency={base} variant="figure" />
        )}
      </KeyFigure>
      {foreign ? (
        <KeyFigure label={a.inBase(base)}>
          <Money amount={o.current_balance} currency={base} variant="figure" />
        </KeyFigure>
      ) : null}
      <KeyFigure label={a.entries} note={first ? a.since(displayDate(first.entry_date, locale)) : null}>
        {o.transactions.length}
      </KeyFigure>
      {latest ? (
        <KeyFigure label={a.latest} note={<Link to={entryPath(latest.entry_id)}>{latest.description}</Link>}>
          {displayDate(latest.entry_date, locale)}
        </KeyFigure>
      ) : null}
    </KeyFigures>
  );
}

function Details({ overview }: { overview: AccountOverview }) {
  const locale = useLocale();
  const account = overview.account;
  const first = overview.transactions[0];
  return (
    <dl className="details">
      <dt>{a.code}</dt>
      <dd className="mono">{account.code}</dd>
      <dt>{a.name}</dt>
      <dd>{account.name}</dd>
      <dt>{a.type}</dt>
      <dd>
        <TypeMark type={account.type} /> {b.typeOne[account.type] ?? account.type}
      </dd>
      {account.asset_role ? (
        <>
          <dt>{a.holds}</dt>
          <dd>{b.roles[account.asset_role] ?? account.asset_role}</dd>
        </>
      ) : null}
      <dt>{a.currency}</dt>
      <dd className="mono">{account.currency}</dd>
      <dt>{a.status}</dt>
      <dd>{account.is_active ? a.active : a.inactive}</dd>
      {account.tax_role ? (
        <>
          <dt>{a.taxRole}</dt>
          <dd className="mono">{account.tax_role}</dd>
        </>
      ) : null}
      {first ? (
        <>
          <dt>{a.first}</dt>
          <dd>
            <Link to={entryPath(first.entry_id)}>{displayDate(first.entry_date, locale)}</Link>
          </dd>
        </>
      ) : null}
    </dl>
  );
}

function AccountPage({ overview }: { overview: AccountOverview }) {
  const account = overview.account;
  const [range, setRange] = useState<Range>('all');
  return (
    <Page
      title={account.name}
      icon="account"
      description={a.description(b.typeOne[account.type] ?? account.type, account.currency, account.code)}
      facts={
        <>
          <Chip mono>{account.code}</Chip>
          <Chip>
            <TypeMark type={account.type} />
            {b.typeOne[account.type] ?? account.type}
          </Chip>
          {account.asset_role ? <Chip>{b.roles[account.asset_role] ?? account.asset_role}</Chip> : null}
          <Chip mono>{account.currency}</Chip>
          <Chip>{a.entriesCount(overview.transactions.length)}</Chip>
          {account.is_active ? null : <Chip>{b.inactive}</Chip>}
        </>
      }
      actions={<BooksActions />}
    >
      <BooksNav />
      <Figures overview={overview} />
      <Grid>
        <Section
          label={a.overTime}
          wide
          aside={
            <Segmented<Range>
              label={a.range}
              value={range}
              onChange={setRange}
              options={(['d90', 'm6', 'all'] as const).map((value) => ({ value, label: a.ranges[value] ?? value }))}
            />
          }
        >
          <Panel>
            <OverTime overview={overview} range={range} />
          </Panel>
        </Section>
        <Section label={a.details}>
          <Details overview={overview} />
          <Provenance>{b.balancesNote}</Provenance>
        </Section>
        <Section label={a.entries} full>
          <Panel>
            <Entries overview={overview} />
            <p>
              <Link to="/books/entries" search={{ account: account.id }}>
                {a.filter}
              </Link>
            </p>
          </Panel>
        </Section>
      </Grid>
    </Page>
  );
}

export function Account() {
  const params = useParams({ strict: false }) as { account?: string };
  const id = params.account ?? '';
  const query = useRead('accounts.overview', accountsOverview, { path: { account_id: id } });
  if (query.isError) {
    return (
      <Page title={a.notFound}>
        <BooksNav />
        <ProblemView error={query.error} onRetry={() => void query.refetch()} />
      </Page>
    );
  }
  return <Loaded query={query} lines={8}>{(overview) => <AccountPage overview={overview} />}</Loaded>;
}

export default Account;
