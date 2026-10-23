/**
 * Where a chart's points go, and nothing else: the one place an amount
 * becomes a number, to place it in pixels (as the console's
 * kit/chart/geometry.ts). Figures on screen stay the server's strings.
 */

export interface Day {
  date: string;
  balance: string;
}

export interface StepChart {
  /** The line: each day's balance held until the next, as an SVG path. */
  path: string;
  /** Where the lowest day and the last day fall. */
  low: { x: number; y: number };
  end: { x: number; y: number };
  /** Where zero falls, when it is inside the chart. */
  zero: number | undefined;
}

function pixels(amount: string): number {
  // eslint-disable-next-line no-restricted-syntax -- not money: pixel geometry
  return Number(amount);
}

/** A step line through `days` in a `width` × `height` box, with room at the edges. */
export function stepChart(days: readonly Day[], lowest: Day, width: number, height: number, pad = 8): StepChart {
  const values = days.map((d) => pixels(d.balance));
  const high = Math.max(...values);
  const low = Math.min(...values);
  // The line's own range with a tenth to spare, so a change shows as a change;
  // zero joins the range only when the line reaches it.
  const margin = (high - low || Math.abs(high) || 1) / 10;
  const top = high + margin;
  const bottom = low < 0 ? low - margin : Math.max(0, low - margin);
  const span = top - bottom || 1;
  const x = (i: number): number => pad + (days.length > 1 ? (i / (days.length - 1)) * (width - 2 * pad) : 0);
  const y = (v: number): number => pad + ((top - v) / span) * (height - 2 * pad);
  let path = '';
  values.forEach((v, i) => {
    const px = x(i).toFixed(1);
    const py = y(v).toFixed(1);
    path += i === 0 ? `M${px} ${py}` : ` H${px} V${py}`;
  });
  const lowIndex = Math.max(0, days.findIndex((d) => d.date === lowest.date));
  const last = values.length - 1;
  return {
    path,
    low: { x: x(lowIndex), y: y(values[lowIndex] ?? 0) },
    end: { x: x(last), y: y(values[last] ?? 0) },
    zero: low < 0 ? y(0) : undefined,
  };
}
