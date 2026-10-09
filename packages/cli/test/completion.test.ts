import { spawnSync } from 'node:child_process';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { runCli, tempConfigDir } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await cleanup();
});

const has = (shell: string): boolean => spawnSync(shell, ['-c', 'true']).status === 0;

/** What bash would offer after `words` (the last one being completed). */
function bashCompletions(script: string, words: string[]): string[] {
  const result = spawnSync(
    'bash',
    ['-c', `source "$1"; COMP_WORDS=(${words.map((w) => `'${w}'`).join(' ')}); COMP_CWORD=${words.length - 1}; _salli; printf '%s\\n' "\${COMPREPLY[@]}"`, 'bash', script],
    { encoding: 'utf8' },
  );
  return result.stdout.split('\n').filter(Boolean);
}

describe('salli completion', () => {
  it('prints a bash script that completes commands, subcommands and flags', async () => {
    const result = await runCli(['completion', 'bash'], { configDir: dir });
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('complete -F _salli salli');
    if (!has('bash')) return;
    const script = join(dir, 'salli.bash');
    await writeFile(script, result.stdout);
    expect(spawnSync('bash', ['-n', script]).status).toBe(0);
    expect(bashCompletions(script, ['salli', 'acc'])).toEqual(['accounts', 'account']);
    expect(bashCompletions(script, ['salli', 'insurance', 'policies', ''])).toEqual(
      expect.arrayContaining(['list', 'show', 'add', 'update', 'delete', '--json']),
    );
    expect(bashCompletions(script, ['salli', '--context', 'home', 'entries', 'list', '--mo'])).toEqual(['--month']);
    expect(bashCompletions(script, ['salli', 'accounts', 'list', '-o', ''])).toEqual(['table', 'json', 'ndjson', 'csv']);
  });

  it('prints zsh and fish scripts', async () => {
    const zsh = await runCli(['completion', 'zsh'], { configDir: dir });
    expect(zsh.stdout.startsWith('#compdef salli')).toBe(true);
    if (has('zsh')) {
      const script = join(dir, '_salli');
      await writeFile(script, zsh.stdout);
      expect(spawnSync('zsh', ['-n', script]).status).toBe(0);
    }
    const fish = await runCli(['completion', 'fish'], { configDir: dir });
    expect(fish.stdout).toContain("complete -c salli -n \"contains -- (__salli_path) ''\" -a 'accounts'");
  });

  it('refuses a shell it does not know', async () => {
    const result = await runCli(['completion', 'tcsh'], { configDir: dir });
    expect(result.code).toBe(2);
  });
});
