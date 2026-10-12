/**
 * A break-even (docs/design/console.md, section 4, "Charts"): the range
 * Salli searched, as a line, and the value where the answer turns, marked
 * and labelled. When the answer doesn't turn within the range, the whole
 * line says so. The value, the range and the words are the server's; this
 * only places them. The drawing repeats the sentence the caller shows
 * beside it as text (the server's `says`), so it is hidden from screen
 * readers; the figures are in the caller's table.
 */
import { compareAmounts } from '@leafmonkeylabs/salli-sdk';
import { amountScale } from './geometry';

export interface RangeChartProps {
  low: string;
  high: string;
  /** Where the answer turns; null when it doesn't within the range. */
  value: string | null;
  /** How a value is shown: a rate as a percentage, an amount with its code. */
  format: (value: string) => string;
  /** The words on the line when there is no value in range. */
  noneLabel: string;
}

interface Layout {
  width: number;
  height: number;
  pad: number;
  font: number;
}

const WIDE: Layout = { width: 1040, height: 62, pad: 12, font: 12 };
const NARROW: Layout = { width: 300, height: 70, pad: 6, font: 12 };

function Plot({ props, layout, variant }: { props: RangeChartProps; layout: Layout; variant: 'wide' | 'narrow' }) {
  const { width, height, pad, font } = layout;
  const { low, high, value } = props;
  const x = amountScale(value ? [low, high, value] : [low, high], [pad, width - pad], { withZero: false });
  const axis = height - font * 2;
  const inRange = value !== null && compareAmounts(value, low) >= 0 && compareAmounts(value, high) <= 0;
  const vx = inRange && value !== null ? x(value) : 0;
  const anchor = vx > width * 0.8 ? 'end' : vx < width * 0.2 ? 'start' : 'middle';
  return (
    <svg className={`chart-svg chart-${variant}`} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" focusable="false">
      <line className={inRange ? 'chart-range' : 'chart-range chart-range-none'} x1={x(low)} x2={x(high)} y1={axis} y2={axis} />
      <line className="chart-range-end" x1={x(low)} x2={x(low)} y1={axis - 4} y2={axis + 4} />
      <line className="chart-range-end" x1={x(high)} x2={x(high)} y1={axis - 4} y2={axis + 4} />
      <text className="chart-tick" x={x(low)} y={height - 2} fontSize={font} textAnchor="start">
        {props.format(low)}
      </text>
      <text className="chart-tick" x={x(high)} y={height - 2} fontSize={font} textAnchor="end">
        {props.format(high)}
      </text>
      {inRange && value !== null ? (
        <>
          <line className="chart-range-mark" x1={vx} x2={vx} y1={axis - 10} y2={axis + 6} />
          <text className="chart-end-label" x={vx} y={axis - 14} fontSize={font} textAnchor={anchor}>
            {props.format(value)}
          </text>
        </>
      ) : (
        <text className="chart-tick" x={width / 2} y={axis - 10} fontSize={font} textAnchor="middle">
          {props.noneLabel}
        </text>
      )}
    </svg>
  );
}

/** A break-even on its range: wide, and redrawn for a phone. */
export function RangeChart(props: RangeChartProps) {
  return (
    <div className="chart-plot chart-range-plot">
      <Plot props={props} layout={WIDE} variant="wide" />
      <Plot props={props} layout={NARROW} variant="narrow" />
    </div>
  );
}
