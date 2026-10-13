/**
 * Books, tax and settings (C4) in a real browser, under the server's CSP,
 * on the server's fixtures: axe finds nothing, each page looks as it did at
 * 360, 768 and 1280 px in light and dark, no page is wider than the screen,
 * no CSP or Trusted Types violation is reported and nothing is asked of
 * another origin. Then: a statement file uploaded and downloads saved under
 * the CSP; the review queue and an activation by keyboard alone, each after
 * its confirmation; and a token shown once and kept nowhere once the page
 * is left.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { MockApi } from '../test/fixtures/api';
import * as books from '../test/fixtures/books';
import * as settings from '../test/fixtures/settings';
import * as tax from '../test/fixtures/tax';
import { mockSalli } from './fixtures';
import { watch, type Watch } from './watch';

const ORIGIN = 'http://localhost:4173';
const WIDTHS = [360, 768, 1280] as const;
const THEMES = ['light', 'dark'] as const;
const TODAY = new Date('2026-10-11T10:00:00Z');
const STATEMENT = books.STATEMENTS.statements[0]!.id;
const SET = tax.RULE_SET.id;

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

const PAGES: Array<{ name: string; path: string; heading: string; act?: (page: Page) => Promise<void> }> = [
  { name: 'books-imports', path: '/books/imports', heading: 'Imports' },
  { name: 'books-review', path: `/books/imports/${STATEMENT}`, heading: 'Review: Example Bank, Oct 1 – 10, 2026' },
  { name: 'books-rules', path: '/books/rules', heading: 'Rules' },
  { name: 'tax', path: '/tax', heading: 'Tax' },
  {
    name: 'tax-explained',
    path: '/tax',
    heading: 'Tax',
    act: async (page) => {
      await page.getByRole('button', { name: 'Explain Income tax', exact: true }).click();
      await expect(page.getByRole('region', { name: 'Where Income tax comes from' })).toBeVisible();
    },
  },
  { name: 'tax-rule-set', path: `/tax/rules/${SET}`, heading: 'XA 2031' },
  { name: 'tax-version', path: `/tax/rules/${SET}/versions/${tax.VERSION_2.id}`, heading: 'XA 2031, version 2' },
  { name: 'tax-version-draft', path: `/tax/rules/${SET}/versions/${tax.VERSION_3.id}`, heading: 'XA 2031, version 3' },
  { name: 'settings-tokens', path: '/settings/tokens', heading: 'Personal access tokens' },
  { name: 'settings-ai', path: '/settings/ai', heading: 'AI connections' },
  { name: 'settings-digests', path: '/settings/digests', heading: 'Digests' },
  { name: 'settings-data', path: '/settings/data', heading: 'Your data' },
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
          if (p.act) {
            await p.act(page);
            await settled(page);
          }
          expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
          await axe(page);
          await expect(page).toHaveScreenshot(`${p.name}-${width}-${theme}.png`, { fullPage: true });
          await seen.check();
        });
      }
    });
  }
}

/** The confirmations, open: axe on each dialog in both themes. */
for (const theme of THEMES) {
  test(`every C4 confirmation passes axe, ${theme}`, async ({ page }) => {
    test.setTimeout(120_000);
    const seen = await open(page, `/tax/rules/${SET}/versions/${tax.VERSION_2.id}`, 1280, theme);
    await settled(page);
    await page.getByRole('button', { name: 'Activate version 2' }).click();
    await expect(page.getByRole('alertdialog', { name: 'Activate version 2?' })).toBeVisible();
    await axe(page);
    await page.keyboard.press('Escape');
    await page.goto(`/console/books/imports/${STATEMENT}`);
    await settled(page);
    await page.getByRole('checkbox', { name: /Select CITY LETTINGS RENT/ }).check();
    await page.getByRole('button', { name: 'Discard the selected' }).click();
    await expect(page.getByRole('alertdialog', { name: 'Discard these?' })).toBeVisible();
    await axe(page);
    await page.keyboard.press('Escape');
    await page.goto('/console/settings/ai');
    await settled(page);
    await page.getByRole('button', { name: 'Turn MCP off' }).click();
    await expect(page.getByRole('alertdialog', { name: 'Turn MCP off?' })).toBeVisible();
    await axe(page);
    await seen.check();
  });
}

