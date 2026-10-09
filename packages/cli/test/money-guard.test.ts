/**
 * Money stays a decimal string. These checks keep it that way: the lint
 * rule that refuses Number()/parseFloat()/parseInt()/unary + is in force,
 * and every place that switches it off says why the value is not money.
 */
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';

const root = fileURLToPath(new URL('../../..', import.meta.url));

async function sources(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'generated' && entry.name !== 'node_modules' && entry.name !== 'dist') out.push(...(await sources(path)));
    } else if (/\.(ts|mts|mjs)$/.test(entry.name)) out.push(path);
  }
  return out;
}

describe('the money guard', () => {
  it('refuses converting an amount to a number', async () => {
    const eslint = new ESLint({ cwd: root });
    const filePath = join(root, 'packages/cli/src/example.ts');
    const offences = [
      'export const a = (amount: string) => Number(amount);',
      'export const b = (amount: string) => parseFloat(amount);',
      'export const c = (amount: string) => Number.parseFloat(amount);',
      'export const d = (amount: string) => parseInt(amount, 10);',
      'export const e = (amount: string) => +amount;',
    ];
    for (const code of offences) {
      const [result] = await eslint.lintText(code, { filePath });
      expect(result?.messages.map((m) => m.ruleId), code).toContain('no-restricted-syntax');
    }
    const [clean] = await eslint.lintText('export const f = (amount: string) => amount.trim();', { filePath });
    expect(clean?.messages).toEqual([]);
  });

  it('is only switched off with a reason saying the value is not money', async () => {
    const files = [...(await sources(join(root, 'packages/cli/src'))), ...(await sources(join(root, 'packages/sdk/src')))];
    const unexplained: string[] = [];
    for (const file of files) {
      const lines = (await readFile(file, 'utf8')).split('\n');
      lines.forEach((line, i) => {
        if (/eslint-disable.*no-restricted-syntax/.test(line) && !/--\s*not money:/.test(line)) {
          unexplained.push(`${relative(root, file)}:${i + 1}`);
        }
      });
    }
    expect(unexplained).toEqual([]);
  });
});
