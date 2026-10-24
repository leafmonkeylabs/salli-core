/**
 * Where a chart's points go, and nothing else: the one place an amount
 * becomes a number, to place it in pixels (as the console's
 * kit/chart/geometry.ts). Figures on screen stay the server's strings:
 * every label is one of the days' own balances, and which day is highest is
 * chosen by comparing the strings exactly, never invented round values.
 */
import { compareAmounts } from '@leafmonkeylabs/salli-sdk';

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
  /** Every day's point, and which day is highest (chosen by its digits) and lowest. */
  points: { x: number; y: number }[];
  highIndex: number;
  lowIndex: number;
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
  let highIndex = 0;
  days.forEach((d, i) => {
    if (compareAmounts(d.balance, days[highIndex]?.balance ?? d.balance) > 0) highIndex = i;
  });
  const points = values.map((v, i) => ({ x: x(i), y: y(v) }));
  return {
    path,
    low: { x: x(lowIndex), y: y(values[lowIndex] ?? 0) },
    end: { x: x(last), y: y(values[last] ?? 0) },
    zero: low < 0 ? y(0) : undefined,
    points,
    highIndex,
    lowIndex,
  };
}

/** A label a chart wants, most wanted first: placed above its point, or below. */
export interface WantedLabel {
  key: string;
  x: number;
  y: number;
  text: string;
  below?: boolean;
}

export interface PlacedLabel {
  key: string;
  /** The text's anchor point, in the chart's pixels. */
  x: number;
  y: number;
  anchor: 'start' | 'middle' | 'end';
  text: string;
}

/** Geist's figures at a size, generously: as the console's ticks estimate them. */
const LABEL_EM = 0.62;

/**
 * Labels for a chart's points: each hangs from its point, inside the chart
 * (a label at an edge hangs inward, so the lowest day on the first or last
 * day keeps its label in view), and one that would overlap a label placed
 * before it is left out. The first wanted is always placed.
 */
export function placeLabels(wanted: readonly WantedLabel[], width: number, height: number, font: number): PlacedLabel[] {
  const placed: (PlacedLabel & { box: [number, number, number, number] })[] = [];
  for (const label of wanted) {
    const w = label.text.length * font * LABEL_EM;
    const anchor: PlacedLabel['anchor'] = label.x - w / 2 < 0 ? 'start' : label.x + w / 2 > width ? 'end' : 'middle';
    const left = anchor === 'start' ? Math.max(0, label.x - 2) : anchor === 'end' ? Math.min(width, label.x + 2) - w : label.x - w / 2;
    const x = anchor === 'start' ? left : anchor === 'end' ? left + w : label.x;
    // The text's baseline: above the point by a gap, or below it by one line.
    const baseline = Math.min(height - 2, Math.max(font, label.below ? label.y + font + 6 : label.y - 6));
    const box: [number, number, number, number] = [left, baseline - font, left + w, baseline + 2];
    const clash = placed.some((p) => box[0] < p.box[2] && box[2] > p.box[0] && box[1] < p.box[3] && box[3] > p.box[1]);
    if (clash && placed.length) continue;
    placed.push({ key: label.key, x, y: baseline, anchor, text: label.text, box });
  }
  return placed.map(({ box: _box, ...label }) => label);
}

/** A line through `amounts`, oldest first, in a `width` × `height` box: a sparkline's path. */
export function lineChart(amounts: readonly string[], width: number, height: number, pad = 4): { path: string; points: { x: number; y: number }[] } {
  const values = amounts.map(pixels);
  if (!values.length) return { path: '', points: [] };
  const high = Math.max(...values);
  const low = Math.min(...values);
  const span = high - low || 1;
  const points = values.map((v, i) => ({
    x: pad + (values.length > 1 ? (i / (values.length - 1)) * (width - 2 * pad) : (width - 2 * pad) / 2),
    y: pad + ((high - v) / span) * (height - 2 * pad),
  }));
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  return { path, points };
}

