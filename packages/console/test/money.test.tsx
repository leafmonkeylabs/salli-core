/**
 * No float touches money (decision 12; docs/design/console.md, section 8).
 *
 * - Amounts a float can't hold (9007199254740993.01, 0.30000000000000004),
 *   a three-decimal and a zero-decimal currency are shown digit for digit,
 *   on <Money> and on Home with every amount in its fixtures replaced.
 * - Every request body's amount fields are decimal strings.
 * - The lint rules refuse converting an amount to a number in the console,
 *   and the one escape, for pixel geometry, is in chart/geometry.ts only.
 */
import { readdir, readFile } from 'node:fs/promises';
import { join, relative, resolve } from 'node:path';
import { render, screen, waitFor, within } from '@testing-library/react';
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';
import { Money, spokenAmount, visibleAmount } from '../src/kit/Money';
import { PreferencesProvider } from '../src/preferences';
import { HOME_READS, MockApi } from './fixtures/api';
import * as where from './fixtures/where';
import { setup } from './harness';

// The tests run in packages/console.
const root = resolve(process.cwd(), '../..');
const consoleSrc = join(root, 'packages/console/src');

async function sources(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await sources(path)));
    else if (/\.(ts|tsx|mts|mjs)$/.test(entry.name)) out.push(path);
  }
  return out;
}

describe('<Money>', () => {
  const cases: Array<[string, string, string, string]> = [
    ['9007199254740993.01', 'USD', 'USD 9,007,199,254,740,993.01', '9,007,199,254,740,993.01 US dollars'],
    ['0.30000000000000004', 'EUR', 'EUR 0.30000000000000004', '0.30000000000000004 euros'],
    ['-1.234', 'KWD', 'KWD -1.234', 'minus 1.234 Kuwaiti dinars'],
    ['1234567', 'JPY', 'JPY 1,234,567', '1,234,567 Japanese yen'],
    ['-370.00', 'USD', 'USD -370.00', 'minus 370.00 US dollars'],
  ];

  it.each(cases)('shows %s %s exactly, and reads it out with its sign as a word', (amount, currency, shown, spoken) => {
    expect(visibleAmount(amount, currency, 'prose', { locale: 'en-US' })).toBe(shown);
    expect(spokenAmount(amount, currency, 'en-US')).toBe(spoken);
  });

  it('puts a negative in brackets in a table, in the locale’s marks', () => {
    expect(visibleAmount('-370.00', 'USD', 'table', { locale: 'en-US' })).toBe('(370.00)');
    expect(visibleAmount('-1234.5', 'EUR', 'table', { locale: 'de-DE' })).toBe('(1.234,50)');
    render(
      <PreferencesProvider locale="en-US">
        <Money amount="-370.00" currency="USD" variant="table" />
      </PreferencesProvider>,
    );
    expect(screen.getByText('(370.00)').getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByText('minus 370.00 US dollars')).toBeTruthy();
  });

  it('shows something that is not an amount as given, rather than guessing', () => {
    expect(visibleAmount('n/a', 'USD')).toBe('n/a');
  });
});

/** Every amount in a fixture, replaced by one a float would round. */
function hardAmounts(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(hardAmounts);
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(
      Object.entries(value).map(([key, v]) => [
        key,
        typeof v === 'string' && /^-?\d+\.\d{2}$/.test(v) && !/rate|score|progress|months|ratio|swr/.test(key) ? (v.startsWith('-') ? '-9007199254740993.01' : '9007199254740993.01') : hardAmounts(v),
      ]),
    );
  }
  return value;
}

