import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { parseCondition, splitWords } from '../src/commands/rules';
import { UsageError } from '../src/errors';
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

const lastBody = (path: string) => mock.data.bodies.filter((b) => b.path === path).at(-1)?.body;

describe('conditions', () => {
  it('split like a shell: quotes group words; a backslash before anything else stays', () => {
    expect(splitWords(`description contains "uber eats"`)).toEqual(['description', 'contains', 'uber eats']);
    expect(splitWords(`description matches '^AMZN\\s'`)).toEqual(['description', 'matches', '^AMZN\\s']);
    expect(splitWords('description matches \\d+')).toEqual(['description', 'matches', '\\d+']);
    expect(splitWords(`description contains Joe\\'s`)).toEqual(['description', 'contains', "Joe's"]);
    expect(() => splitWords('description contains "open')).toThrow(UsageError);
  });

  it('read as the API takes them', () => {
    expect(parseCondition('description contains uber eats')).toEqual({ field: 'description', operator: 'contains', value: 'uber eats' });
    expect(parseCondition('Amount BETWEEN 1,000 2500.50')).toEqual({ field: 'amount', operator: 'between', value: '1000', value2: '2500.50' });
    expect(parseCondition('amount gt 10')).toEqual({ field: 'amount', operator: 'gt', value: '10' });
    expect(parseCondition('currency equals usd')).toEqual({ field: 'currency', operator: 'equals', value: 'USD' });
    expect(parseCondition('direction equals OUT')).toEqual({ field: 'direction', operator: 'equals', value: 'out' });
  });

  it('refuse what cannot be a condition, with what would be', () => {
    expect(() => parseCondition('payee contains uber')).toThrow(/Unknown field "payee"/);
    expect(() => parseCondition('description has uber')).toThrow(/Unknown operator "has"/);
    expect(() => parseCondition('amount gt ten')).toThrow(/must be a number/);
    expect(() => parseCondition('amount between 10')).toThrow(/takes two amounts/);
    expect(() => parseCondition('description contains')).toThrow(/Not a condition/);
  });
});

