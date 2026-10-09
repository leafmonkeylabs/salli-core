/**
 * What the mock server knows: a small USD household ledger. Each fixture
 * is typed with the SDK's generated type for its response, so the compiler
 * keeps the mock in step with the OpenAPI document.
 */
import type {
  Account,
  BalanceSheet,
  FiScore,
  IncomeStatement,
  JournalEntry,
  Posting,
  Reminder,
  StatementUpload,
  Tag,
  TrialBalance,
} from '@leafmonkeylabs/salli-sdk';

/** Fixture ids: distinct in their first eight characters, as real UUIDs are. */
export const uid = (n: number): string => `${n.toString(16).padStart(8, '0')}-5a11-4000-8000-${String(n).padStart(12, '0')}`;

export const ACCOUNTS: Account[] = [
  { id: uid(1), code: '1000', name: 'Cash', type: 'asset', currency: 'USD', parent_id: null, is_active: true, tax_role: null },
  { id: uid(2), code: '1100', name: 'Checking', type: 'asset', currency: 'USD', parent_id: null, is_active: true, tax_role: null },
  { id: uid(3), code: '1200', name: 'Euro Savings', type: 'asset', currency: 'EUR', parent_id: null, is_active: true, tax_role: null },
  { id: uid(4), code: '2000', name: 'Credit Card', type: 'liability', currency: 'USD', parent_id: null, is_active: true, tax_role: null },
  { id: uid(5), code: '4000', name: 'Salary', type: 'income', currency: 'USD', parent_id: null, is_active: true, tax_role: null },
  { id: uid(6), code: '5000', name: 'Groceries', type: 'expense', currency: 'USD', parent_id: null, is_active: true, tax_role: null },
  { id: uid(7), code: '5100', name: 'Rent', type: 'expense', currency: 'USD', parent_id: null, is_active: true, tax_role: null },
  { id: uid(8), code: '5900', name: 'Old Expenses', type: 'expense', currency: 'USD', parent_id: null, is_active: false, tax_role: null },
];

const posting = (id: number, account: number, direction: 1 | -1, amount: string, currency = 'USD', fx = '1'): Posting => ({
  id: uid(100 + id),
  tags: {},
  account_id: uid(account),
  direction,
  amount,
  currency,
  fx_rate: fx,
});

export const ENTRIES: JournalEntry[] = [
  {
    id: uid(201),
    entry_date: '2026-10-01',
    description: 'October salary',
    source: 'manual',
    external_ref: null,
    reversed_by: null,
    postings: [posting(1, 2, 1, '5000.00'), posting(2, 5, -1, '5000.00')],
  },
  {
    id: uid(202),
    entry_date: '2026-10-03',
    description: 'Rent for October',
    source: 'manual',
    external_ref: null,
    reversed_by: null,
    postings: [posting(3, 7, 1, '1800.00'), posting(4, 2, -1, '1800.00')],
  },
  {
    id: uid(203),
    entry_date: '2026-10-05',
    description: 'Weekly groceries',
    source: 'statement',
    external_ref: uid(901),
    reversed_by: null,
    postings: [{ ...posting(5, 6, 1, '412.35'), tags: { category: 'groceries', need: 'essential' } }, posting(6, 4, -1, '412.35')],
  },
  {
    id: uid(204),
    entry_date: '2026-10-06',
    description: 'Split dinner',
    source: 'manual',
    external_ref: null,
    reversed_by: uid(205),
    postings: [posting(7, 6, 1, '30.00'), posting(8, 6, 1, '20.00'), posting(9, 1, -1, '50.00')],
  },
];

export const BALANCE_SHEET = {
  currency: 'USD',
  assets: [
    { account_id: uid(1), code: '1000', name: 'Cash', balance: '250.00' },
    { account_id: uid(2), code: '1100', name: 'Checking', balance: '12784.50' },
    { account_id: uid(3), code: '1200', name: 'Euro Savings', balance: '2200.00' },
  ],
  liabilities: [{ account_id: uid(4), code: '2000', name: 'Credit Card', balance: '1200.00' }],
  equity: [],
  total_assets: '15234.50',
  total_liabilities: '1200.00',
  total_equity: '0.00',
  net_worth: '14034.50',
} satisfies BalanceSheet;

