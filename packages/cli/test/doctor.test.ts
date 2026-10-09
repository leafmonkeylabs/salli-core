import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli } from './helpers/mock-server';
import { closedServerUrl, runCli, tempConfigDir } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli | undefined;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await mock?.close();
  mock = undefined;
  await cleanup();
});

type Checks = { ok: boolean; checks: Array<{ name: string; status: string; detail: string }> };
const statuses = (result: { stdout: string }) =>
  Object.fromEntries((JSON.parse(result.stdout) as Checks).checks.map((c) => [c.name, c.status]));

describe('salli doctor', () => {
  it('passes when the server answers, speaks v1, knows you, and the clocks agree', async () => {
    mock = await MockSalli.start();
    const env = { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid' };
    const result = await runCli(['doctor', '--json'], { configDir: dir, env, now: new Date() });
    expect(result.code).toBe(0);
    expect(JSON.parse(result.stdout).ok).toBe(true);
    expect(statuses(result)).toEqual({
      CLI: 'info',
      Context: 'info',
      Server: 'ok',
      'API version': 'ok',
      Clock: 'ok',
      'Signed in': 'ok',
      Credentials: 'warn', // tests keep credentials in a file
    });
    const human = await runCli(['doctor'], { configDir: dir, env, now: new Date() });
    expect(human.stdout).toMatch(/✓ Server +http:\/\/127\.0\.0\.1:\d+ answered in \d+ ms \(Salli 0\.1\.0\)/);
    expect(human.stdout).toContain('✓ Signed in    as user-123 (SALLI_TOKEN)');
  });

  it('notices a clock that has drifted', async () => {
    mock = await MockSalli.start();
    const result = await runCli(['doctor', '--json'], {
      configDir: dir,
      env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid' },
      now: new Date(Date.now() + 10 * 60 * 1000),
    });
    expect(statuses(result).Clock).toBe('fail');
    expect(JSON.parse(result.stdout).checks.find((c: { name: string }) => c.name === 'Clock').detail).toBe(
      'your clock is 10 minutes ahead of the server',
    );
    expect(result.code).toBe(1);
  });

  it('exits 7 when the server is down, 6 for another API version, 3 when signed out', async () => {
    const closed = await closedServerUrl();
    const down = await runCli(['doctor'], { configDir: dir, env: { SALLI_SERVER: closed }, now: new Date() });
    expect(down.code).toBe(7);
    expect(down.stdout).toContain(`✗ Server       Could not reach ${closed} (connection refused)`);

    mock = await MockSalli.start({ apiVersion: '2' });
    const v2 = await runCli(['doctor'], { configDir: dir, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid' }, now: new Date() });
    expect(v2.code).toBe(6);
    await mock.close();

    mock = await MockSalli.start();
    const signedOut = await runCli(['doctor'], { configDir: dir, env: { SALLI_SERVER: mock.url }, now: new Date() });
    expect(signedOut.code).toBe(3);
    expect(signedOut.stdout).toContain('✗ Signed in    no');
  });
});
