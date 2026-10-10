import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { answersArg, resolveRuleSet, resolveVersion } from '../src/commands/taxrules';
import { routeVersionOption } from '../src/main';
import { NotFoundError, UsageError } from '../src/errors';
import { uid } from './helpers/fixtures';
import { MockSalli } from './helpers/mock-server';
import { XA_V1, XA_V2 } from './helpers/taxrules';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
/** The CLI's own OAuth sign-in: holds tax:activate. */
let signedIn: string;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  signedIn = mock.issueTokens().access_token;
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: signedIn, ...options.env } });

/** A person at a terminal who answers the prompts with `answers`. */
const atTerminal = (answers: string[]) => {
  const prompter = new ScriptedPrompter(answers);
  return { prompter, options: { tty: 120, stdinIsTTY: true, prompter } satisfies Partial<RunOptions> };
};

const SET = uid(1501);
const V1 = uid(1511);
const V2 = uid(1512);

async function file(name: string, content: unknown): Promise<string> {
  const path = join(dir, name);
  await writeFile(path, typeof content === 'string' ? content : JSON.stringify(content, null, 2));
  return path;
}

const xaYear = (label: string, extra: Record<string, unknown> = {}) => ({
  ...XA_V1,
  jurisdiction: { country: 'XB', region: null },
  year: { label, start: `${label}-01-01`, end: `${label}-12-31` },
  ...extra,
});

describe('naming rule sets and versions', () => {
  const sets = [
    { ...mockSet(), id: uid(1501), name: 'XA 2031' },
    { ...mockSet(), id: uid(1502), name: 'XA 2032' },
  ];
  function mockSet() {
    return {
      country: 'XA',
      region: null,
      year_label: '2031',
      active_version_id: null,
      created_at: '',
      updated_at: '',
      versions: [
        { id: uid(1601), version: 1 },
        { id: uid(1602), version: 2 },
      ],
    } as never as Parameters<typeof resolveRuleSet>[0][number];
  }

  it('takes an id, a unique start of one, or a name', () => {
    expect(resolveRuleSet(sets, uid(1502)).name).toBe('XA 2032');
    expect(resolveRuleSet(sets, '000005de').name).toBe('XA 2032');
    expect(resolveRuleSet(sets, 'xa 2031').id).toBe(uid(1501));
    expect(() => resolveRuleSet(sets, '00000')).toThrow(UsageError); // ambiguous
    expect(() => resolveRuleSet(sets, 'XA 2040')).toThrow(NotFoundError);
  });

  it('takes a version number, v-number or id', () => {
    const [set] = sets;
    expect(resolveVersion(set!, '2').id).toBe(uid(1602));
    expect(resolveVersion(set!, 'v1').id).toBe(uid(1601));
    expect(resolveVersion(set!, uid(1602).slice(0, 8)).version).toBe(2);
    expect(() => resolveVersion(set!, '3')).toThrow('XA 2031 has no version 3');
  });

  it('reads answers: true and false as such, anything else as typed', () => {
    expect(answersArg(['filing_status=joint', 'has_children=true', 'donations=1200.50', 'blind=false'])).toEqual({
      filing_status: 'joint',
      has_children: true,
      donations: '1200.50',
      blind: false,
    });
    expect(() => answersArg(['nokey'])).toThrow(UsageError);
    expect(() => answersArg(['=1'])).toThrow(UsageError);
  });

  it('passes --version after a command to the command, not the program', () => {
    expect(routeVersionOption(['tax', 'rules', 'show', 'XA', '--version', '3'])).toEqual(['tax', 'rules', 'show', 'XA', '--version=3']);
    expect(routeVersionOption(['--version'])).toEqual(['--version']);
    expect(routeVersionOption(['--server', 'http://x', '--version'])).toEqual(['--server', 'http://x', '--version']);
    expect(routeVersionOption(['tax', '--version', '--json'])).toEqual(['tax', '--version', '--json']);
  });
});

