/**
 * Dates as the API takes them: YYYY-MM-DD, in the user's local calendar.
 */
import { UsageError } from '../errors';
import { digits } from './numbers';

const pad = (n: number): string => String(n).padStart(2, '0');

// Intl separates some parts with thin or no-break spaces, which terminals
// render at different widths; plain spaces line up everywhere.
const SPECIAL_SPACES = new RegExp('[\\u00a0\\u2009\\u202f]', 'g');
const plainSpaces = (text: string): string => text.replace(SPECIAL_SPACES, ' ');

/** A local date as YYYY-MM-DD. */
export function isoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

/** Whether YYYY-MM-DD is a real calendar date. */
export function isValidIsoDate(text: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!m) return false;
  const [y, mo, d] = [digits(m[1]), digits(m[2]), digits(m[3])];
  const date = new Date(y, mo - 1, d);
  return date.getFullYear() === y && date.getMonth() === mo - 1 && date.getDate() === d;
}

/** A date argument: YYYY-MM-DD, or today / yesterday / tomorrow. */
export function parseDate(input: string, now: Date, flag = 'date'): string {
  const text = input.trim().toLowerCase();
  if (text === 'today') return isoDate(now);
  if (text === 'yesterday') return isoDate(addDays(now, -1));
  if (text === 'tomorrow') return isoDate(addDays(now, 1));
  if (isValidIsoDate(text)) return text;
  throw new UsageError(`${flag} must be a date as YYYY-MM-DD (or today, yesterday); got "${input}".`);
}

export interface Period {
  from: string;
  to: string;
  /** "October 2026". */
  label: string;
}

/** A calendar month, YYYY-MM (default: this month), as a date range. */
export function monthPeriod(month: string | undefined, now: Date, locale?: string): Period {
  let year = now.getFullYear();
  let index = now.getMonth();
  if (month !== undefined) {
    const m = /^(\d{4})-(\d{2})$/.exec(month.trim());
    const parsed = m ? ([digits(m[1]), digits(m[2])] as const) : undefined;
    if (!parsed || parsed[1] < 1 || parsed[1] > 12) {
      throw new UsageError(`--month must be YYYY-MM; got "${month}".`);
    }
    [year, index] = [parsed[0], parsed[1] - 1];
  }
  const first = new Date(year, index, 1);
  const last = new Date(year, index + 1, 0);
  const label = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(first);
  return { from: isoDate(first), to: isoDate(last), label };
}

/** The month so far: the 1st to today. */
export function monthToDate(now: Date, locale?: string): Period {
  const period = monthPeriod(undefined, now, locale);
  return { ...period, to: isoDate(now) };
}

/** "9 Oct 2026" for display ("30 Nov" for a yearly MM-DD); the input as given when it is not a date. */
export function displayDate(value: unknown, locale?: string): string {
  if (typeof value !== 'string' || !value) return '';
  const yearly = /^(\d{2})-(\d{2})$/.exec(value);
  if (yearly) {
    const date = new Date(2000, digits(yearly[1]) - 1, digits(yearly[2]));
    return plainSpaces(new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' }).format(date));
  }
  const day = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!day) return value;
  const date = new Date(digits(day[1]), digits(day[2]) - 1, digits(day[3]));
  return plainSpaces(new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).format(date));
}

/** "Oct 1 – 9, 2026": a date range as compactly as the locale allows. */
export function displayRange(from: unknown, to: unknown, locale?: string): string {
  const parse = (value: unknown): Date | undefined => {
    if (typeof value !== 'string') return undefined;
    const day = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    return day ? new Date(digits(day[1]), digits(day[2]) - 1, digits(day[3])) : undefined;
  };
  const start = parse(from);
  const end = parse(to);
  if (!start || !end) return [from, to].filter((v) => typeof v === 'string' && v).join(' – ');
  return plainSpaces(new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }).formatRange(start, end));
}
