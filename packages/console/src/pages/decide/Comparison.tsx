/**
 * Options side by side, as Salli compares them (docs/scenarios.md,
 * "Comparing options"): each one's figures against one baseline, what each
 * gains and gives up against each other one, how the answer moves with the
 * return, and where it turns. In the order the options were given, never an
 * order of merit; every figure the server's, shown exactly.
 */
import type { ScenarioBreakEven, ScenarioComparison, ScenarioRun, TradeDelta } from '@leafmonkeylabs/salli-sdk';
import type { ReactNode } from 'react';
import { ChartFigure } from '../../kit/chart/ChartFigure';
import { DotChart } from '../../kit/chart/DotChart';
import { RangeChart } from '../../kit/chart/RangeChart';
import { displayDate } from '../../kit/dates';
import { Blank } from '../../kit/layout';
import { Money, visibleAmount } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';
import { dayText, daysChange, monthsChange, monthsOfSpending, monthText, rateText, tradeFigure } from './format';

const l = labStrings;
const f = l.figure;
const cs = l.compare;

interface FigureRow {
  key: string;
  label: string;
  baseline: ReactNode;
  values: ReactNode[];
  change?: ReactNode;
}

/** The figures of one or more runs against their one baseline. */
export function SideBySide({ runs, labels, caption }: { runs: readonly ScenarioRun[]; labels: readonly string[]; caption: string }) {
  const locale = useLocale();
  const first = runs[0];
  if (!first) return null;
  const cur = first.currency;
  const one = runs.length === 1;
  const money = (amount: string | null | undefined, signed = false) => <Money amount={amount ?? null} currency={cur} variant="table" signed={signed} />;
  const rows: FigureRow[] = [
    {
      key: 'lowest',
      label: f.lowestCash,
      baseline: money(first.cash.lowest.baseline),
      values: runs.map((r) => money(r.cash.lowest.scenario)),
      change: money(first.cash.lowest.delta, true),
    },
    {
      key: 'lowest-on',
      label: f.lowestOn,
      baseline: dayText(first.cash.lowest_date.baseline, locale),
      values: runs.map((r) => dayText(r.cash.lowest_date.scenario, locale)),
      change: daysChange(first.cash.lowest_date.delta_days),
    },
    {
      key: 'at-end',
      label: f.cashBy(displayDate(first.cash.end, locale)),
      baseline: money(first.cash.at_end.baseline),
      values: runs.map((r) => money(r.cash.at_end.scenario)),
      change: money(first.cash.at_end.delta, true),
    },
    {
      key: 'safe',
      label: f.safeToSpend,
      baseline: money(first.cash.safe_to_spend.baseline),
      values: runs.map((r) => money(r.cash.safe_to_spend.scenario)),
      change: money(first.cash.safe_to_spend.delta, true),
    },
    ...(first.resilience.basis
      ? [
          {
            key: 'months',
            label: f.emergencyMonths,
            baseline: monthsOfSpending(first.resilience.lowest.baseline, locale),
            values: runs.map((r) => monthsOfSpending(r.resilience.lowest.scenario, locale)),
            change: monthsOfSpending(first.resilience.lowest.delta, locale),
          },
        ]
      : []),
    ...first.monthly.map((point, i) => ({
      key: `nw-${point.years}`,
      label: f.netWorthIn(f.years(point.years)),
      baseline: money(point.net_worth.baseline),
      values: runs.map((r) => money(r.monthly[i]?.net_worth.scenario)),
      change: money(point.net_worth.delta, true),
    })),
    {
      key: 'interest',
      label: f.interest,
      baseline: money(first.debts.total_interest.baseline),
      values: runs.map((r) => money(r.debts.total_interest.scenario)),
      change: money(first.debts.total_interest.delta, true),
    },
    {
      key: 'debt-free',
      label: f.debtFree,
      baseline: monthText(first.debts.debt_free.baseline, locale),
      values: runs.map((r) => monthText(r.debts.debt_free.scenario, locale)),
      change: monthsChange(first.debts.debt_free.delta_months),
    },
    {
      key: 'fi-number',
      label: f.fiNumber,
      baseline: money(first.fi.fi_number.baseline),
      values: runs.map((r) => money(r.fi.fi_number.scenario)),
      change: money(first.fi.fi_number.delta, true),
    },
    {
      key: 'fi',
      label: f.fiMonth,
      baseline: monthText(first.fi.fi_month.baseline, locale),
      values: runs.map((r) => monthText(r.fi.fi_month.scenario, locale)),
      change: monthsChange(first.fi.fi_month.delta_months),
    },
  ];
  const code = cur.toUpperCase();
  return (
    <Table<FigureRow>
      caption={caption}
      captionHidden
      rows={rows}
      rowKey={(row) => row.key}
      columns={[
        { key: 'figure', header: l.figureColumn, label: l.figureColumn, render: (row) => row.label },
        { key: 'baseline', header: `${l.baselineColumn} (${code})`, label: l.baselineColumn, align: 'end', render: (row) => row.baseline },
        ...labels.map((label, i) => ({
          key: `o${i}`,
          header: `${label} (${code})`,
          label,
          align: 'end' as const,
          render: (row: FigureRow) => row.values[i] ?? <Blank>{f.none}</Blank>,
        })),
        ...(one ? [{ key: 'change', header: `${labStrings.entry.difference} (${code})`, label: labStrings.entry.difference, align: 'end' as const, render: (row: FigureRow) => row.change ?? <Blank>{f.none}</Blank> }] : []),
      ]}
    />
  );
}