describe('salli tax schema', () => {
  it('prints the JSON Schema, or writes it to a file', async () => {
    const printed = await run(['tax', 'schema']);
    expect(printed.code).toBe(0);
    expect(JSON.parse(printed.stdout)).toMatchObject({ title: 'Salli tax rule set' });

    const path = join(dir, 'schema.json');
    const written = await run(['tax', 'schema', '-o', path, '--json']);
    expect(written.code).toBe(0);
    expect(JSON.parse(await readFile(path, 'utf8'))).toMatchObject({ title: 'Salli tax rule set' });
    expect(JSON.parse(written.stdout)).toMatchObject({ schema: 'salli.tax/1', path });
  });
});

describe('salli tax rules list | show', () => {
  it('lists rule sets for people, and as the API’s JSON', async () => {
    const result = await run(['tax', 'rules', 'list']);
    expect(result.code).toBe(0);
    expect(result.stdout).toMatch(/^ID +RULE SET +ACTIVE +NEWEST +VERSIONS +UPDATED\n000005dd +XA 2031 +v1 +v2 proposed +2 +Mar 5, 2031\n$/);
    expect(result.stderr).toContain('XA 2031 has a version proposed for your review: `salli tax rules activate 000005dd`');

    const json = JSON.parse((await run(['tax', 'rules', 'list', '--json'])).stdout) as Array<{ id: string; versions: unknown[] }>;
    expect(json).toHaveLength(1);
    expect(json[0]).toMatchObject({ id: SET, name: 'XA 2031', active_version_id: V1 });
  });

  it('shows the versions with status, author, note and hash', async () => {
    const result = await run(['tax', 'rules', 'show', 'XA 2031']);
    expect(result.code).toBe(0);
    const lines = result.stdout.split('\n');
    expect(lines[0]).toBe(`XA 2031 ${SET}`);
    expect(lines[1]).toBe('Active  version 1, since Feb 2, 2031');
    expect(lines[3]).toMatch(/^VERSION +STATUS +AUTHOR +NOTE +HASH +CREATED$/);
    expect(lines[4]).toMatch(/^ +1 +active +you \(Salli CLI\) +— +a1a1a1a1a1a1 +Mar 5, 2031$/);
    expect(lines[5]).toMatch(/^ +2 +proposed +an agent \(Claude\) +Allowance raised to 12,500 by the 2031 budget +b2b2b2b2b2b2 +Mar 5, 2031$/);
    expect(result.stderr).toContain('Version 2 awaits your review');
    const ndjson = await run(['tax', 'rules', 'show', SET.slice(0, 8), '--output', 'ndjson']);
    expect(ndjson.stdout.trim().split('\n').map((l) => JSON.parse(l).version)).toEqual([1, 2]);
  });

  it('shows one version’s details and its validation report', async () => {
    const result = await run(['tax', 'rules', 'show', 'XA 2031', '--version', '2']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('XA 2031, version 2');
    expect(result.stdout).toMatch(/Author +an agent \(Claude\)/);
    expect(result.stdout).toMatch(/Note +Allowance raised to 12,500 by the 2031 budget/);
    expect(result.stdout).toContain('✓ Valid: it compiles, and every worked example passes.');
    expect(result.stdout).toContain("! roles[1]  Role 'tax_withheld' is never used");
    expect(result.stdout).toContain('Worked examples (2 of 2 pass)');

    const json = JSON.parse((await run(['tax', 'rules', 'show', 'XA 2031', '--version', V1.slice(0, 8), '--json'])).stdout);
    expect(json).toMatchObject({ id: V1, version: 1, status: 'active', document: { schema: 'salli.tax/1' } });

    const missing = await run(['tax', 'rules', 'show', 'XA 2031', '--version', '9']);
    expect(missing.code).toBe(4);
    expect(missing.stderr).toContain('XA 2031 has no version 9');
    const noSet = await run(['tax', 'rules', 'show', 'XQ 1999']);
    expect(noSet.code).toBe(4);
    expect(noSet.stderr).toContain('See `salli tax rules list`');
  });
});

describe('salli tax rules create | version | import', () => {
  it('sends the file’s text as it is, and shows what validation found', async () => {
    const text = `${JSON.stringify(xaYear('2040'), null, 2)}\n`;
    const path = await file('xb.json', text);
    const result = await run(['tax', 'rules', 'create', path, '--note', 'From the act']);
    expect(result.code).toBe(0);
    // The text itself, so the server reads it strictly (a key twice is refused, not dropped).
    expect(mock.requestsTo('POST', '/v1/tax/rule-sets')[0]?.json).toEqual({ document: text, note: 'From the act' });
    expect(result.stderr).toContain('✓ Created XB 2040, version 1: validated.');
    expect(result.stdout).toContain('Worked examples (1 of 1 pass)');
    expect(result.stderr).toMatch(/propose it for review \(`salli tax rules propose [0-9a-f]{8} --version 1`\)/);

    const again = await run(['tax', 'rules', 'create', path]);
    expect(again.code).toBe(5);
    expect(again.stderr).toContain('You already have a rule set for XB 2040');
  });

  it('stores a draft with its mistakes, and says what to fix', async () => {
    const path = await file('wrong.json', xaYear('2041', { examples: [{ name: 'A wrong figure', inputs: {}, expected: { payable: '2999' } }] }));
    const result = await run(['tax', 'rules', 'create', path]);
    expect(result.code).toBe(0); // stored: an agent iterates on it
    expect(result.stderr).toContain('version 1: draft');
    expect(result.stdout).toContain('payable: expected 2999, got 3600');
    expect(result.stdout).toContain('from line.balance');
    expect(result.stderr).toContain('Fix what is listed, then add it as a new version');
  });

  it('reads stdin with -, and refuses a missing file before signing in', async () => {
    const result = await run(['tax', 'rules', 'create', '-', '--json'], { stdin: JSON.stringify(xaYear('2042')) });
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout)).toMatchObject({ version: 1, status: 'validated' });

    const missing = await run(['tax', 'rules', 'create', join(dir, 'nope.json')]);
    expect(missing.code).toBe(2);
    expect(missing.stderr).toContain('No such file');
  });

  it('adds a version to a set, with a note', async () => {
    const path = await file('v3.json', XA_V2);
    const result = await run(['tax', 'rules', 'version', 'XA 2031', path, '--note', 'Typo fixed', '--json']);
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout)).toMatchObject({ rule_set_id: SET, version: 3, change_note: 'Typo fixed' });
    expect(mock.requestsTo('POST', `/v1/tax/rule-sets/${SET}/versions`)[0]?.json).toMatchObject({ note: 'Typo fixed' });
  });

  it('imports a file or an https URL, as a draft', async () => {
    const path = await file('shared.json', XA_V2);
    const fromFile = await run(['tax', 'rules', 'import', path]);
    expect(fromFile.code).toBe(0);
    expect(fromFile.stderr).toContain('Imported into XA 2031, version 3: draft.');

    const fromUrl = await run(['tax', 'rules', 'import', 'https://example.org/xa-2031.json', '--json']);
    expect(fromUrl.code).toBe(0);
    expect(mock.requestsTo('POST', '/v1/tax/rule-sets/import')[1]?.json).toEqual({ url: 'https://example.org/xa-2031.json' });
    expect(JSON.parse(fromUrl.stdout)).toMatchObject({ status: 'draft' });

    const http = await run(['tax', 'rules', 'import', 'http://example.org/x.json']);
    expect(http.code).toBe(2);
    expect(http.stderr).toContain('Only https:// URLs can be imported');
  });
});

