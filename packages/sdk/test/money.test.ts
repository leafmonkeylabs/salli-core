import { describe, expect, it } from 'vitest';
import {
  amountSign,
  compareAmounts,
  currencyDigits,
  formatAmount,
  formatRatio,
  isAmount,
  isNegativeAmount,
  isZeroAmount,
  negateAmount,
  normalizeAmountInput,
} from '../src/money';

// Intl separates a currency code from the number with a no-break space.
const plain = (text: string): string => text.replace(/\u00a0/g, ' ');
const fmt = (...args: Parameters<typeof formatAmount>): string => plain(formatAmount(...args));

describe('currencyDigits', () => {
  it("uses each currency's own ISO 4217 exponent", () => {
    expect(currencyDigits('JPY')).toBe(0);
    expect(currencyDigits('USD')).toBe(2);
    expect(currencyDigits('LKR')).toBe(2);
    expect(currencyDigits('KWD')).toBe(3);
    expect(currencyDigits('usd')).toBe(2);
  });

  it('falls back to 2 for a code it cannot read', () => {
    expect(currencyDigits('not-a-code')).toBe(2);
  });
});

describe('formatAmount', () => {
  it('formats USD with two decimals and the code', () => {
    expect(fmt('1234.5', 'USD', { locale: 'en-US' })).toBe('USD 1,234.50');
    expect(fmt('1234.50', 'USD', { locale: 'en-US' })).toBe('USD 1,234.50');
  });

  it('formats JPY with no decimals', () => {
    expect(fmt('1234', 'JPY', { locale: 'en-US' })).toBe('JPY 1,234');
    expect(fmt('1200', 'JPY', { locale: 'en-US', display: 'none' })).toBe('1,200');
  });

  it('formats KWD with three decimals', () => {
    expect(fmt('1234.567', 'KWD', { locale: 'en-US' })).toBe('KWD 1,234.567');
    expect(fmt('5', 'KWD', { locale: 'en-US' })).toBe('KWD 5.000');
  });

  it('shows negatives with a sign and never a negative zero', () => {
    expect(fmt('-1234.50', 'USD', { locale: 'en-US' })).toBe('-USD 1,234.50');
    expect(fmt('-1234.50', 'USD', { locale: 'en-US', display: 'none' })).toBe('-1,234.50');
    expect(fmt('-0.00', 'USD', { locale: 'en-US' })).toBe('USD 0.00');
  });

  it('formats large amounts exactly, with no float rounding', () => {
    expect(fmt('123456789012345678901234567890.12', 'USD', { locale: 'en-US' })).toBe(
      'USD 123,456,789,012,345,678,901,234,567,890.12',
    );
    // 2^53 + 1 cannot be represented as a double.
    expect(fmt('9007199254740993', 'JPY', { locale: 'en-US', display: 'none' })).toBe(
      '9,007,199,254,740,993',
    );
    expect(fmt('0.1', 'USD', { locale: 'en-US', display: 'none' })).toBe('0.10');
  });

  it('never hides precision the server sent', () => {
    expect(fmt('0.1', 'JPY', { locale: 'en-US' })).toBe('JPY 0.1');
    expect(fmt('12.3456', 'USD', { locale: 'en-US', display: 'none' })).toBe('12.3456');
  });

  it('follows the locale', () => {
    expect(fmt('1234.5', 'EUR', { locale: 'de-DE' })).toBe('1.234,50 EUR');
    expect(fmt('1234.5', 'USD', { locale: 'en-US', display: 'symbol' })).toBe('$1,234.50');
    expect(fmt('1234567.5', 'INR', { locale: 'en-IN', display: 'none' })).toBe('12,34,567.50');
  });

  it('can drop grouping and always show the sign', () => {
    expect(fmt('1234.5', 'USD', { locale: 'en-US', display: 'none', grouping: false })).toBe('1234.50');
    expect(fmt('12', 'USD', { locale: 'en-US', display: 'none', signDisplay: 'always' })).toBe('+12.00');
  });

  it('leaves a value that is not an amount as it is', () => {
    expect(formatAmount('n/a', 'USD')).toBe('n/a');
    expect(formatAmount('1e5', 'USD')).toBe('1e5');
    expect(formatAmount(null, 'USD')).toBe('');
    expect(formatAmount(undefined, 'USD')).toBe('');
    expect(formatAmount('', 'USD')).toBe('');
  });

  it('prefixes a currency code Intl will not accept', () => {
    expect(fmt('1234.5', 'XX', { locale: 'en-US' })).toBe('XX 1,234.50');
  });
});

