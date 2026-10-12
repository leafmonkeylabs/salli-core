/**
 * How the import pages name a statement and find its review.
 */
import type { BankStatement } from '@leafmonkeylabs/salli-sdk';
import { bookStrings } from '../../books-strings';
import { displayRange } from '../../kit/dates';
import type { AccountBook } from './ledger';

const t = bookStrings.imports;

/** Where a statement's review is. */
export function reviewPath(id: string): string {
  return `/books/imports/${encodeURIComponent(id)}`;
}

/** "Example Bank" or the account, and the period: how a statement is named. */
export function statementName(statement: Pick<BankStatement, 'bank' | 'account_id'>, book: AccountBook | undefined): string {
  return statement.bank || (statement.account_id && book ? book.name(statement.account_id) : '') || t.statements;
}

export function periodOf(statement: { period_start: string | null; period_end: string | null }, locale?: string): string {
  return statement.period_start && statement.period_end ? displayRange(statement.period_start, statement.period_end, locale) : '';
}
