import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
let files: string;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  files = await mkdtemp(join(tmpdir(), 'salli-scenarios-'));
});
afterEach(async () => {
  await mock.close();
  await cleanup();
  await rm(files, { recursive: true, force: true });
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const lastBody = (path: string) => mock.data.bodies.filter((b) => b.path === path).at(-1)?.body;

describe('salli whatif', () => {
  it('builds the scenario from flags, and shows every figure against the baseline', async () => {
    const result = await run(['whatif', '--buy', '2400@2026-11-02', '--label', 'Laptop']);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/scenarios/run')).toEqual({
      schema: 'salli.scenario/1',
      label: 'Laptop',
      changes: [{ type: 'one_off', date: '2026-11-02', amount: '-2400', label: 'Buy 2400' }],
    });
    expect(result.stdout).toMatchInlineSnapshot(`
      "What if: Laptop as of Oct 11, 2026, in EUR

      #  CHANGE           WHAT
      1  New laptop       -EUR 2,400.00 on Nov 2, 2026
      2  Car loan         EUR 18,000.00 at 6.9% over 48 months: EUR 430.20 a month from Jan 2027
      3  Stop Streamflix  from Nov 1, 2026: Streamflix (-EUR 12.99 monthly)

                                                                    BASELINE      SCENARIO         CHANGE
      Lowest cash                                                  15,740.01     15,085.90        -654.11
      Lowest on                                                 Oct 18, 2026  Nov 24, 2026  37 days later
      Cash by Oct 31, 2027                                         39,200.21     50,654.09     +11,453.88
      Safe to spend until Oct 25, 2026                             15,727.02     15,727.02           0.00
      Checking at its lowest                                        6,063.46      4,883.77      -1,179.69
      Savings at its lowest                                         7,800.00      7,800.00           0.00
      Dollar account at its lowest                                  2,500.00      2,500.00           0.00
      Emergency fund at the low (months of essential spending)          8.29          7.95          -0.34

      IN        MONTH     NET WORTH (EUR)     CHANGE        CASH  INVESTMENTS       DEBTS
      1 year    Oct 2027       362,562.26  -3,193.28  +11,453.88         0.00  +14,647.16
      5 years   Oct 2031       469,546.07  -4,270.06   -4,270.06         0.00        0.00
      10 years  Oct 2036       608,431.58  -3,490.66   -3,490.66         0.00        0.00
      20 years  Oct 2046       893,650.45  -1,931.86   -1,931.86         0.00        0.00

                                 BASELINE    SCENARIO          CHANGE
      Car loan paid off          May 2029    May 2029      same month
      Student loan paid off      Mar 2033    Mar 2033      same month
      Car loan (new) paid off           —    Dec 2030               —
      Interest on debts          2,009.25    4,658.71       +2,649.46
      Debt-free                  Mar 2033    Mar 2033      same month
      FI number                611,127.00  607,230.00       -3,897.00
      Financially independent    May 2047    Apr 2047  1 month sooner
      "
    `);
    expect(result.stderr).toContain('In today’s money.');
    expect(result.stderr).toContain('Placeholders: the real return; the safe withdrawal rate; inflation');
  });

  it('turns every kind of flag into its change', async () => {
    const result = await run([
      'whatif',
      '--loan',
      '18000@6.9%x48@2026-12-01',
      '--recurring',
      '-450/month@2027-01-01',
      '--income',
      '+600/month',
      '--extra-payment',
      'car loan:200/month@2026-11-01',
      '--invest',
      '5000',
      '--cancel',
      'Streaming@2026-11-01',
      '--account',
      'checking',
      '--years',
      '10',
      '--as-of',
      '2026-10-09',
    ]);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/scenarios/run')).toEqual({
      schema: 'salli.scenario/1',
      as_of: '2026-10-09',
      horizon_years: 10,
      changes: [
        { type: 'loan', principal: '18000', annual_rate: '0.069', term_months: 48, start: '2026-12-01', into: uid(2), label: 'Loan of 18000' },
        { type: 'recurring', amount: '-450', cadence: 'monthly', start: '2027-01-01', account: uid(2), label: '-450 a month' },
        { type: 'income_change', monthly_net: '600', from: '2026-10-09', label: 'Income +600 a month' },
        { type: 'invest', amount: '5000', date: '2026-10-09', from: uid(2), label: 'Invest 5000' },
        { type: 'extra_debt_payment', monthly: '200', from: '2026-11-01', debt: uid(412), label: 'Extra on Car loan' },
        { type: 'stop_recurring', key: 'streaming', from: '2026-11-01', label: 'Cancel Streaming' },
      ],
    });
  });

  it('saves the scenario the flags make, to compare later', async () => {
    const saved = join(files, 'cash.json');
    await run(['whatif', '--buy', '2400', '--save', saved]);
    expect(JSON.parse(await readFile(saved, 'utf8'))).toEqual(lastBody('/v1/scenarios/run'));
  });

  it('runs a scenario document, and prints the API’s JSON with --json', async () => {
    const path = join(files, 'laptop.json');
    const doc = { schema: 'salli.scenario/1', changes: [{ type: 'one_off', date: '2026-11-02', amount: '-2400.00', label: 'Laptop' }] };
    await writeFile(path, JSON.stringify(doc));
    const result = await run(['whatif', '--file', path, '--years', '5', '--json']);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/scenarios/run')).toEqual({ ...doc, horizon_years: 5 });
    const body = JSON.parse(result.stdout) as { cash: { lowest: { scenario: string } }; hash: string };
    expect(body.cash.lowest.scenario).toBe('15085.90');
    expect(body.hash).toMatch(/^sha256:/);
  });

  it.each([
    [[], 'Say what changes'],
    [['--buy', '-5'], '--buy takes an amount above zero'],
    [['--loan', '18000@6.9%'], '--loan takes AMOUNT@RATExMONTHS'],
    [['--recurring', '-450'], '--recurring takes AMOUNT/PERIOD'],
    [['--recurring', '-450/fortnight'], 'the period is week, month, quarter or year'],
    [['--income', '+600/week'], '--income is a change a month'],
    [['--extra-payment', '200/month'], '--extra-payment takes DEBT:AMOUNT/month'],
    [['--buy', '10', '--file', 'x.json'], 'flags or as --file, not both'],
  ])('refuses %j before asking the server (exit 2)', async (args, said) => {
    const result = await run(['whatif', ...args]);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain(said);
    expect(lastBody('/v1/scenarios/run')).toBeUndefined();
  });

  it('says what the server refused, with its path (exit 5)', async () => {
    const result = await run(['whatif', '--buy', '10', '--label', 'refuse']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('changes[0].date: is before the as-of date');
  });

  it('finds nothing to cancel by a name no recurring payment has (exit 4)', async () => {
    const result = await run(['whatif', '--cancel', 'lottery']);
    expect(result.code).toBe(4);
    expect(result.stderr).toContain('salli insights recurring');
  });
});

