import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli, type MockOptions } from './helpers/mock-server';
import { runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

async function start(options: MockOptions = {}): Promise<void> {
  mock = await MockSalli.start(options);
}

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, { configDir: dir, ...options, env: { SALLI_SERVER: mock.url, ...options.env } });

describe('salli ui', () => {
  it("opens the console /v1/meta names, prints it, and hands the browser nothing", async () => {
    await start();
    const result = await run(['ui'], { openUrl: async () => true });
    expect(result.code, result.stderr).toBe(0);
    expect(result.opened).toEqual([`${mock.url}/console`]);
    expect(result.stdout.trim()).toBe(`Opening ${mock.url}/console`);
    // No token, no code, no query of any kind.
    expect(result.opened[0]).not.toMatch(/[?#]/);
  });

  it('only prints the address with --no-open, needing no sign-in', async () => {
    await start();
    const result = await run(['ui', '--no-open']);
    expect(result.code, result.stderr).toBe(0);
    expect(result.opened).toEqual([]);
    expect(result.stdout.trim()).toBe(`${mock.url}/console`);
    // Nothing but the public /v1/meta was asked.
    expect(mock.requests.map((r) => `${r.method} ${r.path}`)).toEqual(['GET /v1/meta']);
  });

  it('prints the address when no browser opens', async () => {
    await start();
    const result = await run(['ui'], { openUrl: async () => false });
    expect(result.code).toBe(0);
    expect(result.stdout.trim()).toBe(`${mock.url}/console`);
    expect(result.stderr).toContain('No browser could be opened');
  });

  it('says so when the server serves no console', async () => {
    await start({ consoleUrl: null });
    const result = await run(['ui', '--no-open']);
    expect(result.code).not.toBe(0);
    expect(result.stderr).toContain('serves no console');
    expect(result.stderr).toContain('SALLI_CONSOLE');
  });

  it('answers in JSON with --json', async () => {
    await start();
    const result = await run(['ui', '--no-open', '--json']);
    expect(result.code, result.stderr).toBe(0);
    expect(JSON.parse(result.stdout)).toEqual({ console_url: `${mock.url}/console`, opened: false });
  });
});
