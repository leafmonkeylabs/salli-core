/**
 * The baseline (`baseline.get`; docs/baseline.md): the model every figure
 * starts from. Its two timelines drawn (cash day by day for the as-of
 * month and the twelve after it; net worth month by month to the horizon),
 * income and spending as averaged, balances by role, debts counted once,
 * the assumptions with each placeholder flagged, the rates used. Reading it
 * changes nothing; every figure is the server's.
 */
import { baselineGet, type Baseline as BaselineData, type BaselineBalance, type BaselineDebt, type FiAssumption } from '@leafmonkeylabs/salli-sdk';
import { formatRatio } from '@leafmonkeylabs/salli-sdk';
import { useMemo } from 'react';
import { useRead } from '../../api';
import { LineChart } from '../../kit/chart/LineChart';
import { displayDate, displayMonth } from '../../kit/dates';
import { Empty, Grid, Loaded, Page, Panel, Provenance, Row, Rows, Section } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { Basis } from './Basis';
import { monthText, rateText } from './format';
import { LabNav } from './LabNav';
import { monthTicks, yearTicks } from './Timelines';

const b = labStrings.baseline;

function CashChart({ data }: { data: BaselineData }) {
  const locale = useLocale();
  const days = data.cash.daily ?? [];
  const dates = useMemo(() => days.map((d) => d.date), [days]);
  const at = useMemo(() => dates.map((d) => displayMonth(d.slice(0, 7), locale)), [dates, locale]);
  const low = dates.indexOf(data.cash.lowest_date);
  const caption = b.cashCaption(
    displayDate(data.cash.start, locale),
    displayDate(data.cash.end, locale),
    visibleAmount(data.cash.lowest, data.currency, 'prose', { locale }),
    displayDate(data.cash.lowest_date, locale),
  );
  const code = data.currency.toUpperCase();
  return (
    <LineChart
      caption={caption}
      currency={data.currency}
      at={at}
      ticks={{ wide: monthTicks(dates, 2), narrow: monthTicks(dates, 4) }}
      series={[{ label: labStrings.baselineColumn, values: days.map((d) => d.balance) }]}
      step
      marks={low >= 0 ? [{ series: 0, index: low, label: labStrings.lines.lowest(displayDate(data.cash.lowest_date, locale)) }] : []}
      figures={
        <Table
          caption={caption}
          captionHidden
          rows={days}
          rowKey={(d) => d.date}
          columns={[
            { key: 'date', header: labStrings.lines.date, label: labStrings.lines.date, render: (d) => displayDate(d.date, locale) },
            { key: 'cash', header: `${b.cashTotal} (${code})`, label: b.cashTotal, align: 'end', render: (d) => <Money amount={d.balance} currency={code} variant="table" /> },
          ]}
        />
      }
    />
  );
}

function NetWorthChart({ data }: { data: BaselineData }) {
  const locale = useLocale();
  const points = data.monthly.points;
  const months = useMemo(() => points.map((p) => p.month), [points]);
  const at = useMemo(() => months.map((m) => displayMonth(m, locale)), [months, locale]);
  const last = points[points.length - 1];
  const step = data.monthly.horizon_years > 10 ? 5 : 1;
  const caption = b.netWorthCaption(
    displayMonth(last?.month ?? '', locale),
    visibleAmount(last?.net_worth ?? '', data.currency, 'prose', { locale }),
    data.monthly.inflation === null ? b.noInflation : b.todaysMoney,
  );
  const code = data.currency.toUpperCase();
  return (
    <LineChart
      caption={caption}
      currency={data.currency}
      at={at}
      ticks={{ wide: yearTicks(months, step), narrow: yearTicks(months, step * 2) }}
      series={[{ label: labStrings.baselineColumn, values: points.map((p) => p.net_worth) }]}
      figures={
        <Table
          caption={caption}
          captionHidden
          rows={points}
          rowKey={(p) => p.date}
          columns={[
            { key: 'date', header: labStrings.lines.month, label: labStrings.lines.month, render: (p) => displayDate(p.date, locale) },
            { key: 'cash', header: `${b.cashTotal} (${code})`, label: b.cashTotal, align: 'end', render: (p) => <Money amount={p.cash} currency={code} variant="table" /> },
            { key: 'inv', header: `${b.investments} (${code})`, label: b.investments, align: 'end', render: (p) => <Money amount={p.investments} currency={code} variant="table" /> },
            { key: 'other', header: `${b.otherAssets} (${code})`, label: b.otherAssets, align: 'end', render: (p) => <Money amount={p.other_assets} currency={code} variant="table" /> },
            { key: 'debts', header: `${b.debts} (${code})`, label: b.debts, align: 'end', render: (p) => <Money amount={p.debts} currency={code} variant="table" /> },
            { key: 'nw', header: `${b.netWorthTotal} (${code})`, label: b.netWorthTotal, align: 'end', render: (p) => <Money amount={p.net_worth} currency={code} variant="table" /> },
          ]}
        />
      }
    />
  );
}

