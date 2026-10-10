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
  it('shows the tax year your active rules cover, or says where you are taxed is unknown', async () => {
    expect((await run(['tax', 'year', '--country', 'XA'])).stdout).toMatchInlineSnapshot(`
      "Country   XA (as given)
      Tax year  2031 (Jan 1 – Dec 31, 2031), your rules v1
      Computes  2031 when no year is named
      "
    `);
    expect(mock.requestsTo('GET', '/v1/tax/current-year')[0]?.query.get('country')).toBe('XA');
    mock.data.taxYear = {
      country: 'GB', country_source: 'tax_residency', year: null, region: null, start: null, end: null,
      rule_set_id: null, rule_set_version_id: null, version: null, latest_year: null, latest_rule_set_version_id: null,
    };
    const none = await run(['tax', 'year']);
    expect(none.stdout).toContain('none: no active rules of yours cover today');
    expect(none.stderr).toContain('salli tax rules create <file>');
    mock.data.taxYear = { ...mock.data.taxYear, country: null, country_source: null };
    expect((await run(['tax', 'year'])).stderr).toContain('salli profile set --tax-residency');
  });

  it('sets tax residency, tax ids (merged with the stored ones) and FI assumptions', async () => {
    const result = await run([
      'profile', 'set', '--tax-residency', 'gb', '--tax-id', 'GB-UTR=1234567890', '--tax-id', 'ke-pin=',
      '--fi-swr', '3.5%', '--fi-inflation', 'none',
    ]);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/onboarding/profile')).toEqual({
      tax_residency: 'GB',
      fi_assumptions: { inflation: null, safe_withdrawal_rate: '0.035' },
      tax_ids: [{ scheme: 'GB-UTR', value: '1234567890' }],
    });
    expect((await run(['profile', 'set', '--tax-residency', 'Britain'])).code).toBe(2);
    expect((await run(['profile', 'set', '--tax-id', '123'])).code).toBe(2);
    expect((await run(['profile', 'set', '--tax-id', 'TIN=123'])).code).toBe(2);
    // One country's numbers are not options of their own.
    expect((await run(['profile', 'set', '--ird-number', '123'])).code).toBe(2);
    expect((await run(['profile', 'set', '--nic', '123'])).code).toBe(2);
  });

  it('shows the profile with its tax ids and own assumptions', async () => {
    const out = (await run(['profile', 'get'])).stdout;
    expect(out).toContain('Tax residency');
    expect(out).toContain('KE-PIN A001234567Z');
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
