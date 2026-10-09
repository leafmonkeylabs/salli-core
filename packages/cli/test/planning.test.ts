import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { uid } from './helpers/fixtures';
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

    await run(['fi', 'afford', '2400', '--months', '12', '--rate', '18%']);
    expect(lastBody('/v1/fi/simulate-purchase')).toEqual({ amount: '2400', term_months: 12, annual_interest_rate: '0.18' });
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
      "
    `);
    const plan = await run(['debts', 'payoff-plan', '--strategy', 'snowball', '--extra', '100']);
    expect(plan.stdout).toMatchInlineSnapshot(`
      "Strategy       snowball
      Debt-free in   26 months
      Interest paid  USD 845.12

      MONTH  DEBT         PAYMENT  PRINCIPAL  INTEREST      LEFT
          1  Credit card   135.00     111.01     23.99  1,088.99
          1  Car loan      310.00     261.70     48.30  8,138.30
      "
    `);
    expect(mock.requestsTo('GET', '/v1/debt/payoff-plan')[0]?.query.toString()).toBe('strategy=snowball&extra_monthly_payment=100');
  });

  it('marks a debt paid off, and refuses an update with nothing to change', async () => {
    expect((await run(['debts', 'update', uid(411).slice(0, 8), '--paid-off'])).code).toBe(0);
    expect(lastBody(`/v1/debt/${uid(411)}`)).toEqual({ is_active: false });
    expect((await run(['debts', 'update', uid(411).slice(0, 8)])).code).toBe(2);
  });
});

describe('investments, subscriptions and insurance', () => {
  it('summarises the portfolio with rebalancing against a target', async () => {
    const result = await run(['portfolio', '--target', 'equity:0.6', '--target', 'bond:0.4']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "Value     USD 14,140.50
      Invested  USD 12,000.00
      Gain      USD 2,140.50 (17.84%)

      ASSET CLASS  VALUE (USD)  SHARE
      equity         11,250.40  79.6%
      bond            2,890.10  20.4%

      Rebalancing
      ASSET CLASS    NOW  TARGET  DRIFT
      equity       79.6%     60%  19.6%
      "
    `);
    expect(mock.requestsTo('GET', '/v1/portfolio/summary')[0]?.query.getAll('target')).toEqual(['equity:0.6', 'bond:0.4']);
  });

  it('lists holdings, subscriptions and policies', async () => {
    expect((await run(['holdings', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        SYMBOL  NAME                CLASS       INVESTED          VALUE
      000001a5  VTI     Total Stock Market  equity  USD 9,000.00  USD 11,250.40
      000001a6  BND     Total Bond Market   bond    USD 3,000.00   USD 2,890.10
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
      FI by             Oct 9, 2040

      PART            SCORE  WEIGHT  WHY
      Savings rate       90     30%  56% of income saved
      Emergency fund     80     20%  5.8 months covered
      "
    `);
  });

  it('costs a purchase in months of freedom', async () => {
    expect((await run(['fi', 'simulate-purchase', '2400', '--months', '12'])).stdout).toMatchInlineSnapshot(`
      "Buying something for USD 2,400.00
      HOW                     COSTS  INTEREST  A MONTH  DELAYS FI BY
      Pay cash (cheapest)  2,400.00      0.00                1 month
      Pay over 12 months   2,616.00    216.00   218.00      2 months
      "
    `);
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
      0000012e  Nov 30, 2026  Return due 2025/26     pending
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
    const saved = await run(['reports', 'export', 'balance-sheet', '--file', file, '--json']);
    expect(JSON.parse(saved.stdout)).toEqual({ report: 'balance-sheet', path: file, bytes: 51 });
    expect(await readFile(file, 'utf8')).toBe('Type,Code,Account,Balance\r\nasset,1000,Cash,250.00\r\n');
    expect((await run(['reports', 'export', 'cash-flow'])).code).toBe(2);
  });

  it('computes income tax with its bands', async () => {
    expect((await run(['tax', 'compute'])).stdout).toMatchInlineSnapshot(`
      "Income tax 2025/26 LK pack v1 · not tax advice
      BAND                           RATE  TAXABLE (LKR)  TAX (LKR)
      LKR 0 – LKR 1,000,000            6%   1,000,000.00  60,000.00
      LKR 1,000,000 – LKR 1,500,000   18%     500,000.00  90,000.00

      Gross income              LKR 6,000,000.00
      Personal relief           LKR 1,800,000.00
      Taxable income            LKR 4,200,000.00
      Tax before credits        LKR 540,000.00
      Credits (APIT, AIT, FTC)  LKR 400,000.00
      Tax payable               LKR 140,000.00
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
    const result = await run(['export', '--file', file]);
    expect(result.code).toBe(0);
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
