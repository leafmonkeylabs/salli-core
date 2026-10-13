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
 * - `figure`: a key figure, its code small in Geist Mono before it and the
 *   figure as a statement shows it: `EUR (370.00)`.
 *
 * Screen readers hear "minus 370.00 US dollars": the currency as a word and
 * the sign as a word, not a hyphen some readers skip or brackets they read as
 * nothing (docs/design/console.md, section 4).
 *
 * `signed` is for a change the server computed (a delta, a difference): a
 * positive one shows its plus (`+120.00`, "plus 120.00 euros"), read from
 * the text as the minus is.
 */
import { amountSign, formatAmount, isAmount, isNegativeAmount, negateAmount } from '@leafmonkeylabs/salli-sdk';
import { useLocale } from '../preferences';
import { strings } from '../strings';

export interface MoneyProps {
  amount: string | null | undefined;
  currency: string;
  variant?: 'prose' | 'table' | 'figure';
  /** In a table: show the code too (a column of mixed currencies). */
  withCode?: boolean;
  /** A change: show a positive one's plus as well as a negative's minus. */
  signed?: boolean;
}

/** Whether a change shows a plus: above zero, read from its text. */
function plus(amount: string, signed: boolean | undefined): boolean {
  return Boolean(signed) && isAmount(amount.trim()) && amountSign(amount) > 0;
}

/** What a screen reader says for an amount: "minus 370.00 US dollars". */
export function spokenAmount(amount: string, currency: string, locale?: string, signed?: boolean): string {
  if (!isAmount(amount.trim())) return amount;
  const negative = isNegativeAmount(amount);
  const magnitude = negative ? negateAmount(amount) : amount;
  const words = formatAmount(magnitude, currency, { display: 'name', locale });
  if (negative) return `${strings.money.minus} ${words}`;
  return plus(amount, signed) ? `${strings.money.plus} ${words}` : words;
}

/** The visible text of an amount, as `variant` shows it. */
export function visibleAmount(
  amount: string,
  currency: string,
  variant: MoneyProps['variant'] = 'prose',
  options: { locale?: string | undefined; withCode?: boolean; signed?: boolean } = {},
): string {
  const { locale, withCode = false, signed } = options;
  if (!isAmount(amount.trim())) return amount;
  const code = currency.toUpperCase();
  const sign = plus(amount, signed) ? '+' : '';
  if (variant === 'table') {
    const negative = isNegativeAmount(amount);
    const digits = formatAmount(negative ? negateAmount(amount) : amount, code, { display: 'none', locale });
    const shown = negative ? `(${digits})` : `${sign}${digits}`;
    return withCode ? `${code} ${shown}` : shown;
  }
  return `${code} ${sign}${formatAmount(amount, code, { display: 'none', locale })}`;
}

export function Money({ amount, currency, variant = 'prose', withCode, signed }: MoneyProps) {
  const locale = useLocale();
  if (amount === null || amount === undefined || amount === '') return null;
  const negative = isAmount(amount.trim()) && isNegativeAmount(amount);
  const className = ['money', `money-${variant}`, negative ? 'money-negative' : ''].filter(Boolean).join(' ');
  if (variant === 'figure' && isAmount(amount.trim())) {
    // A key figure: its currency's code small before it, the figure as a statement shows it.
    return (
      <span className={className} data-amount={amount}>
        <span aria-hidden="true">
          <span className="money-code">{currency.toUpperCase()}</span>
          {visibleAmount(amount, currency, 'table', { locale, signed: signed ?? false })}
        </span>
        <span className="sr-only">{spokenAmount(amount, currency, locale, signed)}</span>
      </span>
    );
  }
  return (
    <span className={className} data-amount={amount}>
      <span aria-hidden="true">{visibleAmount(amount, currency, variant, { locale, withCode: withCode ?? false, signed: signed ?? false })}</span>
      <span className="sr-only">{spokenAmount(amount, currency, locale, signed)}</span>
    </span>
  );
}
