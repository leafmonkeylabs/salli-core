/**
 * Where you stand (docs/design/console.md, section 5, C2) on what the real
 * server answers for the golden household (fixtures/where.ts): the books,
 * an entry posted from one account to another and reversed after a
 * confirmation, cash, attention with reminders marked done and deleted,
 * and financial independence with an assumption set. Every figure the
 * server's, shown exactly; every request's amounts decimal strings.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { IdChip } from '../src/kit/chips';
import { MockApi } from './fixtures/api';
import * as where from './fixtures/where';
import { setup } from './harness';

const region = (name: string | RegExp): HTMLElement => screen.getByRole('region', { name });
const bodies = (api: MockApi, path: string, method = 'POST'): Array<Record<string, unknown>> =>
  api.to(path, method).map((r) => JSON.parse(r.body) as Record<string, unknown>);

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

function type(element: HTMLElement, value: string): void {
  fireEvent.change(element, { target: { value } });
}

function choose(element: HTMLElement, value: string): void {
  fireEvent.change(element, { target: { value } });
}

describe('the books', () => {
  it('lists the accounts by type, each balance in the base and a foreign one in its own currency too', async () => {
    await setup({ path: '/console/books' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Books' })).toBeTruthy();
    const assets = await screen.findByRole('region', { name: 'Assets' });
    const dollars = (await within(assets).findByRole('link', { name: /Dollar account/ })).closest('tr') as HTMLElement;
    expect(await within(dollars).findByText('USD 2,500.00')).toBeTruthy();
    expect(within(dollars).getByText('2,275.00')).toBeTruthy();
    // A credit balance in brackets, read out as minus.
    const card = within(region('Liabilities')).getByRole('link', { name: /Credit card/ }).closest('tr') as HTMLElement;
    expect(within(card).getByText('(691.68)')).toBeTruthy();
    expect(within(card).getByText('minus 691.68 euros')).toBeTruthy();
    // The totals are the balance sheet's, as key figures.
    expect(within(screen.getByRole('group', { name: 'Where the books stand' })).getByText('344,026.47')).toBeTruthy();
    // The books' facts: the trial balance's net as the server gave it.
    expect(screen.getByText('Trial balance nets 0.00')).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Books' })).toBeTruthy();
  });

  it('shows an account: its balances, its balance over time and its entries, newest first', async () => {
    await setup({ path: '/console/books/accounts/usd' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Dollar account' })).toBeTruthy();
    const balance = screen.getByRole('group', { name: 'Balance' });
    expect(within(balance).getByText('2,500.00')).toBeTruthy();
    expect(within(balance).getByText('2,500.00 US dollars')).toBeTruthy();
    expect(within(screen.getByRole('group', { name: /^In EUR/ })).getByText('2,275.00')).toBeTruthy();
    const chart = region('Balance over time');
    expect(within(chart).getAllByRole('img')[0]?.getAttribute('aria-label')).toBe('Dollar account’s balance after each day with an entry, from Mar 31, 2026 to Jul 15, 2026. Now USD 2,500.00.');
    await click(within(chart).getByRole('button', { name: 'Show the figures' }));
    expect(within(chart).getByRole('table')).toBeTruthy();
    const rows = within(region('Its entries')).getAllByRole('row');
    expect(rows[1]?.textContent).toContain('TO DOLLAR ACCOUNT');
    expect(rows[2]?.textContent).toContain('Opening balance');
  });

  it('says plainly when an account isn’t there', async () => {
    await setup({ path: '/console/books/accounts/nowhere' });
    expect(await screen.findByRole('heading', { level: 1, name: 'No such account' })).toBeTruthy();
    expect(screen.getByText('Account not found')).toBeTruthy();
  });

  it('narrows the entries by account and words from the address, and by date at the server', async () => {
    const { api } = await setup({ path: '/console/books/entries?account=usd' });
    const list = await screen.findByRole('region', { name: 'Entries' });
    expect(await within(list).findByText('Showing 1–2 of 2 entries')).toBeTruthy();
    expect(within(list).getByRole('link', { name: 'TO DOLLAR ACCOUNT' })).toBeTruthy();
    // The account filter, as a chip that removes it; the button counts it.
    expect(within(list).getByText('1200 Dollar account')).toBeTruthy();
    const filters = within(list).getByRole('button', { name: /^Filters, 1 filter on/ });
    // By date: the server's filter, set in the popover.
    await click(filters);
    const form = within(list).getByRole('search', { name: 'Find entries' });
    type(within(form).getByLabelText('From'), '2026-10-01');
    choose(within(form).getByRole('combobox', { name: 'Account' }), '');
    await click(within(form).getByRole('button', { name: 'Show these' }));
    await waitFor(() => expect(api.requests.some((r) => r.path === '/v1/entries/' && r.search.includes('from_date=2026-10-01'))).toBe(true));
    // Words: picked from what the server sent, as they are typed.
    type(within(region('Entries')).getByRole('searchbox', { name: 'Search descriptions' }), 'freshmart');
    expect(await within(region('Entries')).findByText('Showing 1–1 of 1 entry')).toBeTruthy();
    // The date chip removes the date filter.
    await click(within(region('Entries')).getByRole('button', { name: 'Remove the date filter' }));
    expect(await within(region('Entries')).findByText(/of \d+ entries$/)).toBeTruthy();
  });

  it('refuses a date range that runs backwards before asking', async () => {
    await setup({ path: '/console/books/entries' });
    const list = await screen.findByRole('region', { name: 'Entries' });
    await click(await within(list).findByRole('button', { name: /^Filters/ }));
    const form = within(list).getByRole('search', { name: 'Find entries' });
    type(within(form).getByLabelText('From'), '2026-10-01');
    type(within(form).getByLabelText('To'), '2026-09-01');
    await click(within(form).getByRole('button', { name: 'Show these' }));
    expect(within(form).getAllByText('The first day comes after the last.').length).toBeGreaterThan(0);
  });

  it('pages the entries, shows chosen columns, and opens one beside the list', async () => {
    await setup({ path: '/console/books/entries' });
    const list = await screen.findByRole('region', { name: 'Entries' });
    expect(await within(list).findByText(/^Showing 1–15 of \d+ entries$/)).toBeTruthy();
    await click(within(list).getByRole('button', { name: 'Next page' }));
    expect(within(list).getByText(/^Showing 16–30 of/)).toBeTruthy();
    // The columns menu hides the source.
    expect(within(list).getAllByRole('columnheader', { name: 'Source' })).toHaveLength(1);
    await click(within(list).getByRole('button', { name: 'Columns' }));
    await click(within(list).getByRole('checkbox', { name: 'Source' }));
    expect(within(list).queryAllByRole('columnheader', { name: 'Source' })).toHaveLength(0);
    // The eye opens an entry in a sheet: its lines, a total that is its one line's, and its page.
    await click(within(list).getByRole('button', { name: 'Previous page' }));
    const eye = within(list).getAllByRole('button', { name: /^Open FRESHMART beside the list/ })[0] as HTMLElement;
    await click(eye);
    const sheet = within(list).getByRole('complementary', { name: 'FRESHMART' });
    expect(within(sheet).getByText('Total')).toBeTruthy();
    expect(within(sheet).getByText(/Debits equal credits/)).toBeTruthy();
    expect(within(sheet).getByRole('link', { name: 'Open its page' }).getAttribute('href')).toMatch(/^\/console\/books\/entries\//);
    expect(within(sheet).getByRole('button', { name: 'Reverse this entry' })).toBeTruthy();
    await click(within(sheet).getByRole('button', { name: 'Close' }));
    expect(within(list).queryByRole('complementary')).toBeNull();
  });

  it('orders the entries from the toolbar, and says where the exports are', async () => {
    await setup({ path: '/console/books/entries' });
    const list = await screen.findByRole('region', { name: 'Entries' });
    await within(list).findByText(/^Showing 1–15 of/);
    const order = within(list).getByRole('group', { name: 'Order' });
    const date = within(list).getByRole('columnheader', { name: 'Date' });
    expect(within(order).getByRole('button', { name: 'Newest first' }).getAttribute('aria-pressed')).toBe('true');
    expect(date.getAttribute('aria-sort')).toBe('descending');
    await click(within(order).getByRole('button', { name: 'Oldest first' }));
    expect(date.getAttribute('aria-sort')).toBe('ascending');
    // Export goes to Your data, and says so on the page.
    expect(within(list).getByRole('link', { name: 'Exports, in Your data' }).getAttribute('href')).toBe('/console/settings/data');
    expect(within(list).getByText(/Beancount, hledger or JSON/)).toBeTruthy();
  });

  it('shows an id’s first eight characters, and the whole id on a press, not on hover', async () => {
    const id = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
    render(<IdChip id={id} />);
    const chip = screen.getByRole('button', { name: '7c9e6679, the whole id' });
    expect(chip.getAttribute('title')).toBeNull();
    expect(chip.getAttribute('aria-expanded')).toBe('false');
    await click(chip);
    expect(chip.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('button', { name: `${id}, the whole id` })).toBe(chip);
  });

  it('shows an entry in another currency with the rate it was posted at', async () => {
    await setup({ path: '/console/books/entries/e075' });
    expect(await screen.findByRole('heading', { level: 1, name: 'TO DOLLAR ACCOUNT' })).toBeTruthy();
    const lines = region('Its lines');
    expect(await within(lines).findByText('1 USD = 0.95 EUR')).toBeTruthy();
    expect(within(lines).getByText('USD 500.00')).toBeTruthy();
    expect(within(lines).getByText('EUR 475.00')).toBeTruthy();
    expect(within(region('Where it came from')).getByText('Posted from a bank statement.')).toBeTruthy();
  });
});

describe('adding an entry and reversing it', () => {
  it('finds what it can’t read before asking Salli, at each field', async () => {
    const { api } = await setup({ path: '/console/books/entries/new' });
    const form = await screen.findByRole('region', { name: 'The entry' });
    choose(await within(form).findByRole('combobox', { name: /^From/ }), 'chk');
    choose(within(form).getByRole('combobox', { name: /^To/ }), 'chk');
    type(within(form).getByRole('textbox', { name: /^Amount/ }), 'twelve');
    await click(within(form).getByRole('button', { name: 'Post it' }));
    expect(within(form).getAllByText('This one needs an answer.').length).toBeGreaterThan(0);
    expect(within(form).getAllByText('Choose two different accounts.').length).toBeGreaterThan(0);
    expect(within(form).getAllByText('An amount above zero, like 12.50.').length).toBeGreaterThan(0);
    expect(within(form).getByRole('textbox', { name: /^Amount/ }).getAttribute('aria-invalid')).toBe('true');
    expect(api.to('/v1/entries/', 'POST')).toHaveLength(0);
  });

  it('posts one amount from one account to another after a confirmation, then reverses it after another', async () => {
    const { api } = await setup({ path: '/console/books/entries/new' });
    const form = await screen.findByRole('region', { name: 'The entry' });
    type(within(form).getByRole('textbox', { name: /^Description/ }), 'Lunch with a friend');
    choose(await within(form).findByRole('combobox', { name: /^From/ }), 'chk');
    choose(within(form).getByRole('combobox', { name: /^To/ }), 'out');
    type(within(form).getByRole('textbox', { name: /^Amount/ }), '12.50');
    await click(within(form).getByRole('button', { name: 'Post it' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Post this entry?' });
    expect(within(dialog).getByText('1000 Checking')).toBeTruthy();
    expect(within(dialog).getByText('5200 Eating out')).toBeTruthy();
    expect(within(dialog).getByText(/can’t be edited or deleted/)).toBeTruthy();
    expect(api.to('/v1/entries/', 'POST')).toHaveLength(0);
    await click(within(dialog).getByRole('button', { name: 'Post it' }));
    await waitFor(() => expect(api.to('/v1/entries/', 'POST')).toHaveLength(1));
    // One amount, the same string on both lines: the entry balances without the console adding anything.
    expect(bodies(api, '/v1/entries/')[0]).toEqual({
      entry_date: '2026-10-11',
      description: 'Lunch with a friend',
      postings: [
        { account_id: 'out', direction: 1, amount: '12.50' },
        { account_id: 'chk', direction: -1, amount: '12.50' },
      ],
    });
    await click(await within(form).findByRole('link', { name: 'Open the entry' }));

    // The entry, standing; reversing it asks first.
    expect(await screen.findByRole('heading', { level: 1, name: 'Lunch with a friend' })).toBeTruthy();
    const standing = await screen.findByRole('region', { name: 'Standing' });
    expect(within(standing).getByText(/Posted entries are never edited/)).toBeTruthy();
    await click(await within(standing).findByRole('button', { name: 'Reverse this entry' }));
    const ask = screen.getByRole('alertdialog', { name: 'Reverse this entry?' });
    expect(within(ask).getByText(/Salli will post “REVERSAL: Lunch with a friend” for Oct 11, 2026/)).toBeTruthy();
    expect(api.to(`/v1/entries/${where.LUNCH.id}/reverse`, 'POST')).toHaveLength(0);
    await click(within(ask).getByRole('button', { name: 'Reverse it' }));
    expect(await within(standing).findByText(/Reversed\. Both entries are in the ledger\./)).toBeTruthy();
    expect(await within(standing).findByText(/Reversed by/)).toBeTruthy();
    expect(within(standing).queryByRole('button', { name: 'Reverse this entry' })).toBeNull();

    // Both in the ledger, and in checking's entries.
    await click(within(standing).getByRole('link', { name: 'Open the reversal' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'REVERSAL: Lunch with a friend' })).toBeTruthy();
    expect(await within(screen.getByRole('region', { name: 'Standing' })).findByText(/Reverses/)).toBeTruthy();
  });

  it('offers a foreign account’s currency, and says which rate Salli used', async () => {
    const { api } = await setup({ path: '/console/books/entries/new' });
    const form = await screen.findByRole('region', { name: 'The entry' });
    type(within(form).getByRole('textbox', { name: /^Description/ }), 'Dollars for the trip');
    choose(await within(form).findByRole('combobox', { name: /^From/ }), 'chk');
    choose(within(form).getByRole('combobox', { name: /^To/ }), 'usd');
    expect((within(form).getByRole('combobox', { name: /^Currency/ }) as HTMLSelectElement).value).toBe('USD');
    expect(within(form).getByRole('textbox', { name: /Rate: EUR for 1 USD/ })).toBeTruthy();
    type(within(form).getByRole('textbox', { name: /^Amount/ }), '100');
    await click(within(form).getByRole('button', { name: 'Post it' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Post this entry?' });
    expect(within(dialog).getByText('The rate published for the day')).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Post it' }));
    expect(await within(form).findByText(/Posted at 1 USD = 0.86 EUR, the rate Salli used\./)).toBeTruthy();
    expect(bodies(api, '/v1/entries/')[0]?.postings).toEqual([
      { account_id: 'usd', direction: 1, amount: '100', currency: 'USD' },
      { account_id: 'chk', direction: -1, amount: '100', currency: 'USD' },
    ]);
  });

  it('shows Salli’s refusal for want of a rate at the rate', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.method === 'POST' && r.path === '/v1/entries/' ? { status: 422, body: where.NO_RATE } : undefined));
    await setup({ api, path: '/console/books/entries/new' });
    const form = await screen.findByRole('region', { name: 'The entry' });
    type(within(form).getByRole('textbox', { name: /^Description/ }), 'Dollars');
    choose(await within(form).findByRole('combobox', { name: /^From/ }), 'chk');
    choose(within(form).getByRole('combobox', { name: /^To/ }), 'usd');
    type(within(form).getByRole('textbox', { name: /^Amount/ }), '100');
    await click(within(form).getByRole('button', { name: 'Post it' }));
    await click(within(screen.getByRole('alertdialog', { name: 'Post this entry?' })).getByRole('button', { name: 'Post it' }));
    const rate = await within(form).findByRole('textbox', { name: /Rate: EUR for 1 USD/ });
    await waitFor(() => expect(rate.getAttribute('aria-invalid')).toBe('true'));
    expect(within(form).getAllByText(/No GBP→EUR rate for 2026-10-11/).length).toBeGreaterThan(0);
  });

  it('shows Salli’s refusal to reverse an entry twice', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.method === 'POST' && r.path.endsWith('/reverse') ? { status: 400, body: where.REVERSE_REFUSED } : undefined));
    await setup({ api, path: '/console/books/entries/e070' });
    const standing = await screen.findByRole('region', { name: 'Standing' });
    await click(await within(standing).findByRole('button', { name: 'Reverse this entry' }));
    await click(within(screen.getByRole('alertdialog', { name: 'Reverse this entry?' })).getByRole('button', { name: 'Reverse it' }));
    // An untyped problem gets the console's own title for its status, then the server's detail.
    expect(await within(standing).findByText("Salli didn't do this")).toBeTruthy();
    expect(within(standing).getByText(/already reversed/)).toBeTruthy();
  });
});

describe('cash', () => {
  it('draws the forecast to its low point, with what is free until payday and what it is committed to', async () => {
    await setup({ path: '/console/cash' });
    const forecast = await screen.findByRole('region', { name: 'The next 60 days' });
    const label = (await within(forecast).findAllByRole('img'))[0]?.getAttribute('aria-label') ?? '';
    expect(label).toContain('EUR 15,801.47 today, lowest EUR 15,727.02 on Oct 18, 2026, EUR 19,626.59 at the end');
    expect(within(forecast).getByText('USD at 0.86, ecb, Oct 9, 2026')).toBeTruthy();
    const safe = region('Free until payday');
    expect(within(safe).getByText('15,316.35')).toBeTruthy();
    expect(within(safe).getByText('EUR 206.96')).toBeTruthy();
    expect(within(safe).getByText('until Oct 25, 2026, when Acme Salary comes in')).toBeTruthy();
    expect(within(safe).getByText('Oct 18, 2026 · Bistro Novo')).toBeTruthy();
    const accounts = region('Cash accounts');
    const usd = within(accounts).getByRole('link', { name: 'Dollar account' }).closest('tr') as HTMLElement;
    expect(within(usd).getAllByText('USD 2,500.00').length).toBe(3);
  });

  it('shows cash flow by month with what was left, spending by category and recurring payments', async () => {
    await setup({ path: '/console/cash' });
    const flow = await screen.findByRole('region', { name: 'Cash flow by month' });
    expect(await within(flow).findByText('EUR 1,962.91')).toBeTruthy();
    await click(within(flow).getByRole('button', { name: 'Show the figures' }));
    expect(within(flow).getByText('Oct 2026 (so far)')).toBeTruthy();
    expect(within(flow).getAllByText('(1,750.99)').length).toBeGreaterThan(0);
    const spending = region('Spending by category');
    expect(within(spending).getByText('77.4%')).toBeTruthy();
    const recurring = region('Recurring payments');
    expect(within(recurring).getByText('Bistro Novo').closest('tr')?.textContent).toContain('varies');
  });

  it('says so when there is no full month to average', async () => {
    const api = new MockApi();
    api.where.cashFlow = { ...where.CASH_FLOW, average: { ...where.CASH_FLOW.average, months_observed: [] } };
    await setup({ api, path: '/console/cash' });
    const flow = await screen.findByRole('region', { name: 'Cash flow by month' });
    expect(await within(flow).findByText('No full month of income and spending yet, so no monthly average.')).toBeTruthy();
  });
});

describe('attention', () => {
  it('shows each signal with its kind, its detail and where to look', async () => {
    await setup({ path: '/console/attention' });
    const signals = await screen.findByRole('region', { name: 'What Salli noticed' });
    expect(await within(signals).findByText('A decision is ready for review')).toBeTruthy();
    expect(within(signals).getByText('For information')).toBeTruthy();
    const link = within(signals).getByRole('link', { name: 'Open the decision in your journal' });
    expect(link.getAttribute('href')).toBe(`/console/decide/journal/${where.REMINDERS_ALL.reminders[0]?.source_id ?? ''}`);
  });

  it('groups the reminders by when they are due, and marks one done after a confirmation', async () => {
    const { api } = await setup({ path: '/console/attention' });
    const reminders = await screen.findByRole('region', { name: 'Reminders' });
    expect(await within(reminders).findByText('Send the landlord the signed lease')).toBeTruthy();
    expect(within(reminders).getByText('Nothing is due today.')).toBeTruthy();
    expect(within(reminders).getByText('Done (1)')).toBeTruthy();
    // A decision's review opens it in the journal.
    expect(within(reminders).getByRole('link', { name: 'Open the decision' })).toBeTruthy();
    await click(within(reminders).getByRole('button', { name: 'Mark “Send the landlord the signed lease” done' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Mark this reminder done?' });
    expect(within(dialog).getByText(/due Oct 5, 2026, done/)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Mark it done' }));
    expect(await within(reminders).findByText('Done (2)')).toBeTruthy();
    expect(within(reminders).getByText(/Done: Send the landlord the signed lease\./)).toBeTruthy();
    expect(api.to('/v1/reminders/0000232c-5a11-4000-8000-000000009004/done', 'PATCH')).toHaveLength(1);
  });

  it('deletes a reminder after a confirmation that says it can’t be brought back', async () => {
    const { api } = await setup({ path: '/console/attention' });
    const reminders = await screen.findByRole('region', { name: 'Reminders' });
    await click(await within(reminders).findByRole('button', { name: "Delete “Renew the car's insurance”" }));
    const dialog = screen.getByRole('alertdialog', { name: 'Delete this reminder?' });
    expect(within(dialog).getByText(/It can’t be brought back\./)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Delete it' }));
    expect(await within(reminders).findByText('Nothing is coming up.')).toBeTruthy();
    expect(api.requests.filter((r) => r.method === 'DELETE')).toHaveLength(1);
  });
});

describe('financial independence', () => {
  it('shows the FI number, the way there, the projections at three returns and the placeholders', async () => {
    await setup({ path: '/console/fi' });
    const here = await screen.findByRole('region', { name: 'Where you are' });
    expect(await within(here).findByText('EUR 611,127.00')).toBeTruthy();
    expect(within(here).getByText('May 2042')).toBeTruthy();
    expect(within(here).getByText('49.07%')).toBeTruthy();
    const projections = region('Projections');
    const label = (await within(projections).findAllByRole('img'))[0]?.getAttribute('aria-label') ?? '';
    expect(label).toContain('against your FI number of EUR 611,127.00');
    expect(within(projections).getAllByText('Conservative, 2% a year').length).toBeGreaterThan(0);
    expect(within(projections).getByText('Feb 2045')).toBeTruthy();
    const assumptions = region('Assumptions');
    expect(within(assumptions).getAllByText('Placeholder')).toHaveLength(3);
    expect(within(region('What the score is made of')).getByText('Saving 49.07% of income')).toBeTruthy();
    expect(within(region('The score over time')).getByText('Oct 11, 2026')).toBeTruthy();
  });

  it('sets your own real return with its source, and the placeholder flag goes', async () => {
    const { api } = await setup({ path: '/console/fi' });
    const assumptions = await screen.findByRole('region', { name: 'Assumptions' });
    await click(await within(assumptions).findByRole('button', { name: 'Set your own: Real return' }));
    const form = within(assumptions).getByRole('form', { name: 'Set your own: Real return' });
    type(within(form).getByRole('textbox', { name: /Real return: Rate/ }), '3.5%');
    type(within(form).getByRole('textbox', { name: /Where it comes from/ }), 'My own long-run view, after inflation');
    await click(within(form).getByRole('button', { name: 'Save it' }));
    expect(await within(assumptions).findByText(/Saved: Real return\./)).toBeTruthy();
    expect(bodies(api, '/v1/fi/assumptions', 'PATCH')[0]).toEqual({ real_return: { value: '0.035', source: 'My own long-run view, after inflation', note: null } });
    await waitFor(() => expect(within(assumptions).getAllByText('Placeholder')).toHaveLength(2));
    expect(within(assumptions).getByText('You')).toBeTruthy();
    expect(within(assumptions).getByText('3.5%')).toBeTruthy();
  });

  it('shows Salli’s refusal of a rate at the rate', async () => {
    await setup({ path: '/console/fi' });
    const assumptions = await screen.findByRole('region', { name: 'Assumptions' });
    await click(await within(assumptions).findByRole('button', { name: 'Set your own: Real return' }));
    const form = within(assumptions).getByRole('form', { name: 'Set your own: Real return' });
    const field = within(form).getByRole('textbox', { name: /Real return: Rate/ });
    type(field, '60%');
    await click(within(form).getByRole('button', { name: 'Save it' }));
    await waitFor(() => expect(field.getAttribute('aria-invalid')).toBe('true'));
    expect(within(form).getAllByText(/real_return must be a yearly fraction from -0.05 to 0.15/).length).toBeGreaterThan(0);
  });
});

describe('the places', () => {
  it('lists on More what a phone’s bar has no room for, and marks More as the place', async () => {
    await setup({ path: '/console/attention' });
    await screen.findByRole('heading', { level: 1, name: 'Attention' });
    const bar = screen.getAllByRole('navigation', { name: 'Places' })[1] as HTMLElement;
    expect(within(bar).getAllByRole('link').map((a) => a.textContent)).toEqual(['Home', 'Cash', 'Decide', 'Books', 'More']);
    expect(within(bar).getByRole('link', { name: 'More' }).getAttribute('aria-current')).toBe('page');
    await click(within(bar).getByRole('link', { name: 'More' }));
    const more = await screen.findByRole('heading', { level: 1, name: 'More' });
    const list = more.closest('.page') as HTMLElement;
    expect(within(list).getAllByRole('link').map((a) => a.textContent)).toEqual(['Tax', 'Attention', 'Independence', 'Settings']);
  });
});
