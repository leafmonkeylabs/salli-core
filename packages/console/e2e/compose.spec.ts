/**
 * The console end to end, against compose.yaml (decision 25): sign in on
 * Salli's own page, see Home, end another sign-in, go through the step-up,
 * sign out, be signed out when idle (with a short limit), and weigh a
 * decision in the decision lab: a template run, the decision recorded after
 * its confirmation, found in the journal, a note added; and where you
 * stand: an entry added, seen in the ledger and its account, reversed
 * after confirming; an FI assumption set and cleared; every C2 page
 * loaded. Every page is checked for CSP violations and requests to
 * another origin.
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

test('weighs a decision with a template, records it after confirming, and adds a note in the journal', async ({ page, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  await signIn(page);
  await page.getByRole('navigation', { name: 'Places' }).filter({ visible: true }).getByRole('link', { name: 'Decide' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Decide' })).toBeVisible();
  await page.getByRole('link', { name: 'Afford it' }).click();
  const form = page.getByRole('region', { name: 'Your answers' });
  await form.getByRole('textbox', { name: 'What does it cost?' }).fill('2400');
  await form.getByRole('textbox', { name: /What is it\?/ }).fill('Laptop');
  await form.getByRole('textbox', { name: /Over how many months\?/ }).fill('12');
  await form.getByRole('textbox', { name: 'At what yearly rate?' }).fill('6.9%');
  await form.getByRole('button', { name: 'Build and compare the options' }).click();
  await expect(page.getByRole('heading', { name: 'What Salli built' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Side by side' }).getByRole('table')).toBeVisible();

  const record = page.getByRole('region', { name: 'Record what you choose' });
  await record.getByRole('button', { name: 'Record a decision' }).click();
  const question = `Laptop ${Date.now().toString(36)}: pay cash or spread it?`;
  await record.getByRole('textbox', { name: 'The question, in your words' }).fill(question);
  await record.getByRole('radio', { name: 'Pay cash' }).check();
  await record.getByRole('textbox', { name: /Why\? In your own words/ }).fill('I would rather not owe anything.');
  // The earliest review the server allows.
  const earliest = await record.getByLabel(/When do you want to look back on it\?/).getAttribute('min');
  await record.getByLabel(/When do you want to look back on it\?/).fill(earliest ?? '');
  await record.getByRole('button', { name: 'Record it' }).click();
  const dialog = page.getByRole('alertdialog', { name: 'Record this decision?' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Record' }).click();
  await expect(record.getByText(/Recorded\. Salli will remind you to review it on/)).toBeVisible();

  await page.getByRole('navigation', { name: 'Decision lab' }).getByRole('link', { name: 'Journal' }).click();
  const entries = page.getByRole('region', { name: 'Entries' });
  await entries.getByRole('link', { name: question }).click();
  await expect(page.getByRole('heading', { level: 1, name: question })).toBeVisible();
  await expect(page.getByText('Unchanged since it was recorded')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Your reasons' }).getByText('I would rather not owe anything.')).toBeVisible();

  const notes = page.getByRole('region', { name: 'Notes' });
  await notes.getByRole('textbox', { name: /The note/ }).fill('Bought it on the day.');
  await notes.getByRole('button', { name: 'Add the note' }).click();
  const confirm = page.getByRole('alertdialog', { name: 'Add this note?' });
  await confirm.getByRole('button', { name: 'Add the note' }).click();
  await expect(confirm).toBeHidden();
  await expect(notes.getByRole('listitem').getByText('Bought it on the day.')).toBeVisible();
  // It is the server's: a reload reads it back.
  await page.reload();
  await expect(page.getByRole('region', { name: 'Notes' }).getByText('Bought it on the day.')).toBeVisible();
  await seen.check();
});

test('every page of the decision lab loads from the real server, with no problem shown', async ({ page, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  await signIn(page);
  for (const [path, heading] of [
    ['/console/decide', 'Decide'],
    ['/console/decide/baseline', 'Baseline'],
    ['/console/decide/templates', 'Templates'],
    ['/console/decide/templates/rent-or-buy', 'Rent or buy'],
    ['/console/decide/scenarios', 'Scenarios'],
    ['/console/decide/principles', 'Principles'],
    ['/console/decide/journal', 'Journal'],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.locator('.loading')).toHaveCount(0);
    await expect(page.locator('.problem')).toHaveCount(0);
  }
  // A scenario run against the real server: both timelines drawn.
  await page.getByRole('navigation', { name: 'Decision lab' }).getByRole('link', { name: 'Scenarios' }).click();
  await page.getByRole('button', { name: 'Run it' }).click();
  await expect(page.getByRole('region', { name: 'Cash, day by day' }).getByRole('img').first()).toBeVisible();
  await expect(page.getByRole('region', { name: 'Net worth, month by month' }).getByRole('img').first()).toBeVisible();
  await seen.check();
});

/** An account of the owner's, made through the API as `salli accounts add` makes one. */
async function addAccount(request: APIRequestContext, token: string, body: { code: string; name: string; type: string }): Promise<string> {
  const response = await request.post('/v1/accounts/', { headers: { Authorization: `Bearer ${token}` }, data: body });
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { id: string }).id;
}

