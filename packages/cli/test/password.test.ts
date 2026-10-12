import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli } from './helpers/mock-server';
import { runCli, ScriptedPrompter, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
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

const SIGN_INS = [
  {
    id: '9b2e4c1a-0d6f-4f3e-8a71-2c5d0e9f1b3a',
    kind: 'console',
    client_name: 'Salli console',
    user_agent: null,
    started_at: '2026-10-09T10:00:00Z',
    last_used_at: '2026-10-09T10:30:00Z',
    expires_at: '2026-10-09T22:00:00Z',
    current: false,
  },
  {
    id: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
    kind: 'session',
    client_name: null,
    user_agent: 'Salli for iOS',
    started_at: '2026-10-08T09:00:00Z',
    last_used_at: '2026-10-09T08:00:00Z',
    expires_at: '2026-11-07T09:00:00Z',
    current: false,
  },
  {
    id: '16fd2706-8baf-433b-82eb-8c7fada847da',
    kind: 'cli',
    client_name: 'Salli CLI',
    user_agent: null,
    started_at: '2026-10-01T09:00:00Z',
    last_used_at: null,
    expires_at: null,
    current: true,
  },
];

describe('salli password', () => {
  it('asks for the current password and the new one twice, and says what it ended', async () => {
    mock.on('POST', '/v1/auth/password', () => ({ status: 200, body: { sessions_ended: 2 } }));
    const prompter = new ScriptedPrompter(['old password here', 'a new long password', 'a new long password']);
    const result = await run(['password'], { prompter });
    expect(result.code, result.stderr).toBe(0);
    expect(prompter.asked).toEqual(['Current password', 'New password (at least 12 characters)', 'New password again']);
    expect(mock.requestsTo('POST', '/v1/auth/password')[0]?.json).toEqual({
      current_password: 'old password here',
      new_password: 'a new long password',
    });
    expect(result.stderr).toContain('Password changed. 2 other sessions signed out.');
    // Never echoed.
    expect(result.stdout + result.stderr).not.toContain('a new long password');
  });

  it('refuses new passwords that do not match, before asking the server', async () => {
    const prompter = new ScriptedPrompter(['old password here', 'a new long password', 'a typo password']);
    const result = await run(['password'], { prompter });
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('did not match');
    expect(mock.requestsTo('POST', '/v1/auth/password')).toHaveLength(0);
  });

  it('reads both passwords from stdin exactly as given', async () => {
    mock.on('POST', '/v1/auth/password', () => ({ status: 200, body: { sessions_ended: 0 } }));
    const result = await run(['password', '--password-stdin', '--json'], { stdin: ' old with a space\nnew password, long\n' });
    expect(result.code, result.stderr).toBe(0);
    expect(mock.requestsTo('POST', '/v1/auth/password')[0]?.json).toEqual({
      current_password: ' old with a space',
      new_password: 'new password, long',
    });
    expect(JSON.parse(result.stdout)).toEqual({ sessions_ended: 0 });
  });

  it('says so when the current password is wrong, without telling you to sign in again', async () => {
    mock.on('POST', '/v1/auth/password', () => ({
      status: 403,
      body: { type: 'about:blank', title: 'Forbidden', status: 403, detail: 'The current password is wrong.' },
    }));
    const result = await run(['password', '--password-stdin'], { stdin: 'wrong\nnew password, long\n' });
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('The current password is wrong.');
    expect(result.stderr).not.toContain('salli login');
  });

  it('will not ask without a terminal', async () => {
    const result = await run(['password'], { prompter: new ScriptedPrompter([], false) });
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('--password-stdin');
  });
});

describe('salli sign-ins', () => {
  it('lists every way in, never a token', async () => {
    mock.on('GET', '/v1/auth/sign-ins', () => ({ status: 200, body: SIGN_INS }));
    const result = await run(['sign-ins', 'list']);
    expect(result.code, result.stderr).toBe(0);
    const [header, consoleRow, session, cli] = result.stdout.split('\n');
    expect(header).toMatch(/^ID +KIND +CLIENT +STARTED +LAST USED +ENDS$/);
    expect(consoleRow).toMatch(/^9b2e4c1a +console +Salli console +Oct 9, 2026 +Oct 9, 2026 +Oct 9, 2026$/);
    expect(session).toMatch(/^7c9e6679 +session +Salli for iOS +Oct 8, 2026 +Oct 9, 2026 +Nov 7, 2026$/);
    expect(cli).toMatch(/^16fd2706 +CLI +Salli CLI \(this one\) +Oct 1, 2026 +never +—$/);
  });

  it('passes the sign-ins through with --json', async () => {
    mock.on('GET', '/v1/auth/sign-ins', () => ({ status: 200, body: SIGN_INS }));
    const result = await run(['sign-ins', 'list', '--json']);
    expect(result.code, result.stderr).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual(SIGN_INS);
  });

  it('ends a sign-in by the start of its id', async () => {
    mock.on('GET', '/v1/auth/sign-ins', () => ({ status: 200, body: SIGN_INS }));
    mock.on('DELETE', '/v1/auth/sign-ins/{id}', () => ({ status: 204 }));
    const result = await run(['sign-ins', 'revoke', '9b2e', '--yes']);
    expect(result.code, result.stderr).toBe(0);
    expect(mock.requestsTo('DELETE', `/v1/auth/sign-ins/${SIGN_INS[0]?.id}`)).toHaveLength(1);
    expect(result.stderr).toContain('Signed out the console sign-in (Salli console).');
  });

  it('says when it is ending this one', async () => {
    mock.on('GET', '/v1/auth/sign-ins', () => ({ status: 200, body: SIGN_INS }));
    mock.on('DELETE', '/v1/auth/sign-ins/{id}', () => ({ status: 204 }));
    const result = await run(['sign-ins', 'revoke', '16fd', '--yes']);
    expect(result.code, result.stderr).toBe(0);
    expect(result.stderr).toContain('Signed out this sign-in.');
  });
});
