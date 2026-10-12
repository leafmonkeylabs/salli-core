/**
 * The console end to end, against compose.yaml (decision 25): sign in on
 * Salli's own page, see Home, end another sign-in, go through the step-up,
 * sign out, and be signed out when idle (with a short limit). Every page is
 * checked for CSP violations and requests to another origin.
 *
 * The server's real step-up answer comes only from activating tax rules or
 * minting a token that may, which C1's pages don't do; so the step-up run
 * makes Salli's first answer to one profile save the server's own
 * `/problems/step-up-required` problem, and everything after it (the
 * sign-in page asking again, the grants, the retry) is the real server's.
 */
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { STEP_UP } from '../test/fixtures/api';
import { watch } from './watch';

const EMAIL = process.env.SALLI_E2E_EMAIL ?? '';
const PASSWORD = process.env.SALLI_E2E_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'Set SALLI_E2E_EMAIL and SALLI_E2E_PASSWORD (an owner made with salli-server setup).');

async function signInOnSallisPage(page: Page, heading: string | RegExp = 'Sign in to Salli', button = 'Sign in'): Promise<void> {
  await expect(page.getByRole('heading', { name: heading })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/mcp/oauth/consent-page');
  await page.getByLabel('Email').fill(EMAIL);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: button }).click();
}

async function signIn(page: Page): Promise<void> {
  await page.goto('/console/');
  await signInOnSallisPage(page);
  await expect(page.getByRole('heading', { level: 1, name: 'Home' })).toBeVisible();
}

/** A session for the API, as an app or a script would make one. */
async function session(request: APIRequestContext): Promise<string> {
  const response = await request.post('/v1/auth/sessions', { data: { email: EMAIL, password: PASSWORD } });
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { token: string }).token;
}

async function signIns(request: APIRequestContext, token: string): Promise<Array<{ id: string; kind: string; current: boolean }>> {
  const response = await request.get('/v1/auth/sign-ins', { headers: { Authorization: `Bearer ${token}` } });
  expect(response.ok()).toBe(true);
  return (await response.json()) as Array<{ id: string; kind: string; current: boolean }>;
}

test('signs in through Salli’s own page, and sees Home', async ({ page, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  await signIn(page);
  await expect(page.getByRole('region', { name: 'Net worth', exact: true }).locator('.money').first()).toBeVisible();
  await expect(page.locator('.loading')).toHaveCount(0);
  // A reload keeps the sign-in.
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: 'Home' })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/console/');
  const response = await page.request.get('/console/');
  expect(response.headers()['content-security-policy']).toContain("trusted-types 'none'");
  await seen.check();
});

test('ends another sign-in from Settings', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  await signIn(page);
  await page.getByRole('navigation', { name: 'Places' }).filter({ visible: true }).getByRole('link', { name: 'Settings' }).click();
  const table = page.getByRole('region', { name: 'Sign-ins' }).getByRole('table');
  const row = table.getByRole('row').filter({ hasText: 'Session' }).first();
  await row.getByRole('button', { name: /Sign out Session/ }).click();
  await page.getByRole('alertdialog').getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('region', { name: 'Sign-ins' }).getByText(/Signed out\./)).toBeVisible();
  // The session no longer works.
  const me = await request.get('/v1/auth/me', { headers: { Authorization: `Bearer ${token}` } });
  expect(me.status()).toBe(401);
  await seen.check();
});

test('asks for the password again, keeps the person’s place and retries the save once', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const consoleIds = async (): Promise<string[]> => (await signIns(request, token)).filter((s) => s.kind === 'console').map((s) => s.id);
  const others = await consoleIds();
  await signIn(page);
  const mine = (await consoleIds()).filter((id) => !others.includes(id));
  expect(mine).toHaveLength(1);
  await page.getByRole('navigation', { name: 'Places' }).filter({ visible: true }).getByRole('link', { name: 'Settings' }).click();

  let refused = 0;
  await page.route('**/v1/onboarding/profile', async (route) => {
    if (route.request().method() === 'PATCH' && refused === 0) {
      refused += 1;
      return route.fulfill({ status: STEP_UP.status, headers: { 'content-type': 'application/problem+json', ...STEP_UP.headers }, body: JSON.stringify(STEP_UP.body) });
    }
    return route.continue();
  });
  const name = `Owner ${Date.now().toString(36)}`;
  await page.getByRole('textbox', { name: 'Name' }).fill(name);
  await page.getByRole('button', { name: 'Save the profile' }).click();

  // Salli's own page, asking the same person to confirm it's them.
  await signInOnSallisPage(page, "Confirm it's you", 'Continue');
  await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/console/settings');
  await expect(page.getByRole('region', { name: 'Profile' }).getByText(/Saved\./)).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Name' })).toHaveValue(name);
  expect(refused).toBe(1);

  // This tab's grant was swapped for the new one: the old one is revoked.
  const now = (await consoleIds()).filter((id) => !others.includes(id));
  expect(now).toHaveLength(1);
  expect(now).not.toContain(mine[0]);
  await seen.check();
});

test('signs out, revoking the grant', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const before = (await signIns(request, token)).filter((s) => s.kind === 'console').length;
  await signIn(page);
  expect((await signIns(request, token)).filter((s) => s.kind === 'console').length).toBe(before + 1);
  await page.getByRole('button', { name: 'Sign out', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Signed out' })).toBeVisible();
  await expect.poll(async () => (await signIns(request, token)).filter((s) => s.kind === 'console').length).toBe(before);
  await seen.check();
});

test('signs out after the idle limit (shortened to 3 seconds here)', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const before = (await signIns(request, token)).filter((s) => s.kind === 'console').length;
  await page.addInitScript(() => window.sessionStorage.setItem('salli-console:idle-seconds', '3'));
  await signIn(page);
  await expect(page.getByText(/signed out after 30 minutes without a key or a click/)).toBeVisible({ timeout: 10_000 });
  // The idle sign-out revoked the grant, as signing out does.
  await expect.poll(async () => (await signIns(request, token)).filter((s) => s.kind === 'console').length).toBe(before);
  await seen.check();
});
