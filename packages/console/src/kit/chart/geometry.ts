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
 * A linear scale from amounts to pixels: `from` maps to `range[0]`, `to` to
 * `range[1]`. Zero is always inside the domain, so bars stand on it.
 */
export function amountScale(amounts: readonly string[], range: readonly [number, number]): (amount: string) => number {
  const span = extent([...amounts, '0']) ?? { low: '0', high: '0' };
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
