/**
 * Which points a time axis labels: chosen from the points' own dates, never
 * computed from amounts.
 */

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

/**
 * For points on irregular dates (an account's entries): the first point in
 * each `step`th month that has one.
 */
export function firstInMonthTicks(dates: readonly string[], step: number): number[] {
  const firsts: number[] = [];
  let last = '';
  dates.forEach((d, i) => {
    const month = d.slice(0, 7);
    // The first point is labelled only early in its month: late in it, its
    // label would sit on the next month's.
    if (month !== last && (i > 0 || d.slice(8, 10) <= '15')) firsts.push(i);
    last = month;
  });
  return firsts.filter((_, k) => k % step === 0);
}

/**
 * Fitting an axis's labels so no two overlap.
 *
 * A label's width is estimated from its characters at the chart's font size
 * (in the SVG's own units, so the estimate holds at whatever width the
 * drawing is shown: it scales as a whole). The estimate is generous: Geist's
 * figures and capitals are narrower than 0.62 of the font size. A label
 * near an edge hangs from that edge, so it isn't cut off; the rest hang
 * from their middle. Labels that would come closer than `gap` to one kept
 * before them are dropped, keeping the first and the last where both fit.
 */
export const LABEL_EM = 0.62;

export type Anchor = 'start' | 'middle' | 'end';

export interface TickLabel {
  /** Which point it labels. */
  index: number;
  /** Its position, in the SVG's units. */
  x: number;
  text: string;
}

export interface PlacedTick extends TickLabel {
  anchor: Anchor;
  /** Where its text starts and ends. */
  from: number;
  to: number;
}

/** A label's estimated width at `font`. */
export function labelWidth(text: string, font: number): number {
  return text.length * font * LABEL_EM;
}

/** Where a label hangs from, and the stretch it covers. */
export function placeLabel(label: TickLabel, font: number, [low, high]: readonly [number, number]): PlacedTick {
  const width = labelWidth(label.text, font);
  if (label.x - width / 2 < low) return { ...label, anchor: 'start', from: label.x, to: label.x + width };
  if (label.x + width / 2 > high) return { ...label, anchor: 'end', from: label.x - width, to: label.x };
  return { ...label, anchor: 'middle', from: label.x - width / 2, to: label.x + width / 2 };
}

/** The labels to draw: none closer than `gap` to another, the first and last kept where they fit. */
export function fitTicks(labels: readonly TickLabel[], font: number, range: readonly [number, number], gap: number = font): PlacedTick[] {
  const placed = [...labels].sort((a, b) => a.x - b.x).map((label) => placeLabel(label, font, range));
  const first = placed[0];
  const last = placed[placed.length - 1];
  if (!first || !last || first === last) return placed;
  const kept: PlacedTick[] = [first];
  for (const label of placed.slice(1, -1)) {
    const before = kept[kept.length - 1] as PlacedTick;
    if (label.from >= before.to + gap && label.to + gap <= last.from) kept.push(label);
  }
  while (kept.length > 1 && last.from < (kept[kept.length - 1] as PlacedTick).to + gap) kept.pop();
  if (last.from >= (kept[kept.length - 1] as PlacedTick).to + gap) kept.push(last);
  return kept;
}
