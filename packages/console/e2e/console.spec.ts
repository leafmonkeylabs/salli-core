/**
 * Every page of C1 in a real browser, under the server's CSP, on the
 * golden household's fixtures: axe finds nothing, the page looks as it did
 * (at 360, 768 and 1280 px, light and dark), no CSP or Trusted Types
 * violation is reported, and nothing is requested from another origin.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { mockSalli } from './fixtures';
import { watch, type Watch } from './watch';

const WIDTHS = [360, 768, 1280] as const;
const THEMES = ['light', 'dark'] as const;
/** The golden household's date, so "this month" is its October. */
const TODAY = new Date('2026-10-11T10:00:00Z');

const origin = (page: Page): string => new URL(page.url() === 'about:blank' ? 'http://localhost:4173' : page.url()).origin;

async function open(page: Page, width: number, theme: (typeof THEMES)[number]): Promise<Watch> {
  await page.setViewportSize({ width, height: width < 768 ? 800 : 900 });
  await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
  await page.clock.setFixedTime(TODAY);
  const seen = await watch(page, 'http://localhost:4173');
  await mockSalli(page, 'http://localhost:4173');
  await page.goto('/console/');
  await expect(page.getByRole('heading', { level: 1, name: 'Home' })).toBeVisible();
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

for (const theme of THEMES) {
  for (const width of WIDTHS) {
    test.describe(`${width} px, ${theme}`, () => {
      test('Home', async ({ page }) => {
        const seen = await open(page, width, theme);
        await expect(page.getByRole('region', { name: 'Net worth', exact: true }).getByText('EUR 344,026.47')).toBeVisible();
        await settled(page);
        await axe(page);
        await expect(page).toHaveScreenshot(`home-${width}-${theme}.png`, { fullPage: true });
        // The figures behind the chart, opened.
        await page.getByRole('button', { name: 'Show the figures' }).click();
        await axe(page);
        await seen.check();
      });

      test('Settings', async ({ page }) => {
        const seen = await open(page, width, theme);
        // On a phone, Settings is under More (the bar holds five places).
        const places = page.getByRole('navigation', { name: 'Places' }).filter({ visible: true });
        if (width < 721) {
          await places.getByRole('link', { name: 'More' }).click();
          await page.getByRole('main').getByRole('link', { name: 'Settings' }).click();
        } else {
          await places.getByRole('link', { name: 'Settings' }).click();
        }
        await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
        await expect(page.getByRole('textbox', { name: 'Name' })).toHaveValue('Ana');
        await settled(page);
        await axe(page);
        await expect(page).toHaveScreenshot(`settings-${width}-${theme}.png`, { fullPage: true });
        // The confirmation before ending a sign-in: hidden until asked for.
        await expect(page.getByRole('alertdialog')).toBeHidden();
        await page.getByRole('button', { name: /Sign out salli command/ }).click();
        await expect(page.getByRole('alertdialog')).toBeVisible();
        await axe(page);
        await expect(page).toHaveScreenshot(`settings-confirm-${width}-${theme}.png`);
        await page.getByRole('button', { name: 'Cancel' }).click();
        await seen.check();
      });

      test('signed out', async ({ page }) => {
        const seen = await open(page, width, theme);
        await settled(page);
        await page.getByRole('button', { name: 'Sign out', exact: true }).click();
        await expect(page.getByRole('heading', { name: 'Signed out' })).toBeVisible();
        await axe(page);
        await expect(page).toHaveScreenshot(`signed-out-${width}-${theme}.png`);
        await seen.check();
      });
    });
  }
}

test('the server’s CSP is on every page the console serves', async ({ page, request }) => {
  for (const path of ['/console/', '/console/settings', '/console/callback']) {
    const response = await request.get(path);
    expect(response.headers()['content-security-policy']).toContain("require-trusted-types-for 'script'");
  }
  const seen = await open(page, 1280, 'light');
  await seen.check();
  // The page really is under Trusted Types with no policy: an HTML sink throws.
  const refused = await page.evaluate(() => {
    try {
      document.createElement('div').innerHTML = '<b>x</b>';
      return false;
    } catch {
      return true;
    }
  });
  expect(refused).toBe(true);
  expect(origin(page)).toBe('http://localhost:4173');
});

test('motion: short fades when allowed, none when reduced', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.clock.setFixedTime(TODAY);
  await mockSalli(page, 'http://localhost:4173');
  await page.goto('/console/');
  const page_ = page.locator('.page');
  await expect(page_).toBeVisible();
  const moving = await page_.evaluate((el) => getComputedStyle(el).animationDuration);
  expect(moving).toBe('0.16s');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const still = await page_.evaluate((el) => getComputedStyle(el).animationDuration);
  expect(still).toBe('0s');
});

test('the keyboard reaches everything, starting with a skip link', async ({ page }) => {
  await open(page, 1280, 'light');
  await settled(page);
  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: 'Skip to the page' });
  await expect(skip).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
});