describe('salli tax rules export', () => {
  it('writes the canonical text exactly, so its SHA-256 is the content hash', async () => {
    const piped = await run(['tax', 'rules', 'export', 'XA 2031', '--version', '1']);
    expect(piped.code).toBe(0);
    expect(piped.stdout).toBe(JSON.stringify(XA_V1)); // not a byte more
    expect(piped.stderr).toContain('Suggested file name: xa-2031-v1.salli-tax.json');

    const path = join(dir, 'out.json');
    const written = await run(['tax', 'rules', 'export', 'XA 2031', '-o', path, '--json']);
    expect(written.code).toBe(0);
    const content = await readFile(path, 'utf8');
    expect(content).toBe(JSON.stringify(XA_V2));
    expect(JSON.parse(written.stdout)).toMatchObject({ version: 2, content_hash: 'b2'.repeat(32), canonical: true, bytes: Buffer.byteLength(content) });
    expect(createHash('sha256').update(content).digest('hex')).toHaveLength(64);

    const json = JSON.parse((await run(['tax', 'rules', 'export', 'XA 2031', '--json'])).stdout);
    expect(json).toMatchObject({ filename: 'xa-2031-v2.salli-tax.json', canonical: true });
  });
});

describe('salli tax rules validate | propose', () => {
  it('shows the problems, the warnings and every example, and exits 0 when valid', async () => {
    const result = await run(['tax', 'rules', 'validate', 'XA 2031']);
    expect(result.code).toBe(0);
    expect(mock.requestsTo('POST', `/v1/tax/rule-sets/${SET}/versions/${V2}/validate`)).toHaveLength(1);
    expect(result.stderr).toContain('Version 2, the newest');
    expect(result.stdout).toContain('Warnings (1)');
    expect(result.stdout).toContain('✓ Salary of 30,000');
    expect(result.stdout).toContain('✓ Salary of 60,000');
  });

  it('shows expected and got for each mismatching line, with its expression, and exits 1', async () => {
    const path = await file('wrong.json', { ...XA_V2, examples: [{ name: 'A wrong one', inputs: {}, expected: { payable: '3500' } }, { name: 'A right one', inputs: {}, expected: {} }] });
    await run(['tax', 'rules', 'version', 'XA 2031', path]);
    const result = await run(['tax', 'rules', 'validate', 'XA 2031', '--version', '3']);
    expect(result.code).toBe(1);
    expect(result.stdout).toContain('! Not ready: it compiles, but its worked examples are missing or don');
    expect(result.stdout).toContain('Worked examples (1 of 2 pass)');
    expect(result.stdout).toContain('✗ A wrong one');
    expect(result.stdout).toContain('payable: expected 3500, got 3600');
    expect(result.stdout).toContain('from line.balance');
    expect(result.stdout).toContain('allowance.remaining: expected 17500, got 18000');
    expect(result.stdout).toContain('from max(0, role.salary - line.allowance)');
    expect(result.stdout).toContain('✓ A right one');
    expect(result.stderr).toBe(''); // the report is the output; the exit code says the rest

    const json = await run(['tax', 'rules', 'validate', 'XA 2031', '--version', '3', '--json']);
    expect(json.code).toBe(1);
    expect(JSON.parse(json.stdout).validation.examples[0].mismatches[0]).toMatchObject({ key: 'payable', expected: '3500', got: '3600', expr: 'line.balance' });
  });

  it('reports an invalid document’s problems with the snippet', async () => {
    const path = await file('broken.json', { jurisdiction: { country: 'XA' }, year: { label: '2031' } });
    await run(['tax', 'rules', 'version', 'XA 2031', path]);
    const result = await run(['tax', 'rules', 'validate', 'XA 2031']);
    expect(result.code).toBe(1);
    expect(result.stdout).toContain("✗ Invalid: it doesn't compile");
    expect(result.stdout).toContain('✗ schema  Field required');
  });

  it('proposes a valid version and says who activates it', async () => {
    const path = await file('v3.json', XA_V2);
    await run(['tax', 'rules', 'version', 'XA 2031', path]);
    const result = await run(['tax', 'rules', 'propose', 'XA 2031']);
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Proposed XA 2031, version 3, for review.');
    expect(result.stderr).toContain('review it and confirm yourself, at your own terminal: `salli tax rules activate 000005dd`');
  });

  it('refuses to propose what isn’t valid (exit 5)', async () => {
    const path = await file('wrong.json', { ...XA_V2, examples: [{ name: 'wrong', inputs: {}, expected: { payable: '1' } }] });
    await run(['tax', 'rules', 'version', 'XA 2031', path]);
    const result = await run(['tax', 'rules', 'propose', 'XA 2031', '--version', '3']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain("Version 3 can't be proposed");
  });
});

describe('salli tax rules diff', () => {
  it('compares the active version with the newest, each figure beside its source', async () => {
    const result = await run(['tax', 'rules', 'diff', 'XA 2031']);
    expect(result.code).toBe(0);
    const diff = mock.requestsTo('GET', `/v1/tax/rule-sets/${SET}/diff`)[0];
    expect(diff?.query.get('to')).toBe(V2);
    expect(diff?.query.has('from')).toBe(false); // the server's default: the active one
    expect(result.stdout).toContain('XA 2031: version 1 (active) → version 2 (proposed)');
    expect(result.stdout).toContain('Changed figures (1)\n  ~ blocks[key=allowance].amount  12000 → 12500\n      source: Budget Statement 2031 — https://example.org/xa/budget-2031, retrieved 2031-03-02');
    expect(result.stdout).toContain('+ sources[id=budget]  added: Budget Statement 2031 — https://example.org/xa/budget-2031');
    expect(result.stdout).toContain('Worked examples (2 of 2 pass)');
  });

  it('takes --from and --to, and prints the changes as records', async () => {
    const result = await run(['tax', 'rules', 'diff', 'XA 2031', '--from', '2', '--to', '1', '--output', 'ndjson']);
    expect(result.code).toBe(0);
    const diff = mock.requestsTo('GET', `/v1/tax/rule-sets/${SET}/diff`)[0];
    expect([diff?.query.get('from'), diff?.query.get('to')]).toEqual([V2, V1]);
    expect(JSON.parse(result.stdout.trim().split('\n')[0] ?? '{}')).toMatchObject({ kind: 'changed', figure: true });
  });

  it('says when there is nothing active to compare with', async () => {
    const path = await file('xb.json', xaYear('2043'));
    await run(['tax', 'rules', 'create', path]);
    const result = await run(['tax', 'rules', 'diff', 'XB 2043']);
    expect(result.stdout).toContain('XB 2043: nothing active → version 1 (validated)');
    expect(result.stdout).toContain('First version: no version is active yet');
  });
});

describe('salli tax rules evaluate', () => {
  it('shows each line, then net, payable and refund, from the server’s figures', async () => {
    const result = await run(['tax', 'rules', 'evaluate', 'XA 2031', '--answer', 'filing_status=joint', '--answer', 'blind=false', '--year', '2031']);
    expect(result.code).toBe(0);
    expect(mock.taxRules.evaluated).toEqual([{ answers: { filing_status: 'joint', blind: false }, year: '2031' }]);
    expect(result.stdout).toMatch(/Salary +salary +60,000\.00 +12/);
    expect(result.stdout).toMatch(/income_tax +Income tax +11,000\.00 +line\.income_tax\.band_1\.tax/);
    expect(result.stdout).toMatch(/withholding +Tax withheld \(refundable\) +12,000\.00 +role\.tax_withheld/);
    expect(result.stdout).toMatch(/Net +-USD 1,000\.00 +\(line\.balance\)/);
    expect(result.stdout).toMatch(/Payable +USD 0\.00/);
    expect(result.stdout).toMatch(/Refund +USD 1,000\.00/);
    expect(result.stderr).toContain('Computed from rules you or your agent entered');

    const json = JSON.parse((await run(['tax', 'rules', 'evaluate', 'XA 2031', '--version', '1', '--json'])).stdout);
    expect(json).toMatchObject({ net: '-1000.00', tax_payable: '0.00', refund_due: '1000.00' });
    expect(mock.requestsTo('POST', `/v1/tax/rule-sets/${SET}/versions/${V1}/evaluate`)).toHaveLength(1);

    const bad = await run(['tax', 'rules', 'evaluate', 'XA 2031', '--answer', 'joint']);
    expect(bad.code).toBe(2);
    expect(bad.stderr).toContain('--answer takes KEY=VALUE');
  });
});

describe('salli tax rules activate', () => {
  const activations = () => mock.requestsTo('POST', `/v1/tax/rule-sets/${SET}/versions/${V2}/activate`);
  const status = (id: string) => mock.taxRules.versions.get(id)?.status;

  it('refuses when stdin is not a terminal, before signing in or asking anything', async () => {
    const { prompter } = atTerminal(['2']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031'], { tty: 120, stdinIsTTY: false, prompter });
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('Activating tax rules needs a person at a terminal, and stdin is not a terminal.');
    expect(result.stderr).toContain('There is no --yes');
    expect(result.stderr).toContain('An AI agent can draft, validate and propose rules, never activate them.');
    expect(prompter.asked).toEqual([]);
    expect(mock.requests).toHaveLength(0);
  });

  it('refuses when stdout is not a terminal', async () => {
    const { prompter } = atTerminal(['2']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031'], { stdinIsTTY: true, prompter });
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('stdout is not a terminal');
    expect(mock.requests).toHaveLength(0);
  });

  it('refuses with --json, or any output meant for a program, even at a terminal', async () => {
    for (const flags of [['--json'], ['--output', 'csv'], ['--output=ndjson']]) {
      const { prompter, options } = atTerminal(['2']);
      const result = await run(['tax', 'rules', 'activate', 'XA 2031', ...flags], options);
      expect(result.code).toBe(2);
      expect(prompter.asked).toEqual([]);
      if (flags[0] === '--json') {
        expect(JSON.parse(result.stderr)).toMatchObject({ type: '/problems/cli/needs-a-person', exit_code: 2 });
        expect(JSON.parse(result.stderr).title).toContain('the output is for a program (--json)');
      }
    }
    expect(mock.requests).toHaveLength(0);
  });

  it('has no --yes', async () => {
    const { options } = atTerminal([]);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031', '--yes'], options);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain("Unknown option '--yes'");
  });

  it('shows the review, and does nothing on a wrong confirmation', async () => {
    const { prompter, options } = atTerminal(['yes']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031'], options);
    expect(result.code).toBe(1);
    expect(prompter.asked).toEqual(['Type 2 to activate version 2 of XA 2031, or anything else to cancel']);
    expect(result.stderr).toContain('Not activated: you typed “yes”, not 2.');
    expect(activations()).toHaveLength(0);
    expect(status(V2)).toBe('proposed');
    expect(status(V1)).toBe('active');
  });

  it('activates on the version number typed, after showing the diff, sources, examples and author', async () => {
    const { prompter, options } = atTerminal([' 2 ']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031'], options);
    expect(result.code).toBe(0);
    const screen = result.stdout;
    expect(screen).toContain('Activate XA 2031, version 2?');
    expect(screen).toContain('Salli would compute your XA 2031 tax with version 2 instead of version 1 (active since Feb 2, 2031).');
    expect(screen).toMatch(/Written by +an agent \(Claude\)/);
    expect(screen).toMatch(/Why +Allowance raised to 12,500 by the 2031 budget/);
    expect(screen).toContain('~ blocks[key=allowance].amount  12000 → 12500');
    expect(screen).toContain('source: Budget Statement 2031 — https://example.org/xa/budget-2031');
    expect(screen).toContain('✓ Salary of 30,000');
    expect(screen).toContain('✓ Salary of 60,000');
    expect(screen).toContain('it does not vouch for them');
    expect(prompter.asked).toHaveLength(1);
    expect(activations()).toHaveLength(1);
    expect(result.stderr).toContain('✓ XA 2031, version 2, is active');
    expect(status(V2)).toBe('active');
    expect(status(V1)).toBe('superseded');
  });

  it('says "first version" when nothing is active yet', async () => {
    const path = await file('xb.json', xaYear('2044'));
    await run(['tax', 'rules', 'create', path]);
    const { options } = atTerminal(['1']);
    const result = await run(['tax', 'rules', 'activate', 'XB 2044', '--version', '1'], options);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('It is the first version you activate.');
    expect(result.stdout).toContain('First version: no version is active yet');
  });

  it('defaults to the newest proposed version, and says when there is none', async () => {
    const path = await file('v3.json', XA_V2);
    await run(['tax', 'rules', 'version', 'XA 2031', path]); // v3: validated, not proposed
    const { prompter, options } = atTerminal(['2']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031'], options);
    expect(result.code).toBe(0);
    expect(prompter.asked[0]).toContain('Type 2');

    const none = await run(['tax', 'rules', 'activate', 'XA 2031'], atTerminal([]).options);
    expect(none.code).toBe(4);
    expect(none.stderr).toContain('XA 2031 has no proposed version to review.');
  });

  it('refuses a version that fails validation without asking', async () => {
    const path = await file('wrong.json', { ...XA_V2, examples: [{ name: 'wrong', inputs: {}, expected: { payable: '1' } }] });
    await run(['tax', 'rules', 'version', 'XA 2031', path]);
    const { prompter, options } = atTerminal(['3']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031', '--version', '3'], options);
    expect(result.code).toBe(1);
    expect(result.stdout).toContain('✗ wrong');
    expect(result.stderr).toContain("Version 3 can't be activated: it doesn't pass validation.");
    expect(prompter.asked).toEqual([]);
  });

  it('explains a 403 from a personal access token made without tax:activate', async () => {
    const { options } = atTerminal(['2']);
    const result = await run(['tax', 'rules', 'activate', 'XA 2031'], { ...options, env: { SALLI_TOKEN: 'pat-valid' } });
    expect(result.code).toBe(5);
    expect(activations()).toHaveLength(1);
    expect(result.stderr).toContain("Not activated. This personal access token was made without tax:activate, so it doesn't hold tax:activate.");
    expect(result.stderr).toContain('`salli tokens create <name> --allow tax:activate`');
    expect(result.stderr).toContain('`salli login`');
    expect(status(V2)).toBe('proposed');
  });

  it('explains a 403 from a sign-in salli registered for itself', async () => {
    await mock.close();
    mock = await MockSalli.start({ cliClient: false });
    expect((await runCli(['login', '--server', mock.url], { configDir: dir })).code).toBe(0);
    const { options } = atTerminal(['2']);
    const result = await runCli(['tax', 'rules', 'activate', 'XA 2031'], { configDir: dir, ...options });
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('This sign-in is a client salli registered for itself');
    expect(result.stderr).toContain('Activate in the Salli app, or sign in yourself with `salli login`');
  });

  it('works with the ids the lists show', async () => {
    const { options } = atTerminal(['2']);
    const result = await run(['tax', 'rules', 'activate', SET.slice(0, 8), '--version', V2.slice(0, 8)], options);
    expect(result.code).toBe(0);
    expect(status(V2)).toBe('active');
    const again = await run(['tax', 'rules', 'activate', SET.slice(0, 8), '--version', '2'], atTerminal([]).options);
    expect(again.code).toBe(0);
    expect(again.stderr).toContain('is already active');
  });
});
