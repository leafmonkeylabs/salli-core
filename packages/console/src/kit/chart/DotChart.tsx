/**
 * Figures side by side on one scale, a row for each option, a mark for each
 * reading (docs/design/console.md, section 4, "Sensitivity"): each option's
 * net worth at the horizon at the conservative, base and growth returns.
 * Rows stay in the order given, never sorted. The marks differ in shape as
 * well as fill, and every reading is in the caller's table.
 */
import type { ReactNode } from 'react';
import { ChartFigure } from './ChartFigure';
import { amountScale } from './geometry';

export interface DotRow {
  label: string;
  /** One amount per reading, in the order of `readings`. */
  values: ReadonlyArray<string | null>;
}

export interface DotChartProps {
  caption: string;
  /** What each mark is ("2% a year"), in the order of each row's values. */
  readings: readonly string[];
  rows: readonly DotRow[];
  /** How an amount is shown at a row's end (its middle reading). */
  format: (value: string) => string;
  figures: ReactNode;
}

const SHAPES = ['square', 'disc', 'ring'] as const;

function Mark({ shape, x, y }: { shape: (typeof SHAPES)[number]; x: number; y: number }) {
  if (shape === 'square') return <rect className="chart-dot chart-dot-open" x={x - 4} y={y - 4} width={8} height={8} />;
  if (shape === 'disc') return <circle className="chart-dot" cx={x} cy={y} r={4.5} />;
  return <circle className="chart-dot chart-dot-open" cx={x} cy={y} r={4.5} />;
}

function Plot({ props, variant }: { props: DotChartProps; variant: 'wide' | 'narrow' }) {
  const wide = variant === 'wide';
  const width = wide ? 680 : 320;
  const labelWidth = wide ? 200 : 0;
  const right = wide ? 150 : 8;
  const rowHeight = wide ? 34 : 46;
  const font = wide ? 12 : 11;
  const height = props.rows.length * rowHeight + 8;
  const all = props.rows.flatMap((r) => r.values.filter((v): v is string => v !== null));
  const x = amountScale(all, [labelWidth + 8, width - right], { withZero: false });
  return (
    <svg className={`chart-svg chart-${variant}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={props.caption}>
      {props.rows.map((row, r) => {
        const y = r * rowHeight + (wide ? rowHeight / 2 + 4 : rowHeight - 12);
        const present = row.values.filter((v): v is string => v !== null);
        const first = present[0];
        const last = present[present.length - 1];
        const middle = row.values[1] ?? first;
        return (
          <g key={row.label}>
            <line className="chart-zero" x1={labelWidth + 8} x2={width - right} y1={y} y2={y} />
            {first && last ? <line className="chart-spread" x1={x(first)} x2={x(last)} y1={y} y2={y} /> : null}
            {row.values.map((v, i) => (v === null ? null : <Mark key={i} shape={SHAPES[i % 3] ?? 'disc'} x={x(v)} y={y} />))}
            <text className="chart-end-label" x={wide ? 0 : 4} y={wide ? y + font / 3 : y - 12} fontSize={font}>
              {row.label}
            </text>
            {wide && middle ? (
              <text className="chart-tick" x={width - right + 10} y={y + font / 3} fontSize={font}>
                {props.format(middle)}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}

export function DotChart(props: DotChartProps) {
  return (
    <ChartFigure caption={props.caption} figures={props.figures}>
      <Plot props={props} variant="wide" />
      <Plot props={props} variant="narrow" />
      <ul className="chart-key" aria-hidden="true">
        {props.readings.map((reading, i) => (
          <li key={reading}>
            <svg className="chart-swatch chart-swatch-dot" viewBox="0 0 12 12">
              <Mark shape={SHAPES[i % 3] ?? 'disc'} x={6} y={6} />
            </svg>
            <span>{reading}</span>
          </li>
        ))}
      </ul>
    </ChartFigure>
  );
}