describe('salli rules', () => {
  it('lists the rules, with what each one does', async () => {
    const result = await run(['rules', 'list']);
    expect(result.code).toBe(0);
    expect(result.stdout).toMatchInlineSnapshot(`
      "ID        PRIORITY  NAME       RULE                                                                                ON   HITS
      00000259       100  Groceries  when description contains “groceries” → book to 5000 Groceries, category groceries  yes     3
      "
    `);
    const json = await run(['rules', 'list', '--json']);
    expect(JSON.parse(json.stdout)).toHaveLength(1);
  });

  it('adds a rule from conditions and actions', async () => {
    const result = await run([
      'rules', 'add', 'Uber rides',
      '--if', 'description contains uber',
      '--if', 'amount lt 50',
      '--account', 'rent',
      '--need', 'discretionary',
      '--priority', '10',
      '--any',
    ]);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Added the rule “Uber rides”');
    expect(lastBody('/v1/rules')).toEqual({
      name: 'Uber rides',
      conditions: [
        { field: 'description', operator: 'contains', value: 'uber' },
        { field: 'amount', operator: 'lt', value: '50' },
      ],
      actions: { account_id: uid(7), need: 'discretionary' },
      match_all: false,
      priority: 10,
    });
  });

  it('needs something for a rule to do, and a condition it understands (exit 2)', async () => {
    const nothing = await run(['rules', 'add', 'Idle', '--if', 'description contains x']);
    expect(nothing.code).toBe(2);
    expect(nothing.stderr).toContain('A rule needs something to do.');
    const bad = await run(['rules', 'add', 'Bad', '--if', 'colour equals red', '--category', 'x']);
    expect(bad.code).toBe(2);
    expect(bad.stderr).toContain('Unknown field "colour"');
    expect(mock.requestsTo('POST', '/v1/rules')).toHaveLength(0);
  });

  it('shows one rule by the start of its id', async () => {
    const result = await run(['rules', 'show', '00000259']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('When      description contains “groceries”');
    expect(result.stdout).toContain('Then      book to 5000 Groceries, category groceries');
    expect(result.stdout).toContain('Hits      3, last on Oct 5, 2026');
    expect(mock.requestsTo('GET', `/v1/rules/${uid(601)}`)).toHaveLength(1);
  });

  it('updates a rule, keeping the actions it does not change', async () => {
    const result = await run(['rules', 'update', '00000259', '--need', 'essential', '--disabled']);
    expect(result.code).toBe(0);
    expect(lastBody(`/v1/rules/${uid(601)}`)).toEqual({
      enabled: false,
      actions: { account_id: uid(6), category: 'groceries', need: 'essential' },
    });
    expect((await run(['rules', 'update', '00000259'])).code).toBe(2);
  });

  it('deletes a rule after asking (or with --yes)', async () => {
    const refused = await run(['rules', 'delete', '00000259']);
    expect(refused.code).toBe(2);
    expect(refused.stderr).toContain('Pass --yes to confirm.');
    const result = await run(['rules', 'delete', '00000259', '--yes', '--json']);
    expect(JSON.parse(result.stdout)).toEqual({ id: uid(601), deleted: true });
    expect(mock.data.rules).toHaveLength(0);
  });

  it('tests a rule against what is booked', async () => {
    const result = await run(['rules', 'test', '--if', 'description contains rent', '--account', '5100']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Matches 1 booked transaction; 1 of them already went to 5100 Rent.');
    expect(result.stdout).toContain('Rent for October');
    expect(lastBody('/v1/rules/test')).toEqual({
      name: 'test',
      conditions: [{ field: 'description', operator: 'contains', value: 'rent' }],
      match_all: true,
      actions: { account_id: uid(7) },
    });
    const csv = await run(['rules', 'test', '--if', 'description contains rent', '--output', 'csv']);
    expect(csv.stdout.split('\r\n')[0]).toBe('entry_id,entry_date,description,amount,currency,direction,account_id');
  });

  it('suggests rules, each with the command that adds it', async () => {
    const result = await run(['rules', 'suggest']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Rent  when description contains “landlord\'s rent” → book to 5100 Rent');
    expect(result.stdout).toContain('(4 of 4 agree, e.g. “Rent for October”)');
    const command = /salli rules add .*/.exec(result.stdout)?.[0] ?? '';
    expect(command).toBe(`salli rules add Rent --if 'description contains "landlord'\\''s rent"' --account 5100`);
    // The command it prints adds exactly that rule.
    const words = ['rules', 'add', 'Rent', '--if', `description contains "landlord's rent"`, '--account', '5100'];
    expect((await run(words)).code).toBe(0);
    expect(lastBody('/v1/rules')).toMatchObject({
      conditions: [{ field: 'description', operator: 'contains', value: "landlord's rent" }],
      actions: { account_id: uid(7) },
    });
  });
});

describe('salli export', () => {
  it('prints the ledger as Beancount or hledger', async () => {
    const beancount = await run(['export', 'beancount']);
    expect(beancount.code).toBe(0);
    expect(beancount.stdout).toContain('2026-10-01 * "October salary"');
    expect((await run(['export', 'hledger'])).stdout).toContain('assets:checking');
  });

  it('writes it to a file readable only by you', async () => {
    const file = join(dir, 'ledger.beancount');
    const result = await run(['export', 'beancount', '-o', file, '--json']);
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout)).toMatchObject({ format: 'beancount', path: file });
    expect(await readFile(file, 'utf8')).toContain('open Assets:Cash USD');
    expect((await stat(file)).mode & 0o777).toBe(0o600);
  });
});

describe('salli mcp', () => {
  it('lists connections and disconnects one by the start of its token id', async () => {
    const list = await run(['mcp', 'connections']);
    expect(list.stdout).toContain('Claude');
    expect(list.stdout).toContain('Oct 1, 2026');
    const result = await run(['mcp', 'revoke', '000001d7', '--json']);
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual({ token_id: uid(471), revoked: true });
    expect(mock.data.connections).toHaveLength(0);
  });
});