/** Presses Tab until `target` has the focus. */
async function tabTo(page: Page, target: ReturnType<Page['getByRole']>): Promise<void> {
  for (let i = 0; i < 80 && !(await target.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(target).toBeFocused();
}

test('uploads a statement file from the device under the CSP, and Salli reads its bytes', async ({ page }) => {
  const api = new MockApi(ORIGIN);
  const seen = await open(page, '/books/imports', 1280, 'light', api);
  await settled(page);
  const upload = page.getByRole('region', { name: 'Import a statement' });
  await upload.getByLabel('The statement file').setInputFiles({
    name: 'checking-october.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('Date,Description,Amount\n2026-10-07,CORNER BAKERY,-8.40\n'),
  });
  await upload.getByRole('combobox', { name: /The account it is for/ }).selectOption('chk');
  await upload.getByRole('button', { name: 'Import it' }).click();
  await expect(upload.getByText(/Read 5 transactions from Example Bank/)).toBeVisible();
  const sent = api.to('/v1/statements/upload', 'POST');
  expect(sent).toHaveLength(1);
  expect(sent[0]?.body).toContain('filename="checking-october.csv"');
  expect(sent[0]?.body).toContain('2026-10-07,CORNER BAKERY,-8.40');
  await upload.getByRole('link', { name: 'Review them' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Review: Example Bank, Oct 1 – 10, 2026' })).toBeVisible();
  await seen.check();
});

test('reviews by keyboard alone: an account chosen, a selection posted after its confirmation', async ({ page }) => {
  const api = new MockApi(ORIGIN);
  const seen = await open(page, `/books/imports/${STATEMENT}`, 1280, 'light', api);
  await settled(page);
  const queue = page.getByRole('region', { name: 'Waiting for review' });
  const bakery = queue.getByRole('combobox', { name: /Where it went: CORNER BAKERY/ });
  await tabTo(page, bakery);
  await bakery.selectOption('out');
  await expect(queue.getByText(/Kept: CORNER BAKERY now goes to the account you chose\./)).toBeVisible();
  const clean = queue.getByRole('button', { name: 'Select every one that is complete and not a possible duplicate' });
  await tabTo(page, clean);
  await page.keyboard.press('Enter');
  await expect(queue.getByText('2 selected')).toBeVisible();
  await tabTo(page, queue.getByRole('button', { name: 'Post the selected' }));
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('alertdialog', { name: 'Post these to your books?' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Post them' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(queue.getByText(/Posted 2 entries\./)).toBeVisible();
  expect(api.to(`/v1/statements/${STATEMENT}/post`, 'POST')).toHaveLength(1);
  await seen.check();
});

test('activates a proposed version by keyboard alone, after its confirmation', async ({ page }) => {
  const api = new MockApi(ORIGIN);
  const seen = await open(page, `/tax/rules/${SET}/versions/${tax.VERSION_2.id}`, 1280, 'light', api);
  await settled(page);
  await tabTo(page, page.getByRole('button', { name: 'Activate version 2' }));
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('alertdialog', { name: 'Activate version 2?' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Activate it' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByText(/Activated\. Salli computes XA 2031 with version 2\./)).toBeVisible();
  expect(api.to(`/v1/tax/rule-sets/${SET}/versions/${tax.VERSION_2.id}/activate`, 'POST')).toHaveLength(1);
  await seen.check();
});

test('shows a new token once, and keeps it nowhere once the page is left', async ({ page }) => {
  const api = new MockApi(ORIGIN);
  const seen = await open(page, '/settings/tokens', 1280, 'light', api);
  await settled(page);
  const make = page.getByRole('region', { name: 'Make a token' });
  await make.getByRole('textbox', { name: /Its name/ }).fill('Backups again');
  await make.getByRole('button', { name: 'Make the token' }).click();
  await expect(make.getByLabel('Your new token')).toHaveValue(settings.TOKEN_MADE.token);
  // The browser's own clipboard, where the page may use it.
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: ORIGIN });
  await make.getByRole('button', { name: 'Copy it' }).click();
  await expect(make.getByText('Copied.')).toBeVisible();
  await page.getByRole('navigation', { name: 'Settings' }).getByRole('link', { name: 'Profile and sign-ins' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
  const kept = await page.evaluate(() => [document.documentElement.outerHTML, JSON.stringify({ ...sessionStorage }), JSON.stringify({ ...localStorage })].join('\n'));
  expect(kept).not.toContain(settings.TOKEN_MADE.token);
  await seen.check();
});

test('saves the books and everything on the device, under the CSP', async ({ page }) => {
  const seen = await open(page, '/settings/data', 1280, 'light');
  await settled(page);
  const beancount = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save as Beancount' }).click();
  const plain = await beancount;
  expect(plain.suggestedFilename()).toBe('salli-2026-10-11.beancount');
  expect(Buffer.concat(await (await plain.createReadStream()).toArray()).toString('utf8')).toBe(settings.BEANCOUNT);
  const json = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save all of it (JSON)' }).click();
  const all = await json;
  expect(all.suggestedFilename()).toBe('salli-2026-10-11.json');
  expect(Buffer.concat(await (await all.createReadStream()).toArray()).toString('utf8')).toContain('"amount": "9007199254740993.01"');
  const version = page.waitForEvent('download');
  await page.goto(`/console/tax/rules/${SET}/versions/${tax.VERSION_2.id}`);
  await settled(page);
  await page.getByRole('button', { name: 'Save it on this device' }).click();
  expect((await version).suggestedFilename()).toBe(tax.EXPORT_2.filename);
  await seen.check();
});
