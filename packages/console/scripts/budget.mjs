#!/usr/bin/env node
/**
 * The console's budget (decision 14), checked on every build and in CI:
 *
 * - at most 150 kB of compressed JavaScript for the shell and Home (the
 *   entry chunk and everything it imports statically);
 * - at most 75 kB for each later page (a lazily loaded chunk and what it
 *   imports that the shell doesn't already load);
 * - at most 500 kB of JavaScript in all;
 * - at most 40 kB of compressed CSS.
 *
 * "Compressed" is gzip at level 9, the larger of what the server sends
 * (it prefers the brotli copies the build writes beside each file).
 *
 * It also checks what the CSP needs of the build: index.html has no inline
 * script or style, and no asset is inlined as a data: URL.
 *
 *     node scripts/budget.mjs [dist] [--json]
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { brotliCompressSync, gzipSync } from 'node:zlib';

const KB = 1000;
const BUDGET = { shell: 150 * KB, page: 75 * KB, total: 500 * KB, css: 40 * KB };

const args = process.argv.slice(2);
const dist = args.find((a) => !a.startsWith('--')) ?? 'dist';
const manifest = JSON.parse(readFileSync(join(dist, '.vite/manifest.json'), 'utf8'));

const sizes = new Map();
function size(file) {
  if (!sizes.has(file)) {
    const data = readFileSync(join(dist, file));
    sizes.set(file, { raw: data.length, gzip: gzipSync(data, { level: 9 }).length, brotli: brotliCompressSync(data).length });
  }
  return sizes.get(file);
}

/** A chunk's file and the files of everything it imports statically. */
function closure(key, seen = new Set()) {
  if (seen.has(key)) return seen;
  seen.add(key);
  for (const imported of manifest[key]?.imports ?? []) closure(imported, seen);
  return seen;
}

const entryKey = Object.keys(manifest).find((key) => manifest[key].isEntry);
if (!entryKey) throw new Error('No entry in the manifest');
const shellKeys = closure(entryKey);
const files = (keys) => [...new Set([...keys].map((key) => manifest[key].file))];
const sum = (list, kind) => list.reduce((total, file) => total + size(file)[kind], 0);

const rows = [];
const shellFiles = files(shellKeys);
rows.push({ name: 'shell and Home', files: shellFiles, limit: BUDGET.shell });

const pages = new Set();
for (const key of Object.keys(manifest)) for (const dynamic of manifest[key].dynamicImports ?? []) pages.add(dynamic);
for (const page of pages) {
  const own = files([...closure(page)].filter((key) => !shellKeys.has(key)));
  rows.push({ name: manifest[page].name ?? page, files: own, limit: BUDGET.page });
}

const allJs = [...new Set(Object.values(manifest).map((chunk) => chunk.file).filter((file) => file.endsWith('.js')))];
rows.push({ name: 'all JavaScript', files: allJs, limit: BUDGET.total });
const css = [...new Set(Object.values(manifest).flatMap((chunk) => chunk.css ?? []).concat(Object.values(manifest).map((c) => c.file).filter((f) => f.endsWith('.css'))))];
rows.push({ name: 'CSS', files: css, limit: BUDGET.css });

const problems = [];
const report = rows.map((row) => {
  const gzip = sum(row.files, 'gzip');
  const brotli = sum(row.files, 'brotli');
  if (gzip > row.limit) problems.push(`${row.name}: ${(gzip / KB).toFixed(1)} kB compressed, over its ${row.limit / KB} kB`);
  return { name: row.name, gzip, brotli, limit: row.limit, files: row.files };
});

// What the CSP needs of the build.
const html = readFileSync(join(dist, 'index.html'), 'utf8');
if (/<script(?![^>]*\bsrc=)[^>]*>/i.test(html)) problems.push('index.html has an inline script');
if (/<style[\s>]/i.test(html) || /\sstyle=/i.test(html)) problems.push('index.html has an inline style');
if (/\son[a-z]+=/i.test(html)) problems.push('index.html has an inline event handler');
for (const file of [...allJs, ...css]) {
  const text = readFileSync(join(dist, file), 'utf8');
  if (/url\(\s*['"]?data:/i.test(text)) problems.push(`${file} inlines an asset as a data: URL`);
  if (/https?:\/\/(?!localhost|127\.0\.0\.1|www\.w3\.org)[a-z0-9.-]+\.[a-z]{2,}\/[^\s"'`]*\.(js|css|woff2?)\b/i.test(text)) problems.push(`${file} names a third-party script, stylesheet or font`);
}

if (args.includes('--json')) {
  process.stdout.write(`${JSON.stringify({ budget: BUDGET, report, problems }, null, 2)}\n`);
} else {
  const kb = (n) => `${(n / KB).toFixed(1)} kB`.padStart(9);
  console.log('Budget (compressed)          gzip    brotli    limit');
  for (const row of report) console.log(`  ${row.name.padEnd(22)} ${kb(row.gzip)} ${kb(row.brotli)} ${kb(row.limit)}`);
  for (const problem of problems) console.error(`over budget or unsafe: ${problem}`);
}
process.exitCode = problems.length ? 1 : 0;
