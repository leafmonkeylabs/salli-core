/**
 * How the decision lab says a figure that isn't an amount: a month, a
 * change in months or days, a rate, months of spending. Each reads the
 * server's value as given; nothing is computed.
 */
import { formatDecimal, formatRatio } from '@leafmonkeylabs/salli-sdk';
import { displayDate, displayMonth } from '../../kit/dates';
import { labStrings } from '../../lab-strings';

const f = labStrings.figure;

export function monthText(value: string | null | undefined, locale: string | undefined): string {
  return value ? displayMonth(value, locale) : f.notWithin50;
}

export function monthsChange(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return f.notReached;
  if (delta === 0) return f.sameMonth;
  return delta > 0 ? f.monthsLater(delta) : f.monthsSooner(-delta);
}

export function daysChange(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return f.none;
  if (delta === 0) return f.sameDay;
  return delta > 0 ? f.daysLater(delta) : f.daysSooner(-delta);
}

/** A yearly rate or growth as a percentage, to a basis point: "6.9%", "-1.46%". */
export function rateText(value: string | null | undefined, locale: string | undefined): string {
  return value === null || value === undefined ? f.none : formatRatio(value, { locale, maximumFractionDigits: 2 });
}

/** Months of spending covered, to the hundredth: "7.37". */
export function monthsOfSpending(value: string | null | undefined, locale: string | undefined): string {
  return value === null || value === undefined ? f.none : formatDecimal(value, { locale });
}

/** A day as the CLI shows it, or "None". */
export function dayText(value: string | null | undefined, locale: string | undefined): string {
  return value ? displayDate(value, locale) : f.none;
}

/** A trade figure's name: "lowest cash", "net worth in 5 years". */
export function tradeFigure(figure: string): string {
  const known = f.trade[figure];
  if (known) return known;
  const match = /^monthly\.(\d+)y\.(\w+)$/.exec(figure);
  if (!match) return figure;
  const [, years = '', what = ''] = match;
  return f.tradeMonthly(what, f.years(wholeYears(years)));
}

/** "5" from a figure's name, as a count of years (digits only, read by JSON: never money). */
function wholeYears(text: string): number {
  return /^\d{1,2}$/.test(text) ? (JSON.parse(text) as number) : 0;
}

/** A placeholder's name in words. */
export function placeholderText(key: string): string {
  return labStrings.basis.placeholder[key] ?? key;
}
