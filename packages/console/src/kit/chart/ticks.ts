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
