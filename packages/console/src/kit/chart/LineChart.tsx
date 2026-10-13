/**
 * Lines over time (docs/design/console.md, section 4, "Charts"): the daily
 * cash forecast as a step line, the monthly timeline as lines in today's
 * money. The first series is the baseline, in ink; the others are options,
 * in ledger green and graphite, told apart by dash pattern and by their
 * labels at the line's end as well as by colour (decision 11). Points the
 * caller marks (the low point) are labelled with the server's own figure.
 * Below zero is shaded oxblood at 12%: a shortfall.
 *
 * Every label is `visibleAmount` of the original string; positions come
 * only from the geometry module. Phones get their own drawing, with fewer
 * dates and the labels below the plot.
 */
import { compareAmounts } from '@leafmonkeylabs/salli-sdk';
import type { ReactNode } from 'react';
import { useLocale } from '../../preferences';
import { visibleAmount } from '../Money';
import { ChartFigure } from './ChartFigure';
import { amountScale, dayScale, extent, indexScale, linePath, spread, stepPath } from './geometry';
import { fitTicks } from './ticks';

export interface LineSeries {
  /** What the line is: "Baseline", or an option's label. */
  label: string;
  /** The amount at each point, as the API sent it; null where there is none. */
  values: ReadonlyArray<string | null>;
}

export interface LineMark {
  /** Which series, and which point of it. */
  series: number;
  index: number;
  /** The words beside the point: "Lowest, Nov 15". The amount is added. */
  label: string;
}

export interface LineChartProps {
  /** What the chart shows and its key figure, as a sentence: its text alternative. */
  caption: string;
  currency: string;
  /** Each point's date or month, as shown on the axis. */
  at: ReadonlyArray<string>;
  /**
   * Each point's day (YYYY-MM-DD), when the points fall on irregular days:
   * they are then placed by their dates rather than evenly.
   */
  days?: ReadonlyArray<string>;
  /** The points whose date the axis labels, on a wide screen and on a phone. */
  ticks: { wide: readonly number[]; narrow: readonly number[] };
  /** The baseline first, then each option. */
  series: readonly LineSeries[];
  /** Steps (a balance from day to day) rather than straight lines. */
  step?: boolean;
  marks?: readonly LineMark[];
  /** Draw zero, and shade below it, even when nothing goes below. */
  zero?: boolean;
  /**
   * Shade below zero as a shortfall (the default). Off for a balance that is
   * below zero by nature: what a card or a loan account holds.
   */
  shortfall?: boolean;
  /**
   * A level the lines are read against (the FI number), drawn across the
   * plot as a dashed hairline and labelled with the server's figure.
   */
  reference?: { value: string; label: string };
  /** The same data as a table: the accessible way in. */
  figures: ReactNode;
}

interface Layout {
  width: number;
  height: number;
  top: number;
  bottom: number;
  left: number;
  right: number;
  font: number;
}

const WIDE: Layout = { width: 680, height: 260, top: 18, bottom: 28, left: 8, right: 168, font: 12 };
const NARROW: Layout = { width: 320, height: 210, top: 18, bottom: 24, left: 4, right: 8, font: 11 };

/** The stroke class of the nth series: the baseline, then the options' patterns. */
export function seriesClass(index: number): string {
  return index === 0 ? 'chart-line-baseline' : `chart-line-option chart-line-${((index - 1) % 5) + 1}`;
}