test('adds an entry from one account to another, sees it in the ledger and the balance, and reverses it after confirming', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const stamp = Date.now().toString(36);
  const wallet = await addAccount(request, token, { code: `W${stamp}`, name: `Wallet ${stamp}`, type: 'asset' });
  const lunches = await addAccount(request, token, { code: `L${stamp}`, name: `Lunches ${stamp}`, type: 'expense' });
  await signIn(page);

  await page.goto('/console/books/entries/new');
  const form = page.getByRole('region', { name: 'The entry' });
  await form.getByRole('textbox', { name: /^Description/ }).fill(`Lunch ${stamp}`);
  await form.getByRole('combobox', { name: /^From/ }).selectOption(wallet);
  await form.getByRole('combobox', { name: /^To/ }).selectOption(lunches);
  await form.getByRole('textbox', { name: /^Amount/ }).fill('12.50');
  await form.getByRole('button', { name: 'Post it' }).click();
  const confirm = page.getByRole('alertdialog', { name: 'Post this entry?' });
  await confirm.getByRole('button', { name: 'Post it' }).click();
  await expect(form.getByText(/Posted\./)).toBeVisible();

  // In the ledger, and in the wallet's balance.
  await page.goto(`/console/books/entries?q=${stamp}`);
  const entries = page.getByRole('region', { name: 'Entries' });
  await expect(entries.getByText('1 entry')).toBeVisible();
  await page.goto(`/console/books/accounts/${wallet}`);
  await expect(page.getByRole('region', { name: 'Balance' }).getByText('EUR -12.50')).toBeVisible();
  await page.getByRole('region', { name: 'Its entries' }).getByRole('link', { name: `Lunch ${stamp}` }).click();

  // Reversed after a confirmation; both entries stay.
  const standing = page.getByRole('region', { name: 'Standing' });
  await standing.getByRole('button', { name: 'Reverse this entry' }).click();
  await page.getByRole('alertdialog', { name: 'Reverse this entry?' }).getByRole('button', { name: 'Reverse it' }).click();
  await expect(standing.getByText(/Reversed\. Both entries are in the ledger\./)).toBeVisible();
  await page.goto(`/console/books/entries?q=${stamp}`);
  await expect(entries.getByText('2 entries')).toBeVisible();
  await expect(entries.getByRole('link', { name: `REVERSAL: Lunch ${stamp}` })).toBeVisible();
  await page.goto(`/console/books/accounts/${wallet}`);
  await expect(page.getByRole('region', { name: 'Balance' }).getByText('EUR 0.00')).toBeVisible();
  await seen.check();
});

test('sets an FI assumption with its source, sees its placeholder flag go, and clears it', async ({ page, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  await signIn(page);
  await page.goto('/console/fi');
  const assumptions = page.getByRole('region', { name: 'Assumptions' });
  const real = assumptions.getByRole('listitem').filter({ has: page.getByText('Real return', { exact: true }) });
  await expect(real.locator('.placeholder-tag')).toBeVisible();
  await real.getByRole('button', { name: 'Set your own: Real return' }).click();
  await real.getByRole('textbox', { name: /Real return: Rate/ }).fill('3.5%');
  await real.getByRole('textbox', { name: /Where it comes from/ }).fill('My own long-run view, after inflation');
  await real.getByRole('button', { name: 'Save it' }).click();
  await expect(assumptions.getByText(/Saved: Real return\./)).toBeVisible();
  await expect(real.locator('.placeholder-tag')).toHaveCount(0);
  await expect(real.getByText('You', { exact: true })).toBeVisible();
  await expect(real.getByText('3.5%')).toBeVisible();
  // As it was: the placeholder stands in again.
  await real.getByRole('button', { name: 'Use the placeholder again' }).click();
  await expect(assumptions.getByText(/Cleared: Real return\./)).toBeVisible();
  await expect(real.locator('.placeholder-tag')).toBeVisible();
  await seen.check();
});

test('every page of where you stand loads from the real server, with no problem shown', async ({ page, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  await signIn(page);
  for (const [path, heading] of [
    ['/console/books', 'Books'],
    ['/console/books/entries', 'Entries'],
    ['/console/books/entries/new', 'Add an entry'],
    ['/console/cash', 'Cash'],
    ['/console/attention', 'Attention'],
    ['/console/fi', 'Financial independence'],
    ['/console/more', 'More'],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.locator('.loading')).toHaveCount(0);
    await expect(page.locator('.problem')).toHaveCount(0);
  }
  await seen.check();
});
