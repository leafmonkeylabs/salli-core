/**
 * Where you stand (C2) in a real browser, under the server's CSP, on the
 * golden household's fixtures: axe finds nothing, each page looks as it did
 * at 360, 768 and 1280 px in light and dark, no page is wider than the
 * screen, no CSP or Trusted Types violation is reported and nothing is
 * asked of another origin. Then, by keyboard alone: an entry added after
 * its confirmation and reversed after another.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { MockApi } from '../test/fixtures/api';
import { mockSalli } from './fixtures';
import { watch, type Watch } from './watch';

const ORIGIN = 'http://localhost:4173';
const WIDTHS = [360, 768, 1280] as const;
const THEMES = ['light', 'dark'] as const;
const TODAY = new Date('2026-10-11T10:00:00Z');

async function open(page: Page, path: string, width: number, theme: (typeof THEMES)[number], api?: MockApi): Promise<Watch> {
  await page.setViewportSize({ width, height: width < 768 ? 800 : 900 });
  await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
  await page.clock.setFixedTime(TODAY);
  const seen = await watch(page, ORIGIN);
  await mockSalli(page, ORIGIN, api);
  await page.goto(`/console${path}`);
  return seen;
}

async function settled(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.loading')).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
}

async function axe(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

const PAGES: Array<{ name: string; path: string; heading: string }> = [
  { name: 'books', path: '/books', heading: 'Books' },
  { name: 'books-account', path: '/books/accounts/chk', heading: 'Checking' },
  { name: 'books-account-dollars', path: '/books/accounts/usd', heading: 'Dollar account' },
  { name: 'books-entries', path: '/books/entries?account=chk&from=2026-09-01', heading: 'Entries' },
  { name: 'books-entry', path: '/books/entries/e075', heading: 'TO DOLLAR ACCOUNT' },
  { name: 'books-add', path: '/books/entries/new', heading: 'Add an entry' },
  { name: 'cash', path: '/cash', heading: 'Cash' },
  { name: 'attention', path: '/attention', heading: 'Attention' },
  { name: 'fi', path: '/fi', heading: 'Financial independence' },
  { name: 'more', path: '/more', heading: 'More' },
];

for (const theme of THEMES) {
  for (const width of WIDTHS) {
    test.describe(`${width} px, ${theme}`, () => {
      for (const p of PAGES) {
        test(p.name, async ({ page }) => {
          test.setTimeout(120_000);
          const seen = await open(page, p.path, width, theme);
          await expect(page.getByRole('heading', { level: 1, name: p.heading })).toBeVisible();
          await settled(page);
          expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
          await axe(page);
          await expect(page).toHaveScreenshot(`${p.name}-${width}-${theme}.png`, { fullPage: true });
          const show = page.getByRole('button', { name: 'Show the figures' });
          while ((await show.count()) > 0) await show.first().click();
          await axe(page);
          await seen.check();
        });
      }
    });
  }
}

/** Presses Tab until `target` has the focus. */
async function tabTo(page: Page, target: ReturnType<Page['getByRole']>): Promise<void> {
  for (let i = 0; i < 60 && !(await target.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(target).toBeFocused();
}

test('adds an entry and reverses it by keyboard alone, each after its confirmation', async ({ page }) => {
  const api = new MockApi(ORIGIN);
  const seen = await open(page, '/books/entries/new', 1280, 'light', api);
  await expect(page.getByRole('heading', { level: 1, name: 'Add an entry' })).toBeVisible();
  await settled(page);
  const form = page.getByRole('region', { name: 'The entry' });
  await tabTo(page, form.getByRole('textbox', { name: /^Description/ }));
  await page.keyboard.type('Lunch with a friend');
  await page.keyboard.press('Tab');
  await expect(form.getByRole('combobox', { name: /^From/ })).toBeFocused();
  await form.getByRole('combobox', { name: /^From/ }).selectOption('chk');
  await page.keyboard.press('Tab');
  await form.getByRole('combobox', { name: /^To/ }).selectOption('out');
  await page.keyboard.press('Tab');
  await expect(form.getByRole('textbox', { name: /^Amount/ })).toBeFocused();
  await page.keyboard.type('12.50');
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('alertdialog', { name: 'Post this entry?' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Post it' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(form.getByText(/Posted\./)).toBeVisible();
  expect(api.to('/v1/entries/', 'POST')).toHaveLength(1);
  await tabTo(page, form.getByRole('link', { name: 'Open the entry' }));
  await page.keyboard.press('Enter');

  await expect(page.getByRole('heading', { level: 1, name: 'Lunch with a friend' })).toBeVisible();
  const standing = page.getByRole('region', { name: 'Standing' });
  await tabTo(page, standing.getByRole('button', { name: 'Reverse this entry' }));
  await page.keyboard.press('Enter');
  const ask = page.getByRole('alertdialog', { name: 'Reverse this entry?' });
  await expect(ask).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(ask.getByRole('button', { name: 'Reverse it' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(standing.getByText(/Reversed\. Both entries are in the ledger\./)).toBeVisible();
  await expect(standing.getByText(/Reversed by/)).toBeVisible();
  await seen.check();
});
