// `npm audit --omit=dev --audit-level=high`, except for the advisories
// npm-allowlist.json names, each at the one installed path it names and with
// the reason it is accepted (docs/security.md, "Accepted advisories").
// Anything else at high or critical fails; an entry that no longer matches
// is reported so it can be removed.

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const allowlist = JSON.parse(readFileSync(new URL('./npm-allowlist.json', import.meta.url), 'utf8'));

let out;
try {
  out = execFileSync('npm', ['audit', '--omit=dev', '--json'], { encoding: 'utf8', maxBuffer: 64 << 20 });
} catch (error) {
  out = error.stdout; // npm audit exits non-zero when it finds anything
}
const report = JSON.parse(out);
if (report.error) throw new Error(`npm audit: ${report.error.summary}`);

const failures = [];
const matched = new Set();
for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
  for (const via of vulnerability.via) {
    // A string is a dependency that is vulnerable through another package,
    // which is reported in its own right.
    if (typeof via === 'string' || !['high', 'critical'].includes(via.severity)) continue;
    const advisory = via.url.split('/').pop();
    for (const path of vulnerability.nodes) {
      const entry = allowlist.find((a) => a.advisory === advisory && a.path === path);
      if (entry) matched.add(entry);
      else failures.push(`${advisory} (${via.severity}) in ${path}: ${via.title}`);
    }
  }
}

for (const entry of allowlist) {
  if (!matched.has(entry)) console.log(`::warning::${entry.advisory} at ${entry.path} no longer applies: remove it from .github/audit/npm-allowlist.json`);
}
for (const entry of matched) console.log(`accepted: ${entry.advisory} at ${entry.path}`);
if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log('npm audit: nothing at high or above beyond the accepted advisories');
