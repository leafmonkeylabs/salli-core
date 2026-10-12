/**
 * Paired bars, group by group (docs/design/console.md, section 4, "Cash
 * flow"): for each month, two amounts side by side from zero, such as
 * income in ledger green and spending in graphite, with a figure under each
 * pair that the server computed (what was left), never one this works out.
 * A group the caller marks as partial (this month so far) is drawn lighter
 * and says so in the key. Every label is the server's own string; positions
 * come only from the geometry module. Phones get their own drawing, with
 * the first and last groups labelled and the figures in the table.
 */
import type { ReactNode } from 'react';
import { useLocale } from '../../preferences';
import { visibleAmount } from '../Money';
import { ChartFigure } from './ChartFigure';
import { amountScale, bandScale } from './geometry';
import { fitTicks } from './ticks';

export interface BarGroup {
  /** What the group is, as the axis shows it ("Apr 2026"). */
  label: string;
  /** One amount per series, as the API sent it. */
  values: readonly [string, string];
  /** The server's figure for the pair, shown under it on a wide screen. */
  figure?: string | undefined;
  /** Drawn lighter: not a whole period yet. */
  partial?: boolean;
}

export interface BarChartProps {
  /** What the chart shows and its key figure, as a sentence: its text alternative. */
  caption: string;
  currency: string;
  /** The two series' names, in the order of each group's values. */
  series: readonly [string, string];
  groups: readonly BarGroup[];
  /** The key's words for a partial group. */
  partialLabel?: string;
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

const WIDE: Layout = { width: 680, height: 250, top: 12, bottom: 46, left: 8, right: 8, font: 12 };
const NARROW: Layout = { width: 320, height: 200, top: 12, bottom: 24, left: 4, right: 4, font: 11 };

function Plot({ props, layout, variant }: { props: BarChartProps; layout: Layout; variant: 'wide' | 'narrow' }) {
  const locale = useLocale();
  const { groups, currency } = props;
  const { width, height, top, bottom, left, right, font } = layout;
  const y = amountScale(
    groups.flatMap((g) => [...g.values]),
    [height - bottom, top],
  );
  const band = bandScale(groups.length, [left, width - right], 0.3);
  const zero = y('0');
  const bar = Math.max(1, band.width / 2 - 1);
  // The groups the axis names: every one that fits on a wide drawing, the first and last on a phone's.
  const candidates = groups.flatMap((g, i) => (variant === 'wide' || i === 0 || i === groups.length - 1 ? [{ index: i, x: band.at(i), text: g.label }] : []));
  const ticks = new Map(fitTicks(candidates, font, [left, width - right]).map((t) => [t.index, t]));
  return (
    <svg className={`chart-svg chart-${variant}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={props.caption}>
      {groups.map((g, i) => {
        const x = band.at(i);
        return (
          <g key={`${g.label}-${i}`} className={g.partial ? 'chart-partial' : undefined}>
            {g.values.map((value, k) => {
              const top = Math.min(y(value), zero);
              return (
                <rect
                  key={k}
                  className={k === 0 ? 'chart-bar-1' : 'chart-bar-2'}
                  x={k === 0 ? x - bar - 1 : x + 1}
                  width={bar}
                  y={top}
                  height={Math.max(0.5, Math.abs(zero - y(value)))}
                />
              );
            })}
            {ticks.has(i) ? (
              <text
                className="chart-tick"
                x={x}
                y={variant === 'wide' ? height - bottom + font * 1.5 : height - bottom / 3}
                fontSize={font}
                textAnchor={ticks.get(i)?.anchor ?? 'middle'}
              >
                {g.label}
              </text>
            ) : null}
            {variant === 'wide' && g.figure ? (
              <text className="chart-mark-label" x={x} y={height - bottom + font * 2.9} fontSize={font} textAnchor="middle">
                {visibleAmount(g.figure, currency, 'table', { locale })}
              </text>
            ) : null}
          </g>
        );
      })}
      <line className="chart-zero" x1={left} x2={width - right} y1={zero} y2={zero} />
    </svg>
  );
}

export function BarChart(props: BarChartProps) {
  const partial = props.groups.some((g) => g.partial);
  return (
    <ChartFigure caption={props.caption} figures={props.figures}>
      <Plot props={props} layout={WIDE} variant="wide" />
      <Plot props={props} layout={NARROW} variant="narrow" />
      <ul className="chart-key" aria-hidden="true">
        {props.series.map((name, k) => (
          <li key={name}>
            <svg className="chart-swatch chart-swatch-dot" viewBox="0 0 12 12">
              <rect className={k === 0 ? 'chart-bar-1' : 'chart-bar-2'} x={1} y={1} width={10} height={10} />
            </svg>
            <span>{name}</span>
          </li>
        ))}
        {partial && props.partialLabel ? (
          <li>
            <svg className="chart-swatch chart-swatch-dot" viewBox="0 0 12 12">
              <rect className="chart-bar-1 chart-partial" x={1} y={1} width={10} height={10} />
            </svg>
            <span>{props.partialLabel}</span>
          </li>
        ) : null}
      </ul>
    </ChartFigure>
  );
}