describe('Home', () => {
  it('shows amounts a float can’t hold digit for digit', async () => {
    const api = new MockApi();
    for (const [path, body] of Object.entries(HOME_READS)) api.reads[path] = hardAmounts(body);
    await setup({ api });
    const netWorth = await screen.findByRole('group', { name: 'Net worth' });
    await waitFor(() => expect(within(netWorth).getAllByText('9,007,199,254,740,993.01').length).toBeGreaterThan(0));
    expect(within(netWorth).getAllByText('EUR 9,007,199,254,740,993.01').length).toBeGreaterThan(0);
    // A key figure: its code apart, a negative in brackets as a statement shows it.
    const month = screen.getByRole('group', { name: 'October 2026 so far' });
    await waitFor(() => expect(within(month).getAllByText('(9,007,199,254,740,993.01)').length).toBeGreaterThan(0));
    // Nowhere does the rounded float appear.
    expect(document.body.textContent).not.toMatch(/9,007,199,254,740,992|9007199254740992/);
  });

  it('sends every amount as a decimal string', async () => {
    const { api } = await setup({ path: '/console/settings' });
    await screen.findByRole('region', { name: 'Profile' });
    const numbers: string[] = [];
    const walk = (value: unknown, path: string): void => {
      if (typeof value === 'number' && /amount|balance|price|principal|rate|value|total/i.test(path)) numbers.push(path);
      if (Array.isArray(value)) value.forEach((v, i) => walk(v, `${path}[${i}]`));
      else if (typeof value === 'object' && value !== null) for (const [k, v] of Object.entries(value)) walk(v, path ? `${path}.${k}` : k);
    };
    for (const request of api.requests) {
      if (request.body && request.body.startsWith('{')) walk(JSON.parse(request.body), '');
    }
    expect(numbers).toEqual([]);
  });
});

describe('where you stand', () => {
  it('shows amounts a float can’t hold digit for digit, in the books and in cash', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.method === 'GET' && r.path === '/v1/ledger/trial-balance' ? { status: 200, body: hardAmounts(where.TRIAL_BALANCE) } : undefined));
    api.overrides.push((r) => (r.method === 'GET' && r.path === '/v1/insights/forecast' ? { status: 200, body: hardAmounts(where.FORECAST) } : undefined));
    await setup({ api, path: '/console/books' });
    const assets = await screen.findByRole('region', { name: 'Assets' });
    await waitFor(() => expect(within(assets).getAllByText('9,007,199,254,740,993.01').length).toBeGreaterThan(0));
    const liabilities = screen.getByRole('region', { name: 'Liabilities' });
    expect(within(liabilities).getAllByText('(9,007,199,254,740,993.01)').length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/9,007,199,254,740,992|9007199254740992/);
    await setup({ api, path: '/console/cash' });
    const accounts = await screen.findByRole('region', { name: 'Cash accounts' });
    await waitFor(() => expect(within(accounts).getAllByText('EUR 9,007,199,254,740,993.01').length).toBeGreaterThan(0));
    expect(document.body.textContent).not.toMatch(/9,007,199,254,740,992|9007199254740992/);
  });
});

describe('the money guard in the console', () => {
  it('refuses converting an amount to a number', async () => {
    const eslint = new ESLint({ cwd: root });
    const filePath = join(consoleSrc, 'pages/example.tsx');
    for (const code of [
      'export const a = (amount: string) => Number(amount);',
      'export const b = (amount: string) => parseFloat(amount);',
      'export const c = (amount: string) => +amount;',
      'export const d = (amount: string) => Number.parseInt(amount, 10);',
    ]) {
      const [result] = await eslint.lintText(code, { filePath });
      expect(result?.messages.map((m) => m.ruleId), code).toContain('no-restricted-syntax');
    }
  });

  it('allows the one escape, pixel geometry, in chart/geometry.ts and nowhere else', async () => {
    const escapes: string[] = [];
    for (const file of await sources(consoleSrc)) {
      const lines = (await readFile(file, 'utf8')).split('\n');
      lines.forEach((line, i) => {
        if (/eslint-disable.*no-restricted-syntax/.test(line)) escapes.push(`${relative(consoleSrc, file)}:${i + 1}: ${line.trim()}`);
      });
    }
    expect(escapes).toHaveLength(1);
    expect(escapes[0]).toMatch(/^kit\/chart\/geometry\.ts:\d+: \/\/ eslint-disable-next-line no-restricted-syntax -- not money: pixel geometry$/);
  });
});
