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
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const lastBody = (path: string) => mock.data.bodies.filter((b) => b.path === path).at(-1)?.body;

describe('salli portfolio', () => {
  it('still shows the summary by default, with targets', async () => {
    const result = await run(['portfolio', '--target', 'equity:0.6']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Rebalancing');
    expect((await run(['portfolio', 'summary'])).stdout).toContain('Value');
  });

  it('records transactions by symbol, every amount a decimal string', async () => {
    const buy = await run(['portfolio', 'transactions', 'add', 'vti', 'buy', '--quantity', '10', '--price', '1,240.15', '--fees', '1', '--date', '2026-10-01']);
    expect(buy.code).toBe(0);
    expect(lastBody(`/v1/portfolio/${uid(421)}/transactions`)).toEqual({ kind: 'buy', date: '2026-10-01', quantity: '10', price: '1240.15', fees: '1' });
    await run(['portfolio', 'transactions', 'add', 'VTI', 'sell', '--quantity', '5', '--price', '260', '--lot', `${uid(1401)}:5`, '--date', '2026-10-02']);
    expect(lastBody(`/v1/portfolio/${uid(421)}/transactions`)).toMatchObject({ kind: 'sell', lots: [{ lot_id: uid(1401), quantity: '5' }] });
    expect((await run(['portfolio', 'transactions', 'add', 'VTI', 'gift'])).code).toBe(2);
  });

  it('lists, shows, updates and deletes transactions', async () => {
    expect((await run(['portfolio', 'transactions', 'list', 'VTI'])).stdout).toMatchInlineSnapshot(`
      "DATE         KIND  QUANTITY   PRICE         TOTAL  NOTE  ID
      Mar 1, 2025  buy         45  200.00  USD 9,000.00        00000579
      "
    `);
    expect((await run(['portfolio', 'transactions', 'show', 'VTI', uid(1401).slice(0, 8)])).stdout).toContain('USD 9,000.00');
    await run(['portfolio', 'transactions', 'update', 'VTI', uid(1401).slice(0, 8), '--note', 'first buy']);
    expect(lastBody(`/v1/portfolio/${uid(421)}/transactions/${uid(1401)}`)).toEqual({ note: 'first buy' });
    expect((await run(['portfolio', 'transactions', 'delete', 'VTI', uid(1401).slice(0, 8), '--yes'])).code).toBe(0);
    expect(mock.data.holdingTransactions).toHaveLength(0);
  });

  it('shows lots and sales', async () => {
    expect((await run(['portfolio', 'lots', 'VTI'])).stdout).toMatchInlineSnapshot(`
      "VTI lots 40 held, cost USD 9,000.00
      OPENED       KIND  OPENED WITH  HELD  COST (USD)  PER UNIT  LOT
      Mar 1, 2025  buy            45    40    9,000.00    225.00  00000579

      Sales
      DATE         QUANTITY  PROCEEDS (USD)    GAIN  GAIN (USD)
      May 1, 2026         5        1,245.00  120.00      120.00
      "
    `);
  });

  it('records, lists and deletes prices', async () => {
    await run(['portfolio', 'prices', 'set', 'VTI', '281.26', '--date', '2026-10-08', '--currency', 'usd']);
    expect(lastBody('/v1/portfolio/prices')).toEqual({ symbol: 'VTI', close: '281.26', date: '2026-10-08', currency: 'USD' });
    expect((await run(['portfolio', 'prices', 'list'])).stdout).toContain('USD 281.26');
    expect((await run(['portfolio', 'prices', 'delete', uid(1301).slice(0, 8)])).code).toBe(0);
    expect(mock.data.prices).toHaveLength(0);
  });

  it('shows performance for the portfolio or one holding', async () => {
    const all = await run(['portfolio', 'performance', '--from', '2026-01-01']);
    expect(lastBody('/v1/portfolio/performance')).toEqual({ from_date: '2026-01-01' });
    expect(all.stdout).toMatchInlineSnapshot(`
      "Portfolio performance Jan 1, 2026 – Oct 9, 2026 · 282 days
      Value                  USD 10,000.00 → USD 11,250.40
      Paid in / taken out    USD 0.00 / USD 0.00
      Realised gain          USD 120.00
      Unrealised gain        USD 2,250.40
      Income                 USD 153.00 (dividends USD 180.00, interest USD 0.00, tax USD 27.00)
      Total return           USD 1,523.40
      Time-weighted          15.23% (19.8% a year)
      Money-weighted (XIRR)  18.74%

      HOLDING                 VALUE (USD)  TOTAL RETURN    TWR
      VTI Total Stock Market    11,250.40      1,523.40  15.2%
      "
    `);
    expect(all.stderr).toContain('BND is declared');
    await run(['portfolio', 'performance', 'VTI', '--to', '2026-09-30']);
    expect(lastBody(`/v1/portfolio/${uid(421)}/performance`)).toEqual({ to_date: '2026-09-30' });
  });
});