function DeltaItem({ delta, currency }: { delta: TradeDelta; currency: string }) {
  const locale = useLocale();
  const name = tradeFigure(delta.figure);
  if (delta.unit === 'month') {
    const n = typeof delta.delta === 'number' ? delta.delta : null;
    return (
      <li>
        {name}: {n === null ? f.against(monthText(delta.this, locale), monthText(delta.other, locale)) : monthsChange(n)}
      </li>
    );
  }
  const value = typeof delta.delta === 'string' ? delta.delta : null;
  return (
    <li>
      {name}: {delta.unit === 'months_of_spending' ? monthsOfSpending(value, locale) : <Money amount={value} currency={currency} signed />}
    </li>
  );
}

/** For each two options once, in the order given: where one is ahead, where behind. */
export function Trade({ data }: { data: ScenarioComparison }) {
  const pairs = data.trade.filter((t) => data.labels.indexOf(t.option) < data.labels.indexOf(t.against));
  return (
    <div className="trade">
      <p className="section-help">{cs.tradeHelp}</p>
      {pairs.map((t) => (
        <div key={`${t.option}|${t.against}`} className="trade-pair">
          <h3 className="panel-title">{f.against(t.option, t.against)}</h3>
          <div className="trade-columns">
            <div>
              <p className="subhead">{cs.aheadOn}</p>
              {t.gains.length ? (
                <ul className="list">
                  {t.gains.map((d) => (
                    <DeltaItem key={d.figure} delta={d} currency={data.currency} />
                  ))}
                </ul>
              ) : (
                <p className="empty">{cs.nothing}</p>
              )}
            </div>
            <div>
              <p className="subhead">{cs.behindOn}</p>
              {t.gives_up.length ? (
                <ul className="list">
                  {t.gives_up.map((d) => (
                    <DeltaItem key={d.figure} delta={d} currency={data.currency} />
                  ))}
                </ul>
              ) : (
                <p className="empty">{cs.nothing}</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Each option's net worth at the horizon at three real returns, drawn and tabled. */
export function Sensitivity({ data }: { data: ScenarioComparison }) {
  const locale = useLocale();
  const s = data.sensitivity;
  const rates = [s.real_returns.conservative, s.real_returns.base, s.real_returns.growth].map((r) => rateText(r, locale));
  const [conservative = '', base = '', growth = ''] = rates;
  const code = data.currency.toUpperCase();
  const caption = cs.sensitivityCaption(f.years(data.horizon_years), conservative, base, growth);
  const readings = (['conservative', 'base', 'growth'] as const).map((k) => k);
  return (
    <DotChart
      caption={caption}
      readings={rates.map((r) => cs.sensitivityReading(r))}
      rows={s.options.map((o) => ({ label: o.option, values: readings.map((k) => o[k].net_worth.scenario) }))}
      format={(v) => visibleAmount(v, data.currency, 'prose', { locale })}
      figures={
        <Table
          caption={caption}
          captionHidden
          rows={s.options}
          rowKey={(o) => o.option}
          columns={[
            { key: 'option', header: cs.sensitivityOption, label: cs.sensitivityOption, render: (o) => o.option },
            ...readings.flatMap((k, i) => [
              {
                key: `${k}-nw`,
                header: `${cs.sensitivityNetWorth(rates[i] ?? '')} (${code})`,
                label: cs.sensitivityNetWorth(rates[i] ?? ''),
                align: 'end' as const,
                render: (o: (typeof s.options)[number]) => <Money amount={o[k].net_worth.scenario} currency={code} variant="table" />,
              },
              {
                key: `${k}-fi`,
                header: cs.sensitivityFi(rates[i] ?? ''),
                label: cs.sensitivityFi(rates[i] ?? ''),
                align: 'end' as const,
                render: (o: (typeof s.options)[number]) => monthText(o[k].fi_month.scenario, locale),
              },
            ]),
          ]}
        />
      }
    />
  );
}

function breakEvenValue(b: ScenarioBreakEven, currency: string, locale: string | undefined): (value: string) => string {
  return (value) => (b.unit === 'rate' ? rateText(value, locale) : visibleAmount(value, currency, 'prose', { locale }));
}

/** Where the answer turns: each break-even's sentence, and its value on the range Salli searched. */
export function BreakEvens({ items, currency }: { items: readonly ScenarioBreakEven[]; currency: string }) {
  const locale = useLocale();
  if (!items.length) return <p className="empty">{cs.breakEvensNone}</p>;
  const caption = cs.breakEvensCaption(items.length);
  return (
    <ChartFigure
      caption={caption}
      figures={
        <Table
          caption={caption}
          captionHidden
          rows={items.map((b, i) => ({ b, i }))}
          rowKey={({ i }) => String(i)}
          columns={[
            { key: 'kind', header: cs.kindColumn, label: cs.kindColumn, render: ({ b }) => cs.kind[b.kind] ?? b.kind },
            { key: 'option', header: cs.optionColumn, label: cs.optionColumn, render: ({ b }) => b.option ?? b.options.join(', ') },
            {
              key: 'value',
              header: cs.valueColumn,
              label: cs.valueColumn,
              align: 'end',
              render: ({ b }) => (b.value === null ? (b.ahead ? cs.aheadAcross(b.ahead) : cs.noneInRange) : breakEvenValue(b, currency, locale)(b.value)),
            },
            {
              key: 'range',
              header: cs.rangeColumn,
              label: cs.rangeColumn,
              align: 'end',
              render: ({ b }) => cs.range(breakEvenValue(b, currency, locale)(b.low), breakEvenValue(b, currency, locale)(b.high)),
            },
          ]}
        />
      }
    >
      <ul className="break-evens">
        {items.map((b, i) => (
          <li key={i}>
            <p>
              <span className="break-even-kind">{cs.kind[b.kind] ?? b.kind}.</span> {b.says}
            </p>
            <RangeChart low={b.low} high={b.high} value={b.value} format={breakEvenValue(b, currency, locale)} noneLabel={b.ahead ? cs.aheadAcross(b.ahead) : cs.noneInRange} />
          </li>
        ))}
      </ul>
    </ChartFigure>
  );
}
