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
const lastBody = (path: string) => mock.data.bodies.filter((b) => b.path === path).at(-1)?.body;

describe('tax residency, tax years and FI assumptions', () => {
  it('shows the tax year, or says where you are taxed is unknown', async () => {
    expect((await run(['tax', 'year'])).stdout).toMatchInlineSnapshot(`
      "Country      LK (from your tax residency)
      Tax year     2026/27 (Apr 1, 2026 – Mar 31, 2027)
      Can compute  2025/26 (no pack for the current year yet)
      "
    `);
    mock.data.taxYear = { country: null, country_source: null, year: null, start: null, end: null, has_pack: false, latest_year: null };
    expect((await run(['tax', 'year'])).stderr).toContain('salli profile set --tax-residency');
  });

  it('sets tax residency, tax ids (merged with the stored ones) and FI assumptions', async () => {
    const result = await run([
      'profile', 'set', '--tax-residency', 'gb', '--tax-id', 'GB-UTR=1234567890', '--tax-id', 'lk-tin=', '--nic', '199012345678',
      '--fi-swr', '3.5%', '--fi-inflation', 'none',
    ]);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/onboarding/profile')).toEqual({
      tax_residency: 'GB',
      nic: '199012345678',
      fi_assumptions: { inflation: null, safe_withdrawal_rate: '0.035' },
      tax_ids: [{ scheme: 'GB-UTR', value: '1234567890' }],
    });
    expect((await run(['profile', 'set', '--tax-residency', 'Britain'])).code).toBe(2);
    expect((await run(['profile', 'set', '--tax-id', '123'])).code).toBe(2);
  });

  it('shows the profile with its tax ids and own assumptions', async () => {
    const out = (await run(['profile', 'get'])).stdout;
    expect(out).toContain('Tax residency');
    expect(out).toContain('LK-TIN 123456789');
    expect(out).toContain('safe withdrawal rate 4%');
  });

  it('shows the FI assumptions and where each came from', async () => {
    expect((await run(['fi', 'assumptions'])).stdout).toMatchInlineSnapshot(`
      "FI assumptions defaults for US
      ASSUMPTION            APPLIED  FROM     DEFAULT  SOURCE
      Inflation                  3%  default       3%  US CPI, 10-year average
      Real return                5%  default       5%  A balanced portfolio, after inflation
      Safe withdrawal rate       4%  you         3.5%  Your choice
      "
    `);
  });
});
