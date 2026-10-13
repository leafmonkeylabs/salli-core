/**
 * What a person types, in the API's formats (decision 12): every function
 * here rewrites text and never computes with it. An amount stays a decimal
 * string; a rate typed as a percentage has its decimal point moved, as
 * text; a whole number of months is read only when it is plain digits.
 * Each returns undefined for what it can't read, rather than guessing.
 */
import { isAmount, normalizeAmountInput } from '@leafmonkeylabs/salli-sdk';

/** An amount in the locale's marks (`1.234,56` in de-DE), as the API's decimal string. */
export function amountInput(text: string, locale?: string): string | undefined {
  const value = normalizeAmountInput(text.trim(), locale ? { locale } : {});
  return value === undefined ? undefined : value;
}

/** An amount above zero: no sign, and not zero. */
export function positiveAmountInput(text: string, locale?: string): string | undefined {
  const value = amountInput(text, locale);
  if (value === undefined || value.startsWith('-') || /^\+?0*(\.0*)?$/.test(value)) return undefined;
  return value.replace(/^\+/, '');
}

/** An amount of zero or more. */
export function nonNegativeAmountInput(text: string, locale?: string): string | undefined {
  const value = amountInput(text, locale);
  if (value === undefined || value.startsWith('-')) return undefined;
  return value.replace(/^\+/, '');
}

/** An amount with its sign kept as typed ("+450", "-200"). */
export function signedAmountInput(text: string, locale?: string): string | undefined {
  const trimmed = text.trim();
  const sign = trimmed.startsWith('+') ? '+' : '';
  const value = amountInput(trimmed.replace(/^\+/, ''), locale);
  if (value === undefined) return undefined;
  return value.startsWith('-') ? value : `${sign}${value}`;
}

/**
 * A yearly rate or growth as the API's fraction: `6.9%` is `0.069`, and
 * `0.069` stays as it is. The percentage's decimal point moves two places,
 * as text.
 */
export function rateInput(text: string, locale?: string): string | undefined {
  const trimmed = text.trim();
  if (!trimmed.endsWith('%')) return amountInput(trimmed, locale);
  const number = amountInput(trimmed.slice(0, -1), locale);
  if (number === undefined) return undefined;
  const negative = number.startsWith('-');
  const digits = number.replace(/^[-+]/, '');
  const [whole = '0', fraction = ''] = digits.split('.');
  const padded = whole.padStart(3, '0');
  const shifted = `${padded.slice(0, -2).replace(/^0+(?=\d)/, '')}.${padded.slice(-2)}${fraction}`.replace(/\.?0+$/, '') || '0';
  const result = shifted.startsWith('.') ? `0${shifted}` : shifted;
  return negative && result !== '0' ? `-${result}` : result;
}

/**
 * A whole number of months or years (a count, never money), read only when
 * it is plain digits: JSON reads them, so no float is ever involved.
 */
export function wholeNumberInput(text: string): number | undefined {
  const trimmed = text.trim();
  if (!/^\d{1,4}$/.test(trimmed)) return undefined;
  return JSON.parse(trimmed.replace(/^0+(?=\d)/, '')) as number;
}

/** A day as the API takes it, YYYY-MM-DD (a date input gives exactly that). */
export function dateInput(text: string): string | undefined {
  const trimmed = text.trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(trimmed) ? trimmed : undefined;
}

/** Whether an answer the server sent is a decimal string the inputs above would accept back. */
export function isDecimalText(value: unknown): value is string {
  return typeof value === 'string' && isAmount(value.trim());
}