describe('salli compare', () => {
  it('puts the options side by side, with the trade, sensitivity and break-evens', async () => {
    const cash = join(files, 'cash.json');
    const instalments = join(files, 'instalments.json');
    await writeFile(cash, JSON.stringify({ schema: 'salli.scenario/1', changes: [] }));
    await writeFile(instalments, JSON.stringify({ schema: 'salli.scenario/1', label: 'Instalments', changes: [] }));
    const result = await run(['compare', cash, instalments]);
    expect(result.code).toBe(0);
    // An option without a label is named after its file.
    expect(lastBody('/v1/scenarios/compare')).toEqual({
      options: [
        { schema: 'salli.scenario/1', changes: [], label: 'cash' },
        { schema: 'salli.scenario/1', label: 'Instalments', changes: [] },
      ],
    });
    expect(result.stdout).toMatchInlineSnapshot(`
      "Comparing 2 options as of Oct 11, 2026, in EUR, over 20 years

                                       BASELINE      PAY CASH   INSTALMENTS
      Lowest cash                     15,740.01     15,072.91     15,740.01
      Lowest on                    Oct 18, 2026  Nov 24, 2026  Oct 18, 2026
      Cash by Oct 31, 2027            39,200.21     36,800.21     36,917.16
      Safe to spend                   15,727.02     15,727.02     15,727.02
      Emergency months at the low          8.29          7.94          8.29
      Net worth in 1 year            365,755.54    363,355.54    363,266.05
      Net worth in 5 years           473,816.13    471,416.13    471,325.45
      Net worth in 10 years          611,922.24    609,522.24    609,431.56
      Net worth in 20 years          895,582.31    893,182.31    893,091.63
      Interest on debts                2,009.25      2,009.25      2,099.93
      Debt-free                        Mar 2033      Mar 2033      Mar 2033
      FI number                      611,127.00    611,127.00    611,127.00
      Financially independent          May 2047      Jun 2047      Jun 2047

      The trade
        Pay cash against Instalments
          ahead on:  net worth in 1 year +89.49; debts in 1 year -206.44; net worth in 5 years +90.68; cash in 5 years +90.68; net worth in 10 years +90.68; cash in 10 years +90.68; net worth in 20 years +90.68; cash in 20 years +90.68; interest -90.68
          behind on: lowest cash -667.10; emergency months at the low -0.35; cash in 1 year -116.95

      AT 20 YEARS     CONSERVATIVE (2%)             BASE (4%)           GROWTH (6%)
      Pay cash     865,267.93  Jul 2048  893,182.31  Jun 2047  934,747.31  Feb 2046
      Instalments  865,177.25  Jul 2048  893,091.63  Jun 2047  934,656.63  Feb 2046

      Break-evens
        Only at a loan rate of 0% does Instalments end the horizon with at least Pay cash's net worth; at any higher rate, Pay cash costs less.
      "
    `);
    expect(result.stdout).not.toMatch(/best|cheapest|recommend/i);
    expect(result.stderr).toContain('Salli doesn’t rank options');
  });

  it('prints the API’s JSON with --json', async () => {
    const a = join(files, 'a.json');
    const b = join(files, 'b.json');
    await writeFile(a, '{"schema": "salli.scenario/1"}');
    await writeFile(b, '{"schema": "salli.scenario/1"}');
    const body = JSON.parse((await run(['compare', a, b, '--json'])).stdout) as { break_evens: Array<{ kind: string; value: string }> };
    expect(body.break_evens[0]).toMatchObject({ kind: 'loan_rate', value: '0' });
  });

  it('needs two to five readable scenarios (exit 2)', async () => {
    const a = join(files, 'a.json');
    await writeFile(a, '[1, 2]');
    expect((await run(['compare', a])).code).toBe(2);
    const notObject = await run(['compare', a, a]);
    expect(notObject.code).toBe(2);
    expect(notObject.stderr).toContain('is not a scenario');
    const b = join(files, 'b.json');
    await writeFile(b, '{"schema": "salli.scenario/1"}');
    expect((await run(['compare', b, join(files, 'missing.json')])).stderr).toContain('No such file');
  });
});
