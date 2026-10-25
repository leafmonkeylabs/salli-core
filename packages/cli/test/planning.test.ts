import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { FI_SCORE, uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, {
    configDir: dir,
    ...options,
    env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env },
  });

const lastBody = (path: string) => mock.data.bodies.filter((b) => b.path.startsWith(path)).at(-1)?.body;

describe('money on the wire', () => {
  it("reads amounts in the comma-decimal locale set for it, and only that one", async () => {
    const de = { env: { SALLI_LOCALE: 'de-DE' } };
    const added = await run(['debts', 'add', 'Store card', '--balance', '1.234,50', '--apr', '18,5%', '--minimum', '25'], de);
    expect(added.code, added.stderr).toBe(0);
    expect(lastBody('/v1/debt/')).toEqual({ name: 'Store card', principal: '1234.50', apr: '0.185', minimum_payment: '25' });

    // A thousand in German, a little over one in the API's format: refused.
    const ambiguous = await run(['debts', 'add', 'Loan', '--balance', '1.234', '--apr', '5%', '--minimum', '25'], de);
    expect(ambiguous.code).toBe(2);
    expect(ambiguous.stderr).toContain('--balance');

    // Without a locale set, the machine's own never changes what is read.
    const plain = await run(['debts', 'add', 'Loan', '--balance', '1.234,50', '--apr', '5%', '--minimum', '25']);
    expect(plain.code).toBe(2);
  });

  it('sends every amount as the decimal string typed, never a JSON number', async () => {
    await run(['debts', 'add', 'Store card', '--balance', '1,234.50', '--apr', '18%', '--minimum', '25']);
    expect(lastBody('/v1/debt/')).toEqual({ name: 'Store card', principal: '1234.50', apr: '0.18', minimum_payment: '25' });

    await run(['holdings', 'add', 'VXUS', '--name', 'Intl stocks', '--class', 'equity', '--invested', '5000', '--value', '5321.07']);
    expect(lastBody('/v1/portfolio/')).toEqual({ symbol: 'VXUS', name: 'Intl stocks', asset_class: 'equity', cost_basis: '5000', current_value: '5321.07' });

    await run(['subscriptions', 'add', 'Gym', '--amount', '39.99', '--frequency', 'monthly', '--next', '2026-11-01', '--tolerance', '5%']);
    expect(lastBody('/v1/subscriptions/')).toEqual({ name: 'Gym', amount: '39.99', frequency: 'monthly', next_due_date: '2026-11-01', amount_tolerance_pct: '0.05' });

    await run(['budgets', 'add', '--month', '2026-11', '--line', 'groceries:400', '--line', '5100:1800.00']);
    expect(lastBody('/v1/budget/')).toEqual({
      period_start: '2026-11-01',
      period_end: '2026-11-30',
      lines: [
        { account_id: uid(6), limit_amount: '400' },
        { account_id: uid(7), limit_amount: '1800.00' },
      ],
    });

    await run(['insurance', 'targets', 'set', 'life', '--amount', '750000']);
    expect(lastBody('/v1/insurance/targets')).toEqual({ policy_type: 'life', target_amount: '750000' });

    await run(['goals', 'allocate', uid(451).slice(0, 8), 'checking', '9000.00']);
    expect(lastBody('/v1/fi/goals/')).toEqual({ account_id: uid(2), allocated_amount: '9000.00' });

  });
});

