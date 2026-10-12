import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';
import { AFFORD_IT_START } from './helpers/templates';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
let files: string;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  files = await mkdtemp(join(tmpdir(), 'salli-decide-'));
});
afterEach(async () => {
  await mock.close();
  await cleanup();
  await rm(files, { recursive: true, force: true });
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const bodies = (path: string) => mock.decisions.bodies.filter((b) => b.path === path).map((b) => b.body);

const SET = ['--set', 'price=2400', '--set', 'what=Laptop', '--set', 'date=2026-11-02', '--set', 'account=checking', '--set', 'instalment_months=12', '--set', 'instalment_rate=6.9%'];

describe('salli decide', () => {
  it('lists the templates', async () => {
    const result = await run(['decide', '--list']);
    expect(result.code).toBe(0);
    for (const id of ['afford-it', 'debt-or-invest', 'windfall', 'big-change', 'borrow', 'emergency-fund']) {
      expect(result.stdout).toContain(id);
    }
    expect(result.stderr).toContain('Conveniences, not advice');
  });

  it('shows a template’s questions and your defaults', async () => {
    const result = await run(['decide', 'afford-it', '--questions']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('instalment_rate');
    expect(result.stdout).toContain('2026-10-11 (the as-of date');
    const json = await run(['decide', 'afford-it', '--questions', '--json']);
    expect(JSON.parse(json.stdout).questions[0].id).toBe('price');
  });

  it('answers from flags, in the API’s formats, and records nothing', async () => {
    const result = await run(['decide', 'afford-it', ...SET]);
    expect(result.code).toBe(0);
    expect(bodies('/v1/decisions/start')).toEqual([
      {
        template: 'afford-it',
        answers: { price: '2400', what: 'Laptop', date: '2026-11-02', account: uid(2), instalment_months: 12, instalment_rate: '0.069' },
      },
    ]);
    expect(result.stdout).toContain('Can I afford Laptop (2400.00 EUR), and how would I pay for it?');
    expect(result.stdout).toContain('Comparing 2 options');
    expect(result.stdout).toContain('Six months of essentials in cash');
    expect(result.stdout).not.toMatch(/\b(best|recommend\w*|should)\b/i);
    expect(result.stderr).toContain('Nothing is recorded.');
    expect(bodies('/v1/decisions')).toEqual([]);
  });

  it('passes answers to the tax rules’ questions to every option', async () => {
    const result = await run(['decide', 'afford-it', ...SET, '--tax-answer', 'filing_status=joint', '--tax-answer', 'blind=true']);
    expect(result.code).toBe(0);
    expect(bodies('/v1/decisions/start')[0]).toMatchObject({ tax_answers: { filing_status: 'joint', blind: true } });
  });

  it('reads answers from a file and prints the server’s JSON', async () => {
    const file = join(files, 'answers.json');
    await writeFile(file, JSON.stringify({ price: '2400.00', instalment_months: 12, instalment_rate: '0.069' }));
    const result = await run(['decide', 'afford-it', '--answers', file, '--set', 'what=Laptop', '--json']);
    expect(result.code).toBe(0);
    expect(bodies('/v1/decisions/start').at(-1)).toEqual({
      template: 'afford-it',
      answers: { price: '2400.00', instalment_months: 12, instalment_rate: '0.069', what: 'Laptop' },
    });
    const data = JSON.parse(result.stdout);
    expect(data.schema).toBe('salli.decision-start/1');
    expect(data.record.labels).toEqual(['Pay cash', 'Spread over 12 months']);
  });

  it('records only when asked, and only once you confirm', async () => {
    const recordFlags = ['--record', '--chosen', 'Pay cash', '--reasons', 'I’d rather not owe anything.', '--review-on', '2027-04-11'];
    const unconfirmed = await run(['decide', 'afford-it', ...SET, ...recordFlags]);
    expect(unconfirmed.code).toBe(2);
    expect(unconfirmed.stderr).toContain('Pass --yes to confirm.');
    expect(bodies('/v1/decisions')).toEqual([]);

    const wrong = await run(['decide', 'afford-it', ...SET, '--record', '--chosen', 'Lease', '--reasons', 'x', '--review-on', '2027-04-11', '--yes']);
    expect(wrong.code).toBe(2);
    expect(wrong.stderr).toContain('--chosen is one of the options: Pay cash, Spread over 12 months');

    const recorded = await run(['decide', 'afford-it', ...SET, ...recordFlags, '--yes']);
    expect(recorded.code).toBe(0);
    expect(bodies('/v1/decisions')).toEqual([
      {
        question: AFFORD_IT_START.record.question,
        options: AFFORD_IT_START.record.options,
        chosen: 'Pay cash',
        reasons: 'I’d rather not owe anything.',
        review_on: '2027-04-11',
      },
    ]);
    expect(recorded.stderr).toContain('Recorded “Can I afford Laptop');
  });

  it('asks each question in a terminal, then offers to record', async () => {
    const prompter = new ScriptedPrompter([
      '2400', // price
      'Laptop', // what
      '', // date: the default
      'Checking', // account
      '12', // instalment_months
      '6.9%', // instalment_rate
      '', // wait_months: skipped
      '', // horizon_years: the default
      true, // record?
      'Spread over 12 months', // chosen
      'Keeps a buffer.', // reasons
      '2027-04-11', // review date
      '', // the question: the suggestion
      true, // confirm
    ]);
    const result = await run(['decide', 'afford-it'], { prompter });
    expect(result.code).toBe(0);
    expect(prompter.asked).toEqual([
      'What does it cost?',
      'What is it?',
      'When would you pay?',
      'Which cash account would it come out of?',
      'Could you spread it? Over how many months?',
      'At what yearly rate?',
      'Could you wait? For how many months?',
      'How many years ahead do you want the long-run figures to run?',
      'Record what you choose in your decision journal?',
      'Which did you choose?',
      'Why? In your own words.',
      'When do you want to look back on it?',
      'The question, in your words:',
      'Record “Can I afford Laptop (2400.00 EUR), and how would I pay for it?”, chose “Spread over 12 months”? Entries can\'t be edited or deleted afterwards',
    ]);
    expect(bodies('/v1/decisions/start')).toEqual([
      {
        template: 'afford-it',
        answers: {
          price: '2400',
          what: 'Laptop',
          date: '2026-10-11',
          account: uid(2),
          instalment_months: 12,
          instalment_rate: '0.069',
          horizon_years: 20,
        },
      },
    ]);
    expect((bodies('/v1/decisions')[0] as { chosen: string }).chosen).toBe('Spread over 12 months');
  });

  it('shows when cash covers an emergency fund’s target', async () => {
    const result = await run(['decide', 'emergency-fund', '--set', 'target_months=9', '--set', 'set_aside=200,500']);
    expect(result.code).toBe(0);
    expect(bodies('/v1/decisions/start')).toEqual([{ template: 'emergency-fund', answers: { target_months: '9', set_aside: ['200', '500'] } }]);
    expect(result.stdout).toContain('Cash covering 9 months of essential spending');
    expect(result.stdout).toMatch(/Set aside 200\.00 a month\s+May 2027\s+7/);
    expect(result.stdout).toMatch(/Baseline\s+not within 50 years/);
  });

  it('says what the server refused, with its path', async () => {
    const result = await run(['decide', 'afford-it', '--set', 'price=0', '--set', 'wait_months=3']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('must be greater than zero');
    const unknown = await run(['decide', 'rent-or-buy', '--set', 'price=1']);
    expect(unknown.code).toBe(4);
    const nameless = await run(['decide', 'afford-it', '--set', 'colour=red']);
    expect(nameless.code).toBe(2);
    expect(nameless.stderr).toContain('afford-it has no question "colour"');
  });
});
