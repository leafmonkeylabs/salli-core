/**
 * An account (`accounts.overview`; `salli accounts show`): its balance in
 * its own currency and, for one held in another, in your base currency at
 * the rates its entries recorded; what it is; its balance after each day
 * with an entry, drawn; and its entries, newest first, each with the
 * balance after it. Every figure is the server's running balance.
 */
import { accountsOverview, type AccountActivity, type AccountOverview } from '@leafmonkeylabs/salli-sdk';
import { Link, useParams } from '@tanstack/react-router';
import { useMemo } from 'react';
import { useRead } from '../../api';
import { LineChart } from '../../kit/chart/LineChart';
import { firstInMonthTicks } from '../../kit/chart/ticks';
import { displayDate, displayMonth } from '../../kit/dates';
import { Empty, Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { ProblemView } from '../../kit/Problem';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { BooksNav, entryPath } from './ledger';

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

function OverTime({ overview }: { overview: AccountOverview }) {
  const locale = useLocale();
  const { native, code } = shownIn(overview);
  const days = useMemo(() => lastOfEachDay(overview.transactions, native), [overview, native]);
  const first = days[0];
  const last = days[days.length - 1];
  if (!first || !last) return <Empty>{a.noEntries}</Empty>;
  if (days.length < 2) return <Empty>{a.onlyOne}</Empty>;
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
  if (!rows.length) return <Empty>{a.noEntries}</Empty>;
  return (
    <>
      <p className="section-help">{a.entriesHelp}</p>
      <Table<AccountActivity>
        caption={a.entries}
        captionHidden
        rows={rows}
        rowKey={(t) => t.entry_id}
        columns={[
          { key: 'date', header: a.date, label: a.date, render: (t) => displayDate(t.entry_date, locale) },
          { key: 'what', header: a.what, label: a.what, render: (t) => <Link to={entryPath(t.entry_id)}>{t.description}</Link> },
          { key: 'source', header: a.source, label: a.source, render: (t) => whereStrings.entry.sources[t.source]?.replace(/\.$/, '') ?? t.source },
          {
            key: 'after',
            header: a.after(code),
            label: a.after(code),
            align: 'end',
            render: (t) => <Money amount={native ? t.running_balance_native : t.running_balance} currency={code} variant="table" />,
          },
        ]}
      />
    </>
  );
}

function Balance({ overview }: { overview: AccountOverview }) {
  const o = overview;
  const account = o.account;
  const base = o.base_currency.toUpperCase();
  const foreign = account.currency.toUpperCase() !== base;
  return (
    <Panel>
      <p className="figure">
        {foreign ? (
          o.balance === null ? (
            <span className="figure-note">{a.nativeUnknown(account.currency)}</span>
          ) : (
            <Money amount={o.balance} currency={account.currency} variant="figure" />
          )
        ) : (
          <Money amount={o.current_balance} currency={base} variant="figure" />
        )}
      </p>
      <Rows>
        {foreign ? (
          <Row label={a.inBase(base)}>
            <Money amount={o.current_balance} currency={base} variant="table" withCode />
          </Row>
        ) : null}
        <Row label={a.type}>{b.typeOne[account.type] ?? account.type}</Row>
        {account.asset_role ? <Row label={a.holds}>{b.roles[account.asset_role] ?? account.asset_role}</Row> : null}
        <Row label={a.currency}>{account.currency}</Row>
        <Row label={a.status}>{account.is_active ? a.active : a.inactive}</Row>
        {account.tax_role ? <Row label={a.taxRole}>{account.tax_role}</Row> : null}
      </Rows>
      <Provenance>{b.balancesNote}</Provenance>
    </Panel>
  );
}

function AccountPage({ overview }: { overview: AccountOverview }) {
  const account = overview.account;
  return (
    <Page title={account.name} description={a.description(b.typeOne[account.type] ?? account.type, account.currency, account.code)}>
      <BooksNav />
      <Grid>
        <Section label={a.balance}>
          <Balance overview={overview} />
        </Section>
        <Section label={a.overTime} wide>
          <Panel>
            <OverTime overview={overview} />
          </Panel>
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
