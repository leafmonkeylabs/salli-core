/**
 * An amount, exactly as Salli sent it (decision 12).
 *
 * The amount stays the API's decimal string from the response to the
 * screen: `formatAmount` formats the string itself at the currency's own
 * precision in this device's locale, and nothing here turns it into a
 * number or does arithmetic with it. The sign is read from the text.
 *
 * - `prose` (the default): `USD -370.00`, the code first, as the CLI shows it.
 * - `table`: `(370.00)` in oxblood for a negative, with no code (the column
 *   header names the currency), right-aligned in tabular figures.
 *
 * Screen readers hear "minus 370.00 US dollars": the currency as a word and
 * the sign as a word, not a hyphen some readers skip or brackets they read as
 * nothing (docs/design/console.md, section 4).
 */
import { formatAmount, isAmount, isNegativeAmount, negateAmount } from '@leafmonkeylabs/salli-sdk';
import { useLocale } from '../preferences';
import { strings } from '../strings';

export interface MoneyProps {
  amount: string | null | undefined;
  currency: string;
  variant?: 'prose' | 'table' | 'figure';
  /** In a table: show the code too (a column of mixed currencies). */
  withCode?: boolean;
}

/** What a screen reader says for an amount: "minus 370.00 US dollars". */
export function spokenAmount(amount: string, currency: string, locale?: string): string {
  if (!isAmount(amount.trim())) return amount;
  const negative = isNegativeAmount(amount);
  const magnitude = negative ? negateAmount(amount) : amount;
  const words = formatAmount(magnitude, currency, { display: 'name', locale });
  return negative ? `${strings.money.minus} ${words}` : words;
}

/** The visible text of an amount, as `variant` shows it. */
export function visibleAmount(
  amount: string,
  currency: string,
  variant: MoneyProps['variant'] = 'prose',
  options: { locale?: string | undefined; withCode?: boolean } = {},
): string {
  const { locale, withCode = false } = options;
  if (!isAmount(amount.trim())) return amount;
  const code = currency.toUpperCase();
  if (variant === 'table') {
    const negative = isNegativeAmount(amount);
    const digits = formatAmount(negative ? negateAmount(amount) : amount, code, { display: 'none', locale });
    const shown = negative ? `(${digits})` : digits;
    return withCode ? `${code} ${shown}` : shown;
  }
  return `${code} ${formatAmount(amount, code, { display: 'none', locale })}`;
}

export function Money({ amount, currency, variant = 'prose', withCode }: MoneyProps) {
  const locale = useLocale();
  if (amount === null || amount === undefined || amount === '') return null;
  const negative = isAmount(amount.trim()) && isNegativeAmount(amount);
  const className = ['money', `money-${variant}`, negative ? 'money-negative' : ''].filter(Boolean).join(' ');
  return (
    <span className={className} data-amount={amount}>
      <span aria-hidden="true">{visibleAmount(amount, currency, variant, { locale, withCode: withCode ?? false })}</span>
      <span className="sr-only">{spokenAmount(amount, currency, locale)}</span>
    </span>
  );
}
