/**
 * salli skills: the agent skills that teach an AI agent (Claude Code, or any
 * agent that reads SKILL.md folders) to drive this CLI, so "add this month's
 * statement" works from the user's own agent.
 *
 * The skills travel inside the CLI (src/skills/bundled.ts), so a standalone
 * binary installs them as well as the npm package does.
 */
import { mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, normalize, resolve } from 'node:path';
import type { Command } from '@commander-js/extra-typings';
import type { App } from '../app';
import { UsageError } from '../errors';
import { singleLine } from '../output/text';
import { BUNDLED_SKILLS, type BundledSkill } from '../skills/bundled';

type InstallStatus = 'installed' | 'updated' | 'up-to-date' | 'kept';
type RemoveStatus = 'removed' | 'not-installed';

interface TargetOptions {
  project?: boolean;
  dir?: string;
}

/** Where the skills go: --dir, ./.claude/skills with --project, else ~/.claude/skills. */
function targetDirectory(app: App, options: TargetOptions): string {
  if (options.project && options.dir) throw new UsageError('Pass either --project or --dir, not both.');
  if (options.dir) return resolve(app.runtime.cwd, options.dir);
  return join(options.project ? app.runtime.cwd : app.runtime.homedir, '.claude', 'skills');
}

/** The skills named, or all of them; an unknown name is a usage error. */
function selected(names: string[]): BundledSkill[] {
  if (!names.length) return [...BUNDLED_SKILLS];
  const known = new Map(BUNDLED_SKILLS.map((s) => [s.name, s]));
  const unknown = names.filter((n) => !known.has(n));
  if (unknown.length) {
    throw new UsageError(
      `No skill named ${unknown.map((n) => `“${singleLine(n)}”`).join(', ')}.`,
      `The skills are: ${BUNDLED_SKILLS.map((s) => s.name).join(', ')}.`,
    );
  }
  return [...new Set(names)].map((n) => known.get(n) as BundledSkill);
}

/** A file's path inside the skill's folder, refusing anything that leaves it. */
function within(folder: string, relative: string): string {
  const path = normalize(relative);
  if (isAbsolute(path) || path === '..' || path.startsWith(`..${'/'}`) || path.startsWith('..\\')) {
    throw new Error(`A bundled skill file would land outside its folder: ${relative}`);
  }
  return join(folder, path);
}

async function exists(path: string): Promise<boolean> {
  return stat(path).then(
    () => true,
    () => false,
  );
}

/** Whether every file of the skill is already there, byte for byte. */
async function identical(folder: string, skill: BundledSkill): Promise<boolean> {
  for (const [relative, text] of Object.entries(skill.files)) {
    const current = await readFile(within(folder, relative), 'utf8').catch(() => undefined);
    if (current !== text) return false;
  }
  return true;
}

async function install(folder: string, skill: BundledSkill, force: boolean): Promise<InstallStatus> {
  const present = await exists(folder);
  if (present && (await identical(folder, skill))) return 'up-to-date';
  // A copy the user may have edited is theirs until they say otherwise.
  if (present && !force) return 'kept';
  for (const [relative, text] of Object.entries(skill.files)) {
    const path = within(folder, relative);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, text);
  }
  return present ? 'updated' : 'installed';
}

export function registerSkills(program: Command, app: App): void {
  const skills = program
    .command('skills')
    .description('Agent skills that teach your AI agent to drive salli (Claude Code and others)');

  skills
    .command('list')
    .description('List the skills that come with salli')
    .action(() => {
      const list = BUNDLED_SKILLS.map(({ name, description }) => ({ name, description }));
      app.out.emit(list, {
        human: (d) => {
          app.out.line(
            app.out.table(d, [
              { header: 'SKILL', get: (s) => s.name },
              { header: 'WHAT IT DOES', get: (s) => s.description, shrink: true },
            ]),
          );
          app.out.note('Install them with `salli skills install` (add --project for this project only).');
        },
      });
    });

  skills
    .command('install')
    .description('Install the skills where your agent finds them (~/.claude/skills by default)')
    .argument('[skills...]', 'Which skills (default: all of them)')
    .option('--project', 'Install into ./.claude/skills, for this project only')
    .option('--dir <path>', 'Install into this directory instead (for another agent)')
    .option('--force', 'Overwrite skills that are installed but differ (your edits are lost)')
    .action(async (names: string[], options: TargetOptions & { force?: boolean }) => {
      const target = targetDirectory(app, options);
      const results: Array<{ name: string; status: InstallStatus }> = [];
      for (const skill of selected(names)) {
        results.push({ name: skill.name, status: await install(join(target, skill.name), skill, !!options.force) });
      }
      app.out.emit(
        { target, skills: results },
        {
          records: (d) => d.skills,
          human: (d) => {
            const by = (status: InstallStatus): string[] => d.skills.filter((s) => s.status === status).map((s) => s.name);
            const written = [...by('installed'), ...by('updated')];
            if (written.length) app.out.success(`Installed into ${d.target}: ${written.join(', ')}`);
            if (by('up-to-date').length) app.out.note(`Already up to date: ${by('up-to-date').join(', ')}`);
            if (by('kept').length) {
              app.out.warn(
                `Kept your copies of ${by('kept').join(', ')}: they differ from this version of salli. ` +
                  'Pass --force to replace them.',
              );
            }
          },
        },
      );
    });

  skills
    .command('uninstall')
    .description('Remove installed salli skills (only those that come with salli)')
    .argument('[skills...]', 'Which skills (default: all of them)')
    .option('--project', 'From ./.claude/skills')
    .option('--dir <path>', 'From this directory instead')
    .action(async (names: string[], options: TargetOptions) => {
      const target = targetDirectory(app, options);
      const results: Array<{ name: string; status: RemoveStatus }> = [];
      for (const skill of selected(names)) {
        const folder = join(target, skill.name);
        if (await exists(folder)) {
          await rm(folder, { recursive: true, force: true });
          results.push({ name: skill.name, status: 'removed' });
        } else {
          results.push({ name: skill.name, status: 'not-installed' });
        }
      }
      app.out.emit(
        { target, skills: results },
        {
          records: (d) => d.skills,
          human: (d) => {
            const removed = d.skills.filter((s) => s.status === 'removed').map((s) => s.name);
            if (removed.length) app.out.success(`Removed from ${d.target}: ${removed.join(', ')}`);
            else app.out.note(`None of them were installed in ${d.target}.`);
          },
        },
      );
    });
}
