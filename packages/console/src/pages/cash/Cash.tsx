/**
 * Cash (docs/design/console.md, section 5; `salli insights forecast`,
 * `safe-to-spend`, `cash-flow`, `spending`, `recurring`): the daily
 * forecast to its low point, drawn; safe to spend until money next comes
 * in and what it is committed to; each cash account; what is expected to
 * come and go; cash flow by month, drawn; spending by category; recurring
 * payments. Every figure is the server's, in the currency it names, with
 * the rates and notes it gives. Signals link to each part by its anchor.
 */
import {
  formatRatio,
  insightsCashFlow,
  insightsForecast,
  insightsRecurring,
  insightsSafeToSpend,
  insightsSpending,
  type CashFlow,
  type CashForecast,
  type ExchangeRate,
  type ExpectedFlow,
  type MonthCashFlow,
  type RecurringPayment,
  type SpendingLine,
  type AccountForecast,
} from '@leafmonkeylabs/salli-sdk';
import { Link } from '@tanstack/react-router';
import { useMemo } from 'react';
import { useRead } from '../../api';
import { BarChart } from '../../kit/chart/BarChart';
import { LineChart } from '../../kit/chart/LineChart';
import { monthTicks } from '../../kit/chart/ticks';
import { displayDate, displayMonth } from '../../kit/dates';
import { Blank, Empty, Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { whereStrings } from '../../where-strings';
import { accountPath } from '../books/ledger';

const c = whereStrings.cash;
/** The forecast's reach, as `salli insights forecast` asks by default. */
const DAYS = 60;
/** Full months of cash flow before this one. */
const MONTHS = 6;

function Rates({ fx }: { fx: readonly ExchangeRate[] | undefined }) {
  const locale = useLocale();
  return (
    <>
      {(fx ?? []).map((rate) => (
        <Provenance key={rate.currency}>
          {rate.rate ? c.rate(rate.currency, rate.rate, rate.source ?? '', displayDate(rate.as_of, locale)) : c.noRate(rate.currency)}
        </Provenance>
      ))}
    </>
  );
}

function ForecastChart({ data }: { data: CashForecast }) {
  const locale = useLocale();
  const dates = useMemo(() => data.daily.map((d) => d.date), [data]);
  const low = dates.indexOf(data.lowest_date);
  const code = data.currency.toUpperCase();
  const caption = c.forecastCaption(
    displayDate(data.start, locale),
    displayDate(data.end, locale),
    visibleAmount(data.today, code, 'prose', { locale }),
    visibleAmount(data.lowest, code, 'prose', { locale }),
    displayDate(data.lowest_date, locale),
    visibleAmount(data.end_balance, code, 'prose', { locale }),
  );
  return (
    <LineChart
      caption={caption}
      currency={code}
      at={dates.map((d) => displayDate(d, locale))}
      ticks={{ wide: [0, ...monthTicks(dates, 1)], narrow: [0, ...monthTicks(dates, 2)] }}
      series={[{ label: c.cashColumn(code), values: data.daily.map((d) => d.balance) }]}
      step
      marks={low >= 0 ? [{ series: 0, index: low, label: c.lowest(displayDate(data.lowest_date, locale)) }] : []}
      figures={
        <Table
          caption={caption}
          captionHidden
          rows={data.daily}
          rowKey={(d) => d.date}
          columns={[
            { key: 'date', header: c.day, label: c.day, render: (d) => displayDate(d.date, locale) },
            { key: 'cash', header: c.cashColumn(code), label: c.cashColumn(code), align: 'end', render: (d) => <Money amount={d.balance} currency={code} variant="table" /> },
          ]}
        />
      }
    />
  );
}

function Forecast() {
  const query = useRead('insights.forecast', insightsForecast);
  return (
    <Section label={c.forecast(DAYS)} wide anchor="forecast">
      <Loaded query={query} lines={6}>
        {(data) => (
          <Panel>
            <ForecastChart data={data} />
            <Rates fx={data.fx} />
            {(data.notes ?? []).map((note, i) => (
              <Provenance key={i}>{note}</Provenance>
            ))}
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function SafeToSpend() {
  const locale = useLocale();
  const query = useRead('insights.safeToSpend', insightsSafeToSpend);
  return (
    <Section label={c.safe}>
      <Loaded query={query}>
        {(safe) => (
          <Panel>
            <p className="figure">
              <Money amount={safe.amount} currency={safe.currency} variant="figure" />{' '}
              <span className="figure-note">
                {safe.next_income ? c.safeUntilIncome(displayDate(safe.next_income.date, locale), safe.next_income.description) : c.safeFor30(displayDate(safe.until, locale))}
              </span>
            </p>
            <p className="section-help">{c.safeHelp}</p>
            <Rows>
              <Row label={c.cashToday}>
                <Money amount={safe.cash_today} currency={safe.currency} variant="table" withCode />
              </Row>
              {safe.next_income ? (
                <Row label={c.nextIncome(displayDate(safe.next_income.date, locale), safe.next_income.description)}>
                  <Money amount={safe.next_income.amount} currency={safe.next_income.currency} variant="table" withCode />
                </Row>
              ) : null}
            </Rows>
            <p className="subhead">{c.committed}</p>
            {safe.committed.length ? (
              <Rows>
                {safe.committed.map((flow, i) => (
                  <Row key={`${flow.date}-${i}`} label={`${displayDate(flow.date, locale)} · ${flow.description}`} indent>
                    <Money amount={flow.amount} currency={flow.currency} variant="table" withCode />
                  </Row>
                ))}
              </Rows>
            ) : (
              <Provenance>{c.nothingCommitted}</Provenance>
            )}
            <Rates fx={safe.fx} />
            {safe.notes.map((note, i) => (
              <Provenance key={i}>{note}</Provenance>
            ))}
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function Accounts() {
  const locale = useLocale();
  const query = useRead('insights.forecast', insightsForecast);
  return (
    <Section label={c.accounts} full>
      <Loaded query={query}>
        {(data) => (
          <Panel>
            <p className="section-help">{c.accountsHelp}</p>
            <Table<AccountForecast>
              caption={c.accounts}
              captionHidden
              rows={data.accounts}
              rowKey={(a) => a.account_id}
              columns={[
                { key: 'account', header: c.account, label: c.account, render: (a) => <Link to={accountPath(a.account_id)}>{a.name}</Link> },
                { key: 'today', header: c.today, label: c.today, align: 'end', render: (a) => <Money amount={a.today} currency={a.currency} variant="table" withCode /> },
                { key: 'lowest', header: c.lowestColumn, label: c.lowestColumn, align: 'end', render: (a) => <Money amount={a.lowest} currency={a.currency} variant="table" withCode /> },
                { key: 'on', header: c.on, label: c.on, render: (a) => displayDate(a.lowest_date, locale) },
                { key: 'end', header: c.atEnd(displayDate(data.end, locale)), label: c.atEnd(displayDate(data.end, locale)), align: 'end', render: (a) => <Money amount={a.end} currency={a.currency} variant="table" withCode /> },
              ]}
            />
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function ComingUp() {
  const locale = useLocale();
  const query = useRead('insights.forecast', insightsForecast);
  return (
    <Section label={c.comingUp} full>
      <Loaded query={query}>
        {(data) => {
          const names = new Map(data.accounts.map((a) => [a.account_id, a.name]));
          return (
            <Panel>
              <p className="section-help">{c.comingUpHelp}</p>
              {data.flows.length ? (
                <Table<ExpectedFlow>
                  caption={c.comingUp}
                  captionHidden
                  rows={data.flows}
                  rowKey={(f) => `${f.date}-${f.account_id ?? ''}-${f.description}-${f.amount}`}
                  columns={[
                    { key: 'date', header: c.date, label: c.date, render: (f) => displayDate(f.date, locale) },
                    { key: 'what', header: c.what, label: c.what, render: (f) => f.description },
                    { key: 'account', header: c.account, label: c.account, render: (f) => (f.account_id ? (names.get(f.account_id) ?? f.account_id) : '') },
                    { key: 'source', header: c.sourceColumn, label: c.sourceColumn, render: (f) => c.sources[f.source] ?? f.source },
                    { key: 'amount', header: c.amount, label: c.amount, align: 'end', render: (f) => <Money amount={f.amount} currency={f.currency} variant="table" withCode signed /> },
                  ]}
                />
              ) : (
                <Empty>{c.nothingComing}</Empty>
              )}
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

function FlowChart({ data }: { data: CashFlow }) {
  const locale = useLocale();
  const code = data.currency.toUpperCase();
  const first = data.months[0];
  const last = data.months[data.months.length - 1];
  const observed = data.average.months_observed.length;
  const caption = observed
    ? c.cashFlowCaption(displayMonth(first?.month, locale), displayMonth(last?.month, locale), visibleAmount(data.average.net, code, 'prose', { locale }), c.months(observed))
    : c.cashFlowNoAverage(displayMonth(first?.month, locale), displayMonth(last?.month, locale));
  const month = (m: MonthCashFlow): string => (m.complete ? displayMonth(m.month, locale) : c.monthSoFar(displayMonth(m.month, locale)));
  return (
    <BarChart
      caption={caption}
      currency={code}
      series={[c.income, c.spending]}
      partialLabel={c.soFar}
      groups={data.months.map((m) => ({ label: displayMonth(m.month, locale), values: [m.income, m.expenses] as const, figure: m.net, partial: !m.complete }))}
      figures={
        <Table<MonthCashFlow>
          caption={caption}
          captionHidden
          rows={data.months}
          rowKey={(m) => m.month}
          columns={[
            { key: 'month', header: c.month, label: c.month, render: month },
            { key: 'income', header: `${c.income} (${code})`, label: c.income, align: 'end', render: (m) => <Money amount={m.income} currency={code} variant="table" /> },
            { key: 'spending', header: `${c.spending} (${code})`, label: c.spending, align: 'end', render: (m) => <Money amount={m.expenses} currency={code} variant="table" /> },
            { key: 'net', header: `${c.leftOver} (${code})`, label: c.leftOver, align: 'end', render: (m) => <Money amount={m.net} currency={code} variant="table" /> },
            { key: 'saved', header: c.saved, label: c.saved, align: 'end', render: (m) => (m.savings_rate === null ? <Blank>{c.noIncome}</Blank> : formatRatio(m.savings_rate, { locale })) },
          ]}
        />
      }
    />
  );
}

function Flow() {
  const locale = useLocale();
  const query = useRead('insights.cashFlow', insightsCashFlow, { query: { months: MONTHS } });
  return (
    <Section label={c.cashFlow} wide anchor="cash-flow">
      <Loaded query={query} lines={6}>
        {(data) => (
          <Panel>
            <FlowChart data={data} />
            {data.average.months_observed.length ? (
              <>
                <p className="subhead">{c.average(c.months(data.average.months_observed.length))}</p>
                <Rows>
                  <Row label={c.income}>
                    <Money amount={data.average.income} currency={data.currency} variant="table" withCode />
                  </Row>
                  <Row label={c.spending}>
                    <Money amount={data.average.expenses} currency={data.currency} variant="table" withCode />
                  </Row>
                  <Row label={c.leftOver} total>
                    <Money amount={data.average.net} currency={data.currency} variant="table" withCode />
                  </Row>
                  {data.average.savings_rate ? <Row label={c.saved}>{formatRatio(data.average.savings_rate, { locale })}</Row> : null}
                </Rows>
              </>
            ) : (
              <Provenance>{c.noAverage}</Provenance>
            )}
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

function Spending() {
  const locale = useLocale();
  const query = useRead('insights.spending', insightsSpending, { query: { months: 3, by: 'category' } });
  return (
    <Section label={c.byCategory} anchor="spending">
      <Loaded query={query}>
        {(data) => {
          const code = data.currency.toUpperCase();
          if (!data.lines.length) return <Empty>{c.noSpending}</Empty>;
          return (
            <Panel>
              <p className="section-help">{c.byCategoryHelp(displayMonth(data.months[0], locale), displayMonth(data.months[data.months.length - 1], locale))}</p>
              <Table<SpendingLine>
                caption={c.byCategory}
                captionHidden
                rows={data.lines}
                rowKey={(l) => l.key}
                columns={[
                  { key: 'key', header: c.category, label: c.category, render: (l) => l.key },
                  { key: 'total', header: `${c.total} (${code})`, label: c.total, align: 'end', render: (l) => <Money amount={l.total} currency={code} variant="table" /> },
                  { key: 'share', header: c.share, label: c.share, align: 'end', render: (l) => (l.share === null ? <Blank>{c.noShare}</Blank> : formatRatio(l.share, { locale })) },
                ]}
              />
            </Panel>
          );
        }}
      </Loaded>
    </Section>
  );
}

function Recurring() {
  const locale = useLocale();
  const query = useRead('insights.recurring', insightsRecurring);
  return (
    <Section label={c.recurring} full anchor="recurring">
      <Loaded query={query}>
        {(data) => (
          <Panel>
            <p className="section-help">{c.recurringHelp}</p>
            {data.items.length ? (
              <Table<RecurringPayment>
                caption={c.recurring}
                captionHidden
                rows={data.items}
                rowKey={(r) => r.key}
                columns={[
                  { key: 'payee', header: c.payee, label: c.payee, render: (r) => r.payee },
                  { key: 'every', header: c.every, label: c.every, render: (r) => c.cadence[r.cadence] ?? r.cadence },
                  {
                    key: 'typical',
                    header: c.typical,
                    label: c.typical,
                    align: 'end',
                    render: (r) => (
                      <>
                        <Money amount={r.typical_amount} currency={r.currency} variant="table" withCode />
                        {r.varies ? <span className="muted"> {c.varies}</span> : null}
                      </>
                    ),
                  },
                  { key: 'next', header: c.next, label: c.next, render: (r) => displayDate(r.next_expected, locale) },
                  { key: 'tracked', header: c.tracked, label: c.tracked, render: (r) => (r.tracked ? c.yes : c.no) },
                ]}
              />
            ) : (
              <Empty>{c.noRecurring}</Empty>
            )}
          </Panel>
        )}
      </Loaded>
    </Section>
  );
}

export function Cash() {
  return (
    <Page title={c.title} description={c.description}>
      <Grid>
        <Forecast />
        <SafeToSpend />
        <Accounts />
        <Flow />
        <Spending />
        <ComingUp />
        <Recurring />
      </Grid>
    </Page>
  );
}

export default Cash;
