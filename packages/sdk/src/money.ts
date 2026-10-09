/**
 * Money, for display.
 *
 * The API sends every amount as a decimal string in its currency's own
 * precision ("1234.50", "1200", "1.234") with the currency alongside. These
 * helpers format that string exactly, through `Intl.NumberFormat`'s decimal
 * string support: the amount never passes through a binary float, so
 * "123456789012345678.91" prints as exactly that.
 *
 * Nothing here does arithmetic on an amount. Totals, balances and
 * conversions come from the server; a client only shows them.
 */

/** A string Intl.NumberFormat formats as an exact decimal. */
export type DecimalString = `${number}`;

/** An amount as the API contract sends it: `-?\d+(\.\d+)?`. */
const AMOUNT = /^[+-]?\d+(?:\.\d+)?$/;
const ZERO = /^[+-]?0+(?:\.0+)?$/;

/** Whether `value` is a decimal string in the API's amount format. */
export function isAmount(value: unknown): value is DecimalString {
  return typeof value === 'string' && AMOUNT.test(value);
}

/** Whether an amount is zero ("0", "0.00", "-0.000"). */
export function isZeroAmount(amount: string): boolean {
  return ZERO.test(amount.trim());
}

/** Whether an amount is below zero. Reads the sign; never parses the number. */
export function isNegativeAmount(amount: string): boolean {
  const a = amount.trim();
  return a.startsWith('-') && !isZeroAmount(a);
}

/** The sign of an amount: -1, 0 or 1. */
export function amountSign(amount: string): -1 | 0 | 1 {
  if (isZeroAmount(amount)) return 0;
  return isNegativeAmount(amount) ? -1 : 1;
}

/** An amount with its sign flipped, as a string ("12.50" → "-12.50"). */
export function negateAmount(amount: string): string {
  const a = amount.trim();
  if (isZeroAmount(a)) return a.replace(/^[+-]/, '');
  if (a.startsWith('-')) return a.slice(1);
  return `-${a.replace(/^\+/, '')}`;
}

function fractionDigitsOf(amount: string): number {
  const dot = amount.indexOf('.');
  return dot === -1 ? 0 : amount.length - dot - 1;
}

const digitsCache = new Map<string, number>();

/**
 * How many decimals a currency is kept in (its ISO 4217 exponent): 0 for
 * JPY, 2 for USD, 3 for KWD. 2 for a code Intl does not know.
 */
export function currencyDigits(currency: string): number {
  const code = currency.toUpperCase();
  const cached = digitsCache.get(code);
  if (cached !== undefined) return cached;
  let digits = 2;
  try {
    digits =
      new Intl.NumberFormat('en', { style: 'currency', currency: code }).resolvedOptions()
        .maximumFractionDigits ?? 2;
  } catch {
    // Not a well-formed currency code: keep the default.
  }
  digitsCache.set(code, digits);
  return digits;
}

export interface FormatAmountOptions {
  /** BCP 47 locale(s) for separators and placement. Default: the runtime's. */
  locale?: string | readonly string[] | undefined;
  /**
   * How to show the currency: its ISO code (the default, unambiguous), its
   * symbol, its name, or not at all (`none`, for a column already labelled).
   */
  display?: 'code' | 'symbol' | 'narrowSymbol' | 'name' | 'none';
  /** When to show the sign. Default `negative`: only below zero. */
  signDisplay?: 'auto' | 'always' | 'exceptZero' | 'negative' | 'never';
  /** Thousands separators. Default true. */
  grouping?: boolean;
}

const formatterCache = new Map<string, Intl.NumberFormat>();

function formatter(
  locale: string | readonly string[] | undefined,
  options: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = JSON.stringify([locale ?? null, options]);
  let f = formatterCache.get(key);
  if (!f) {
    f = new Intl.NumberFormat(locale as string | string[] | undefined, options);
    formatterCache.set(key, f);
  }
  return f;
}

/**
 * Formats an amount for display, exactly.
 *
 * Shows at least the currency's own decimals (so "5" USD is "5.00") and never
 * fewer than the amount carries, so nothing the server sent is rounded away.
 * A value that is not a decimal amount is returned as given rather than
 * guessed at; null and undefined become an empty string.
 */
export function formatAmount(
  amount: string | number | null | undefined,
  currency: string,
  options: FormatAmountOptions = {},
): string {
  if (amount === null || amount === undefined || amount === '') return '';
  const text = typeof amount === 'number' ? String(amount) : amount.trim();
  if (!isAmount(text)) return text;

  const digits = currencyDigits(currency);
  const numberOptions: Intl.NumberFormatOptions = {
    minimumFractionDigits: digits,
    maximumFractionDigits: Math.min(100, Math.max(digits, fractionDigitsOf(text))),
    useGrouping: options.grouping ?? true,
    signDisplay: options.signDisplay ?? 'negative',
  };
  const display = options.display ?? 'code';
  if (display !== 'none') {
    try {
      return formatter(options.locale, {
        ...numberOptions,
        style: 'currency',
        currency: currency.toUpperCase(),
        currencyDisplay: display,
      }).format(text);
    } catch {
      // Not a currency Intl accepts: fall through and prefix the code.
      return `${currency} ${formatter(options.locale, numberOptions).format(text)}`;
    }
  }
  return formatter(options.locale, numberOptions).format(text);
}

export interface FormatRatioOptions {
  locale?: string | readonly string[] | undefined;
  /** Decimals in the percentage. Default 1. */
  maximumFractionDigits?: number;
  signDisplay?: 'auto' | 'always' | 'exceptZero' | 'negative' | 'never';
}

/**
 * Formats a fraction as a percentage ("0.185" → "18.5%"), exactly when it
 * arrives as a decimal string. For ratios the API sends: savings rates,
 * APRs, progress. Returns the input as given when it is not a number.
 */
export function formatRatio(
  fraction: string | number | null | undefined,
  options: FormatRatioOptions = {},
): string {
  if (fraction === null || fraction === undefined || fraction === '') return '';
  const text = typeof fraction === 'number' ? String(fraction) : fraction.trim();
  if (typeof fraction === 'string' && !isAmount(text)) return text;
  return formatter(options.locale, {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: options.maximumFractionDigits ?? 1,
    signDisplay: options.signDisplay ?? 'negative',
  }).format(text as DecimalString);
}

/**
 * Normalises an amount someone typed into the API's format, or returns
 * undefined when it is not one. Accepts `1500`, `1500.5`, `-12.30`, and
 * comma thousands separators in their proper places (`1,234,567.89`). It
 * rewrites the text; it never computes with it.
 */
export function normalizeAmountInput(input: string): string | undefined {
  let text = input.trim().replace(/^\+/, '');
  if (/^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$/.test(text)) text = text.replaceAll(',', '');
  if (/^-?\d+\.$/.test(text)) text = text.slice(0, -1);
  if (/^-?\.\d+$/.test(text)) text = text.replace('.', '0.');
  return AMOUNT.test(text) ? text : undefined;
}
