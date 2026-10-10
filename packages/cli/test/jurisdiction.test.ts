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

  it('sets tax residency and tax ids (merged with the stored ones)', async () => {
    const result = await run(['profile', 'set', '--tax-residency', 'gb', '--tax-id', 'GB-UTR=1234567890', '--tax-id', 'ke-pin=']);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/onboarding/profile')).toEqual({
      tax_residency: 'GB',
      tax_ids: [{ scheme: 'GB-UTR', value: '1234567890' }],
    });
    // FI assumptions are set with `salli fi assumptions set`, each with its source.
    expect((await run(['profile', 'set', '--fi-swr', '3.5%'])).code).toBe(2);
    expect((await run(['profile', 'set', '--tax-residency', 'Britain'])).code).toBe(2);
    expect((await run(['profile', 'set', '--tax-id', '123'])).code).toBe(2);
    expect((await run(['profile', 'set', '--tax-id', 'TIN=123'])).code).toBe(2);
    // One country's numbers are not options of their own.
    expect((await run(['profile', 'set', '--ird-number', '123'])).code).toBe(2);
    expect((await run(['profile', 'set', '--nic', '123'])).code).toBe(2);
  });

  it('shows the profile with its tax ids', async () => {
    const out = (await run(['profile', 'get'])).stdout;
    expect(out).toContain('Tax residency');
    expect(out).toContain('KE-PIN A001234567Z');
    expect(out).not.toContain('FI assumptions');
  });
});

describe('FI planning assumptions: real terms, placeholders, your own figures', () => {
  it('shows which apply, where each came from, and which are placeholders', async () => {
    const result = await run(['fi', 'assumptions']);
    expect(result.stdout).toMatchInlineSnapshot(`
      "FI assumptions real terms: after inflation, in today’s money
      ASSUMPTION            APPLIED  FROM         SOURCE
      Real return                4%  placeholder  Placeholder: a round 4% a year after inflation.
      Nominal return        not set
      Inflation             not set
      Safe withdrawal rate     3.5%  you          https://example.org/withdrawal-study
      Scenarios (real): 2% / 4% / 6% (conservative / base / growth)
      "
    `);
    expect(result.stderr).toContain('Using placeholder assumptions for the real return');
    expect(result.stderr).toContain('salli fi assumptions set <name> <rate> --source');
  });

  it('sets one figure with its source, as a rate string, and clears figures', async () => {
    const set = await run(['fi', 'assumptions', 'set', 'inflation', '3%', '--source', 'https://example.org/cpi', '--note', 'official target']);
    expect(set.code).toBe(0);
    expect(lastBody('/v1/fi/assumptions')).toEqual({
      inflation: { value: '0.03', source: 'https://example.org/cpi', note: 'official target' },
    });
    expect(set.stderr).toContain('Inflation set to 3% (source: https://example.org/cpi).');

    const unsourced = await run(['fi', 'assumptions', 'set', 'safe_withdrawal_rate', '0.035']);
    expect(lastBody('/v1/fi/assumptions')).toEqual({ safe_withdrawal_rate: { value: '0.035', source: null, note: null } });
    expect(unsourced.stderr).toContain('No source given');

    await run(['fi', 'assumptions', 'clear', 'real-return', 'swr']);
    expect(lastBody('/v1/fi/assumptions')).toEqual({ real_return: null, safe_withdrawal_rate: null });

    expect((await run(['fi', 'assumptions', 'set', 'growth', '3%'])).code).toBe(2);
    expect((await run(['fi', 'assumptions', 'set', 'inflation', 'three'])).code).toBe(2);
  });

  it('shows projections in today’s money, then future money once inflation is set', async () => {
    const real = await run(['fi', 'projections']);
    expect(real.stdout).not.toContain('THEN');
    expect(real.stderr).toContain('in today’s money. Set your inflation');
    expect(real.stderr).toContain('Using placeholder assumptions for the real return');

    await run(['fi', 'assumptions', 'set', 'inflation', '3%', '--source', 'https://example.org/cpi']);
    const both = await run(['fi', 'projections']);
    expect(both.stdout).toMatchInlineSnapshot(`
      "FI number     USD 663,705.00
      Invested now  USD 12,834.50
      FI in         19 years / 14 years / 11 years (conservative / base / growth)

      YEAR  CONSERVATIVE       BASE     GROWTH  BASE (THEN)  FI NUMBER (THEN)
         0     30,000.00  30,000.00  30,000.00    30,000.00        663,705.00
         1     48,000.00  52,000.00  57,000.00    53,560.00        683,616.15
      "
    `);
    expect(both.stderr).toContain('at your inflation of 3%');
  });

  it('says when the score and a purchase rest on placeholders', async () => {
    expect((await run(['fi', 'score'])).stderr).toContain('Using placeholder assumptions for the real return');
    expect((await run(['fi', 'afford', '2400'])).stderr).toContain('Using placeholder assumptions for the real return');
    // Machine output is the API's JSON, flag included.
    const json = JSON.parse((await run(['fi', 'score', '--json'])).stdout);
    expect(json.assumptions.status).toBe('placeholder');
  });
});
