/**
 * The console in a real browser, on fixtures (decision 25): the built
 * console, served as the server serves it (its CSP and headers), with the
 * API answered from the fixtures the server writes. Accessibility (axe) and
 * visual regression at 360, 768 and 1280 px in light and dark, and CSP
 * violations and any request to another origin as failures. Screenshots
 * are made in Playwright's Linux image, as CI makes them (README.md).
 *
 * End to end against compose.yaml is playwright.compose.config.ts.
 */
import { defineConfig, devices } from '@playwright/test';

const PORT = 4173;

export default defineConfig({
  testDir: 'e2e',
  testMatch: ['console.spec.ts', 'lab.spec.ts'],
  outputDir: 'test-results/fixtures',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]] : 'list',
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.001, animations: 'disabled', caret: 'hide' },
  },
  snapshotPathTemplate: '{testDir}/screenshots/{arg}{ext}',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://localhost:${PORT}`,
    locale: 'en-US',
    timezoneId: 'UTC',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'fixtures' }],
  webServer: {
    command: `node e2e/serve.mjs dist ${PORT}`,
    url: `http://localhost:${PORT}/console/`,
    reuseExistingServer: !process.env.CI,
  },
});
