/**
 * The console's guards (docs/design/console.md, sections 2, 4 and 8):
 *
 * - text is rendered only through React: no HTML from strings and no code
 *   from strings, refused by lint with no escape hatch;
 * - every word is in the catalogue (strings.ts), in the brand's voice, and
 *   nothing ranks (as tests/guardrails.py holds the API's results);
 * - no request leaves for another origin: the source names none, and
 *   carries no telemetry or service worker;
 * - the console ships at the server's version (decision 24).
 */
import { readdir, readFile } from 'node:fs/promises';
import { join, relative, resolve } from 'node:path';
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';
import { bookStrings } from '../src/books-strings';
import { labStrings } from '../src/lab-strings';
import { settingsStrings } from '../src/settings-strings';
import { strings } from '../src/strings';
import { taxStrings } from '../src/tax-strings';
import { whereStrings } from '../src/where-strings';

// The tests run in packages/console.
const root = resolve(process.cwd(), '../..');
const consoleDir = join(root, 'packages/console');
const consoleSrc = join(consoleDir, 'src');

async function sources(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await sources(path)));
    else if (/\.(ts|tsx|css)$/.test(entry.name)) out.push(path);
  }
  return out;
}

describe('rendering', () => {
  it('refuses HTML and code from strings', async () => {
    const eslint = new ESLint({ cwd: root });
    const filePath = join(consoleSrc, 'pages/example.tsx');
    const offences: Array<[string, string]> = [
      ['export const A = (html: string) => <div dangerouslySetInnerHTML={{ __html: html }} />;', 'salli/no-html-sinks'],
      ['export const b = (el: HTMLElement, html: string) => { el.innerHTML = html; };', 'salli/no-html-sinks'],
      ["export const c = (el: HTMLElement, html: string) => el.insertAdjacentHTML('beforeend', html);", 'salli/no-html-sinks'],
      ['export const d = (html: string) => document.write(html);', 'salli/no-html-sinks'],
      ['export const e = (code: string) => eval(code);', 'no-eval'],
      ["export const f = (code: string) => new Function('x', code);", 'no-new-func'],
      ["export const g = () => setTimeout('alert(1)', 1);", 'no-implied-eval'],
    ];
    for (const [code, rule] of offences) {
      const [result] = await eslint.lintText(code, { filePath });
      expect(result?.messages.map((m) => m.ruleId), code).toContain(rule);
    }
  });

  it('has no way to switch those rules off', async () => {
    const found: string[] = [];
    for (const file of await sources(consoleSrc)) {
      (await readFile(file, 'utf8')).split('\n').forEach((line, i) => {
        if (/eslint-disable/.test(line) && /no-html-sinks|no-eval|no-implied-eval|no-new-func|no-script-url|eslint-disable(-next-line|-line)?\s*(\*\/)?$/.test(line)) {
          found.push(`${relative(consoleSrc, file)}:${i + 1}`);
        }
      });
    }
    expect(found).toEqual([]);
  });
});

/** Every string in the catalogue, with the functions called on sample values. */
function catalogue(value: unknown, path = 'strings'): Array<[string, string]> {
  if (typeof value === 'string') return [[path, value]];
  if (typeof value === 'function') return [[path, String((value as (...args: string[]) => string)('X', 'Y', 'Z', 'W'))]];
  if (typeof value === 'object' && value !== null) return Object.entries(value).flatMap(([k, v]) => catalogue(v, `${path}.${k}`));
  return [];
}

/** (path, word) pairs that use a ranking word to forbid ranking. Each needs a reason. */
const ALLOWED = new Set([
  // The prompt for the person's own AI tells it not to rank, as MCP's guardrails do.
  'strings.home.prompt:rank',
]);