describe('amount predicates', () => {
  it('recognises the API amount format only', () => {
    expect(isAmount('1234.50')).toBe(true);
    expect(isAmount('-1')).toBe(true);
    expect(isAmount('1,234')).toBe(false);
    expect(isAmount('1e3')).toBe(false);
    expect(isAmount(12)).toBe(false);
  });

  it('reads signs without parsing numbers', () => {
    expect(isZeroAmount('0')).toBe(true);
    expect(isZeroAmount('-0.000')).toBe(true);
    expect(isZeroAmount('0.01')).toBe(false);
    expect(isNegativeAmount('-0.01')).toBe(true);
    expect(isNegativeAmount('-0.00')).toBe(false);
    expect(amountSign('12')).toBe(1);
    expect(amountSign('-12')).toBe(-1);
    expect(amountSign('0.00')).toBe(0);
  });

  it('negates by rewriting the sign', () => {
    expect(negateAmount('12.50')).toBe('-12.50');
    expect(negateAmount('-12.50')).toBe('12.50');
    expect(negateAmount('-0.00')).toBe('0.00');
  });
});

describe('formatRatio', () => {
  it('formats fractions as percentages exactly', () => {
    expect(formatRatio('0.185', { locale: 'en-US' })).toBe('18.5%');
    expect(formatRatio('0.18', { locale: 'en-US' })).toBe('18%');
    expect(formatRatio('1.25', { locale: 'en-US' })).toBe('125%');
    expect(formatRatio(0.5, { locale: 'en-US' })).toBe('50%');
    expect(formatRatio('unknown')).toBe('unknown');
    expect(formatRatio(null)).toBe('');
  });
});

describe('normalizeAmountInput', () => {
  it('accepts what people type', () => {
    expect(normalizeAmountInput('1500')).toBe('1500');
    expect(normalizeAmountInput(' 1500.5 ')).toBe('1500.5');
    expect(normalizeAmountInput('+12')).toBe('12');
    expect(normalizeAmountInput('-12.30')).toBe('-12.30');
    expect(normalizeAmountInput('1,234,567.89')).toBe('1234567.89');
    expect(normalizeAmountInput('.5')).toBe('0.5');
    expect(normalizeAmountInput('-.5')).toBe('-0.5');
    expect(normalizeAmountInput('12.')).toBe('12');
  });

  it('refuses anything ambiguous', () => {
    expect(normalizeAmountInput('1,23')).toBeUndefined();
    expect(normalizeAmountInput('12,34.5')).toBeUndefined();
    expect(normalizeAmountInput('1.234,50')).toBeUndefined();
    expect(normalizeAmountInput('abc')).toBeUndefined();
    expect(normalizeAmountInput('1e3')).toBeUndefined();
    expect(normalizeAmountInput('')).toBeUndefined();
  });
});

describe('compareAmounts', () => {
  it('orders amounts exactly by their digits', () => {
    expect(compareAmounts('412.35', '1800.00')).toBe(-1);
    expect(compareAmounts('1800', '1800.00')).toBe(0);
    expect(compareAmounts('0.10', '0.09')).toBe(1);
    expect(compareAmounts('-5', '3')).toBe(-1);
    expect(compareAmounts('-5.5', '-5.25')).toBe(-1);
    expect(compareAmounts('-0.00', '0')).toBe(0);
    expect(compareAmounts('007.5', '7.50')).toBe(0);
    // Beyond a double's precision, still exact.
    expect(compareAmounts('9007199254740993', '9007199254740992')).toBe(1);
    expect(compareAmounts('0.30000000000000001', '0.3')).toBe(1);
  });

  it('sorts a list without converting to numbers', () => {
    expect(['1800.00', '412.35', '9.99', '1800.01'].sort(compareAmounts)).toEqual(['9.99', '412.35', '1800.00', '1800.01']);
  });
});
