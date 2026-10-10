import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
let statement: string;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  statement = join(dir, 'september.csv');
  await writeFile(statement, 'date,description,amount\n2026-09-02,SUPERMARKET 123,-45.20\n');
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

describe('salli import', () => {
  it('uploads the file into an account and, with --yes, posts only what is complete and not a possible duplicate', async () => {
    const result = await run(['import', statement, '--account', 'checking', '--currency', 'usd', '--bank', 'Acme', '--date-order', 'DMY', '--yes']);
    expect(result.code).toBe(0);
    const upload = mock.requestsTo('POST', '/v1/statements/upload')[0];
    expect(upload?.headers['content-type']).toMatch(/^multipart\/form-data; boundary=/);
    expect(upload?.body).toContain('filename="september.csv"');
    expect(Object.fromEntries(upload?.query ?? [])).toEqual({ bank: 'Acme', currency: 'USD', account_id: uid(2), date_order: 'DMY' });
    // The possible duplicate stays pending; the earlier import's repeat is never posted.
    expect(mock.data.posted).toEqual([[uid(901)]]);
    expect(result.stderr).toContain('Read 3 transactions from Acme Bank for Sep 1 – 30, 2026 into 1100 Checking.');
    expect(result.stderr).toContain('! Row 4: no amount');
    expect(result.stderr).toContain('Posted 1 of 3; 1 imported before; 1 left pending (salli statements pending).');
  });

  it('passes --source-account and --replaces, resolving the earlier statement by its start', async () => {
    expect((await run(['import', statement, '--source-account', 'Visa 1234', '--replaces', '00000321'])).code).toBe(0);
    const upload = mock.requestsTo('POST', '/v1/statements/upload')[0];
    expect(upload?.query.get('source_account')).toBe('Visa 1234');
    expect(upload?.query.get('replaces')).toBe(uid(801));
  });

  it('approves possible duplicates with --yes only when told to', async () => {
    const result = await run(['import', statement, '--yes', '--allow-possible-duplicates']);
    expect(result.code).toBe(0);
    expect(mock.data.posted).toEqual([[uid(901), uid(902)]]);
  });

  it('leaves everything pending without a terminal or --yes', async () => {
    const result = await run(['import', statement]);
    expect(result.code).toBe(0);
    expect(mock.data.posted).toEqual([]);
    expect(result.stdout).toMatchInlineSnapshot(`
      "DATE         DESCRIPTION                AMOUNT  FROM      TO         SURE  CHECK              ID
      Sep 2, 2026  SUPERMARKET 123     USD 45.20 out  Checking  Groceries   92%                     00000385
      Sep 3, 2026  COFFEE SHOP          USD 4.50 out  Checking  Groceries   61%  maybe a duplicate  00000386
      Sep 5, 2026  RENT SEPT        USD 1,800.00 out  Checking  Rent        99%  already imported   00000387
      "
    `);
    expect(result.stderr).toContain('Nothing posted.');
  });

  it('reviews each transaction: a changed account is categorized before posting, a discarded one is discarded', async () => {
    const prompter = new ScriptedPrompter([
      // 1: change where it went, then approve
      'change',
      uid(7),
      'approve',
      // 2: the possible duplicate: discard it
      'discard',
    ]);
    const result = await run(['import', statement, '--account', 'checking', '--json'], { prompter });
    expect(result.code).toBe(0);
    expect(prompter.asked).toEqual(['Post this one?', 'Where did it go?', 'Post this one?', 'Post this one?']);
    expect(mock.data.bodies.filter((b) => b.path === '/v1/statements/categorize').map((b) => b.body)).toEqual([
      { choices: [{ transaction_id: uid(901), account_id: uid(7) }] },
    ]);
    expect(mock.data.posted).toEqual([[uid(901)]]);
    expect(mock.data.bodies.find((b) => b.path.endsWith('/discard'))?.body).toEqual({ ids: [uid(902)] });
    // Nothing is reversed or re-entered any more.
    expect(mock.requestsTo('POST', '/v1/entries/')).toHaveLength(0);
    const output = JSON.parse(result.stdout);
    expect(output.categorized).toEqual([uid(901)]);
    expect(output.posted).toEqual({ posted: 1, entry_ids: [expect.any(String)] });
    expect(output.discarded).toBe(1);
    expect(output.skipped).toEqual([uid(903)]);
    expect(mock.data.statementTransactions.find((t) => t.id === uid(901))?.debit_account_id).toBe(uid(7));
  });

  it('refuses a file that is not there or too big', async () => {
    expect((await run(['import', join(dir, 'missing.pdf')])).code).toBe(2);
    const big = join(dir, 'big.pdf');
    await writeFile(big, Buffer.alloc(10 * 1024 * 1024 + 1));
    const result = await run(['import', big]);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('larger than the server accepts (10 MB)');
    expect(mock.requestsTo('POST', '/v1/statements/upload')).toHaveLength(0);
  });
});

describe('salli statements', () => {
  it('lists statements and what waits in review', async () => {
    expect((await run(['statements', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        ACCOUNT        BANK       PERIOD            STATUS   IMPORTED
      00000321  1100 Checking  Acme Bank  Sep 1 – 30, 2026  pending  Oct 2, 2026
      "
    `);
    const pending = await run(['statements', 'pending', '--output', 'ndjson']);
    // The earlier import's repeat never waits in review.
    expect(pending.stdout.trim().split('\n')).toHaveLength(2);
    expect((await run(['statements', 'pending', 'ffffffff'])).code).toBe(4);
  });

  it('posts named transactions, or all clean ones with --all --yes', async () => {
    const named = await run(['statements', 'post', uid(801).slice(0, 8), uid(902).slice(0, 8), '--json']);
    expect(named.code).toBe(0);
    expect(mock.data.posted).toEqual([[uid(902)]]);
    expect(JSON.parse(named.stdout)).toEqual({ posted: 1, entry_ids: [expect.any(String)] });

    const refused = await run(['statements', 'post', uid(801).slice(0, 8), '--all']);
    expect(refused.code).toBe(2);
    const all = await run(['statements', 'post', uid(801).slice(0, 8), '--all', '--yes']);
    expect(all.code).toBe(0);
    expect(mock.data.posted[1]).toEqual([uid(901)]);
  });

  it('discards named transactions, or every pending one after asking', async () => {
    const one = await run(['statements', 'discard', '00000321', uid(902).slice(0, 8), '--json']);
    expect(JSON.parse(one.stdout)).toEqual({ statement_id: uid(801), discarded: 1 });
    expect((await run(['statements', 'discard', '00000321'])).code).toBe(2);
    const rest = await run(['statements', 'discard', '00000321', '--yes']);
    expect(rest.stderr).toContain('Discarded 1 transaction.');
    expect((await run(['statements', 'pending'])).stderr).toContain('Nothing pending.');
  });

  it('chooses where a pending transaction goes', async () => {
    const result = await run(['statements', 'categorize', uid(901).slice(0, 8), 'rent', '--category', 'housing', '--need', 'essential']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('“SUPERMARKET 123” goes to 5100 Rent.');
    expect(mock.data.bodies.find((b) => b.path === '/v1/statements/categorize')?.body).toEqual({
      choices: [{ transaction_id: uid(901), account_id: uid(7), category: 'housing', need: 'essential' }],
    });
    const own = await run(['statements', 'categorize', uid(901).slice(0, 8), 'checking']);
    expect(own.code).toBe(2);
    expect(own.stderr).toContain('the statement’s own account');
  });
});