function Flows({ data }: { data: BaselineData }) {
  const locale = useLocale();
  const f = data.flows;
  const months = data.months_observed;
  if (!months.length) return <Empty>{b.flowsNone}</Empty>;
  const cur = data.currency;
  return (
    <Panel>
      <Rows>
        <Row label={b.income}>
          <Money amount={f.monthly_income} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.expenses}>
          <Money amount={f.monthly_expenses} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.surplus} total>
          <Money amount={f.monthly_surplus} currency={cur} variant="table" withCode />
        </Row>
        {f.savings_rate ? <Row label={b.savingsRate}>{formatRatio(f.savings_rate, { locale })}</Row> : null}
        {f.essential_monthly ? (
          <Row label={b.essential}>
            <Money amount={f.essential_monthly} currency={cur} variant="table" withCode />
          </Row>
        ) : null}
      </Rows>
      {f.essential_monthly ? null : <Provenance>{b.noEssential}</Provenance>}
      {f.need_coverage ? <Provenance>{b.needCoverage(formatRatio(f.need_coverage, { locale }))}</Provenance> : null}
      <Provenance>{b.flowsHelp(displayMonth(months[0] ?? '', locale), displayMonth(months[months.length - 1] ?? '', locale), months.length)}</Provenance>
    </Panel>
  );
}

function Balances({ data }: { data: BaselineData }) {
  const t = data.totals;
  const cur = data.currency;
  const code = cur.toUpperCase();
  return (
    <Panel>
      <Rows>
        <Row label={b.cashTotal}>
          <Money amount={t.cash} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.investments}>
          <Money amount={t.investments} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.otherAssets}>
          <Money amount={t.other_assets} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.debts}>
          <Money amount={t.debts} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.otherLiabilities}>
          <Money amount={t.other_liabilities} currency={cur} variant="table" withCode />
        </Row>
        <Row label={b.netWorthTotal} total>
          <Money amount={t.net_worth} currency={cur} variant="table" withCode />
        </Row>
      </Rows>
      <Table<BaselineBalance>
        caption={b.accounts}
        rows={data.balances}
        rowKey={(a) => a.account_id}
        columns={[
          { key: 'name', header: b.account, label: b.account, render: (a) => a.name },
          { key: 'role', header: b.role, label: b.role, render: (a) => b.roles[a.role] ?? a.role },
          {
            key: 'own',
            header: b.inItsCurrency,
            label: b.inItsCurrency,
            align: 'end',
            render: (a) => (a.currency.toUpperCase() === code ? null : <Money amount={a.amount} currency={a.currency} variant="table" withCode />),
          },
          {
            key: 'value',
            header: b.value(code),
            label: b.value(code),
            align: 'end',
            render: (a) => (a.value === null ? <span className="muted">{b.noRate}</span> : <Money amount={a.value} currency={cur} variant="table" />),
          },
        ]}
      />
    </Panel>
  );
}

function Debts({ data }: { data: BaselineData }) {
  const locale = useLocale();
  const code = data.currency.toUpperCase();
  if (!data.debts.length) return <Empty>{b.debtsNone}</Empty>;
  return (
    <Panel>
      <Table<BaselineDebt>
        caption={b.debtsTitle}
        captionHidden
        rows={data.debts}
        rowKey={(d) => d.debt_id}
        columns={[
          { key: 'name', header: b.debt, label: b.debt, render: (d) => d.name },
          { key: 'owes', header: b.owes(code), label: b.owes(code), align: 'end', render: (d) => <Money amount={d.balance} currency={code} variant="table" /> },
          { key: 'apr', header: b.apr, label: b.apr, align: 'end', render: (d) => rateText(d.apr, locale) },
          { key: 'min', header: b.minimum(code), label: b.minimum(code), align: 'end', render: (d) => <Money amount={d.minimum_payment} currency={code} variant="table" /> },
          { key: 'off', header: b.paidOff, label: b.paidOff, align: 'end', render: (d) => monthText(d.paid_off, locale) },
          { key: 'int', header: b.debtInterest(code), label: b.debtInterest(code), align: 'end', render: (d) => <Money amount={d.total_interest} currency={code} variant="table" /> },
        ]}
      />
      {data.debt_free ? <Provenance>{b.debtFree(displayMonth(data.debt_free, locale))}</Provenance> : null}
    </Panel>
  );
}

