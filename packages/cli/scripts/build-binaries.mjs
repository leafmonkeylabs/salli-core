#!/usr/bin/env node
// Builds standalone `salli` executables with `bun build --compile` from the
// npm bundle (dist/salli.js; `npm run build` makes it). Needs Bun 1.3+.
//
//   node scripts/build-binaries.mjs              every target
//   node scripts/build-binaries.mjs --host       this machine's only
//   node scripts/build-binaries.mjs linux-x64    the ones named
//
// Output: dist/bin/salli-<os>-<arch>[.exe] and dist/bin/SHA256SUMS.
//
// The system keychain module (@napi-rs/keyring) is native code. Bun embeds
// the one installed for the machine that builds, so a binary built for its
// own platform keeps tokens in the keychain through it. A binary built for
// another platform cannot load it, and falls back at runtime to the OS's
// own tool (macOS `security`, Linux `secret-tool`) or, failing those, to a
// file readable only by the user (see src/auth/store.ts).
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { arch, platform } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const bundle = join(root, 'dist', 'salli.js');
const outDir = join(root, 'dist', 'bin');

const TARGETS = ['darwin-arm64', 'darwin-x64', 'linux-x64', 'linux-arm64', 'windows-x64'];

const host = `${platform() === 'win32' ? 'windows' : platform()}-${arch()}`;
const args = process.argv.slice(2);
const wanted = args.includes('--host') ? [host] : args.filter((a) => !a.startsWith('-'));
const targets = wanted.length ? wanted : TARGETS;
for (const target of targets) {
  if (!TARGETS.includes(target)) {
    console.error(`Unknown target "${target}". Targets: ${TARGETS.join(', ')}`);
    process.exit(2);
  }
}

if (!existsSync(bundle)) {
  console.error('dist/salli.js is missing: run `npm run build` first.');
  process.exit(1);
}
const bun = spawnSync('bun', ['--version'], { encoding: 'utf8' });
if (bun.status !== 0) {
  console.error('Bun is needed to build standalone binaries: https://bun.sh');
  process.exit(1);
}
mkdirSync(outDir, { recursive: true });

const sums = [];
for (const target of targets) {
  const file = `salli-${target}${target.startsWith('windows') ? '.exe' : ''}`;
  const outfile = join(outDir, file);
  const result = spawnSync(
    'bun',
    ['build', '--compile', '--minify', `--target=bun-${target}`, bundle, '--outfile', outfile],
    { cwd: root, stdio: ['ignore', 'inherit', 'inherit'] },
  );
  if (result.status !== 0) {
    console.error(`Building ${file} failed.`);
    process.exit(result.status ?? 1);
  }
  const bytes = statSync(outfile).size;
  sums.push(`${createHash('sha256').update(readFileSync(outfile)).digest('hex')}  ${file}`);
  console.log(`${file}  ${(bytes / 1024 / 1024).toFixed(1)} MiB${target === host ? '  (this machine)' : ''}`);
}
writeFileSync(join(outDir, 'SHA256SUMS'), `${sums.join('\n')}\n`);
