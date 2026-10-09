/**
 * What several commands share: confirmation, the chart of accounts as a
 * lookup, and reading loosely typed responses.
 */
import { accountsList, normalizeAmountInput, type Account, type SalliClient } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { parseWholeNumber } from '../util/numbers';
import { accountLabel, resolveAccount } from '../util/resolve';

/** Asks before doing something hard to undo; --yes answers for scripts. */
export async function confirmAction(app: App, yes: boolean | undefined, message: string): Promise<boolean> {
  if (yes) return true;
  if (!app.prompter.interactive) {
    throw new UsageError(`${message.replace(/\?$/, '')}: this needs confirmation.`, 'Pass --yes to confirm.');
  }
  return app.prompter.confirm({ message, initialValue: false });
}

/** An amount someone typed, in the API's format; a usage error if it is not one. */
export function amountArg(value: string, flag = 'amount'): string {
  const amount = normalizeAmountInput(value);
  if (amount === undefined) {
    throw new UsageError(`${flag} must be a number like 1500 or 1234.50 (got "${value}").`);
  }
  return amount;
}

/** An ISO 4217 code someone typed, upper-cased. */
export function currencyArg(value: string): string {
  const code = value.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(code)) throw new UsageError(`A currency is a three-letter ISO 4217 code like USD (got "${value}").`);
  return code;
}

/** The chart of accounts, for naming and finding accounts. */
export class AccountBook {
  readonly accounts: Account[];
  private readonly byIdMap: Map<string, Account>;

  constructor(accounts: Account[]) {
    this.accounts = accounts;
    this.byIdMap = new Map(accounts.map((a) => [a.id, a]));
  }

  static async load(api: SalliClient): Promise<AccountBook> {
    return new AccountBook(await api.call(accountsList));
  }

  get(id: string | null | undefined): Account | undefined {
    return id ? this.byIdMap.get(id) : undefined;
  }

  /** "5000 Groceries", or the id's start when the account is unknown. */
  label(id: string | null | undefined): string {
    return id ? accountLabel(this.get(id), id) : '—';
  }

  /** Just the name ("Groceries"). */
  name(id: string | null | undefined): string {
    const account = this.get(id);
    return account ? account.name : id ? id.slice(0, 8) : '—';
  }

  resolve(query: string): Account {
    return resolveAccount(this.accounts, query);
  }
}

/** Splits `ACCOUNT:AMOUNT` at its last colon. */
export function accountAmountArg(value: string, flag: string): { account: string; amount: string } {
  const at = value.lastIndexOf(':');
  if (at <= 0 || at === value.length - 1) {
    throw new UsageError(`${flag} takes ACCOUNT:AMOUNT, e.g. ${flag} groceries:12.50 (got "${value}").`);
  }
  return { account: value.slice(0, at), amount: amountArg(value.slice(at + 1), flag) };
}

/** `axis=slug` pairs into a tags object. */
export function tagArgs(values: readonly string[]): Record<string, string> {
  const tags: Record<string, string> = {};
  for (const value of values) {
    const [axis, slug] = value.split('=', 2);
    if (!axis || !slug) throw new UsageError(`A tag is AXIS=SLUG, e.g. category=groceries (got "${value}").`);
    tags[axis.trim()] = slug.trim();
  }
  return tags;
}

/** Collects a repeatable option's values. */
export function collect(value: string, previous: string[] = []): string[] {
  return [...previous, value];
}

/** Accepts a positive whole number for --limit. */
export function limitArg(value: string): number {
  const n = parseWholeNumber(value);
  if (n === undefined || n < 1) throw new UsageError(`--limit must be a positive whole number (got "${value}").`);
  return n;
}
