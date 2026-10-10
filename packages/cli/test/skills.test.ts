import { spawnSync } from 'node:child_process';
import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { BUNDLED_SKILLS } from '../src/skills/bundled';
import { runCli, tempConfigDir } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
});
afterEach(async () => {
  await cleanup();
});

// The test runtime's home directory is the temporary one.
const userSkills = (): string => join(dir, '.claude', 'skills');
const names = BUNDLED_SKILLS.map((s) => s.name);
const isDir = (path: string): Promise<boolean> =>
  stat(path).then(
    (s) => s.isDirectory(),
    () => false,
  );

describe('salli skills', () => {
  it('carries the skills in packages/cli/skills, as they are now', () => {
    const script = fileURLToPath(new URL('../scripts/bundle-skills.mjs', import.meta.url));
    const check = spawnSync(process.execPath, [script, '--check'], { encoding: 'utf8' });
    expect(check.stderr).toBe('');
    expect(check.status).toBe(0);
    expect(names).toEqual(expect.arrayContaining(['salli-cli', 'salli-import-statement', 'salli-tax']));
  });

  it('lists each skill with what it does', async () => {
    const result = await runCli(['skills', 'list', '--json'], { configDir: dir });
    expect(result.code).toBe(0);
    const listed = JSON.parse(result.stdout) as Array<{ name: string; description: string }>;
    expect(listed.map((s) => s.name)).toEqual(names);
    for (const skill of listed) expect(skill.description.length).toBeGreaterThan(20);
  });

  it('installs every skill where Claude Code finds them, and again is a no-op', async () => {
    const first = await runCli(['skills', 'install', '--json'], { configDir: dir });
    expect(first.code).toBe(0);
    const report = JSON.parse(first.stdout) as { target: string; skills: Array<{ name: string; status: string }> };
    expect(report.target).toBe(userSkills());
    expect(report.skills).toEqual(names.map((name) => ({ name, status: 'installed' })));
    for (const skill of BUNDLED_SKILLS) {
      for (const [file, text] of Object.entries(skill.files)) {
        expect(await readFile(join(userSkills(), skill.name, file), 'utf8')).toBe(text);
      }
    }

    const again = await runCli(['skills', 'install', '--json'], { configDir: dir });
    const statuses = (JSON.parse(again.stdout) as { skills: Array<{ status: string }> }).skills.map((s) => s.status);
    expect(new Set(statuses)).toEqual(new Set(['up-to-date']));
  });

  it('keeps a copy the user changed unless told to replace it', async () => {
    await runCli(['skills', 'install', 'salli-tax'], { configDir: dir });
    const skillMd = join(userSkills(), 'salli-tax', 'SKILL.md');
    await writeFile(skillMd, 'my own notes');

    const kept = await runCli(['skills', 'install', 'salli-tax'], { configDir: dir });
    expect(kept.code).toBe(0);
    expect(kept.stderr).toContain('Kept your copies of salli-tax');
    expect(await readFile(skillMd, 'utf8')).toBe('my own notes');

    const forced = await runCli(['skills', 'install', 'salli-tax', '--force', '--json'], { configDir: dir });
    expect(JSON.parse(forced.stdout).skills).toEqual([{ name: 'salli-tax', status: 'updated' }]);
    expect(await readFile(skillMd, 'utf8')).toBe(BUNDLED_SKILLS.find((s) => s.name === 'salli-tax')?.files['SKILL.md']);
  });

  it('installs for one project, or into any directory another agent reads', async () => {
    const project = join(dir, 'my-project');
    await mkdir(project);
    const local = await runCli(['skills', 'install', 'salli-cli', '--project'], { configDir: dir, cwd: project });
    expect(local.code).toBe(0);
    expect(await isDir(join(project, '.claude', 'skills', 'salli-cli'))).toBe(true);
    expect(await isDir(userSkills())).toBe(false);

    const other = await runCli(['skills', 'install', 'salli-cli', '--dir', 'agent-skills'], { configDir: dir, cwd: project });
    expect(other.code).toBe(0);
    expect(await isDir(join(project, 'agent-skills', 'salli-cli'))).toBe(true);
  });

  it('refuses an unknown skill, and --project with --dir', async () => {
    const unknown = await runCli(['skills', 'install', 'salli-nope'], { configDir: dir });
    expect(unknown.code).toBe(2);
    expect(unknown.stderr).toContain('No skill named “salli-nope”');
    expect(unknown.stderr).toContain('salli-cli');
    expect(await isDir(userSkills())).toBe(false);

    const both = await runCli(['skills', 'install', '--project', '--dir', 'x'], { configDir: dir });
    expect(both.code).toBe(2);
  });

  it('uninstalls only the skills that come with salli', async () => {
    await runCli(['skills', 'install'], { configDir: dir });
    const theirs = join(userSkills(), 'someone-elses-skill');
    await mkdir(theirs);

    const result = await runCli(['skills', 'uninstall', 'salli-tax', '--json'], { configDir: dir });
    expect(JSON.parse(result.stdout).skills).toEqual([{ name: 'salli-tax', status: 'removed' }]);
    const left = await readdir(userSkills());
    expect(left).not.toContain('salli-tax');
    expect(left).toContain('salli-cli');

    await runCli(['skills', 'uninstall'], { configDir: dir });
    expect(await readdir(userSkills())).toEqual(['someone-elses-skill']);
  });
});
