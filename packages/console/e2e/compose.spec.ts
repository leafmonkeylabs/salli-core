/**
 * The console end to end, against compose.yaml (decision 25): sign in on
 * Salli's own page, see Home, end another sign-in, sign out, be signed out
 * when idle (with a short limit), and weigh a decision in the decision lab:
 * a template run, the decision recorded after its confirmation, found in
 * the journal, a note added; where you stand: an entry added, seen in the
 * ledger and its account, reversed after confirming; an FI assumption set
 * and cleared; and books, tax and settings (C4): a rule made, a CSV
 * statement imported, reviewed and posted, its entries found in the
 * ledger; a token made and revoked; MCP turned off and on; and a tax rule
 * set activated through a real step-up. Every page is loaded, and checked
 * for CSP violations and requests to another origin.
 *
 * The step-up is the server's own: a console sign-in holds tax:activate
 * only within five minutes of its password check (decision 6), and no
 * setting shortens that, so the test waits the five minutes out. Then
 * Salli answers activating with `/problems/step-up-required`, its sign-in
 * page asks the same person again, the console swaps its grant, and the
 * activation runs on return.
 */
import { readFileSync } from 'node:fs';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
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

// ── Books, tax and settings (C4) ─────────────────────────────────────────

async function api<T>(request: APIRequestContext, token: string, method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, data?: unknown): Promise<T> {
  const response = await request.fetch(path, { method, headers: { Authorization: `Bearer ${token}` }, ...(data === undefined ? {} : { data }) });
  expect(response.ok(), `${method} ${path}: ${response.status()}`).toBe(true);
  return (response.status() === 204 ? undefined : await response.json()) as T;
}

test('makes a rule, imports a CSV statement, reviews it, posts it after confirming, and finds the entries in the ledger', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const stamp = Date.now().toString(36);
  const wallet = await addAccount(request, token, { code: `C${stamp}`, name: `Current ${stamp}`, type: 'asset' });
  const groceries = await addAccount(request, token, { code: `G${stamp}`, name: `Groceries ${stamp}`, type: 'expense' });
  const bakery = await addAccount(request, token, { code: `B${stamp}`, name: `Bakery ${stamp}`, type: 'expense' });
  await signIn(page);

  // A rule first: what it decides needs no model (compose has none).
  await page.goto('/console/books/rules');
  const form = page.getByRole('region', { name: 'Add a rule' });
  await form.getByRole('textbox', { name: /Its name/ }).fill(`Market ${stamp}`);
  await form.getByRole('textbox', { name: /^Value/ }).fill(`MARKET ${stamp.toUpperCase()}`);
  await form.getByRole('combobox', { name: /Where the other side goes/ }).selectOption(groceries);
  await form.getByRole('button', { name: 'Save the rule' }).click();
  await expect(page.getByText(`Saved: Market ${stamp}.`)).toBeVisible();

  // The statement, uploaded from this device for the new account.
  await page.goto('/console/books/imports');
  const upload = page.getByRole('region', { name: 'Import a statement' });
  await upload.getByLabel('The statement file').setInputFiles({
    name: `statement-${stamp}.csv`,
    mimeType: 'text/csv',
    buffer: Buffer.from(`Date,Description,Amount\n2026-10-07,MARKET ${stamp.toUpperCase()},-46.20\n2026-10-08,CORNER BAKERY ${stamp.toUpperCase()},-8.40\n`),
  });
  await upload.getByRole('combobox', { name: /The account it is for/ }).selectOption(wallet);
  await upload.getByRole('button', { name: 'Import it' }).click();
  await expect(upload.getByText(/Read 2 transactions from .* Nothing is booked yet\./)).toBeVisible();
  // Nothing booked yet.
  expect((await api<{ transactions: unknown[] }>(request, token, 'GET', `/v1/accounts/${wallet}/overview`)).transactions).toHaveLength(0);
  await upload.getByRole('link', { name: 'Review them' }).click();

  const queue = page.getByRole('region', { name: 'Waiting for review' });
  const market = queue.getByRole('listitem').filter({ hasText: `MARKET ${stamp.toUpperCase()}` });
  await expect(market.getByText(`Proposed by your rule “Market ${stamp}”`)).toBeVisible();
  await queue.getByRole('combobox', { name: new RegExp(`Where it went: CORNER BAKERY ${stamp.toUpperCase()}`) }).selectOption(bakery);
  await expect(queue.getByText(/Kept: CORNER BAKERY .* now goes to the account you chose\./)).toBeVisible();
  await queue.getByRole('button', { name: 'Select every one that is complete and not a possible duplicate' }).click();
  await expect(queue.getByText('2 selected')).toBeVisible();
  await queue.getByRole('button', { name: 'Post the selected' }).click();
  await page.getByRole('alertdialog', { name: 'Post these to your books?' }).getByRole('button', { name: 'Post them' }).click();
  await expect(queue.getByText(/Posted 2 entries\./)).toBeVisible();
  await expect(queue.getByText('Nothing in this statement waits for review.')).toBeVisible();

  // In the ledger: both entries, on the statement's account.
  await queue.getByRole('link', { name: 'See them in your books' }).click();
  const entries = page.getByRole('region', { name: 'Entries' });
  await expect(entries.getByText('2 entries')).toBeVisible();
  await expect(entries.getByRole('link', { name: `MARKET ${stamp.toUpperCase()}` })).toBeVisible();
  await expect(entries.getByRole('link', { name: `CORNER BAKERY ${stamp.toUpperCase()}` })).toBeVisible();
  await page.goto(`/console/books/accounts/${wallet}`);
  await expect(page.getByRole('region', { name: 'Balance' }).getByText('EUR -54.60').first()).toBeVisible();
  await seen.check();
});

