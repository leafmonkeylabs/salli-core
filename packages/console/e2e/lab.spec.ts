/**
 * The decision lab (C3) in a real browser, under the server's CSP, on the
 * golden household's fixtures: axe finds nothing, each page looks as it did
 * at 360, 768 and 1280 px in light and dark, no CSP or Trusted Types
 * violation is reported and nothing is asked of another origin. Then, by
 * keyboard alone: a template answered and run, the decision recorded after
 * its confirmation, the journal's export saved on the device.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { MockApi } from '../test/fixtures/api';
import * as lab from '../test/fixtures/lab';
import { mockSalli } from './fixtures';
import { watch, type Watch } from './watch';

const ORIGIN = 'http://localhost:4173';
const WIDTHS = [360, 768, 1280] as const;
const THEMES = ['light', 'dark'] as const;
const TODAY = new Date('2026-10-11T10:00:00Z');
const LAPTOP = lab.DECISION.id;
const AUGUST = lab.DECISION_DUE.id;

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

/** Afford it, answered as the laptop was, and run. */
async function runAffordIt(page: Page): Promise<void> {
  const form = page.getByRole('region', { name: 'Your answers' });
  await form.getByRole('textbox', { name: 'What does it cost?' }).fill('2400');
  await form.getByRole('textbox', { name: /What is it\?/ }).fill('Laptop');
  await form.getByRole('textbox', { name: /Over how many months\?/ }).fill('12');
  await form.getByRole('textbox', { name: 'At what yearly rate?' }).fill('6.9%');
  await form.getByRole('button', { name: 'Build and compare the options' }).click();
  await expect(page.getByRole('heading', { name: 'What Salli built' })).toBeVisible();
}

const PAGES: Array<{ name: string; path: string; heading: string; act?: (page: Page) => Promise<void> }> = [
  { name: 'lab', path: '/decide', heading: 'Decide' },
  { name: 'lab-baseline', path: '/decide/baseline', heading: 'Baseline' },
  { name: 'lab-templates', path: '/decide/templates', heading: 'Templates' },
  { name: 'lab-template', path: '/decide/templates/rent-or-buy', heading: 'Rent or buy' },
  { name: 'lab-template-result', path: '/decide/templates/afford-it', heading: 'Afford it', act: runAffordIt },
  {
    name: 'lab-scenarios',
    path: '/decide/scenarios',
    heading: 'Scenarios',
    act: async (page) => {
      await page.getByRole('button', { name: 'Add an option' }).click();
      await page.getByRole('button', { name: 'Compare the 2 options' }).click();
      await expect(page.getByRole('heading', { name: 'The options compared' })).toBeVisible();
    },
  },
  { name: 'lab-principles', path: '/decide/principles', heading: 'Principles' },
  { name: 'lab-journal', path: '/decide/journal', heading: 'Journal' },
  { name: 'lab-entry', path: `/decide/journal/${LAPTOP}`, heading: 'Laptop: pay cash, spread it or wait?' },
  { name: 'lab-review', path: `/decide/journal/${AUGUST}`, heading: 'Change anything?' },
];

for (const theme of THEMES) {
  for (const width of WIDTHS) {
    test.describe(`${width} px, ${theme}`, () => {
      for (const p of PAGES) {
        test(p.name, async ({ page }) => {
          // A year of days and thirty years of months, opened as tables, take axe a while.
          test.setTimeout(120_000);
          const seen = await open(page, p.path, width, theme);
          await expect(page.getByRole('heading', { level: 1, name: p.heading })).toBeVisible();
          if (p.act) await p.act(page);
          await settled(page);
          // Nothing wider than the screen: the page never scrolls sideways.
          expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
          await axe(page);
          await expect(page).toHaveScreenshot(`${p.name}-${width}-${theme}.png`, { fullPage: true });
          // Each chart's figures, opened, are accessible too.
          const show = page.getByRole('button', { name: 'Show the figures' });
          while ((await show.count()) > 0) await show.first().click();
          await axe(page);
          await seen.check();
        });
      }
    });
  }
}

test('records a decision by keyboard alone, after its confirmation', async ({ page }) => {
  const api = new MockApi(ORIGIN);
  api.lab.withoutLaptop();
  const seen = await open(page, '/decide/templates/afford-it', 1280, 'light', api);
  await expect(page.getByRole('heading', { level: 1, name: 'Afford it' })).toBeVisible();
  await settled(page);
  // Into the form, by Tab only.
  const price = page.getByRole('textbox', { name: 'What does it cost?' });
  for (let i = 0; i < 40 && !(await price.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(price).toBeFocused();
  await page.keyboard.type('2400');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'What Salli built' })).toBeVisible();
  const record = page.getByRole('region', { name: 'Record what you choose' });
  await record.getByRole('button', { name: 'Record a decision' }).focus();
  await page.keyboard.press('Enter');
  const chosen = record.getByRole('radio', { name: 'Pay cash' });
  await chosen.focus();
  await page.keyboard.press('Space');
  await expect(chosen).toBeChecked();
  await record.getByRole('textbox', { name: /Why\? In your own words/ }).focus();
  await page.keyboard.type('The old one is failing.');
  await record.getByLabel(/When do you want to look back on it\?/).fill('2027-04-30');
  await record.getByRole('button', { name: 'Record it' }).focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('alertdialog', { name: 'Record this decision?' });
  await expect(dialog).toBeVisible();
  // Focus starts on Cancel, inside the dialog; Tab moves to Record.
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Record' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(record.getByText(/Recorded\. Salli will remind you to review it on Apr 30, 2027\./)).toBeVisible();
  expect(api.to('/v1/decisions', 'POST')).toHaveLength(1);
  await record.getByRole('link', { name: 'Open it in your journal' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: /Can I afford Laptop/ })).toBeVisible();
  await seen.check();
});

test('saves the journal on the device, under the CSP', async ({ page }) => {
  const seen = await open(page, '/decide/journal', 1280, 'light');
  await settled(page);
  const json = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save as JSON' }).click();
  const file = await json;
  expect(file.suggestedFilename()).toBe('salli-decisions-2026-10-11.json');
  const text = await (await file.createReadStream()).toArray();
  expect(JSON.parse(Buffer.concat(text).toString('utf8'))).toMatchObject({ schema: 'salli.decision-journal/1' });
  const md = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save as Markdown' }).click();
  expect((await md).suggestedFilename()).toBe('salli-decisions-2026-10-11.md');
  await seen.check();
});
