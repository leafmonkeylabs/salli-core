import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { configDirectory } from '../src/config/config';
import { runCli, tempConfigDir } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await cleanup();
});

const run = (args: string[], env: Record<string, string> = {}) => runCli(args, { configDir: dir, env });

describe('configDirectory', () => {
  it('follows XDG on Linux and macOS, APPDATA on Windows, and SALLI_CONFIG_DIR everywhere', () => {
    expect(configDirectory({}, 'linux', '/home/ada')).toBe('/home/ada/.config/salli');
    expect(configDirectory({}, 'darwin', '/Users/ada')).toBe('/Users/ada/.config/salli');
    expect(configDirectory({ XDG_CONFIG_HOME: '/xdg' }, 'linux', '/home/ada')).toBe('/xdg/salli');
    expect(configDirectory({ APPDATA: 'C:\\Users\\ada\\AppData\\Roaming' }, 'win32', 'C:\\Users\\ada')).toMatch(/Roaming[\\/]salli$/);
    expect(configDirectory({ SALLI_CONFIG_DIR: '/tmp/x' }, 'linux', '/home/ada')).toBe('/tmp/x');
  });
});

describe('salli context', () => {
  it('starts with no contexts, pointing at localhost', async () => {
    const list = await run(['context', 'list']);
    expect(list.code).toBe(0);
    expect(list.stdout).toBe('');
    expect(list.stderr).toContain('No contexts yet');

    const current = await run(['context', 'current', '--json']);
    expect(JSON.parse(current.stdout)).toEqual({
      name: 'default',
      server: 'http://localhost:8000',
      saved: false,
      server_from: 'default',
    });
  });

  it('adds, lists, switches and removes contexts', async () => {
    expect((await run(['context', 'add', 'home', 'http://localhost:8000/'])).code).toBe(0);
    const added = await run(['context', 'add', 'work', 'https://salli.example.com', '--json']);
    expect(JSON.parse(added.stdout)).toEqual({ name: 'work', server: 'https://salli.example.com', current: false });

    const table = await run(['context', 'list']);
    expect(table.stdout).toMatchInlineSnapshot(`
      "   NAME  SERVER                     SIGNED IN
      *  home  http://localhost:8000      no
         work  https://salli.example.com  no
      "
    `);

    expect((await run(['context', 'use', 'work'])).code).toBe(0);
    expect(JSON.parse((await run(['context', 'current', '--json'])).stdout)).toMatchObject({ name: 'work', server: 'https://salli.example.com' });

    // --context picks one for a single command.
    expect(JSON.parse((await run(['--context', 'home', 'context', 'current', '--json'])).stdout).name).toBe('home');

    const removed = await run(['context', 'remove', 'work']);
    expect(removed.code).toBe(0);
    const after = JSON.parse((await run(['context', 'list', '--json'])).stdout) as Array<{ name: string; current: boolean }>;
    expect(after).toEqual([{ name: 'home', server: 'http://localhost:8000', current: true, signed_in: false }]);
  });

  it('keeps the file private and well-formed', async () => {
    await run(['context', 'add', 'home', 'http://localhost:8000']);
    const path = join(dir, 'config.json');
    expect((await stat(path)).mode & 0o777).toBe(0o600);
    expect(JSON.parse(await readFile(path, 'utf8'))).toEqual({
      version: 1,
      current_context: 'home',
      contexts: [{ name: 'home', server: 'http://localhost:8000' }],
      settings: {},
    });
  });

  it('lets SALLI_SERVER and --server override the context server', async () => {
    await run(['context', 'add', 'home', 'http://localhost:8000']);
    expect(JSON.parse((await run(['context', 'current', '--json'], { SALLI_SERVER: 'http://env.test:9000' })).stdout)).toMatchObject({
      server: 'http://env.test:9000',
      server_from: 'env',
    });
    expect(JSON.parse((await run(['--server', 'http://flag.test', 'context', 'current', '--json'])).stdout)).toMatchObject({
      server: 'http://flag.test',
      server_from: 'flag',
    });
  });

  it('refuses bad names, duplicates, unknown contexts and bad URLs', async () => {
    expect((await run(['context', 'add', 'bad name', 'http://x.test'])).code).toBe(2);
    expect((await run(['context', 'add', 'home', 'localhost:8000'])).code).toBe(2);
    await run(['context', 'add', 'home', 'http://localhost:8000']);
    expect((await run(['context', 'add', 'home', 'http://localhost:9000'])).code).toBe(2);
    const missing = await run(['context', 'use', 'nowhere']);
    expect(missing.code).toBe(4);
    expect(missing.stderr).toContain('No context named "nowhere"');
    expect((await run(['--context', 'nowhere', 'context', 'current'])).code).toBe(2);
  });
});

describe('salli config', () => {
  it('sets, reads and unsets settings', async () => {
    expect((await run(['config', 'set', 'output', 'json'])).code).toBe(0);
    expect((await run(['config', 'set', 'locale', 'en-gb'])).code).toBe(0);
    // output=json is now the default format, so get prints JSON.
    expect(JSON.parse((await run(['config', 'get', 'locale'])).stdout)).toEqual({ locale: 'en-GB' });
    expect(JSON.parse((await run(['config', 'list'])).stdout)).toEqual({ output: 'json', locale: 'en-GB' });
    await run(['config', 'unset', 'output']);
    expect((await run(['config', 'get', 'output'])).stdout).toBe('(default)\n');
  });

  it('validates keys and values', async () => {
    const badKey = await run(['config', 'set', 'colour', 'never']);
    expect(badKey.code).toBe(2);
    expect(badKey.stderr).toContain('Unknown setting "colour"');
    const badValue = await run(['config', 'set', 'output', 'xml']);
    expect(badValue.code).toBe(2);
    expect(badValue.stderr).toContain('output must be one of: table, json, ndjson, csv');
    expect((await run(['config', 'set', 'locale', 'not a locale!'])).code).toBe(2);
  });

  it('prints settings as a table for people', async () => {
    await run(['config', 'set', 'color', 'never']);
    const listed = await run(['config', 'list']);
    expect(listed.stdout).toMatchInlineSnapshot(`
      "SETTING  VALUE      DESCRIPTION
      output   (default)  Default output format
      color    never      Colour output (auto: only in a terminal)
      locale   (default)  Locale for amounts and dates (BCP 47, e.g. en-GB); default: the system locale
      "
    `);
  });
});
