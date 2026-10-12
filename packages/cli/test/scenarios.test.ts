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

describe('salli whatif on your holdings', () => {
  it('sells units of a holding, and invests into one, by symbol', async () => {
    const result = await run([
      'whatif',
      '--sell',
      'VTI:4@2026-11-02',
      '--sell-value',
      'vti:2500',
      '--invest',
      '1000',
      '--holding',
      'VTI',
      '--fees',
      '2.00',
      '--gain-tax-role',
      'gains',
      '--account',
      'checking',
      '--as-of',
      '2026-10-11',
    ]);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/scenarios/run')).toEqual({
      schema: 'salli.scenario/1',
      as_of: '2026-10-11',
      changes: [
        { type: 'invest', amount: '1000', date: '2026-10-11', from: uid(2), holding: uid(421), fees: '2.00', label: 'Invest 1000 in Total Stock Market' },
        { type: 'sell', holding: uid(421), quantity: '4', date: '2026-11-02', fees: '2.00', into: uid(2), tax_role: 'gains', label: 'Sell Total Stock Market' },
        { type: 'sell', holding: uid(421), amount: '2500', date: '2026-10-11', fees: '2.00', into: uid(2), tax_role: 'gains', label: 'Sell Total Stock Market' },
      ],
    });
    // The server's answer: the 3b household's sale and invest.
    expect(result.stdout).toContain('4 units of My index fund at NZD 150 on Jun 30, 2031: NZD 600.00, fees NZD 2.00, a gain of NZD 196.00, taxed (gains)');
    expect(result.stdout).toContain('NZD 1,000.00 on Jun 30, 2031: 6.666666666666666666 units of My index fund at NZD 150');
    expect(result.stderr).toContain('no fees given, so none are counted');
  });

  it('refuses holding flags that have nothing to apply to', async () => {
    expect((await run(['whatif', '--buy', '100', '--holding', 'VTI'])).stderr).toContain('--holding is the holding --invest goes into');
    expect((await run(['whatif', '--buy', '100', '--fees', '2'])).stderr).toContain('--fees are on a --sell');
    expect((await run(['whatif', '--invest', '100', '--gain-tax-role', 'gains'])).stderr).toContain('--gain-tax-role tags a --sell');
    expect((await run(['whatif', '--sell', 'VTI'])).stderr).toContain('--sell takes HOLDING:UNITS, like FUND:4');
    expect((await run(['whatif', '--sell', 'NOPE:1'])).code).toBe(4);
  });
});

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

                                                                    BASELINE      SCENARIO          CHANGE
      Lowest cash                                                  13,998.91     11,626.24       -2,372.67
      Lowest on                                                 Feb 24, 2027  Nov 24, 2026  92 days sooner
      Cash by Oct 31, 2027                                         15,801.47     31,401.47      +15,600.00
      Safe to spend until Oct 25, 2026                             15,727.02     15,727.02            0.00
      Checking at its lowest                                        6,063.46      4,883.77       -1,179.69
      Savings at its lowest                                         7,800.00      7,800.00            0.00
      Dollar account at its lowest                                  2,500.00      2,500.00            0.00
      Emergency fund at the low (months of essential spending)          7.37          6.12           -1.25

      IN        MONTH     NET WORTH (EUR)      CHANGE        CASH  INVESTMENTS       DEBTS
      1 year    Oct 2027       363,010.64   -3,255.50  +15,600.00    -4,208.34  +14,647.16
      5 years   Oct 2031       478,903.79   -6,648.03  +15,600.00   -22,248.03        0.00
      10 years  Oct 2036       653,675.96  -10,703.54  +15,600.00   -26,303.54        0.00
      20 years  Oct 2046     1,127,647.79  -21,701.41  +15,600.00   -37,301.41        0.00

                                 BASELINE    SCENARIO          CHANGE
      Car loan paid off          May 2029    May 2029      same month
      Student loan paid off      Mar 2033    Mar 2033      same month
      Car loan (new) paid off           —    Dec 2030               —
      Interest on debts          2,009.25    4,658.71       +2,649.46
      Debt-free                  Mar 2033    Mar 2033      same month
      FI number                611,127.00  607,230.00       -3,897.00
      Financially independent    May 2042    Sep 2042  4 months later
      "
    `);
    expect(result.stderr).toContain('In today’s money.');
    expect(result.stderr).toContain(
      'Placeholders: the real return; the safe withdrawal rate; the share of your monthly surplus invested (all of it); inflation',
    );
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
        { type: 'income_change', monthly: '600', from: '2026-10-09', label: 'Income +600 a month' },
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
    expect(body.cash.lowest.scenario).toBe('11626.24');
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
    [['--invest', '10', '--tax-role', 'salary'], '--tax-role tags --income, --recurring and --buy changes'],
    [['--income', '+600/month', '--tax-role', 'Salary!'], "--tax-role takes a role's key"],
    [['--income', '+600/month', '--tax-answer', 'single'], '--tax-answer takes KEY=VALUE'],
  ])('refuses %j before asking the server (exit 2)', async (args, said) => {
    const result = await run(['whatif', ...args]);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain(said);
    expect(lastBody('/v1/scenarios/run')).toBeUndefined();
  });

  it('tags changes with a tax role, and shows the tax each year', async () => {
    const result = await run([
      'whatif',
      '--income',
      '+1000/month@2031-07-01',
      '--tax-role',
      'salary',
      '--tax-answer',
      'filing_status=single',
      '--tax-answer',
      'blind=false',
      '--as-of',
      '2031-06-30',
      '--label',
      'Raise',
    ]);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/scenarios/run')).toEqual({
      schema: 'salli.scenario/1',
      label: 'Raise',
      as_of: '2031-06-30',
      changes: [{ type: 'income_change', monthly: '1000', from: '2031-07-01', tax_role: 'salary', label: 'Income +1000 a month' }],
      tax: { answers: { filing_status: 'single', blind: false } },
    });
    expect(result.stdout).toContain('NZD 1,000.00 a month from Jul 1, 2031, before tax (salary)');
    const tax = result.stdout.slice(result.stdout.indexOf('Tax\n'));
    expect(tax).toMatchInlineSnapshot(`
      "Tax
      TAX YEAR  RULES                   BASELINE   SCENARIO     CHANGE
      2031      2031                    7,200.00   8,800.00  +1,600.00
      2032      2031 (carried forward)  7,200.00  11,200.00  +4,000.00
      2036      2031 (carried forward)  7,200.00  11,200.00  +4,000.00
      2041      2031 (carried forward)  7,200.00  11,200.00  +4,000.00
      2051      2031 (carried forward)  7,200.00  11,200.00  +4,000.00
      "
    `);
    expect(result.stderr).toContain('your latest tax rules, carried forward to years with none of their own');
    expect(result.stderr).toContain('This tax year’s change comes out of cash from Jul 2031 to Dec 2031');
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
      Lowest cash                     13,998.91     11,598.91     13,821.01
      Lowest on                    Feb 24, 2027  Feb 24, 2027  Feb 24, 2027
      Cash by Oct 31, 2027            15,801.47     13,401.47     15,801.47
      Safe to spend                   15,727.02     15,727.02     15,727.02
      Emergency months at the low          7.37          6.11          7.28
      Net worth in 1 year            366,266.13    363,866.13    363,738.21
      Net worth in 5 years           485,551.81    483,151.81    482,585.47
      Net worth in 10 years          664,379.50    661,979.50    660,757.60
      Net worth in 20 years        1,149,349.20  1,146,949.20  1,143,949.56
      Interest on debts                2,009.25      2,009.25      2,099.93
      Debt-free                        Mar 2033      Mar 2033      Mar 2033
      FI number                      611,127.00    611,127.00    611,127.00
      Financially independent          May 2042      Jun 2042      Jul 2042

      The trade
        Pay cash against Instalments
          ahead on:  net worth in 1 year +127.92; investments in 1 year +2,321.48; debts in 1 year -206.44; net worth in 5 years +566.34; investments in 5 years +2,966.34; net worth in 10 years +1,221.90; investments in 10 years +3,621.90; net worth in 20 years +2,999.64; investments in 20 years +5,399.64; interest -90.68; FI 1 month sooner
          behind on: lowest cash -2,222.10; emergency months at the low -1.17; cash in 1 year -2,400.00; cash in 5 years -2,400.00; cash in 10 years -2,400.00; cash in 20 years -2,400.00

      AT 20 YEARS     CONSERVATIVE (2%)               BASE (4%)             GROWTH (6%)
      Pay cash     975,256.19  Feb 2045  1,146,949.20  Jun 2042  1,377,923.33  Jul 2040
      Instalments  973,987.81  Mar 2045  1,143,949.56  Jul 2042  1,372,380.21  Aug 2040

      Break-evens
        Pay cash ends the horizon with more net worth than Instalments at every loan rate from 0% to 100%.
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
    expect(body.break_evens[0]).toMatchObject({ kind: 'loan_rate', status: 'none_in_range', value: null, ahead: 'Pay cash' });
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