interface AssumptionRow {
  key: string;
  assumption: FiAssumption;
}

function Assumptions({ data }: { data: BaselineData }) {
  const locale = useLocale();
  const a = data.assumptions;
  const rows: AssumptionRow[] = [
    { key: 'real_return', assumption: a.real_return },
    { key: 'safe_withdrawal_rate', assumption: a.safe_withdrawal_rate },
    { key: 'surplus_invested', assumption: a.surplus_invested },
    ...(a.inflation ? [{ key: 'inflation', assumption: a.inflation }] : []),
  ];
  const origin = (x: FiAssumption) =>
    x.origin === 'placeholder' ? (
      <span className="placeholder-tag">
        <span className="warn-mark" aria-hidden="true">
          !
        </span>{' '}
        {b.placeholderTag}
      </span>
    ) : x.origin === 'strategy' ? (
      b.fromStrategy
    ) : (
      b.yours
    );
  return (
    <Panel>
      <p className="section-help">{b.assumptionsHelp}</p>
      <Table<AssumptionRow>
        caption={b.assumptions}
        captionHidden
        rows={rows}
        rowKey={(r) => r.key}
        columns={[
          { key: 'name', header: b.assumption, label: b.assumption, render: (r) => b.names[r.key] ?? r.key },
          { key: 'value', header: b.assumptionValue, label: b.assumptionValue, align: 'end', render: (r) => rateText(r.assumption.value, locale) },
          { key: 'origin', header: b.setBy, label: b.setBy, render: (r) => origin(r.assumption) },
          { key: 'source', header: b.source, label: b.source, render: (r) => [r.assumption.source, r.assumption.note].filter(Boolean).join(' · ') },
        ]}
      />
      <Provenance>{a.message}</Provenance>
    </Panel>
  );
}

function Rates({ data }: { data: BaselineData }) {
  const locale = useLocale();
  if (!data.rates.length) return null;
  return (
    <Section label={b.rates}>
      <Panel>
        {data.rates.map((r) => (
          <Provenance key={r.currency}>{r.rate ? b.rate(r.currency, r.rate, r.source ?? '', displayDate(r.as_of, locale)) : `${r.currency}: ${b.noRate}`}</Provenance>
        ))}
      </Panel>
    </Section>
  );
}

function BaselinePage({ data }: { data: BaselineData }) {
  const locale = useLocale();
  return (
    <Grid>
      <Section label={b.cash} wide>
        <Panel>
          <CashChart data={data} />
        </Panel>
      </Section>
      <Section label={labStrings.basis.label}>
        <Basis
          asOf={labStrings.basis.asOf(displayDate(data.as_of, locale), data.currency)}
          placeholders={data.placeholders}
          isStale={false}
          dataAsOf={null}
          notes={data.notes}
        />
      </Section>
      <Section label={b.netWorth(labStrings.figure.years(data.monthly.horizon_years))} wide>
        <Panel>
          <NetWorthChart data={data} />
        </Panel>
      </Section>
      <Section label={b.flows}>
        <Flows data={data} />
      </Section>
      <Section label={b.assumptions} full>
        <Assumptions data={data} />
      </Section>
      <Section label={b.balances} wide>
        <Balances data={data} />
      </Section>
      <Rates data={data} />
      <Section label={b.debtsTitle} full>
        <Debts data={data} />
      </Section>
    </Grid>
  );
}

export function Baseline() {
  const locale = useLocale();
  const query = useRead('baseline.get', baselineGet);
  return (
    <Page title={b.title} description={query.data ? b.description(displayDate(query.data.as_of, locale)) : labStrings.places.baseline}>
      <LabNav />
      <Loaded query={query} lines={8}>
        {(data) => (
          <>
            <BaselinePage data={data} />
            <Provenance>
              {b.fingerprint}{' '}
              <code className="hash">{data.fingerprint}</code>
            </Provenance>
          </>
        )}
      </Loaded>
    </Page>
  );
}

export default Baseline;
