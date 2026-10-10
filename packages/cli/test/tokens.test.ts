import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli } from './helpers/mock-server';
import { runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
/** An access token for the CLI's own client: the user's own sign-in. */
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
  runCli(args, {
    configDir: dir,
    ...options,
    env: { SALLI_SERVER: mock.url, SALLI_TOKEN: signedIn, ...options.env },
  });

describe('salli tokens', () => {
  it('creates a token, printed once and alone on stdout, that works at once', async () => {
    const result = await run(['tokens', 'create', 'ci', '--expires-in-days', '90']);
    expect(result.code).toBe(0);
    const token = result.stdout.trim();
    expect(token).toMatch(/^salli_pat_[A-Za-z0-9_-]+$/);
    expect(result.stderr).toContain('Created the token “ci”');
    expect(result.stderr).toContain('only time it is shown');
    expect(result.stderr).not.toContain('allowed');
    // No permissions unless asked for.
    expect(mock.requestsTo('POST', '/v1/tokens')[0]?.json).toEqual({ name: 'ci', expires_in_days: 90 });
    const login = await runCli(['login', '--token', token, '--server', mock.url], { configDir: dir });
    expect(login.code).toBe(0);
  });

  it('gives a token tax:activate with --allow, and warns what it means', async () => {
    const result = await run(['tokens', 'create', 'my laptop', '--allow', 'tax:activate', '--allow', 'tax:activate']);
    expect(result.code).toBe(0);
    expect(mock.requestsTo('POST', '/v1/tokens')[0]?.json).toEqual({ name: 'my laptop', permissions: ['tax:activate'] });
    expect(result.stderr).toContain('Created the token “my laptop”, allowed tax:activate');
    expect(result.stderr).toContain('never give it to an AI agent');

    const json = await run(['tokens', 'create', 'other', '--allow', 'tax:activate', '--json']);
    expect(JSON.parse(json.stdout)).toMatchObject({ name: 'other', permissions: ['tax:activate'] });
  });

  it('refuses a permission that does not exist, before asking the server', async () => {
    const result = await run(['tokens', 'create', 'x', '--allow', 'admin']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('--allow takes a permission: tax:activate (got "admin")');
    expect(mock.requestsTo('POST', '/v1/tokens')).toHaveLength(0);
  });

  it('cannot make a token while signed in with one', async () => {
    const result = await run(['tokens', 'create', 'more', '--allow', 'tax:activate'], { env: { SALLI_TOKEN: 'pat-valid' } });
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('A personal access token cannot create another');
  });

  it('lists tokens with what each may do, never the tokens themselves', async () => {
    await run(['tokens', 'create', 'laptop', '--allow', 'tax:activate']);
    const result = await run(['tokens', 'list']);
    const [header, backup, laptop] = result.stdout.split('\n');
    expect(header).toMatch(/^ID +NAME +TOKEN +MAY ALSO +CREATED +EXPIRES +LAST USED$/);
    expect(backup).toMatch(/^000002bd +backup job +salli_pat_bk7Q… +— +Sep 1, 2026 +never +Oct 8, 2026$/);
    expect(laptop).toMatch(/^[0-9a-f]{8} +laptop +salli_pat_\S{4}… +tax:activate +Oct 9, 2026 +never +never$/);
    expect(result.stdout).not.toMatch(/salli_pat_\S{20,}/);
    const json = JSON.parse((await run(['tokens', 'list', '--json'])).stdout) as Array<{ permissions: string[] }>;
    expect(json.map((t) => t.permissions)).toEqual([[], ['tax:activate']]);
  });

  it('revokes a token, and says so when it is the one this context uses', async () => {
    const created = await run(['tokens', 'create', 'laptop']);
    const token = created.stdout.trim();
    await runCli(['login', '--token', token, '--server', mock.url], { configDir: dir });
    const id = mock.data.tokens.find((t) => t.name === 'laptop')?.id ?? '';
    const result = await runCli(['tokens', 'revoke', id.slice(0, 8), '--yes'], { configDir: dir });
    expect(result.code).toBe(0);
    expect(result.stderr).toContain('Revoked the token “laptop”.');
    expect(result.stderr).toContain('This context signed in with that token');
    expect((await runCli(['whoami'], { configDir: dir })).code).toBe(3);
  });
});
