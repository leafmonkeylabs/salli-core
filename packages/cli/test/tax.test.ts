import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';

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
  runCli(args, { configDir: dir, tty: 140, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });

const atTerminal = (answers: string[]) => {
  const prompter = new ScriptedPrompter(answers);
  return { prompter, options: { tty: 140, stdinIsTTY: true, prompter } satisfies Partial<RunOptions> };
};

describe('salli tax compute, latest and explain', () => {
  it('prints every line with its expression, the amount owed, and which rules computed it', async () => {
    const result = await run(['tax', 'compute', '--country', 'XA', '--year', '2031', '--answer', 'filing_status=single']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Tax XA 2031');
    expect(result.stdout).toContain('Computed from your rules, version 1 (a1a1a1a1a1a1)');
    expect(result.stdout).toMatch(/Income tax\s+income_tax\s+11,200\.00\s+line\.income_tax\.band_1\.tax/);
    expect(result.stdout).toMatch(/Refund\s+USD 800\.00/);
    expect(result.stderr).toContain("Salli doesn't vouch for the law");
    expect(mock.taxRules.calls[0]).toEqual({
      path: '/v1/tax/compute',
      query: { country: 'XA', year: '2031' },
      body: { answers: { filing_status: 'single' } },
    });
  });

  it('prints the lines as records, and the API’s JSON untouched', async () => {
    const records = await run(['tax', 'compute', '--output', 'ndjson']);
    expect(records.stdout.trim().split('\n').map((l) => JSON.parse(l).key)).toEqual(['allowance', 'income_tax', 'withholding', 'balance']);
    const json = JSON.parse((await run(['tax', 'latest', '--json'])).stdout);
    expect(json.result.rule_set_version_id).toBe(uid(1511));
    expect(json.result.net).toBe('-800.00');
  });

  it('says what to do when there are no active rules', async () => {
    mock.taxRules.hasRules = false;
    const result = await run(['tax', 'compute']);
    expect(result.code).not.toBe(0);
    expect(result.stderr).toContain('no tax rules for the United Kingdom');
    expect(result.stderr).toContain('salli tax rules create <file>');
    expect((await run(['tax', 'latest'])).code).toBe(4);
  });

  it('explains a line: what it used and its source', async () => {
    const result = await run(['tax', 'explain', 'income_tax']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Income tax (income_tax)');
    expect(result.stdout).toContain('Income Tax Act 2031');
    expect(result.stdout).toMatch(/Income tax: band 2\s+income_tax\.band_2\.tax\s+3,200\.00/);
    expect(result.stderr).toContain('Used by: balance.');
    const missing = await run(['tax', 'explain', 'nowhere']);
    expect(missing.code).toBe(4);
    expect(missing.stderr).toContain("There is no line 'nowhere'");
  });
});

describe('salli tax return', () => {
  it('prepares a return from the rules’ forms and names the thread to review', async () => {
    const result = await run(['tax', 'return', 'prepare', '--thread', 't1', '--year', '2031']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Draft return: XA 2031');
    expect(result.stdout).toMatch(/box_2\s+Income tax\s+11200/);
    expect(result.stdout).toMatch(/box_3\s+Claims a refund\s+yes/);
    expect(result.stdout).toContain('Sign in to the XA revenue portal');
    expect(result.stdout).toContain('https://example.org/xa/file');
    expect(result.stderr).toContain('salli tax return review t1');
    expect(mock.taxRules.calls[0]?.body).toEqual({ answers: {}, year: '2031', thread_id: 't1' });
  });

  it('approves a prepared return into a worksheet, ready to file', async () => {
    await run(['tax', 'return', 'prepare', '--thread', 't1']);
    const approved = await run(['tax', 'return', 'review', 't1', '--approve']);
    expect(approved.code).toBe(0);
    expect(approved.stdout).toContain('Ready to file: XA 2031');
    expect(approved.stderr).toContain('Salli files nothing');
    expect((await run(['tax', 'return', 'review', 't1', '--approve'])).code).toBe(4);
  });

  it('edits with new answers and comes back for review', async () => {
    await run(['tax', 'return', 'prepare', '--thread', 't1']);
    const edited = await run(['tax', 'return', 'review', 't1', '--edit', '--answer', 'filing_status=joint']);
    expect(edited.code).toBe(0);
    expect(edited.stdout).toContain('New draft return');
    expect(edited.stderr).toContain('salli tax return review t1');
    expect(mock.taxRules.returns.get('t1')?.answers).toEqual({ filing_status: 'joint' });
  });

  it('asks a person what to do, and loops after an edit', async () => {
    await run(['tax', 'return', 'prepare', '--thread', 't1']);
    const { prompter, options } = atTerminal(['edit', 'filing_status=joint', 'approve']);
    const result = await run(['tax', 'return', 'review', 't1'], options);
    expect(result.code).toBe(0);
    expect(prompter.asked.filter((m) => m === 'This return:')).toHaveLength(2);
    expect(result.stdout).toContain('Ready to file');
  });

  it('needs a decision when nobody can be asked', async () => {
    await run(['tax', 'return', 'prepare', '--thread', 't1']);
    const result = await run(['tax', 'return', 'review', 't1']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('--approve, --edit (with --answer) or --reject');
  });

  it('rejects a return', async () => {
    await run(['tax', 'return', 'prepare', '--thread', 't1']);
    const result = await run(['tax', 'return', 'review', 't1', '--reject']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Rejected');
  });
});

describe('salli tax rules accounts', () => {
  it('shows the accounts a rule set suggests, then creates the missing ones once', async () => {
    const preview = await run(['tax', 'rules', 'accounts', 'XA 2031']);
    expect(preview.code).toBe(0);
    expect(preview.stdout).toMatch(/1450\s+Tax withheld\s+asset\s+tax_withheld\s+missing/);
    expect(preview.stdout).toMatch(/1000\s+Bank.*you have it/);
    expect(preview.stderr).toContain("You have 1000 as 'Checking'");
    expect(preview.stderr).toContain(`salli tax rules accounts ${uid(1501).slice(0, 8)} --apply`);

    const applied = await run(['tax', 'rules', 'accounts', 'XA 2031', '--apply']);
    expect(applied.stdout).toMatch(/1450\s+Tax withheld\s+asset\s+tax_withheld\s+created/);
    const again = JSON.parse((await run(['tax', 'rules', 'accounts', 'XA 2031', '--apply', '--json'])).stdout);
    expect(again.accounts.map((a: { status: string }) => a.status)).toEqual(['exists', 'exists', 'exists']);
  });
});

describe('what is gone', () => {
  it('has no tax packs command', async () => {
    const result = await run(['tax', 'packs']);
    expect(result.code).toBe(2);
  });
});