export const INCOME_STATEMENT = (from: string, to: string): IncomeStatement => ({
  from_date: from,
  to_date: to,
  currency: 'USD',
  income: { Salary: '5000.00' },
  expenses: { Groceries: '412.35', Rent: '1800.00' },
  total_income: '5000.00',
  total_expenses: '2212.35',
  net_income: '2787.65',
  lines: [
    { account_id: uid(5), code: '4000', name: 'Salary', type: 'income', amount: '5000.00', is_active: true },
    { account_id: uid(6), code: '5000', name: 'Groceries', type: 'expense', amount: '412.35', is_active: true },
    { account_id: uid(7), code: '5100', name: 'Rent', type: 'expense', amount: '1800.00', is_active: true },
  ],
});

export const TRIAL_BALANCE = {
  currency: 'USD',
  balances: { [uid(1)]: '250.00', [uid(2)]: '12784.50', [uid(4)]: '-1200.00', [uid(5)]: '-11834.50' },
  net: '0.00',
} satisfies TrialBalance;

export const FI_SCORE = {
  pack_version: '1',
  overall_score: '72.5',
  grade: 'B',
  monthly_income: '5000.00',
  monthly_expenses: '2212.35',
  monthly_surplus: '2787.65',
  savings_rate: '0.5575',
  swr: '0.04',
  annual_expenses: '26548.20',
  fi_number: '663705.00',
  net_worth: '14034.50',
  fi_asset_base: '12834.50',
  progress_to_fi: '0.0193',
  emergency_fund_months: '5.8',
  debt_to_asset: '0.0788',
  projected_fi_years: '14',
  currency: 'USD',
  components: [
    { key: 'savings_rate', label: 'Savings rate', score: '90', weight: '0.3', detail: '56% of income saved' },
    { key: 'emergency_fund', label: 'Emergency fund', score: '80', weight: '0.2', detail: '5.8 months covered' },
  ],
  projected_fi_date: '2040-10-09',
  inputs_hash: 'abc',
} satisfies FiScore;

export const REMINDERS: Reminder[] = [
  {
    id: uid(301),
    kind: 'budget_overspend',
    due_date: '2026-10-09',
    status: 'pending',
    alert_type: 'budget_overspend',
    source_domain: 'budget',
    source_id: uid(401),
    severity: 'warning',
    created_at: '2026-10-08T09:00:00+00:00',
  },
  {
    id: uid(302),
    kind: 'return_due_2025/26',
    due_date: '2026-11-30',
    status: 'pending',
    alert_type: null,
    source_domain: null,
    source_id: null,
    severity: null,
    created_at: '2026-04-01T09:00:00+00:00',
  },
  {
    id: uid(303),
    kind: 'quarterly_installment',
    due_date: '2026-08-15',
    status: 'done',
    alert_type: null,
    source_domain: null,
    source_id: null,
    severity: null,
    created_at: '2026-04-01T09:00:00+00:00',
  },
];

export const TAGS: Tag[] = [
  { id: uid(501), slug: 'groceries', name: 'Groceries', kind: 'category', color: '#4caf50', is_system: false },
  { id: uid(502), slug: 'essential', name: 'Essential', kind: 'need', color: '#9e9e9e', is_system: true },
];

export const STATEMENT_UPLOAD = {
  statement_id: uid(801),
  bank: 'Acme Bank',
  period_start: '2026-09-01',
  period_end: '2026-09-30',
  total_rows: 4,
  parsed: 3,
  errors: ['Row 4: no amount'],
  transactions: [
    {
      id: uid(901),
      date: '2026-09-02',
      description: 'SUPERMARKET 123',
      amount: '45.20',
      credit_flag: false,
      bank_ref: 'REF1',
      currency: 'USD',
      debit_account_id: uid(6),
      credit_account_id: uid(2),
      category: 'Groceries',
      confidence: 0.92,
      dedup_status: 'unique',
    },
    {
      id: uid(902),
      date: '2026-09-03',
      description: 'COFFEE SHOP',
      amount: '4.50',
      credit_flag: false,
      bank_ref: 'REF2',
      currency: 'USD',
      debit_account_id: uid(6),
      credit_account_id: uid(2),
      category: 'Dining',
      confidence: 0.61,
      dedup_status: 'fuzzy_match',
    },
    {
      id: uid(903),
      date: '2026-09-05',
      description: 'RENT SEPT',
      amount: '1800.00',
      credit_flag: false,
      bank_ref: 'REF3',
      currency: 'USD',
      debit_account_id: uid(7),
      credit_account_id: uid(2),
      category: 'Rent',
      confidence: 0.99,
      dedup_status: 'exact_duplicate',
    },
  ],
} satisfies StatementUpload;