test('makes a personal access token, sees it once, and revokes it after confirming', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const name = `Script ${Date.now().toString(36)}`;
  await signIn(page);
  await page.goto('/console/settings/tokens');
  const make = page.getByRole('region', { name: 'Make a token' });
  await make.getByRole('textbox', { name: /Its name/ }).fill(name);
  await make.getByRole('button', { name: 'Make the token' }).click();
  const shown = make.getByLabel('Your new token');
  await expect(shown).toHaveValue(/^salli_pat_/);
  const secret = await shown.inputValue();
  // It works, as the server's own.
  const me = await request.get('/v1/auth/me', { headers: { Authorization: `Bearer ${secret}` } });
  expect(me.ok()).toBe(true);
  await make.getByRole('button', { name: 'I have copied it' }).click();
  expect(await page.content()).not.toContain(secret);

  const row = page.getByRole('region', { name: 'Your tokens' }).getByRole('row').filter({ hasText: name });
  await row.getByRole('button', { name: `Revoke ${name}` }).click();
  await page.getByRole('alertdialog', { name: 'Revoke this token?' }).getByRole('button', { name: 'Revoke it' }).click();
  await expect(page.getByText(`Revoked: ${name}.`)).toBeVisible();
  expect((await request.get('/v1/auth/me', { headers: { Authorization: `Bearer ${secret}` } })).status()).toBe(401);
  expect((await api<Array<{ name: string }>>(request, token, 'GET', '/v1/tokens')).map((t) => t.name)).not.toContain(name);
  await seen.check();
});

