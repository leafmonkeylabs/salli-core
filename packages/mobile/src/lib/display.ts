/**
 * How the app shows the server's figures: exactly, through the SDK's
 * formatter, with no arithmetic on money (docs/design/mobile.md).
 */
import { formatAmount, isNegativeAmount, negateAmount } from '@leafmonkeylabs/salli-sdk';

const MONTHS: Record<string, string> = {
  '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun',
  '07': 'Jul', '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec',
};

/** An amount for a screen: its digits without the code, and whether it is below zero. */
export interface AmountParts {
  /** The figure, unsigned: "1,500.00". Negatives are shown in brackets, so the sign is left out. */
  digits: string;
  negative: boolean;
  /** What a screen reader says: "minus 1,500.00 euros". */
  spoken: string;
}

export function amountParts(amount: string, currency: string, locale?: string): AmountParts {
  const negative = isNegativeAmount(amount);
  const unsigned = negative ? negateAmount(amount) : amount;
  const digits = formatAmount(unsigned, currency, { display: 'none', locale });
  const named = formatAmount(unsigned, currency, { display: 'name', locale });
  return { digits, negative, spoken: negative ? `minus ${named}` : named };
}

/** An ISO date ("2026-10-25") as the brand writes it on screens: "Oct 25, 2026". */
export function displayDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;
  const [, year, month = '', day = ''] = match;
  const name = MONTHS[month];
  return name ? `${name} ${day.replace(/^0/, '')}, ${year}` : iso;
}

/** When something happened, from the phone's clock: "09:41 today", or "Oct 23, 2026, 14:05". */
export function displayMoment(at: Date, now: Date = new Date()): string {
  return isoDayOf(at) === isoDayOf(now) ? `${timeOf(at)} today` : displayDateTime(at);
}

/** A moment with its date, always: "Oct 24, 2026, 07:01". */
export function displayDateTime(at: Date): string {
  return `${displayDate(isoDayOf(at))}, ${timeOf(at)}`;
}

const pad = (n: number): string => String(n).padStart(2, '0');
const timeOf = (d: Date): string => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
const isoDayOf = (d: Date): string => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** A day in a list under a year already said: "Oct 1". */
export function displayDay(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  const name = match ? MONTHS[match[2] ?? ''] : undefined;
  return match && name ? `${name} ${(match[3] ?? '').replace(/^0/, '')}` : iso;
}

/** A period, its year said once when both ends share it: "Oct 1 to Oct 10, 2026". */
export function displayRange(from: string, to: string): string {
  if (from.slice(0, 4) === to.slice(0, 4) && /^\d{4}-\d{2}-\d{2}/.test(from)) return `${displayDay(from)} to ${displayDate(to)}`;
  return `${displayDate(from)} to ${displayDate(to)}`;
}

const MONTH_NAMES: Record<string, string> = {
  '01': 'January', '02': 'February', '03': 'March', '04': 'April', '05': 'May', '06': 'June',
  '07': 'July', '08': 'August', '09': 'September', '10': 'October', '11': 'November', '12': 'December',
};

/** The month an ISO date is in, by name: "October". */
export function monthNameOf(iso: string): string {
  return MONTH_NAMES[iso.slice(5, 7)] ?? '';
}

/** The month so far, from its first day to `today`, as ISO dates. */
export function monthOf(today: string): { from: string; to: string } {
  return { from: `${today.slice(0, 7)}-01`, to: today };
}

/** Today's date where the phone is, as ISO 8601. */
/** Last month up to the same day as `today` (its last day, when it is shorter): spending so far, like for like. */
export function sameDaysLastMonth(today: string): { from: string; to: string } {
  // eslint-disable-next-line no-restricted-syntax -- not money: a date's year, month and day
  const [y, m, d] = [Number(today.slice(0, 4)), Number(today.slice(5, 7)), Number(today.slice(8, 10))];
  const year = m === 1 ? y - 1 : y;
  const month = m === 1 ? 12 : m - 1;
  const mm = String(month).padStart(2, '0');
  const day = Math.min(d, new Date(year, month, 0).getDate());
  return { from: `${year}-${mm}-01`, to: `${year}-${mm}-${String(day).padStart(2, '0')}` };
}

/** An amount in whole units, as a glance shows it: the server's digits up to the decimal point. */
export function wholeDigits(amount: string, currency: string): string {
  const parts = amountParts(amount, currency);
  const whole = parts.digits.replace(/\.\d+$/, '');
  return parts.negative ? `(${whole})` : whole;
}

export function todayIso(now: Date = new Date()): string {
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