describe('the catalogue', () => {
  // The shell's words, and the decision lab's, where you stand's, and books', tax's and settings', which load with their pages.
  const all = [
    ...catalogue(strings),
    ...catalogue(labStrings, 'labStrings'),
    ...catalogue(whereStrings, 'whereStrings'),
    ...catalogue(bookStrings, 'bookStrings'),
    ...catalogue(taxStrings, 'taxStrings'),
    ...catalogue(settingsStrings, 'settingsStrings'),
  ];

  it('ranks nothing and urges nothing', () => {
    const ranking = /\b(best|worst|better|worse|top|ranked|rank|winner|optimal|ideal|recommended|recommend|should choose|smartest|cheapest option)\b/i;
    const hype = /\b(revolutionary|ai-powered|smart|seamless|effortless|unlock|supercharge|magic|game-changing|oops|hurry|don't miss|act now)\b/i;
    for (const [path, text] of all) {
      const word = ranking.exec(text)?.[1]?.toLowerCase();
      if (word && !ALLOWED.has(`${path}:${word}`)) expect(text, path).not.toMatch(ranking);
      expect(text, path).not.toMatch(hype);
      expect(text, path).not.toMatch(/!/);
      expect(text, path).not.toMatch(/\p{Extended_Pictographic}/u);
    }
  });

  it('is in British English', () => {
    const american = /\b(color|colors|organize|organization|license|behavior|favorite|center|analyze|canceled|catalog)\b/i;
    for (const [path, text] of all) expect(text, path).not.toMatch(american);
  });

  it('holds every word a page shows: pages name no sentence of their own', async () => {
    const strays: string[] = [];
    for (const file of await sources(join(consoleSrc, 'pages'))) {
      if (!file.endsWith('.tsx')) continue;
      const text = await readFile(file, 'utf8');
      // A capitalised run of words between JSX tags is copy that belongs in strings.ts.
      for (const match of text.matchAll(/>\s*([A-Z][a-z]+(?: [a-z]+){2,}[.]?)\s*</g)) strays.push(`${relative(consoleSrc, file)}: ${match[1]}`);
    }
    expect(strays).toEqual([]);
  });
});

describe('nothing from elsewhere', () => {
  it('names no other origin, and keeps no telemetry or service worker', async () => {
    const found: string[] = [];
    for (const file of await sources(consoleSrc)) {
      const text = await readFile(file, 'utf8');
      const rel = relative(consoleSrc, file);
      for (const match of text.matchAll(/https?:\/\/[^\s'"`)]+/g)) {
        // Comments may cite where something comes from; code may not call it.
        const line = text.slice(text.lastIndexOf('\n', match.index) + 1, text.indexOf('\n', match.index));
        if (!/^\s*(\*|\/\/|\/\*)/.test(line) && !/http:\/\/localhost/.test(match[0])) found.push(`${rel}: ${match[0]}`);
      }
      if (/serviceWorker|navigator\.sendBeacon|@sentry|posthog|analytics/i.test(text)) found.push(`${rel}: telemetry or a service worker`);
    }
    expect(found).toEqual([]);
  });

  it('loads its fonts from its own files', async () => {
    const css = await readFile(join(consoleSrc, 'styles/index.css'), 'utf8');
    expect(css).not.toMatch(/fonts\.googleapis|@import\s+url\(https?:/);
    expect(css).toMatch(/@fontsource-variable\/geist/);
    expect(css).toMatch(/@fontsource\/geist-mono/);
  });
});

describe('the package', () => {
  it('ships at the server’s version, under the AGPL', async () => {
    const pkg = JSON.parse(await readFile(join(consoleDir, 'package.json'), 'utf8')) as { version: string; license: string; dependencies: Record<string, string> };
    const pyproject = await readFile(join(root, 'pyproject.toml'), 'utf8');
    const server = /^version\s*=\s*"([^"]+)"/m.exec(pyproject)?.[1];
    expect(pkg.version).toBe(server);
    expect(pkg.license).toBe('AGPL-3.0-only');
    expect(await readFile(join(consoleDir, 'LICENSE'), 'utf8')).toMatch(/GNU AFFERO GENERAL PUBLIC LICENSE\s+Version 3/);
  });

  it('pins every dependency to an exact version', async () => {
    const pkg = JSON.parse(await readFile(join(consoleDir, 'package.json'), 'utf8')) as Record<string, Record<string, string>>;
    for (const field of ['dependencies', 'devDependencies']) {
      for (const [name, version] of Object.entries(pkg[field] ?? {})) expect(version, `${field}.${name}`).toMatch(/^\d+\.\d+\.\d+$/);
    }
  });
});
