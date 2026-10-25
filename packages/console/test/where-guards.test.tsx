/**
 * Where you stand never ranks and never advises: tests/guardrails.py's
 * words, read from that file as the lab's guard reads them, held over C2's
 * catalogue (src/where-strings.ts) and over what its pages render from the
 * server's fixtures, with every chart's figures opened.
 *
 * One word is allowed, on the financial independence page only: "score",
 * the name of the FI score (the API's Freedom Score), a figure Salli
 * computes about where one person stands. It orders no options.
 */
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';
import { whereStrings } from '../src/where-strings';
import { setup } from './harness';

const root = resolve(process.cwd(), '../..');
let ranking: RegExp;
let negated: RegExp;
/** The FI score's name, allowed where it is the figure's name. */
const SCORE = /\b(score|scored|scores)\b/gi;

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

function ranks(text: string, allowScore = false): string | undefined {
  const plain = text.replace(negated, '$1');
  return ranking.exec(allowScore ? plain.replace(SCORE, '') : plain)?.[0];
}

function catalogue(value: unknown, path = 'whereStrings'): Array<[string, string]> {
  if (typeof value === 'string') return [[path, value]];
  if (typeof value === 'function') return [[path, String((value as (...args: string[]) => string)('X', 'Y', 'Z', 'W', 'V', 'U'))]];
  if (typeof value === 'object' && value !== null) return Object.entries(value).flatMap(([k, v]) => catalogue(v, `${path}.${k}`));
  return [];
}

describe('where you stand’s catalogue', () => {
  it('ranks nothing, recommends nothing and says no should', () => {
    const found = catalogue(whereStrings).flatMap(([path, text]) => {
      const word = ranks(text, path.startsWith('whereStrings.fi.'));
      return word ? [`${path}: ${word} in “${text}”`] : [];
    });
    expect(found).toEqual([]);
  });

  it('urges nothing: no exclamation, no countdown', () => {
    for (const [path, text] of catalogue(whereStrings)) {
      expect(text, path).not.toMatch(/!/);
      expect(text, path).not.toMatch(/\b(hurry|urgent|act now|don't miss|last chance|days left|streak)\b/i);
    }
  });
});

async function rendered(): Promise<string> {
  const main = document.querySelector('main') as HTMLElement;
  for (const button of within(main).queryAllByRole('button', { name: 'Show the figures' })) {
    await act(async () => {
      fireEvent.click(button);
    });
  }
  return main.textContent ?? '';
}

describe('what its pages render from the server’s answers', () => {
  it.each([
    ['the accounts', '/console/books', 'Assets'],
    ['an account', '/console/books/accounts/chk', 'Its entries'],
    ['the entries', '/console/books/entries', 'Entries'],
    ['an entry', '/console/books/entries/e075', 'Its lines'],
    ['adding an entry', '/console/books/entries/new', 'The entry'],
    ['cash', '/console/cash', 'Recurring payments'],
    ['attention', '/console/attention', 'Reminders'],
  ])('%s ranks nothing', async (_name, path, section) => {
    await setup({ path });
    await screen.findByRole('region', { name: section });
    await new Promise((r) => setTimeout(r, 50));
    const text = await rendered();
    expect(text.length).toBeGreaterThan(200);
    expect(ranks(text)).toBeUndefined();
  });

  it('financial independence ranks nothing', async () => {
    await setup({ path: '/console/fi' });
    await screen.findByRole('region', { name: 'Assumptions' });
    await new Promise((r) => setTimeout(r, 50));
    expect(ranks(await rendered(), true)).toBeUndefined();
  });
});
