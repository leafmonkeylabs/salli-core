import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ENTRIES, uid } from './helpers/fixtures';
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
  it('uploads the file and, with --yes, posts only what is unique and complete', async () => {
    const result = await run(['import', statement, '--currency', 'usd', '--bank', 'Acme', '--yes']);
    expect(result.code).toBe(0);
    const upload = mock.requestsTo('POST', '/v1/statements/upload')[0];
    expect(upload?.headers['content-type']).toMatch(/^multipart\/form-data; boundary=/);
    expect(upload?.body).toContain('filename="september.csv"');
    expect(upload?.body).toContain('SUPERMARKET 123');
    expect(upload?.query.get('currency')).toBe('USD');
    expect(upload?.query.get('bank')).toBe('Acme');
    // The fuzzy match and the exact duplicate stay out.
    expect(mock.data.posted).toEqual([[uid(901)]]);
    expect(result.stderr).toContain('Read 3 transactions from Acme Bank for Sep 1 – 30, 2026.');
    expect(result.stderr).toContain('! Row 4: no amount');
    expect(result.stderr).toContain('Posted 1 of 3; 1 already in your ledger; 1 left pending (salli statements pending).');
  });

  it('leaves everything pending without a terminal or --yes', async () => {
    const result = await run(['import', statement]);
    expect(result.code).toBe(0);
    expect(mock.data.posted).toEqual([]);
    expect(result.stdout).toMatchInlineSnapshot(`
      "DATE         DESCRIPTION                AMOUNT  FROM      TO         SURE  CHECK              ID
      Sep 2, 2026  SUPERMARKET 123     USD 45.20 out  Checking  Groceries   92%                     00000385
      Sep 3, 2026  COFFEE SHOP          USD 4.50 out  Checking  Groceries   61%  maybe a duplicate  00000386
      Sep 5, 2026  RENT SEPT        USD 1,800.00 out  Checking  Rent        99%  duplicate          00000387
      "
    `);
    expect(result.stderr).toContain('Nothing posted.');
  });

  it('reviews each transaction, and corrects one whose account you changed', async () => {
    // The server posts with its suggested accounts and records the transaction id.
    mock.on('POST', '/v1/statements/{id}/post', (req) => {
      const ids = (req.json as { approved_ids: string[] }).approved_ids;
      mock.data.posted.push(ids);
      for (const id of ids) {
        mock.data.entries.push({
          ...structuredClone(ENTRIES[0]!),
          id: `${id.slice(0, 8)}-e000-4000-8000-000000000000`,
          entry_date: '2026-09-02',
          source: 'statement',
          external_ref: id,
          reversed_by: null,
          postings: [
            { id: uid(951), tags: {}, account_id: uid(6), direction: 1, amount: '45.20', currency: 'USD', fx_rate: '1' },
            { id: uid(952), tags: {}, account_id: uid(2), direction: -1, amount: '45.20', currency: 'USD', fx_rate: '1' },
          ],
        });
      }
      return { status: 200, body: { posted: ids.length, entry_ids: ids } };
    });
    const prompter = new ScriptedPrompter([
      // 1: change "From" to the credit card, then approve
      'change',
      'credit',
      uid(4),
      'approve',
      // 2: the possible duplicate: skip it
      'skip',
    ]);
    const result = await run(['import', statement, '--json'], { prompter });
    expect(result.code).toBe(0);
    expect(prompter.asked).toEqual(['Post this one?', 'Which side?', 'Which account paid?', 'Post this one?', 'Post this one?']);
    expect(mock.data.posted).toEqual([[uid(901)]]);
    // Reversed, and re-entered with the chosen account, keeping its provenance.
    expect(mock.requestsTo('POST', '/v1/entries/').filter((r) => r.path.endsWith('/reverse'))).toHaveLength(1);
    expect(mock.data.created).toEqual([
      {
        entry_date: '2026-09-02',
        description: 'SUPERMARKET 123',
        source: 'statement',
        external_ref: uid(901),
        postings: [
          { account_id: uid(6), direction: 1, amount: '45.20', currency: 'USD' },
          { account_id: uid(4), direction: -1, amount: '45.20', currency: 'USD' },
        ],
      },
    ]);
    const output = JSON.parse(result.stdout);
    expect(output.posted).toEqual({ posted: 1, entry_ids: [uid(901)] });
    expect(output.corrections).toEqual([{ transaction_id: uid(901), reversed_entry: '00000385-e000-4000-8000-000000000000', entry: expect.any(String) }]);
    expect(output.skipped).toEqual([uid(902), uid(903)]);
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
  it('lists statements and pending transactions', async () => {
    expect((await run(['statements', 'list'])).stdout).toMatchInlineSnapshot(`
      "ID        BANK       PERIOD            STATUS  IMPORTED
      00000321  Acme Bank  Sep 1 – 30, 2026  parsed  Oct 2, 2026
      "
    `);
    const pending = await run(['statements', 'pending', '-o', 'ndjson']);
    expect(pending.stdout.trim().split('\n')).toHaveLength(3);
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
});
