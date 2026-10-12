/**
 * The decision lab never ranks (docs/design/decision-lab.md, decision 1):
 * tests/guardrails.py's words, read from that file so the two can't drift,
 * held over the lab's catalogue (src/lab-strings.ts) and over what its pages
 * render from the server's fixtures. A word right after "not", "never",
 * "nor" or "no" is a disclaimer, as the Python guard treats it.
 */
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeAll, describe, expect, it } from 'vitest';
import { labStrings } from '../src/lab-strings';
import * as lab from './fixtures/lab';
import { MockApi } from './fixtures/api';
import { setup } from './harness';

const root = resolve(process.cwd(), '../..');
let ranking: RegExp;
let negated: RegExp;

/** A `re.compile(r"…" r"…", re.IGNORECASE)` from guardrails.py, as a JavaScript RegExp. */
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

/** The first ranking word in `text`, after disclaimers are taken out. */
function ranks(text: string): string | undefined {
  return ranking.exec(text.replace(negated, '$1'))?.[0];
}

function catalogue(value: unknown, path = 'labStrings'): Array<[string, string]> {
  if (typeof value === 'string') return [[path, value]];
  if (typeof value === 'function') return [[path, String((value as (...args: string[]) => string)('X', 'Y', 'Z', 'W'))]];
  if (typeof value === 'object' && value !== null) return Object.entries(value).flatMap(([k, v]) => catalogue(v, `${path}.${k}`));
  return [];
}

describe('the guard itself', () => {
  it('is the Python guard’s: it catches what that one catches, and lets disclaimers through', () => {
    expect(ranks('Pay cash is the best option')).toBe('best');
    expect(ranks('We recommend instalments')).toBe('recommend');
    expect(ranks('You should wait')).toBe('should');
    expect(ranks('Salli ranks none: this is not a recommendation')).toBeUndefined();
  });
});

describe('the lab’s catalogue', () => {
  it('ranks nothing, recommends nothing and says no should', () => {
    const found = catalogue(labStrings).flatMap(([path, text]) => {
      const word = ranks(text);
      return word ? [`${path}: ${word} in “${text}”`] : [];
    });
    expect(found).toEqual([]);
  });

  it('urges nothing: no exclamation, no countdown', () => {
    for (const [path, text] of catalogue(labStrings)) {
      expect(text, path).not.toMatch(/!/);
      expect(text, path).not.toMatch(/\b(hurry|act now|don't miss|last chance|days left|streak)\b/i);
    }
  });
});

async function rendered(): Promise<string> {
  const main = document.querySelector('main');
  // The figures behind each chart are text too.
  for (const button of within(main as HTMLElement).queryAllByRole('button', { name: 'Show the figures' })) {
    await act(async () => {
      fireEvent.click(button);
    });
  }
  return main?.textContent ?? '';
}

async function startTemplate(id: string, answers: (form: HTMLElement) => void): Promise<string> {
  await setup({ path: `/console/decide/templates/${id}` });
  const form = await screen.findByRole('region', { name: 'Your answers' });
  answers(form);
  await act(async () => {
    fireEvent.click(within(form).getByRole('button', { name: 'Build and compare the options' }));
  });
  await screen.findByRole('heading', { name: 'What Salli built' });
  return rendered();
}

describe('what the lab’s pages render from the server’s answers', () => {
  const set = (form: HTMLElement, name: RegExp | string, value: string): void => {
    fireEvent.change(within(form).getByRole('textbox', { name }), { target: { value } });
  };

  it.each([
    ['afford-it', (form: HTMLElement) => set(form, 'What does it cost?', '2400')],
    [
      'emergency-fund',
      (form: HTMLElement) => {
        set(form, /How many months of spending do you want your cash to cover\?/, '9');
        set(form, 'Amount 1', '200');
      },
    ],
    [
      'rent-or-buy',
      (form: HTMLElement) => {
        set(form, 'What would the home cost?', '350000');
        set(form, 'How much would you put down?', '70000');
        fireEvent.change(within(form).getAllByRole('textbox', { name: 'Its yearly rate' })[0] as HTMLElement, { target: { value: '0.042' } });
        fireEvent.change(within(form).getAllByRole('textbox', { name: 'Its term, in months' })[0] as HTMLElement, { target: { value: '300' } });
        set(form, /What would buying cost, once/, '9000');
        set(form, /What would owning cost a month/, '250');
        set(form, /What would selling the home cost/, '0.03');
      },
    ],
  ])('%s: the result ranks nothing', async (id, answers) => {
    const text = await startTemplate(id, answers);
    expect(text.length).toBeGreaterThan(1000);
    expect(ranks(text)).toBeUndefined();
  });

  it('a comparison of scenarios ranks nothing', async () => {
    await setup({ path: '/console/decide/scenarios' });
    await screen.findAllByRole('group', { name: 'Option 1' });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Add an option' }));
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Compare the 2 options' }));
    });
    await screen.findByRole('heading', { name: 'The options compared' });
    expect(ranks(await rendered())).toBeUndefined();
  });

  it.each([
    ['the journal', '/console/decide/journal', 'Entries'],
    ['an entry', `/console/decide/journal/${lab.DECISION.id}`, 'The entry'],
    ['an entry due for review', `/console/decide/journal/${lab.DECISION_DUE.id}`, 'Look back on it'],
    ['the principles', '/console/decide/principles', 'In use'],
    ['the baseline', '/console/decide/baseline', 'Assumptions'],
  ])('%s ranks nothing', async (_name, path, section) => {
    await setup({ api: new MockApi(), path });
    await screen.findByRole('region', { name: section });
    await new Promise((r) => setTimeout(r, 50));
    expect(ranks(await rendered())).toBeUndefined();
  });
});
