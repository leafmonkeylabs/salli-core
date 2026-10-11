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
const lastQuery = () => mock.data.bodies.filter((b) => b.path === '/v1/baseline').at(-1)?.body;

describe('salli baseline', () => {
  it('shows the money as of a day, with the definitions behind it', async () => {
    const result = await run(['baseline', '--years', '20']);
    expect(result.code).toBe(0);
    expect(lastQuery()).toEqual({ horizon_years: '20', daily: 'false' });
    expect(result.stdout).toMatchInlineSnapshot(`
      "Baseline as of Oct 9, 2026 in USD

      Averaged over  6 full months, Apr 2026 to Sep 2026
      Income         USD 5,000.00 a month
      Spending       USD 2,212.35 a month
      Left over      USD 2,787.65 a month
      Saved          55.8%
      Essential      USD 1,800.00 a month

      ACCOUNT            ROLE             BALANCE  VALUE (USD)
      1000 Cash          cash          USD 250.00       250.00
      1200 Euro Savings  cash        EUR 8,452.00     9,147.60
      2000 Credit Card   liability  -USD 8,400.00    -8,400.00

      Cash               USD 9,397.60
      Investments        USD 30,000.00
      Other assets       USD 250,000.00
      Debts              USD 8,400.00
      Other liabilities  USD 0.00
      Net worth          USD 280,997.60

      DEBT      OWES  FROM         RATE  PAID OFF
      Card  8,400.00  its account  6.9%  Jul 2029

      Cash today       USD 9,397.60
      Lowest ahead     USD 8,801.12 on Oct 24, 2026
      By Oct 31, 2027  USD 40,200.00

      IN        MONTH     NET WORTH (USD)        CASH  INVESTMENTS     DEBTS
      1 year    Oct 2027       316,300.00   40,200.00    31,200.00  5,100.00
      5 years   Oct 2031       457,500.00  171,000.00    36,500.00      0.00
      10 years  Oct 2036       640,400.00  346,000.00    44,400.00      0.00
      20 years  Oct 2046     1,011,800.00  696,000.00    65,800.00      0.00
      "
    `);
    // Where the figures come from, on stderr beside them.
    expect(result.stderr).toContain('EUR at 1.0823 USD, published by ecb for Oct 9, 2026.');
    expect(result.stderr).toContain('Placeholders: the real return; inflation (none set: nominal amounts keep their real value).');
  });

  it('asks for a past day, and prints the API’s JSON', async () => {
    const result = await run(['baseline', '--as-of', '2026-06-30', '--daily', '--json']);
    expect(lastQuery()).toEqual({ as_of: '2026-06-30', daily: 'true' });
    const body = JSON.parse(result.stdout) as { cash: { daily: unknown[] }; months_observed: string[] };
    expect(body.cash.daily).toHaveLength(1);
    expect(body.months_observed).toHaveLength(6);
  });

  it('refuses a date it cannot read before asking', async () => {
    const result = await run(['baseline', '--as-of', 'last tuesday']);
    expect(result.code).toBe(2);
    expect(lastQuery()).toBeUndefined();
  });
});