describe('budgets', () => {
  it('lists budgets and compares a budget with spending', async () => {
    expect((await run(['budgets', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        PERIOD            CATEGORIES  CURRENCY
      00000191  Oct 1 – 31, 2026           2  USD
      "
    `);
    const summary = await run(['budgets', 'summary', uid(401).slice(0, 8)]);
    expect(summary.stdout).toMatchInlineSnapshot(`
      "Budget Oct 1 – 31, 2026
      CATEGORY      LIMIT     SPENT    LEFT
      Groceries    400.00    412.35  -12.35
      Rent       1,800.00  1,800.00    0.00
      Total      2,200.00  2,212.35  -12.35
      "
    `);
  });
});

describe('debts', () => {
  it('lists debts and plans their payoff', async () => {
    expect((await run(['debts', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        NAME              BALANCE     APR     MINIMUM
      0000019b  Credit card  USD 1,200.00  23.99%   USD 35.00
      0000019c  Car loan     USD 8,400.00    6.9%  USD 310.00
      Owed in all       USD 9,600.00
      Minimums a month  USD 345.00
      "
    `);
    const plan = await run(['debts', 'payoff-plan', '--strategy', 'snowball', '--extra', '100']);
    expect(plan.stdout).toMatchInlineSnapshot(`
      "Strategy       snowball
      Debt-free      after Dec 2028 (26 months)
      Interest paid  USD 845.12

      MONTH     DEBT         PAYMENT  PRINCIPAL  INTEREST      LEFT
      Nov 2026  Credit card   135.00     111.01     23.99  1,088.99
      Nov 2026  Car loan      310.00     261.70     48.30  8,138.30
      "
    `);
    expect(mock.requestsTo('GET', '/v1/debt/payoff-plan')[0]?.query.toString()).toBe('strategy=snowball&extra_monthly_payment=100');
  });

  it('marks a debt paid off, and refuses an update with nothing to change', async () => {
    expect((await run(['debts', 'update', uid(411).slice(0, 8), '--paid-off'])).code).toBe(0);
    expect(lastBody(`/v1/debt/${uid(411)}`)).toEqual({ is_active: false });
    expect((await run(['debts', 'update', uid(411).slice(0, 8)])).code).toBe(2);
  });

  it('links a debt to the account that holds it, and unlinks it', async () => {
    expect((await run(['debts', 'update', uid(411).slice(0, 8), '--account', '2000'])).code).toBe(0);
    expect(lastBody(`/v1/debt/${uid(411)}`)).toEqual({ account_id: uid(4) });
    expect((await run(['debts', 'update', uid(411).slice(0, 8), '--no-account'])).code).toBe(0);
    expect(lastBody(`/v1/debt/${uid(411)}`)).toEqual({ account_id: null });
    await run(['debts', 'add', 'Store card', '--balance', '600', '--apr', '21%', '--minimum', '30', '--account', 'credit']);
    expect(lastBody('/v1/debt/')).toEqual({ name: 'Store card', principal: '600', apr: '0.21', minimum_payment: '30', account_id: uid(4) });
  });
});

describe('investments, subscriptions and insurance', () => {
  it('links a holding to the investment account that holds it, and unlinks it', async () => {
    expect((await run(['holdings', 'update', 'VTI', '--account', '1200'])).code).toBe(0);
    expect(lastBody(`/v1/portfolio/${uid(421)}`)).toEqual({ account_id: uid(3) });
    expect((await run(['holdings', 'update', 'VTI', '--no-account'])).code).toBe(0);
    expect(lastBody(`/v1/portfolio/${uid(421)}`)).toEqual({ account_id: null });
    await run(['holdings', 'add', 'VXUS', '--name', 'Intl', '--class', 'equity', '--account', 'euro']);
    expect(lastBody('/v1/portfolio/')).toEqual({ symbol: 'VXUS', name: 'Intl', asset_class: 'equity', account_id: uid(3) });
  });

  it('summarises the portfolio with rebalancing against a target', async () => {
    const result = await run(['portfolio', '--target', 'equity:0.6', '--target', 'bond:0.4']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "Value     USD 14,140.50
      Invested  USD 12,000.00
      Gain      USD 2,140.50 (17.84%)

      ASSET CLASS  VALUE (USD)  SHARE
      equity         11,250.40  79.6%
      bond            2,890.10  20.4%

      Expense ratio  0.03% weighted, on USD 11,250.40
      Yearly cost    USD 3.38

      Rebalancing
      ASSET CLASS    NOW  TARGET  DRIFT
      equity       79.6%     60%  19.6%
      "
    `);
    expect(mock.requestsTo('GET', '/v1/portfolio/summary')[0]?.query.getAll('target')).toEqual(['equity:0.6', 'bond:0.4']);
  });

  it('keeps an investment policy and reports drift beside the risk profile', async () => {
    const set = await run(['ips', 'set', '--target', 'equity:0.8:0.05', '--target', 'bond:20%', '--rebalance', 'both', '--every-months', '12', '--horizon', '12', '--review-on', '2027-10-01']);
    expect(set.code).toBe(0);
    expect(lastBody('/v1/ips')).toEqual({
      targets: [{ asset_class: 'equity', target: '0.8', band: '0.05' }, { asset_class: 'bond', target: '0.2' }],
      rebalancing: { rule: 'both', every_months: 12 },
      horizon_years: 12,
      review_on: '2027-10-01',
    });
    const drift = await run(['ips', 'drift']);
    expect(drift.stdout).toContain('Capacity');
    expect(drift.stdout).toContain('above your balanced profile');
    expect((await run(['ips'])).stdout).toContain('version 2');
    expect((await run(['ips', 'history'])).stdout).toContain('equity 80%');
    expect((await run(['ips', 'risk'])).stdout).toContain('balanced: equity up to 70%');
  });

  it('works out insurance needs as figures and sets a holding’s cost method', async () => {
    const needs = await run(['insurance', 'needs', '--years', '15']);
    expect(mock.requestsTo('GET', '/v1/insurance/needs')[0]?.query.get('replacement_years')).toBe('15');
    expect(needs.stdout).toContain('Life cover need');
    await run(['holdings', 'update', 'VTI', '--cost-method', 'average', '--expense-ratio', '0.03%']);
    expect(lastBody('/v1/portfolio/')).toEqual({ cost_method: 'average', expense_ratio: '0.0003' });
    await run(['holdings', 'update', 'VTI', '--cost-method', 'default', '--expense-ratio', 'none']);
    expect(lastBody('/v1/portfolio/')).toEqual({ cost_method: null, expense_ratio: null });
  });

  it('lists holdings, subscriptions and policies', async () => {
    expect((await run(['holdings', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        SYMBOL  NAME                CLASS   QUANTITY      INVESTED          VALUE
      000001a5  VTI     Total Stock Market  equity        40  USD 9,000.00  USD 11,250.40
      000001a6  BND     Total Bond Market   bond              USD 3,000.00   USD 2,890.10
      "
    `);
    expect((await run(['subscriptions', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        NAME          AMOUNT  EVERY  NEXT
      000001af  Streaming  USD 15.99  month  Oct 20, 2026
      "
    `);
    expect((await run(['insurance', 'policies', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        NAME       TYPE  PROVIDER            COVER            PREMIUM  EXPIRES
      000001b9  Term life  life  Acme Life  USD 500,000.00  USD 42.00 monthly  Jan 1, 2046
      "
    `);
  });

  it('reports cover gaps', async () => {
    expect((await run(['insurance', 'report'])).stdout).toMatchInlineSnapshot(`
      "TYPE      TARGET     COVERED         GAP
      life  750,000.00  500,000.00  250,000.00
      ! No cover at all for: health
      "
    `);
  });
});

describe('financial independence and goals', () => {
  it('shows the FI score with its parts', async () => {
    expect((await run(['fi', 'score'])).stdout).toMatchInlineSnapshot(`
      "FI score 72.5 (grade B)
      Monthly income    USD 5,000.00
      Monthly spending  USD 2,212.35
      Monthly surplus   USD 2,787.65
      Savings rate      55.8%
      FI number         USD 663,705.00
      Net worth         USD 14,034.50
      Progress to FI    1.9%
      Emergency fund    5.8 months
      FI by             Oct 2040

      PART            SCORE  WEIGHT  WHY
      Savings rate       90     30%  56% of income saved
      Emergency fund     80     20%  5.80 months of spending covered, against a target of 6
      "
    `);
  });

  it('shows no score or grade until two months of data are behind it', async () => {
    mock.on('GET', '/v1/fi/score', () => ({ status: 200, body: { ...FI_SCORE, status: 'not_enough_data', months_observed: 1 } }));
    const shown = (await run(['fi', 'score'])).stdout;
    expect(shown.split('\n')[0]).toBe('FI score Needs two months of data');
    expect(shown).not.toContain('grade');
  });

  it('lists goals with their funding', async () => {
    expect((await run(['goals', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        NAME                   TARGET    FUNDED  PROGRESS  BY
      000001c3  Emergency fund  USD 15,000.00  9,000.00       60%  Jun 30, 2027
      "
    `);
  });

  it('says when there is no advisor report yet (exit 4)', async () => {
    const result = await run(['advisor', 'latest']);
    expect(result.code).toBe(4);
    expect(result.stderr).toContain('salli advisor run');
  });
});

describe('reminders, reports and tax', () => {
  it('lists reminders soonest first, overdue ones flagged', async () => {
    expect((await run(['reminders', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        DUE           WHAT                   STATUS   ALERT
      0000012f  Aug 15, 2026  Quarterly installment  done
      0000012d  Oct 9, 2026   Budget overspend       pending  warning
      0000012e  Nov 30, 2026  Return due (XA 2026)   pending
      "
    `);
  });

  it('prints the balance sheet', async () => {
    expect((await run(['reports', 'balance-sheet'])).stdout).toMatchInlineSnapshot(`
      "In USD
      Assets
        1000 Cash             250.00
        1100 Checking      12,784.50
        1200 Euro Savings   2,200.00
      Total assets         15,234.50

      Liabilities
        2000 Credit Card    1,200.00
      Total liabilities     1,200.00

      Net worth            14,034.50
      "
    `);
  });

  it('exports a report as CSV to stdout or a file', async () => {
    expect((await run(['reports', 'export', 'balance-sheet'])).stdout).toBe('Type,Code,Account,Balance\r\nasset,1000,Cash,250.00\r\n');
    const file = join(dir, 'bs.csv');
    const saved = await run(['reports', 'export', 'balance-sheet', '-o', file, '--json']);
    expect(JSON.parse(saved.stdout)).toEqual({ report: 'balance-sheet', path: file, bytes: 51 });
    expect(await readFile(file, 'utf8')).toBe('Type,Code,Account,Balance\r\nasset,1000,Cash,250.00\r\n');
    expect((await run(['reports', 'export', 'cash-flow'])).code).toBe(2);
  });

  it('computes tax from your rules, line by line', async () => {
    expect((await run(['tax', 'compute'])).stdout).toMatchInlineSnapshot(`
      "Tax XA 2031 Jan 1 – Dec 31, 2031 · USD · computed Jun 1, 2031 · not tax advice
      Computed from your rules, version 1 (a1a1a1a1a1a1).

      FROM YOUR LEDGER  ROLE          TOTAL (USD)  POSTINGS
      Salary            salary          60,000.00        12
      Tax withheld      tax_withheld    12,000.00        12

      LINE                       KEY          AMOUNT (USD)  FROM
      Allowance                  allowance       12,000.00  min(12000, max(0, role.salary))
      Income tax                 income_tax      11,200.00  line.income_tax.band_1.tax + line.income_tax.band_2.tax
      Tax withheld (refundable)  withholding     12,000.00  role.tax_withheld
      Tax less withholding       balance           -800.00  line.income_tax - line.withholding

      Net      -USD 800.00
      Payable  USD 0.00
      Refund   USD 800.00
      "
    `);
  });
});

describe('your data and settings', () => {
  it('shows and changes the profile; a locked base currency is a refusal (exit 5)', async () => {
    expect((await run(['profile', 'get'])).stdout).toMatchInlineSnapshot(`
      "ID                      user-123
      Display name            Ada
      Base currency           USD
      Date of birth           1990-04-01
      Dependents count        0
      Residency status        resident
      MCP enabled             yes
      Daily briefing enabled  no
      Tax residency           KE
      Tax ids                 KE-PIN A001234567Z
      "
    `);
    expect((await run(['profile', 'set', '--name', 'Ada L', '--dependents', '2'])).code).toBe(0);
    expect(lastBody('/v1/onboarding/profile')).toEqual({ display_name: 'Ada L', dependents_count: 2 });
    const locked = await run(['profile', 'set', '--base-currency', 'eur']);
    expect(locked.code).toBe(5);
    expect(locked.stderr).toContain('Base currency is fixed: Your ledger already has amounts in USD.');
  });

  it('exports your data exactly as sent, readable only by you', async () => {
    const file = join(dir, 'me.json');
    const result = await run(['profile', 'export', '-o', file]);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('readable only by you');
    expect(await readFile(file, 'utf8')).toBe('{\n  "profile": {\n    "display_name": "Ada"\n  },\n  "progress": 0.0\n}\n');
    expect((await stat(file)).mode & 0o777).toBe(0o600);
  });

  it('reads an LLM key from stdin and never prints it', async () => {
    const result = await run(['llm-keys', 'set'], { stdin: 'example-key-value\n' });
    expect(result.code).toBe(0);
    expect(lastBody('/v1/llm-keys/anthropic')).toEqual({ key: 'example-key-value' });
    expect(result.stdout + result.stderr).not.toContain('example-key-value');
    expect((await run(['llm-keys', 'list'])).stdout).toContain('…Ab12');
  });

  it('switches MCP off and lists connections', async () => {
    const off = await run(['mcp', 'disable', '--json']);
    expect(JSON.parse(off.stdout)).toEqual({ enabled: false });
    expect(lastBody('/v1/mcp/connections/enabled')).toEqual({ enabled: false });
    expect((await run(['mcp', 'connections'])).stdout).toContain('Claude');
  });

  it('lists and shows documents', async () => {
    expect((await run(['documents', 'list'])).stdout).toContain('Receipt.pdf');
    const shown = await run(['documents', 'show', uid(461).slice(0, 8)]);
    expect(shown.stdout).toContain('Thank you for shopping');
  });
});
