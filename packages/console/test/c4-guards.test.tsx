/**
 * Books, tax and settings (C4) never rank and never advise:
 * tests/guardrails.py's words, read from that file as the lab's and where
 * you stand's guards read them, held over C4's catalogues
 * (src/books-strings.ts, src/tax-strings.ts, src/settings-strings.ts) and
 * over what their pages render from the server's fixtures, with every
 * explanation and confirmation opened. Rules and suggestions are told
 * apart by their order, never by merit; a rule set's version is proposed
 * by an agent, never recommended.
 */
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';
import { bookStrings } from '../src/books-strings';
import { settingsStrings } from '../src/settings-strings';
import { taxStrings } from '../src/tax-strings';
import * as books from './fixtures/books';
import * as tax from './fixtures/tax';
import { setup } from './harness';

const root = resolve(process.cwd(), '../..');
let ranking: RegExp;
let negated: RegExp;

function pythonRegex(source: string, name: string, flags: string): RegExp {
  const found = new RegExp(`^${name} = re\\.compile\\(([\\s\\S]*?)re\\.IGNORECASE`, 'm').exec(source);
  if (!found?.[1]) throw new Error(`${name} isn't in tests/guardrails.py`);
  const parts = [...found[1].matchAll(/r"((?:[^"\\]|\\.)*)"/g)].map((m) => m[1] ?? '');
  return new RegExp(parts.join(''), flags);
}

beforeAll(async () => {
  const source = await readFile(join(root, 'tests/guardrails.py'), 'utf8');
  ranking = pythonRegex(source, 'RANKING_WORDS', 'i');
  negated = pythonRegex(source, 'NEGATED', 'gi');
});

function ranks(text: string): string | undefined {
  return ranking.exec(text.replace(negated, '$1'))?.[0];
}

function catalogue(value: unknown, path: string): Array<[string, string]> {
  if (typeof value === 'string') return [[path, value]];
  if (typeof value === 'function') return [[path, String((value as (...args: unknown[]) => string)('X', 'Y', 'Z', 'W', 'V', 'U'))], [`${path}(1)`, String((value as (...args: unknown[]) => string)(1, 2, 'Z'))]];
  if (typeof value === 'object' && value !== null) return Object.entries(value).flatMap(([k, v]) => catalogue(v, `${path}.${k}`));
  return [];
}

const ALL = (): Array<[string, string]> => [
  ...catalogue(bookStrings, 'bookStrings'),
  ...catalogue(taxStrings, 'taxStrings'),
  ...catalogue(settingsStrings, 'settingsStrings'),
];

describe('books’, tax’s and settings’ catalogues', () => {
  it('rank nothing, recommend nothing and say no should', () => {
    const found = ALL().flatMap(([path, text]) => {
      const word = ranks(text);
      return word ? [`${path}: ${word} in “${text}”`] : [];
    });
    expect(found).toEqual([]);
  });

  it('urge nothing: no exclamation, no countdown', () => {
    for (const [path, text] of ALL()) {
      expect(text, path).not.toMatch(/!/);
      expect(text, path).not.toMatch(/\b(hurry|urgent|act now|don't miss|last chance|days left|streak)\b/i);
    }
  });
});

async function rendered(): Promise<string> {
  const main = document.querySelector('main') as HTMLElement;
  await new Promise((r) => setTimeout(r, 50));
  return main.textContent ?? '';
}

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

describe('what their pages render from the server’s answers', () => {
  it.each([
    ['imports', '/console/books/imports', 'Bank connections', 'Everyday checking'],
    ['the review queue', `/console/books/imports/${books.STATEMENTS.statements[0]!.id}`, 'Waiting for review', 'FRESHMART'],
    ['rules', '/console/books/rules', 'Suggestions', 'Acme'],
    ['your tax', '/console/tax', 'The last computation', 'Tax to pay'],
    ['a rule set', `/console/tax/rules/${tax.RULE_SET.id}`, 'Versions', 'Rounding the examples.'],
    ['a version proposed', `/console/tax/rules/${tax.RULE_SET.id}/versions/${tax.VERSION_2.id}`, 'Worked examples', 'A pension contribution'],
    ['a version failing', `/console/tax/rules/${tax.RULE_SET.id}/versions/${tax.VERSION_3.id}`, 'Worked examples', 'Fails'],
    ['tokens', '/console/settings/tokens', 'Your tokens', 'Spreadsheet'],
    ['AI connections', '/console/settings/ai', 'Model keys', 'Anthropic key'],
    ['digests', '/console/settings/digests', 'Digests sent', '2026-W41'],
    ['your data', '/console/settings/data', 'Everything', 'Save all of it (JSON)'],
  ])('%s ranks nothing', async (_name, path, section, text) => {
    await setup({ path });
    const region = await screen.findByRole('region', { name: section });
    await within(region).findAllByText(text, { exact: false });
    const found = await rendered();
    expect(found.length).toBeGreaterThan(200);
    expect(ranks(found)).toBeUndefined();
  });

  it('an explanation and the activation’s confirmation rank nothing', async () => {
    await setup({ path: '/console/tax' });
    const latest = await screen.findByRole('region', { name: 'The last computation' });
    await click(await within(latest).findByRole('button', { name: 'Explain Income tax' }));
    await within(latest).findByRole('region', { name: 'Where Income tax comes from' });
    expect(ranks(await rendered())).toBeUndefined();
  });

  it('the activation’s confirmation ranks nothing', async () => {
    await setup({ path: `/console/tax/rules/${tax.RULE_SET.id}/versions/${tax.VERSION_2.id}` });
    await click(await screen.findByRole('button', { name: 'Activate version 2' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Activate version 2?' });
    expect(ranks(dialog.textContent ?? '')).toBeUndefined();
  });
});
