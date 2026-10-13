/**
 * Dates as the CLI shows them (`displayDate` in packages/cli/src/util/dates.ts):
 * `Nov 1, 2026` in English, in the locale's own order elsewhere; ISO 8601 in
 * anything copied. Dates are read from their ISO text by the Date parser,
 * never by turning digits into numbers.
 */

const SPECIAL_SPACES = new RegExp('[\\u00a0\\u2009\\u202f]', 'g');
const plain = (text: string): string => text.replace(SPECIAL_SPACES, ' ');

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const MONTH = /^\d{4}-\d{2}$/;
const MOMENT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

const pad = (n: number): string => String(n).padStart(2, '0');

/** A local date as YYYY-MM-DD. */
export function isoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** YYYY-MM-DD (or YYYY-MM, its first day) as a local Date, or undefined. */
export function localDate(value: string): Date | undefined {
  const text = MONTH.test(value) ? `${value}-01` : value.slice(0, 10);
  if (!DAY.test(text)) return undefined;
  const date = new Date(`${text}T00:00:00`);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

/** "Oct 11, 2026"; a moment with an offset on the local calendar; the input as given otherwise. */
export function displayDate(value: string | null | undefined, locale?: string): string {
  if (!value) return '';
  let date: Date | undefined;
  if (MOMENT.test(value)) {
    const moment = new Date(value);
    date = Number.isNaN(moment.getTime()) ? undefined : moment;
  } else {
    date = DAY.test(value) ? localDate(value) : undefined;
  }
  if (!date) return value;
  return plain(new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(date));
}

/** "Oct 11, 2026, 14:05" for a moment (when a sign-in was last used). */
export function displayMoment(value: string | null | undefined, locale?: string): string {
  if (!value) return '';
  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) return value;
  return plain(
    new Intl.DateTimeFormat(locale, {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(moment),
  );
}

/** "Oct 2026" for YYYY-MM. */
export function displayMonth(value: string | null | undefined, locale?: string, month: 'short' | 'long' = 'short'): string {
  if (!value) return '';
  const date = MONTH.test(value) ? localDate(value) : undefined;
  if (!date) return value;
  return plain(new Intl.DateTimeFormat(locale, { month, year: 'numeric' }).format(date));
}

/** "Oct 1 – 11, 2026". */
export function displayRange(from: string, to: string, locale?: string): string {
  const start = localDate(from);
  const end = localDate(to);
  if (!start || !end) return `${from} – ${to}`;
  return plain(new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).formatRange(start, end));
}

/** The calendar month of `now` so far: the 1st to today, as the API takes it. */
export function monthToDate(now: Date): { from: string; to: string; month: string } {
  const first = new Date(now.getFullYear(), now.getMonth(), 1);
  return { from: isoDate(first), to: isoDate(now), month: isoDate(first).slice(0, 7) };
}
