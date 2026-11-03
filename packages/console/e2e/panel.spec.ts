/**
 * A page the server describes (`/console/panel/<id>`, `salli.panel/1`) in a
 * real browser under the server's CSP: axe finds nothing on the page, with
 * the confirmation open, or with a refusal shown; no CSP or Trusted Types
 * violation is reported; nothing is requested from another origin. (No
 * screenshot: the page is the kit's rows, which the other pages' shots hold.)
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { MockApi } from '../test/fixtures/api';
import { PanelsState } from '../test/fixtures/panels';
import { mockSalli } from './fixtures';
import { watch } from './watch';

const ORIGIN = 'http://localhost:4173';

async function axe(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const theme of ['light', 'dark'] as const) {
  for (const width of [360, 1280] as const) {
    test(`a panel, ${width} px, ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
      const seen = await watch(page, ORIGIN);
      const api = new MockApi(ORIGIN);
      api.panels = new PanelsState();
      await mockSalli(page, ORIGIN, api);
      await page.goto('/console/panel/account');
      await expect(page.getByRole('heading', { level: 1, name: 'Your account' })).toBeVisible();
      await page.waitForLoadState('networkidle');
      await axe(page);
      await page.getByRole('button', { name: 'Ask for more room' }).click();
      await expect(page.getByRole('alertdialog')).toBeVisible();
      await axe(page);
      await page.getByRole('button', { name: 'Not now' }).click();
      await page.getByRole('button', { name: 'Send' }).click();
      await expect(page.getByText('Required')).toBeVisible();
      await axe(page);
      await seen.check();
    });
  }
}
