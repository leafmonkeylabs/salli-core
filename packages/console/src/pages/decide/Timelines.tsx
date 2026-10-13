/**
 * A run's two timelines, drawn (docs/design/console.md, section 4,
 * "Charts"): cash day by day for the as-of month and the twelve after it, a
 * step line with each low point labelled and a shortfall shaded; and net
 * worth month by month to the horizon, in today's money, labelled at the
 * lines' ends. The baseline once, then each option in the order given. The
 * lines are the server's (`?timeline=true`); each label is its figure.
 */
import type { ScenarioRun } from '@leafmonkeylabs/salli-sdk';
import { useMemo } from 'react';
import { displayDate, displayMonth } from '../../kit/dates';
import { LineChart, type LineMark, type LineSeries } from '../../kit/chart/LineChart';
import { Money, visibleAmount } from '../../kit/Money';
import { Table } from '../../kit/Table';
import { useLocale } from '../../preferences';
import { labStrings } from '../../lab-strings';

const t = labStrings.lines;

/** Every `step`th first-of-the-month, and the last day: where the axis says a date. */
export function monthTicks(dates: readonly string[], step: number): number[] {
  const firsts = dates.flatMap((d, i) => (d.endsWith('-01') ? [i] : []));
  return firsts.filter((_, k) => k % step === 0);
}

/**
 * The as-of date, then every `step`th whole year on: the month-ends in the
 * as-of month's month of the year (the first of them is the as-of month's
 * own end, beside the as-of date, so it isn't labelled again).
 */
export function yearTicks(months: readonly string[], step: number): number[] {
  const month = (months[0] ?? '').slice(5, 7);
  const years = months.flatMap((m, i) => (i > 0 && m.slice(5, 7) === month ? [i] : []));
  return [0, ...years.filter((_, k) => k > 0 && k % step === 0)];
}

interface DayRow {
  date: string;
  values: ReadonlyArray<string | null>;
}

export function CashLines({ runs, labels }: { runs: readonly ScenarioRun[]; labels: readonly string[] }) {
  const locale = useLocale();
  const first = runs[0];
  const days = first?.timeline?.daily ?? [];
  const dates = useMemo(() => days.map((d) => d.date), [days]);
  const at = useMemo(() => dates.map((d) => displayMonth(d.slice(0, 7), locale)), [dates, locale]);
  if (!first || !days.length) return null;
  const series: LineSeries[] = [
    { label: labStrings.baselineColumn, values: days.map((d) => d.baseline) },
    ...runs.map((run, i) => ({ label: labels[i] ?? run.label ?? '', values: (run.timeline?.daily ?? []).map((d) => d.scenario) })),
  ];
  const marks: LineMark[] = [];
  const seen = new Set<number>();
  const lowAt = (date: string): number => dates.indexOf(date);
  const baselineLow = lowAt(first.cash.lowest_date.baseline);
  if (baselineLow >= 0) {
    marks.push({ series: 0, index: baselineLow, label: t.lowest(displayDate(first.cash.lowest_date.baseline, locale)) });
    seen.add(baselineLow);
  }
  runs.forEach((run, i) => {
    const index = lowAt(run.cash.lowest_date.scenario);
    if (index >= 0 && !seen.has(index)) {
      marks.push({ series: i + 1, index, label: t.lowest(displayDate(run.cash.lowest_date.scenario, locale)) });
      seen.add(index);
    }
  });
  const code = first.currency.toUpperCase();
  const caption = t.cashCaption(
    displayDate(first.cash.start, locale),
    displayDate(first.cash.end, locale),
    visibleAmount(first.cash.lowest.baseline ?? '', first.currency, 'prose', { locale }),
    displayDate(first.cash.lowest_date.baseline, locale),
  );
  const rows: DayRow[] = days.map((d, i) => ({ date: d.date, values: series.map((s) => s.values[i] ?? null) }));
  return (
    <LineChart
      caption={caption}
      currency={first.currency}
      at={at}
      ticks={{ wide: monthTicks(dates, 2), narrow: monthTicks(dates, 4) }}
      series={series}
      step
      marks={marks}
      figures={
        <Table<DayRow>
          caption={caption}
          captionHidden
          rows={rows}
          rowKey={(r) => r.date}
          columns={[
            { key: 'date', header: t.date, label: t.date, render: (r) => displayDate(r.date, locale) },
            ...series.map((s, k) => ({
              key: `s${k}`,
              header: t.column(s.label, code),
              label: s.label,
              align: 'end' as const,
              render: (r: DayRow) => <Money amount={r.values[k] ?? null} currency={code} variant="table" />,
            })),
          ]}
        />
      }
    />
  );
}

interface MonthRow {
  month: string;
  date: string;
  values: ReadonlyArray<string | null>;
}

export function NetWorthLines({ runs, labels }: { runs: readonly ScenarioRun[]; labels: readonly string[] }) {
  const locale = useLocale();
  const first = runs[0];
  const points = first?.timeline?.monthly ?? [];
  const months = useMemo(() => points.map((p) => p.month), [points]);
  const at = useMemo(() => months.map((m) => displayMonth(m, locale)), [months, locale]);
  if (!first || !points.length) return null;
  const series: LineSeries[] = [
    { label: labStrings.baselineColumn, values: points.map((p) => p.net_worth.baseline) },
    ...runs.map((run, i) => ({ label: labels[i] ?? run.label ?? '', values: (run.timeline?.monthly ?? []).map((p) => p.net_worth.scenario) })),
  ];
  const last = points[points.length - 1];
  const code = first.currency.toUpperCase();
  const caption = t.netWorthCaption(
    displayMonth(last?.month ?? '', locale),
    labStrings.figure.years(first.horizon_years),
    visibleAmount(last?.net_worth.baseline ?? '', first.currency, 'prose', { locale }),
  );
  const step = first.horizon_years > 10 ? 5 : 1;
  const rows: MonthRow[] = points.map((p, i) => ({ month: p.month, date: p.date, values: series.map((s) => s.values[i] ?? null) }));
  return (
    <LineChart
      caption={caption}
      currency={first.currency}
      at={at}
      ticks={{ wide: yearTicks(months, step), narrow: yearTicks(months, step * 2) }}
      series={series}
      figures={
        <Table<MonthRow>
          caption={caption}
          captionHidden
          rows={rows}
          rowKey={(r) => r.date}
          columns={[
            { key: 'date', header: t.month, label: t.month, render: (r) => displayDate(r.date, locale) },
            ...series.map((s, k) => ({
              key: `s${k}`,
              header: t.column(s.label, code),
              label: s.label,
              align: 'end' as const,
              render: (r: MonthRow) => <Money amount={r.values[k] ?? null} currency={code} variant="table" />,
            })),
          ]}
        />
      }
    />
  );
}
