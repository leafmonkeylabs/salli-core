/**
 * Response shapes the CLI reads.
 *
 * Many operations are still `unknown` in the OpenAPI document. For those,
 * `Typed<Generated, Today>` falls back to the shape the Python handler
 * returns today (written out below, from src/salli/interfaces/api/routers).
 * When the spec types an operation and the SDK is regenerated, the
 * generated type takes over automatically, and the compiler points at any
 * use that no longer fits.
 */
import type {
  Account,
  DataOf,
  entriesGet,
  entriesList,
  entriesProvenance,
  fiScoreGet,
  ledgerIncomeStatement,
  ledgerTrialBalance,
  remindersList,
  reportsBalanceSheet,
  statementsList,
  statementsPending,
  statementsPost,
  statementsUpload,
  tagsList,
} from '@leafmonkeylabs/salli-sdk';

/** The generated type once the spec describes it; until then, today's shape. */
export type Typed<Generated, Today> = unknown extends Generated ? Today : Generated;

export type { Account };

// ── Entries ──────────────────────────────────────────────────────────────────

export interface TodayPosting {
  id: string;
  tags: Record<string, string>;
  account_id: string;
  /** 1 debit, -1 credit. */
  direction: number;
  amount: string;
  currency: string;
  fx_rate: string;
}

export interface TodayEntry {
  id: string;
  entry_date: string;
  description: string;
  source: string;
  external_ref: string | null;
  reversed_by: string | null;
  postings: TodayPosting[];
}

export type EntryList = Typed<DataOf<typeof entriesList>, TodayEntry[]>;
export type Entry = Typed<DataOf<typeof entriesGet>, TodayEntry>;
export type Posting = Entry['postings'][number];

export interface TodayProvenance {
  entry_id: string;
  source: string;
  external_ref: string | null;
  statement: {
    parsed_transaction_id: string;
    raw_description: string;
    raw_amount: string;
    raw_date: string;
    bank_ref: string | null;
    statement: { bank?: string | null; period_start?: string | null; period_end?: string | null; storage_key?: string | null } | null;
  } | null;
  receipt: { document_id: string; title: string; mime_type: string } | null;
  possible_subscriptions?: unknown[];
}
export type Provenance = Typed<DataOf<typeof entriesProvenance>, TodayProvenance>;

// ── Ledger and reports ───────────────────────────────────────────────────────

export interface TodayTrialBalance {
  currency: string;
  /** account id → balance, debit positive. */
  balances: Record<string, string>;
  net: string;
}
export type TrialBalance = Typed<DataOf<typeof ledgerTrialBalance>, TodayTrialBalance>;

export interface TodayIncomeStatement {
  from_date: string;
  to_date: string;
  currency: string;
  /** account name → amount */
  income: Record<string, string>;
  expenses: Record<string, string>;
  net_income: string;
}
export type IncomeStatement = Typed<DataOf<typeof ledgerIncomeStatement>, TodayIncomeStatement>;

export interface BalanceSheetLine {
  account_id: string;
  code: string;
  name: string;
  balance: string;
}
export interface TodayBalanceSheet {
  currency: string;
  assets: BalanceSheetLine[];
  liabilities: BalanceSheetLine[];
  equity: BalanceSheetLine[];
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  net_worth: string;
}
export type BalanceSheet = Typed<DataOf<typeof reportsBalanceSheet>, TodayBalanceSheet>;

export interface TodayTag {
  id: string;
  slug: string;
  name: string;
  kind: string;
  color: string | null;
  is_system: boolean;
}
export type TagList = Typed<DataOf<typeof tagsList>, { tags: TodayTag[] }>;

// ── Financial independence and reminders ─────────────────────────────────────

export interface TodayFiScore {
  pack_version?: string;
  overall_score: string;
  grade: string;
  monthly_income: string;
  monthly_expenses: string;
  monthly_surplus: string;
  /** A fraction. */
  savings_rate: string;
  fi_number: string;
  net_worth: string;
  /** A fraction, unclamped. */
  progress_to_fi: string;
  emergency_fund_months: string;
  projected_fi_date: string | null;
  currency: string;
  components?: Array<{ label?: string; score?: string; weight?: string; detail?: string }>;
}
export type FiScore = Typed<DataOf<typeof fiScoreGet>, TodayFiScore>;

export interface TodayReminder {
  id: string;
  kind: string;
  due_date: string;
  status: string;
  alert_type: string | null;
  source_domain?: string | null;
  source_id?: string | null;
  severity: string | null;
  created_at?: string;
}
export type ReminderList = Typed<DataOf<typeof remindersList>, { reminders: TodayReminder[] }>;

// ── Statements ───────────────────────────────────────────────────────────────

export interface TodayStatementTransaction {
  id: string | null;
  date: string;
  description: string;
  amount: string;
  /** true: money in (a credit on the statement). */
  credit_flag: boolean;
  bank_ref: string | null;
  currency: string;
  debit_account_id: string | null;
  credit_account_id: string | null;
  category: string | null;
  confidence: number;
  /** unique | exact_duplicate | fuzzy_match | confirmed_duplicate */
  dedup_status: string;
}

export interface TodayStatementUpload {
  statement_id: string;
  bank: string;
  period_start: string | null;
  period_end: string | null;
  total_rows: number;
  parsed: number;
  errors: string[];
  transactions: TodayStatementTransaction[];
}
export type StatementUpload = Typed<DataOf<typeof statementsUpload>, TodayStatementUpload>;
export type StatementPending = Typed<
  DataOf<typeof statementsPending>,
  { statement_id: string; transactions: TodayStatementTransaction[] }
>;
export type StatementPost = Typed<DataOf<typeof statementsPost>, { posted: number; entry_ids: string[] }>;

export interface TodayStatement {
  id: string;
  bank: string | null;
  period_start: string | null;
  period_end: string | null;
  status: string | null;
  created_at: string | null;
}
export type StatementList = Typed<DataOf<typeof statementsList>, { statements: TodayStatement[] }>;
