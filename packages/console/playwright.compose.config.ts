/**
 * The console end to end against compose.yaml (decision 25), as image.yml
 * starts it: the real sign-in page, Home, revoking a sign-in, the step-up,
 * signing out and the idle timer. The server is SALLI_E2E_URL (default
 * http://localhost:8000, compose's SALLI_PUBLIC_URL); the owner, set up
 * with `salli-server setup`, is SALLI_E2E_EMAIL and SALLI_E2E_PASSWORD.
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: 'e2e',
  testMatch: 'compose.spec.ts',
  outputDir: 'test-results/compose',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-compose' }]] : 'list',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.SALLI_E2E_URL ?? 'http://localhost:8000',
    locale: 'en-US',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'compose' }],
});
