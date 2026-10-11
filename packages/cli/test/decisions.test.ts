import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DECISION } from './helpers/decisions';
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
  files = await mkdtemp(join(tmpdir(), 'salli-decisions-'));
});
afterEach(async () => {
  await mock.close();
  await cleanup();
  await rm(files, { recursive: true, force: true });
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const lastBody = (path: string) => mock.decisions.bodies.filter((b) => b.path === path).at(-1)?.body;

async function scenarioFile(name: string, doc: Record<string, unknown>): Promise<string> {
  const path = join(files, name);
  await writeFile(path, JSON.stringify({ schema: 'salli.scenario/1', ...doc }));
  return path;
}

describe('salli principles', () => {
  it('lists the principles in use', async () => {
    const result = await run(['principles', 'list']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Six months of essentials in cash');
    expect(result.stdout).toContain('emergency_months >= 6');
    expect(result.stdout).toContain('account_lowest >= 5000');
  });

  it('adds one with its account found by name, and the server validates the check', async () => {
    const result = await run(['principles', 'add', 'Checking above 2,000', '--check', 'account_lowest >= 2000', '--account', 'checking']);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/principles')).toEqual({ label: 'Checking above 2,000', check: 'account_lowest >= 2000', account: uid(2) });
    expect(result.stderr).toContain('Kept the principle “Checking above 2,000”');
  });

  it('says what the server refused, with its path (exit 5)', async () => {
    const result = await run(['principles', 'add', 'Bad', '--check', 'nonsense >= 1']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain("There is no figure 'nonsense'");
  });

  it('edits and archives, never deletes', async () => {
    const [first] = mock.decisions.principles;
    const edited = await run(['principles', 'edit', first!.id.slice(0, 8), '--check', 'emergency_months >= 4', '--note', '']);
    expect(edited.code).toBe(0);
    expect(lastBody(`/v1/principles/${first!.id}`)).toEqual({ check: 'emergency_months >= 4', note: null });
    const second = mock.decisions.principles[1]!;
    await run(['principles', 'edit', second.id, '--no-account', '--check', 'lowest_cash >= 0']);
    expect(lastBody(`/v1/principles/${second.id}`)).toEqual({ check: 'lowest_cash >= 0', account: null });
    expect((await run(['principles', 'archive', first!.id])).code).toBe(2); // needs --yes in a script
    const archived = await run(['principles', 'archive', first!.id, '--yes']);
    expect(archived.code).toBe(0);
    expect(archived.stderr).toContain('It stays in your records.');
    const all = await run(['principles', 'list', '--all']);
    expect(all.stdout).toContain('archived');
  });

  it('checks options from files against the principles, never ranking them', async () => {
    const cash = await scenarioFile('pay-cash.json', { label: 'Pay cash', changes: [] });
    const spread = await scenarioFile('instalments.json', { changes: [] });
    const result = await run(['principles', 'check', cash, spread]);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/principles/check')).toEqual({
      options: [
        { schema: 'salli.scenario/1', label: 'Pay cash', changes: [] },
        { schema: 'salli.scenario/1', label: 'instalments', changes: [] },
      ],
    });
    expect(result.stdout).toContain('PRINCIPLE');
    expect(result.stdout).toContain('breaks');
    expect(result.stdout).toContain("account_lowest >= 5000 doesn't hold: account_lowest is 4883.77.");
    expect(result.stderr).toContain('Salli doesn’t rank options');
  });

  it('lists the figures a check may read', async () => {
    const result = await run(['principles', 'figures']);
    expect(result.stdout).toContain('max_debt_rate_while_investing');
    expect(result.stdout).toContain('months of spending');
  });
});

describe('salli decisions', () => {
  it('lists the journal and shows an entry, whose words are whose', async () => {
    const list = await run(['decisions', 'list']);
    expect(list.code).toBe(0);
    expect(list.stdout).toContain('Laptop: pay cash or spread it?');
    expect(list.stdout).toContain('review due');
    const shown = await run(['decisions', 'show', DECISION.id.slice(0, 8)]);
    expect(shown.code).toBe(0);
    expect(shown.stdout).toContain('Your reasons');
    expect(shown.stdout).toContain('I’d rather not owe anything.'.replace('’', "'"));
    expect(shown.stdout).toContain('The agent’s summary (Claude) written by the agent, not you');
    expect(shown.stdout).toContain('PAY CASH (CHOSEN)');
    expect(shown.stdout).toContain('11,598.91');
    expect(shown.stdout).toContain('(unchanged)');
  });

  it('records a decision only once confirmed, with Salli running the options', async () => {
    const cash = await scenarioFile('cash.json', { label: 'Pay cash' });
    const wait = await scenarioFile('wait.json', {});
    const args = ['decisions', 'record', '--question', 'Laptop?', '--option', cash, '--option', wait, '--chosen', 'Pay cash', '--reasons', 'Needed it.', '--review-on', '2027-04-11'];
    const unconfirmed = await run(args);
    expect(unconfirmed.code).toBe(2);
    expect(unconfirmed.stderr).toContain('Pass --yes to confirm.');
    expect(lastBody('/v1/decisions')).toBeUndefined();
    const result = await run([...args, '--agent-summary', 'Cash costs nothing.', '--agent', 'Claude', '--yes']);
    expect(result.code).toBe(0);
    expect(lastBody('/v1/decisions')).toEqual({
      question: 'Laptop?',
      options: [
        { schema: 'salli.scenario/1', label: 'Pay cash' },
        { schema: 'salli.scenario/1', label: 'wait' },
      ],
      chosen: 'Pay cash',
      reasons: 'Needed it.',
      review_on: '2027-04-11',
      agent_summary: 'Cash costs nothing.',
      agent: 'Claude',
    });
    expect(result.stderr).toContain('Salli will remind you to review it on Apr 11, 2027.');
  });

  it('adds a note', async () => {
    const result = await run(['decisions', 'note', DECISION.id, 'Delivered on the 4th.']);
    expect(result.code).toBe(0);
    expect(lastBody(`/v1/decisions/${DECISION.id}/notes`)).toEqual({ text: 'Delivered on the 4th.' });
  });

  it('shows what is due, and records a review with the reflection', async () => {
    const due = await run(['decisions', 'reviews']);
    expect(due.code).toBe(0);
    expect(due.stdout).toContain('What Pay cash projected for Mar 31, 2027, and what happened');
    expect(due.stdout).toContain('PROJECTED');
    expect(due.stdout).toContain('Your reasons then:');
    const scripted = await run(['decisions', 'review', DECISION.id]);
    expect(scripted.code).toBe(2);
    expect(scripted.stderr).toContain('Pass --reflection');
    const result = await run(['decisions', 'review', DECISION.id, '--reflection', 'Glad I did.']);
    expect(result.code).toBe(0);
    expect(lastBody(`/v1/decisions/${DECISION.id}/review`)).toEqual({ reflection: 'Glad I did.' });
    expect(result.stderr).toContain('The entry itself is unchanged.');
    const again = await run(['decisions', 'review', DECISION.id, '--reflection', 'Again.']);
    expect(again.code).toBe(5);
    expect(again.stderr).toContain('is before the review date');
    expect((await run(['decisions', 'reviews'])).stderr).toContain('No decisions are due for review.');
  });

  it('exports the journal as Markdown or JSON', async () => {
    const md = await run(['decisions', 'export']);
    expect(md.code).toBe(0);
    expect(md.stdout).toContain('# Decision journal');
    expect(md.stdout).toContain(`Entry hash \`${DECISION.hash}\``);
    const out = join(files, 'journal.json');
    const json = await run(['decisions', 'export', '--format', 'json', '-o', out]);
    expect(json.code).toBe(0);
    const written = JSON.parse(await readFile(out, 'utf8')) as { schema: string; entries: Array<{ hash: string }> };
    expect(written.schema).toBe('salli.decision-journal/1');
    expect(written.entries[0]?.hash).toBe(DECISION.hash);
    const one = await run(['decisions', 'export', DECISION.id.slice(0, 8)]);
    expect(one.stdout).toContain('Laptop: pay cash or spread it?');
    expect((await run(['decisions', 'export', '--format', 'pdf'])).code).toBe(2);
  });
});
