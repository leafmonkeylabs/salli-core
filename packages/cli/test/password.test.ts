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

const SESSIONS = [
  {
    id: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
    user_agent: 'Salli for iOS',
    created_at: '2026-10-08T09:00:00Z',
    last_used_at: '2026-10-09T08:00:00Z',
    expires_at: '2026-11-07T09:00:00Z',
    current: false,
  },
  {
    id: '16fd2706-8baf-433b-82eb-8c7fada847da',
    user_agent: null,
    created_at: '2026-10-01T09:00:00Z',
    last_used_at: null,
    expires_at: '2026-10-31T09:00:00Z',
    current: false,
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
  it('lists sessions, never their tokens', async () => {
    mock.on('GET', '/v1/auth/sessions', () => ({ status: 200, body: SESSIONS }));
    const result = await run(['sign-ins', 'list']);
    expect(result.code, result.stderr).toBe(0);
    const [header, ios, other] = result.stdout.split('\n');
    expect(header).toMatch(/^ID +CLIENT +STARTED +LAST USED +EXPIRES$/);
    expect(ios).toMatch(/^7c9e6679 +Salli for iOS +Oct 8, 2026 +Oct 9, 2026 +Nov 7, 2026$/);
    expect(other).toMatch(/^16fd2706 +— +Oct 1, 2026 +never +Oct 31, 2026$/);
  });

  it('revokes a session by the start of its id', async () => {
    mock.on('GET', '/v1/auth/sessions', () => ({ status: 200, body: SESSIONS }));
    mock.on('DELETE', '/v1/auth/sessions/{id}', () => ({ status: 204 }));
    const result = await run(['sign-ins', 'revoke', '7c9e', '--yes']);
    expect(result.code, result.stderr).toBe(0);
    expect(mock.requestsTo('DELETE', `/v1/auth/sessions/${SESSIONS[0]?.id}`)).toHaveLength(1);
    expect(result.stderr).toContain('Signed out the session from Salli for iOS.');
  });
});
