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
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid', ...options.env } });
const lastBody = (path: string) => mock.data.bodies.filter((b) => b.path === path).at(-1)?.body;

describe('salli banks', () => {
  it('lists connections with their accounts and where each is imported', async () => {
    expect((await run(['banks', 'list'])).stdout).toMatchInlineSnapshot(`
      "Acme Credit Union simplefin · 0000044d · synced Oct 8, 2026 active
      BANK ACCOUNT                 ID           BALANCE  IMPORTED INTO
      Acme CU · Everyday Checking  ACT-1  USD 12,784.50  1100 Checking
      Acme CU · Rewards Visa       ACT-2  -USD 1,200.00  not mapped
      "
    `);
    const csv = await run(['banks', 'list', '--output', 'csv']);
    expect(csv.stdout.split('\r\n')[0]).toContain('connection_id,remote_id,name');
  });

  it('connects with a setup token from a hidden prompt or stdin, never an echo', async () => {
    const prompter = new ScriptedPrompter(['setup-token-ok']);
    const result = await run(['banks', 'connect', '--name', 'My CU'], { prompter });
    expect(result.code).toBe(0);
    expect(prompter.asked).toEqual(['Setup token']);
    expect(lastBody('/v1/bank-connections')).toEqual({ provider: 'simplefin', setup_token: 'setup-token-ok', name: 'My CU' });
    expect(result.stdout + result.stderr).not.toContain('setup-token-ok');
    expect(result.stderr).toContain('Only 90 days of history are available.');

    const piped = await run(['banks', 'connect', '--setup-token', '-'], { stdin: 'nope\n' });
    expect(piped.code).toBe(5);
    expect(piped.stderr).toContain('That setup token was not accepted.');
  });

  it('maps a bank account to an account, or creates one, or unmaps it', async () => {
    expect((await run(['banks', 'map', uid(1101).slice(0, 8), 'ACT-2', '--account', 'credit card'])).stderr).toContain('Mapped.');
    expect(lastBody(`/v1/bank-connections/${uid(1101)}/accounts/ACT-2`)).toEqual({ account_id: uid(4) });
    await run(['banks', 'map', uid(1101).slice(0, 8), 'ACT-2', '--create']);
    expect(lastBody(`/v1/bank-connections/${uid(1101)}/accounts/ACT-2`)).toEqual({ create: true });
    expect((await run(['banks', 'map', uid(1101).slice(0, 8), 'ACT-2', '--unmap'])).stderr).toContain('Unmapped.');
    expect((await run(['banks', 'map', uid(1101).slice(0, 8), 'ACT-2', '--create', '--unmap'])).code).toBe(2);
  });

  it('syncs every connection, saying what waits in review, and fails when one cannot', async () => {
    const result = await run(['banks', 'sync']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Everyday Checking: 3 new to review, 1 seen before');
    expect(result.stderr).toContain('Rewards Visa: not mapped, skipped');
    mock.data.bankConnections[0]!.status = 'error';
    const failed = await run(['banks', 'sync', '--json']);
    expect(failed.code).toBe(1);
    expect(JSON.parse(failed.stdout)[0].error).toContain('The bank refused the credential.');
  });

  it('disconnects after asking', async () => {
    expect((await run(['banks', 'disconnect', uid(1101).slice(0, 8)])).code).toBe(2);
    expect((await run(['banks', 'disconnect', uid(1101).slice(0, 8), '--yes'])).code).toBe(0);
    expect(mock.data.bankConnections).toHaveLength(0);
  });
});