function Plot({ props, layout, variant }: { props: LineChartProps; layout: Layout; variant: 'wide' | 'narrow' }) {
  const locale = useLocale();
  const { series, at, currency, marks = [] } = props;
  const { width, height, top, bottom, left, right, font } = layout;
  const all = [...series.flatMap((s) => s.values.filter((v): v is string => v !== null)), ...(props.reference ? [props.reference.value] : [])];
  const span = extent(all);
  const below = span ? compareAmounts(span.low, '0') < 0 : false;
  const withZero = props.zero || below;
  const y = amountScale(withZero ? [...all, '0'] : all, [height - bottom, top], { withZero });
  const x = props.days ? dayScale(props.days, [left, width - right]) : indexScale(at.length, [left, width - right]);
  const path = props.step ? stepPath : linePath;
  const zero = y('0');
  const ticks = variant === 'wide' ? props.ticks.wide : props.ticks.narrow;
  const ends = series.map((s) => {
    let i = s.values.length - 1;
    while (i >= 0 && s.values[i] === null) i -= 1;
    return i;
  });
  const endY = spread(
    series.map((s, k) => y(s.values[ends[k] ?? 0] ?? '0')),
    font * 2.4,
    [top + font, height - bottom - font],
  );
  return (
    <svg className={`chart-svg chart-${variant}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={props.caption}>
      {withZero ? (
        <>
          {below && props.shortfall !== false ? <rect className="chart-shortfall" x={left} width={width - right - left} y={zero} height={Math.max(0, height - bottom - zero)} /> : null}
          <line className="chart-zero" x1={left} x2={width - right} y1={zero} y2={zero} />
        </>
      ) : null}
      <line className="chart-axis" x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} />
      {props.reference ? (
        <g>
          <line className="chart-reference" x1={left} x2={width - right} y1={y(props.reference.value)} y2={y(props.reference.value)} />
          <text className="chart-mark-label" x={left + 2} y={y(props.reference.value) - font * 0.6} fontSize={font}>
            {`${props.reference.label} ${visibleAmount(props.reference.value, currency, 'prose', { locale })}`}
          </text>
        </g>
      ) : null}
      {series.map((s, k) => {
        const points = s.values.flatMap((v, i) => (v === null ? [] : [[x(i), y(v)] as const]));
        return <path key={s.label} className={seriesClass(k)} d={path(points)} />;
      })}
      {marks.map((mark) => {
        const value = series[mark.series]?.values[mark.index];
        if (!value) return null;
        const cx = x(mark.index);
        const cy = y(value);
        // A low point's label goes below it, where the line isn't, when there is room.
        const above = cy + font * 3 > height - bottom && cy - top > font * 3;
        const anchor = cx > (width - right) * 0.7 ? 'end' : cx < width * 0.2 ? 'start' : 'middle';
        return (
          <g key={`${mark.series}-${mark.index}`}>
            <circle className="chart-point" cx={cx} cy={cy} r={3} />
            <text className="chart-mark-label" x={cx} y={above ? cy - font * 1.9 : cy + font * 1.4} fontSize={font} textAnchor={anchor}>
              <tspan x={cx}>{mark.label}</tspan>
              <tspan x={cx} dy={font * 1.2}>
                {visibleAmount(value, currency, 'prose', { locale })}
              </tspan>
            </text>
          </g>
        );
      })}
      {fitTicks(
        ticks.flatMap((i) => (at[i] === undefined ? [] : [{ index: i, x: x(i), text: at[i] as string }])),
        font,
        [left, width - right],
      ).map((tick) => (
        <text key={tick.index} className="chart-tick" x={tick.x} y={height - bottom / 3} fontSize={font} textAnchor={tick.anchor}>
          {tick.text}
        </text>
      ))}
      {variant === 'wide'
        ? series.map((s, k) => {
            const i = ends[k] ?? -1;
            const value = s.values[i];
            if (!value) return null;
            const ly = endY[k] ?? y(value);
            return (
              <text key={s.label} className="chart-end-label" x={x(i) + 10} y={ly - font * 0.2} fontSize={font}>
                <tspan x={x(i) + 10}>{s.label}</tspan>
                <tspan x={x(i) + 10} dy={font * 1.2} className="chart-end-amount">
                  {visibleAmount(value, currency, 'prose', { locale })}
                </tspan>
              </text>
            );
          })
        : null}
    </svg>
  );
}

/** The key below a chart: each line's pattern, its name and where it ends. */
export function LineKey({ series, currency, narrowOnly }: { series: readonly LineSeries[]; currency: string; narrowOnly?: boolean }) {
  const locale = useLocale();
  return (
    <ul className={['chart-key', narrowOnly ? 'chart-key-narrow' : ''].filter(Boolean).join(' ')} aria-hidden="true">
      {series.map((s, k) => {
        const last = [...s.values].reverse().find((v): v is string => v !== null);
        return (
          <li key={s.label}>
            <svg className="chart-swatch" viewBox="0 0 28 8">
              <line className={seriesClass(k)} x1={0} x2={28} y1={4} y2={4} />
            </svg>
            <span>{s.label}</span>
            {last ? <span className="chart-key-amount">{visibleAmount(last, currency, 'prose', { locale })}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

export function LineChart(props: LineChartProps) {
  return (
    <ChartFigure caption={props.caption} figures={props.figures}>
      <Plot props={props} layout={WIDE} variant="wide" />
      <Plot props={props} layout={NARROW} variant="narrow" />
      <LineKey series={props.series} currency={props.currency} narrowOnly />
    </ChartFigure>
  );
}
