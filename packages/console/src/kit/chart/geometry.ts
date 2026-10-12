/**
 * Pixel geometry for charts: the one place in the console where an amount
 * becomes a number (decision 12).
 *
 * A chart has to place a point, so this module turns a decimal string into a
 * float, only to compute where on screen it goes. What it returns is a pixel
 * position: never shown, never sent, never compared as money. Every label on
 * a chart is formatAmount of the original string, and which value is the
 * highest or lowest is decided by `compareAmounts` on the strings, exactly.
 *
 * test/money.test.ts fails if the lint escape below appears in any other file.
 */
import { compareAmounts } from '@leafmonkeylabs/salli-sdk';

/** A float for placing a point: never shown, sent or compared. */
function position(amount: string): number {
  // eslint-disable-next-line no-restricted-syntax -- not money: pixel geometry
  const value = Number(amount);
  return Number.isFinite(value) ? value : 0;
}

/** The lowest and highest of some amounts, chosen exactly by their digits. */
export function extent(amounts: readonly string[]): { low: string; high: string } | undefined {
  if (amounts.length === 0) return undefined;
  let low = amounts[0] as string;
  let high = low;
  for (const amount of amounts) {
    if (compareAmounts(amount, low) < 0) low = amount;
    if (compareAmounts(amount, high) > 0) high = amount;
  }
  return { low, high };
}

/**
 * A linear scale from amounts (or rates: any decimal strings) to pixels:
 * the lowest maps to `range[0]`, the highest to `range[1]`. Zero is inside
 * the domain unless `withZero` is false, so bars stand on it; a line far
 * from zero (net worth over twenty years) leaves it out.
 */
export function amountScale(
  amounts: readonly string[],
  range: readonly [number, number],
  { withZero = true }: { withZero?: boolean } = {},
): (amount: string) => number {
  const span = extent(withZero ? [...amounts, '0'] : amounts) ?? { low: '0', high: '0' };
  const low = position(span.low);
  const high = position(span.high);
  const [r0, r1] = range;
  if (high === low) return () => (r0 + r1) / 2;
  return (amount) => r0 + ((position(amount) - low) / (high - low)) * (r1 - r0);
}

/** Positions for `count` evenly spaced items across `range`, at their centres. */
export function bandScale(count: number, range: readonly [number, number], padding = 0.25): { at: (index: number) => number; width: number } {
  const [r0, r1] = range;
  const step = count > 0 ? (r1 - r0) / count : 0;
  return { at: (index) => r0 + step * (index + 0.5), width: Math.max(1, step * (1 - padding)) };
}

/** An SVG path through points, as straight segments. */
export function linePath(points: ReadonlyArray<readonly [number, number]>): string {
  return points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
}

/**
 * Positions for `count` points spread evenly across `range`, the first at
 * `range[0]` and the last at `range[1]`: a timeline's days or months.
 */
export function indexScale(count: number, range: readonly [number, number]): (index: number) => number {
  const [r0, r1] = range;
  if (count <= 1) return () => (r0 + r1) / 2;
  return (index) => r0 + (index / (count - 1)) * (r1 - r0);
}

/** An SVG path through points as steps: level until the next point, then up or down. */
export function stepPath(points: ReadonlyArray<readonly [number, number]>): string {
  return points.map(([x, y], i) => (i === 0 ? `M${x.toFixed(1)} ${y.toFixed(1)}` : `H${x.toFixed(1)} V${y.toFixed(1)}`)).join(' ');
}

/**
 * Pixel positions for labels that must not overlap: each wanted position,
 * moved apart to at least `gap` pixels, kept inside `range` where they fit.
 * Returned in the order given.
 */
export function spread(wanted: readonly number[], gap: number, range: readonly [number, number]): number[] {
  const order = wanted.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
  const [low, high] = range[0] < range[1] ? range : [range[1], range[0]];
  for (let k = 0; k < order.length; k++) {
    const item = order[k] as { y: number; i: number };
    const before = order[k - 1];
    item.y = Math.max(item.y, low, before ? before.y + gap : low);
  }
  for (let k = order.length - 1; k >= 0; k--) {
    const item = order[k] as { y: number; i: number };
    const after = order[k + 1];
    item.y = Math.min(item.y, high, after ? after.y - gap : high);
  }
  const out = new Array<number>(wanted.length);
  for (const item of order) out[item.i] = item.y;
  return out;
}

/** A day's place in time, in milliseconds: dates only, never money. */
function dayTime(date: string): number {
  return new Date(`${date.slice(0, 10)}T00:00:00Z`).getTime();
}

/**
 * Positions for points on their own days (an account's entries, which
 * fall on irregular dates): the first day at `range[0]`, the last at
 * `range[1]`, each in proportion to the days between.
 */
export function dayScale(dates: readonly string[], range: readonly [number, number]): (index: number) => number {
  const [r0, r1] = range;
  const first = dates[0];
  const last = dates[dates.length - 1];
  if (first === undefined || last === undefined || first === last) return () => (r0 + r1) / 2;
  const start = dayTime(first);
  const span = dayTime(last) - start;
  return (index) => r0 + ((dayTime(dates[index] ?? last) - start) / span) * (r1 - r0);
}
