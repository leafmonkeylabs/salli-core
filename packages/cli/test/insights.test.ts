import { afterEach, beforeEach, describe, expect, it } from 'vitest';
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
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const lastQuery = (name: string) => mock.data.bodies.filter((b) => b.path === `/v1/insights/${name}`).at(-1)?.body;

describe('salli insights', () => {
  it('shows cash flow month by month', async () => {
    const result = await run(['insights', 'cash-flow', '--months', '2']);
    expect(lastQuery('cash-flow')).toEqual({ months: '2' });
    expect(result.stdout).toMatchInlineSnapshot(`
      "MONTH     INCOME (USD)  SPENDING  LEFT OVER  SAVED
      Sep 2026      5,000.00  2,400.00   2,600.00    52%
      Oct 2026      5,000.00  2,212.35   2,787.65  55.8%
      "
    `);
  });

  it('shows spending by category, or by account', async () => {
    expect((await run(['insights', 'spending'])).stdout).toMatchInlineSnapshot(`
      "By category, Aug 2026 to Oct 2026, in USD
      CATEGORY      TOTAL  SHARE
      rent       5,400.00    70%
      groceries  2,312.35    30%
      "
    `);
    const byAccount = await run(['insights', 'spending', '--by', 'account', '-m', '6']);
    expect(lastQuery('spending')).toEqual({ by: 'account', months: '6' });
    expect(byAccount.stdout).toContain('Rent');
    expect((await run(['insights', 'spending', '--by', 'payee'])).code).toBe(2);
  });

  it('shows net worth by month and recurring payments', async () => {
    expect((await run(['insights', 'net-worth'])).stdout).toMatchInlineSnapshot(`
      "MONTH     ASSETS (USD)  LIABILITIES  NET WORTH
      Sep 2026     13,000.00     1,500.00  11,500.00
      Oct 2026     15,234.50     1,200.00  14,034.50
      "
    `);
    const recurring = await run(['insights', 'recurring']);
    expect(recurring.stdout).toMatchInlineSnapshot(`
      "PAYEE      EVERY     TYPICAL  NEXT          TRACKED
      Streaming  month   USD 15.99  Oct 20, 2026  yes
      Gym        month  ~USD 39.99  Nov 1, 2026   no
      "
    `);
    expect(recurring.stderr).toContain('1 not tracked');
  });

  it('forecasts cash, flagging the low point', async () => {
    const result = await run(['insights', 'forecast', '--days', '60', '--flows', '1']);
    expect(lastQuery('forecast')).toEqual({ days: '60' });
    expect(result.stdout).toMatchInlineSnapshot(`
      "Cash today USD 13,034.50; on Dec 8, 2026 USD 14,200.00.
      Lowest: -USD 120.00 on Nov 2, 2026

      ACCOUNT           TODAY       LOWEST  ON              AT THE END
      Checking  USD 12,784.50  -USD 370.00  Nov 2, 2026  USD 13,950.00

      Coming up
      DATE          WHAT                      AMOUNT
      Oct 20, 2026  Streaming (declared)  -USD 15.99
      "
    `);
    expect(result.stderr).toContain('Based on 6 months of history.');
  });

  it('says what is safe to spend, and what needs attention', async () => {
    expect((await run(['insights', 'safe-to-spend'])).stdout).toMatchInlineSnapshot(`
      "Safe to spend USD 1,234.56 until Nov 1, 2026, when Salary comes in
      Cash today USD 12,784.50; 1 payment expected before then.
      DATE          WHAT          AMOUNT
      Oct 20, 2026  Streaming  USD 15.99
      "
    `);
    expect((await run(['insights', 'signals'])).stdout).toMatchInlineSnapshot(`
      "! Checking runs short on Nov 2
        It is forecast to reach USD -370.00 before payday.
      • 2 transactions to review
        From the statement imported on Oct 2.
      "
    `);
    const json = JSON.parse((await run(['insights', 'signals', '--json'])).stdout);
    expect(json.signals[0].kind).toBe('low_balance_ahead');
    mock.data.signals = [];
    expect((await run(['insights', 'signals'])).stderr).toContain('Nothing needs your attention.');
  });
});
