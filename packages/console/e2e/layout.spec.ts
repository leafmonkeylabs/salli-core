/**
 * No page scrolls sideways, at the widths people use: a phone (360, 390), a
 * tablet (768), a laptop (1280) and a wide screen (1830), on the golden
 * household's fixtures. Wide tables and charts scroll inside their own
 * boxes, never the page.
 */
import { expect, test } from '@playwright/test';
import { MockApi } from '../test/fixtures/api';
import * as books from '../test/fixtures/books';
import * as tax from '../test/fixtures/tax';
import { mockSalli } from './fixtures';

const WIDTHS = [360, 390, 768, 1280, 1830] as const;
const TODAY = new Date('2026-10-11T10:00:00Z');
const ROUTES = [
  '/',
  '/cash',
  '/books',
  '/books/entries',
  '/books/entries/new',
  '/books/imports',
  `/books/imports/${books.STATEMENTS.statements[0]?.id ?? ''}`,
  '/books/rules',
  '/books/accounts/chk',
  '/decide',
  '/decide/templates',
  '/decide/templates/afford-it',
  '/decide/scenarios',
  '/decide/principles',
  '/decide/journal',
  '/decide/baseline',
  '/tax',
  `/tax/rules/${tax.RULE_SETS[0]?.id ?? ''}`,
  '/attention',
  '/fi',
  '/more',
  '/settings',
  '/settings/tokens',
  '/settings/ai',
  '/settings/digests',
  '/settings/data',
];

for (const theme of ['light', 'dark'] as const) {
  for (const width of WIDTHS) {
    test(`no page scrolls sideways at ${width} px, ${theme}`, async ({ page }) => {
      test.setTimeout(120_000);
      await page.clock.setFixedTime(TODAY);
      await mockSalli(page, 'http://localhost:4173', new MockApi('http://localhost:4173'));
      await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
      await page.setViewportSize({ width, height: 900 });
      const wide: string[] = [];
      for (const route of ROUTES) {
        await page.goto(`/console${route}`);
        await page.waitForLoadState('networkidle');
        await expect(page.locator('h1').first()).toBeVisible();
        const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (over > 0) wide.push(`${route}: ${over} px`);
      }
      expect(wide).toEqual([]);
    });
  }
}