test('turns MCP off after confirming, and on again', async ({ page, request, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  await signIn(page);
  await page.goto('/console/settings/ai');
  const mcp = page.getByRole('region', { name: 'MCP' });
  // An owner starts with MCP off: on first, at once.
  if (!(await api<{ enabled: boolean }>(request, token, 'GET', '/v1/mcp/connections/enabled')).enabled) {
    await mcp.getByRole('button', { name: 'Turn MCP on' }).click();
    await expect(mcp.getByText(/MCP is on\./)).toBeVisible();
  }
  await mcp.getByRole('button', { name: 'Turn MCP off' }).click();
  await page.getByRole('alertdialog', { name: 'Turn MCP off?' }).getByRole('button', { name: 'Turn it off' }).click();
  await expect(mcp.getByText(/MCP is off\./)).toBeVisible();
  expect((await api<{ enabled: boolean }>(request, token, 'GET', '/v1/mcp/connections/enabled')).enabled).toBe(false);
  await mcp.getByRole('button', { name: 'Turn MCP on' }).click();
  await expect(mcp.getByText(/MCP is on\./)).toBeVisible();
  expect((await api<{ enabled: boolean }>(request, token, 'GET', '/v1/mcp/connections/enabled')).enabled).toBe(true);
  await seen.check();
});

/** The fictional rules XA 2031 (tests/golden/rules/xa2031.json), as a new version of the owner's XA 2031, proposed. */
async function proposeXa(request: APIRequestContext, token: string, note: string): Promise<{ set: string; version: string; number: number }> {
  const document = readFileSync(new URL('../../../tests/golden/rules/xa2031.json', import.meta.url), 'utf8');
  const sets = await api<Array<{ id: string; country: string; year_label: string }>>(request, token, 'GET', '/v1/tax/rule-sets');
  const existing = sets.find((s) => s.country === 'XA' && s.year_label === '2031');
  const made = existing
    ? await api<{ id: string; rule_set_id: string; version: number }>(request, token, 'POST', `/v1/tax/rule-sets/${existing.id}/versions`, { document, note })
    : await api<{ id: string; rule_set_id: string; version: number }>(request, token, 'POST', '/v1/tax/rule-sets', { document, note });
  await api(request, token, 'POST', `/v1/tax/rule-sets/${made.rule_set_id}/versions/${made.id}/propose`);
  return { set: made.rule_set_id, version: made.id, number: made.version };
}

test('activates a tax rule set through a real step-up: five minutes after the password, Salli asks again', async ({ page, request, baseURL }) => {
  test.setTimeout(9 * 60_000);
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  const token = await session(request);
  const consoleIds = async (): Promise<string[]> => (await signIns(request, token)).filter((s) => s.kind === 'console').map((s) => s.id);
  const note = `For the step-up, ${Date.now().toString(36)}`;
  const xa = await proposeXa(request, token, note);
  const others = await consoleIds();
  await signIn(page);
  const signedInAt = Date.now();
  const mine = (await consoleIds()).filter((id) => !others.includes(id));
  expect(mine).toHaveLength(1);

  // The review, while the sign-in is fresh.
  await page.goto(`/console/tax/rules/${xa.set}/versions/${xa.version}`);
  await expect(page.getByRole('heading', { level: 1, name: `XA 2031, version ${xa.number}` })).toBeVisible();
  await expect(page.getByText(`“${note}”`)).toBeVisible();
  await expect(page.getByRole('region', { name: 'Worked examples' }).getByText('Passes')).toHaveCount(4);
  await expect(page.getByRole('region', { name: 'Activating' }).getByText(/Only a person activates tax rules, never an AI/)).toBeVisible();

  // Past the five minutes the console's sign-in holds tax:activate for.
  await page.waitForTimeout(Math.max(0, signedInAt + 305_000 - Date.now()));
  // A key or a click keeps the console from its idle sign-out, which is 30 minutes anyway.
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: `XA 2031, version ${xa.number}` })).toBeVisible();

  const answers: number[] = [];
  page.on('response', (response) => {
    if (response.request().method() === 'POST' && response.url().endsWith(`/versions/${xa.version}/activate`)) answers.push(response.status());
  });
  const activating = page.getByRole('region', { name: 'Activating' });
  await activating.getByRole('button', { name: `Activate version ${xa.number}` }).click();
  await page.getByRole('alertdialog', { name: `Activate version ${xa.number}?` }).getByRole('button', { name: 'Activate it' }).click();

  // Salli's own page asks the same person to confirm it's them.
  await signInOnSallisPage(page, "Confirm it's you", 'Continue');
  await expect(page.getByRole('heading', { level: 1, name: `XA 2031, version ${xa.number}` })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe(`/console/tax/rules/${xa.set}/versions/${xa.version}`);
  await expect(page.getByText(`Activated. Salli computes XA 2031 with version ${xa.number}.`)).toBeVisible();
  // The server refused once with its step-up answer, then activated on the retry.
  expect(answers).toEqual([403, 200]);
  const version = await api<{ status: string; author_kind: string }>(request, token, 'GET', `/v1/tax/rule-sets/${xa.set}/versions/${xa.version}`);
  expect(version.status).toBe('active');

  // This tab's grant was swapped for the new one: the old one is revoked.
  const now = (await consoleIds()).filter((id) => !others.includes(id));
  expect(now).toHaveLength(1);
  expect(now).not.toContain(mine[0]);

  // Just after the password, a token that may activate is made at once, shown once, and revoked.
  await page.goto('/console/settings/tokens');
  const make = page.getByRole('region', { name: 'Make a token' });
  const name = `Tax helper ${Date.now().toString(36)}`;
  await make.getByRole('textbox', { name: /Its name/ }).fill(name);
  await make.getByRole('checkbox', { name: /It may activate tax rules/ }).check();
  await make.getByRole('button', { name: 'Make the token' }).click();
  await page.getByRole('alertdialog', { name: 'Make a token that may activate tax rules?' }).getByRole('button', { name: 'Make it' }).click();
  await expect(make.getByLabel('Your new token')).toHaveValue(/^salli_pat_/);
  const row = page.getByRole('region', { name: 'Your tokens' }).getByRole('row').filter({ hasText: name });
  await expect(row.getByText('Read and write your data, and activate tax rules')).toBeVisible();
  await row.getByRole('button', { name: `Revoke ${name}` }).click();
  await page.getByRole('alertdialog', { name: 'Revoke this token?' }).getByRole('button', { name: 'Revoke it' }).click();
  await expect(page.getByText(`Revoked: ${name}.`)).toBeVisible();
  await seen.check();
});

test('every page of books, tax and settings loads from the real server, with no problem shown', async ({ page, baseURL }) => {
  const seen = await watch(page, new URL(baseURL ?? '').origin);
  await signIn(page);
  for (const [path, heading] of [
    ['/console/books/imports', 'Imports'],
    ['/console/books/rules', 'Rules'],
    ['/console/tax', 'Tax'],
    ['/console/settings/tokens', 'Personal access tokens'],
    ['/console/settings/ai', 'AI connections'],
    ['/console/settings/digests', 'Digests'],
    ['/console/settings/data', 'Your data'],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.locator('.loading')).toHaveCount(0);
    await expect(page.locator('.problem')).toHaveCount(0);
  }
  await seen.check();
});
