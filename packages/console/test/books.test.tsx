/**
 * Imports, review and rules (docs/design/console.md, section 5, C4) on what
 * the real server answers for the golden household (fixtures/books.ts): a
 * statement uploaded, the review queue with an account chosen, a selection
 * posted and another discarded after confirmations, a rule made from a
 * transaction, rules tested, refused, made, edited and deleted. Nothing is
 * booked until posted; every amount Salli's, shown exactly.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MockApi } from './fixtures/api';
import * as books from './fixtures/books';
import { setup } from './harness';

const STATEMENT = books.STATEMENTS.statements[0]!.id;
const REVIEW = `/console/books/imports/${STATEMENT}`;
const byDescription = (d: string) => books.PENDING.transactions.find((t) => t.description === d)!;

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

const json = (body: string): Record<string, unknown> => JSON.parse(body) as Record<string, unknown>;

describe('imports', () => {
  it('uploads a statement for an account and says what Salli read, with nothing booked yet', async () => {
    const { api } = await setup({ path: '/console/books/imports' });
    const upload = await screen.findByRole('region', { name: 'Import a statement' });
    const file = new File(['Date,Description,Amount\n2026-10-07,CORNER BAKERY,-8.40\n'], 'checking-october.csv', { type: 'text/csv' });
    fireEvent.change(await within(upload).findByLabelText('The statement file'), { target: { files: [file] } });
    fireEvent.change(within(upload).getByRole('combobox', { name: /The account it is for/ }), { target: { value: 'chk' } });
    fireEvent.change(within(upload).getByRole('combobox', { name: /Dates in the file/ }), { target: { value: 'YMD' } });
    await click(within(upload).getByRole('button', { name: 'Import it' }));
    expect(await within(upload).findByText(/Read 5 transactions from Example Bank for Oct 1 – 10, 2026\. Nothing is booked yet\./)).toBeTruthy();
    expect(within(upload).getByText(/4 transaction\(s\) need an account/)).toBeTruthy();
    expect(within(upload).getByRole('link', { name: 'Review them' }).getAttribute('href')).toBe(REVIEW);
    const sent = api.to('/v1/statements/upload', 'POST');
    expect(sent).toHaveLength(1);
    const query = new URLSearchParams(sent[0]?.search);
    expect(query.get('account_id')).toBe('chk');
    expect(query.get('date_order')).toBe('YMD');
    // A multipart upload of the file (jsdom's fetch leaves out a file's bytes; the browser runs send them).
    expect(sent[0]?.body).toContain('form-data; name="file"');
    // Importing posts nothing.
    expect(api.to(`/v1/statements/${STATEMENT}/post`, 'POST')).toHaveLength(0);
  });

  it('asks for a file first, and shows what Salli couldn’t read', async () => {
    const api = new MockApi();
    // What the server answers a file with no transactions in it (jsdom's fetch sends no file bytes to tell it by).
    api.overrides.push((r) => (r.method === 'POST' && r.path === '/v1/statements/upload' ? { status: 422, body: books.UPLOAD_REFUSED } : undefined));
    await setup({ api, path: '/console/books/imports' });
    const upload = await screen.findByRole('region', { name: 'Import a statement' });
    await click(await within(upload).findByRole('button', { name: 'Import it' }));
    expect(within(upload).getAllByText('Choose a statement file to import.').length).toBeGreaterThan(0);
    expect(api.to('/v1/statements/upload')).toHaveLength(0);
    const empty = new File(['Nothing,to,see\n'], 'notes.csv', { type: 'text/csv' });
    fireEvent.change(within(upload).getByLabelText('The statement file'), { target: { files: [empty] } });
    await click(within(upload).getByRole('button', { name: 'Import it' }));
    expect(await within(upload).findByText(/Couldn.t tell which columns hold the date and the amount in this CSV file/)).toBeTruthy();
  });

  it('lists the statements and where each bank connection stands, connecting staying with salli banks', async () => {
    await setup({ path: '/console/books/imports' });
    const statements = await screen.findByRole('region', { name: 'Statements' });
    const row = (await within(statements).findByText('Example Bank')).closest('tr') as HTMLElement;
    expect(within(row).getByText('Waiting for review')).toBeTruthy();
    expect(within(row).getByText('1000 Checking')).toBeTruthy();
    expect(within(row).getByRole('link', { name: /Review Example Bank/ }).getAttribute('href')).toBe(REVIEW);
    const banks = screen.getByRole('region', { name: 'Bank connections' });
    expect(await within(banks).findByText('Everyday checking')).toBeTruthy();
    expect(within(banks).getByText('EUR 2,104.33')).toBeTruthy();
    expect(within(banks).getByText(/done with salli banks/)).toBeTruthy();
  });
});

describe('the review queue', () => {
  it('shows each transaction as Salli read it, with who proposed its account and what may be booked already', async () => {
    await setup({ path: REVIEW });
    expect(await screen.findByRole('heading', { level: 1, name: 'Review: Example Bank, Oct 1 – 10, 2026' })).toBeTruthy();
    const queue = screen.getByRole('region', { name: 'Waiting for review' });
    const items = await within(queue).findAllByRole('listitem');
    const fresh = items.find((i) => i.textContent?.includes('FRESHMART')) as HTMLElement;
    expect(within(fresh).getByText('Proposed by your rule “FreshMart is groceries”')).toBeTruthy();
    expect(within(fresh).getByText('EUR 46.20')).toBeTruthy();
    expect((within(fresh).getByRole('combobox', { name: /Where it went: FRESHMART/ }) as HTMLSelectElement).value).toBe('food');
    const rent = items.find((i) => i.textContent?.includes('CITY LETTINGS RENT')) as HTMLElement;
    expect(within(rent).getByText(/This looks like an entry already in your books/)).toBeTruthy();
    expect(within(rent).getByRole('link', { name: 'Open that entry' }).getAttribute('href')).toBe('/console/books/entries/e067');
    const refund = items.find((i) => i.textContent?.includes('HARDWARE STORE REFUND')) as HTMLElement;
    expect(within(refund).getByRole('combobox', { name: /Where it came from: HARDWARE STORE REFUND/ })).toBeTruthy();
    expect(within(refund).getByText('Needs an account before it can be posted')).toBeTruthy();
    expect(screen.getByText(/Nothing is booked until you post it, and nothing is booked twice/)).toBeTruthy();
  });

  it('keeps an account chosen for a transaction at once', async () => {
    const { api } = await setup({ path: REVIEW });
    const queue = await screen.findByRole('region', { name: 'Waiting for review' });
    const bakery = await within(queue).findByRole('combobox', { name: /Where it went: CORNER BAKERY/ });
    await act(async () => {
      fireEvent.change(bakery, { target: { value: 'out' } });
    });
    await waitFor(() => expect(api.to('/v1/statements/categorize', 'POST')).toHaveLength(1));
    expect(json(api.to('/v1/statements/categorize', 'POST')[0]?.body ?? '{}')).toEqual({
      choices: [{ transaction_id: byDescription('CORNER BAKERY').id, account_id: 'out' }],
    });
    expect(await within(queue).findByText(/Kept: CORNER BAKERY now goes to the account you chose\./)).toBeTruthy();
    await waitFor(() => expect((within(queue).getByRole('combobox', { name: /Where it went: CORNER BAKERY/ }) as HTMLSelectElement).value).toBe('out'));
  });

  it('posts the selection after saying what Salli will post, and links to it in the books', async () => {
    const api = new MockApi();
    await setup({ api, path: REVIEW });
    const queue = await screen.findByRole('region', { name: 'Waiting for review' });
    await act(async () => {
      fireEvent.change(await within(queue).findByRole('combobox', { name: /Where it went: CORNER BAKERY/ }), { target: { value: 'out' } });
    });
    await within(queue).findByText(/Kept: CORNER BAKERY/);
    // Every complete one that isn't a possible duplicate: FreshMart and the bakery.
    await click(within(queue).getByRole('button', { name: 'Select every one that is complete and not a possible duplicate' }));
    expect(within(queue).getByText('2 selected')).toBeTruthy();
    await click(within(queue).getByRole('button', { name: 'Post the selected' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Post these to your books?' });
    expect(within(dialog).getByText(/Salli will post these 2 transactions as entries in your books/)).toBeTruthy();
    expect(within(dialog).getByText(/FRESHMART/)).toBeTruthy();
    expect(api.to(`/v1/statements/${STATEMENT}/post`)).toHaveLength(0);
    await click(within(dialog).getByRole('button', { name: 'Post them' }));
    await waitFor(() => expect(api.to(`/v1/statements/${STATEMENT}/post`, 'POST')).toHaveLength(1));
    expect(json(api.to(`/v1/statements/${STATEMENT}/post`, 'POST')[0]?.body ?? '{}')).toEqual({
      approved_ids: [byDescription('CORNER BAKERY').id, byDescription('FRESHMART').id].sort((a, b) => books.PENDING.transactions.findIndex((t) => t.id === a) - books.PENDING.transactions.findIndex((t) => t.id === b)),
    });
    expect(await within(queue).findByText(/Posted 2 entries\./)).toBeTruthy();
    expect(within(queue).getByRole('link', { name: 'See them in your books' }).getAttribute('href')).toBe('/console/books/entries?account=chk&from=2026-10-01&to=2026-10-10');
    await waitFor(() => expect(within(queue).queryByText('FRESHMART')).toBeNull());
  });

  it('discards a selection after a confirmation that says it can’t be brought back', async () => {
    const { api } = await setup({ path: REVIEW });
    const queue = await screen.findByRole('region', { name: 'Waiting for review' });
    await click(await within(queue).findByRole('checkbox', { name: /Select CITY LETTINGS RENT/ }));
    await click(within(queue).getByRole('checkbox', { name: /Select AUTOFIN CAR LOAN/ }));
    await click(within(queue).getByRole('button', { name: 'Discard the selected' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Discard these?' });
    expect(within(dialog).getByText(/They can’t be brought back/)).toBeTruthy();
    // Cancelling discards nothing.
    await click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(api.to(`/v1/statements/${STATEMENT}/discard`)).toHaveLength(0);
    await click(within(queue).getByRole('button', { name: 'Discard the selected' }));
    await click(within(await screen.findByRole('alertdialog', { name: 'Discard these?' })).getByRole('button', { name: 'Discard them' }));
    await waitFor(() => expect(api.to(`/v1/statements/${STATEMENT}/discard`, 'POST')).toHaveLength(1));
    expect(json(api.to(`/v1/statements/${STATEMENT}/discard`, 'POST')[0]?.body ?? '{}')).toEqual({
      ids: [byDescription('CITY LETTINGS RENT').id, byDescription('AUTOFIN CAR LOAN').id],
    });
    expect(await within(queue).findByText(/Discarded 2\./)).toBeTruthy();
  });

  it('makes a rule from a transaction, its form filled from it', async () => {
    const { api } = await setup({ path: REVIEW });
    const queue = await screen.findByRole('region', { name: 'Waiting for review' });
    await click(await within(queue).findByRole('button', { name: 'Make a rule from FRESHMART' }));
    const form = await screen.findByRole('region', { name: 'Make a rule from this' });
    expect((within(form).getByRole('textbox', { name: /Its name/ }) as HTMLInputElement).value).toBe('FRESHMART');
    expect((within(form).getByRole('combobox', { name: /Where the other side goes/ }) as HTMLSelectElement).value).toBe('food');
    await click(within(form).getByRole('button', { name: 'Save the rule' }));
    await waitFor(() => expect(api.to('/v1/rules', 'POST')).toHaveLength(1));
    expect(json(api.to('/v1/rules', 'POST')[0]?.body ?? '{}')).toEqual({
      name: 'FRESHMART',
      conditions: [
        { field: 'description', operator: 'contains', value: 'FRESHMART' },
        { field: 'direction', operator: 'equals', value: 'out' },
      ],
      actions: { account_id: 'food' },
      priority: 100,
      match_all: true,
      enabled: true,
    });
    expect(await within(queue).findByText(/Saved: FRESHMART\./)).toBeTruthy();
  });

  it('says plainly when a statement isn’t there', async () => {
    await setup({ path: '/console/books/imports/nowhere' });
    expect(await screen.findByRole('heading', { level: 1, name: 'No such statement' })).toBeTruthy();
    expect(await screen.findByText('Statement not found')).toBeTruthy();
  });
});

describe('rules', () => {
  it('lists the rules in words, with what each has decided', async () => {
    await setup({ path: '/console/books/rules' });
    const yours = await screen.findByRole('region', { name: 'Your rules' });
    const rule = (await within(yours).findByText('FreshMart is groceries')).closest('li') as HTMLElement;
    expect(within(rule).getByText(/The description contains FRESHMART/)).toBeTruthy();
    expect(within(rule).getByText(/Goes to 5100 Groceries, category groceries, need essential/)).toBeTruthy();
    expect(within(rule).getByText('Has decided 1 transaction, the last on Oct 11, 2026')).toBeTruthy();
  });

  it('tests a new rule against the books, then saves it', async () => {
    const { api } = await setup({ path: '/console/books/rules' });
    const form = await screen.findByRole('region', { name: 'Add a rule' });
    fireEvent.change(await within(form).findByRole('textbox', { name: /Its name/ }), { target: { value: 'Bistro Novo is eating out' } });
    fireEvent.change(within(form).getByRole('textbox', { name: /^Value/ }), { target: { value: 'BISTRO' } });
    fireEvent.change(within(form).getByRole('combobox', { name: /Where the other side goes/ }), { target: { value: 'out' } });
    fireEvent.change(within(form).getByRole('textbox', { name: /^Category/ }), { target: { value: 'eating-out' } });
    fireEvent.change(within(form).getByRole('combobox', { name: /^Need/ }), { target: { value: 'discretionary' } });
    await click(within(form).getByRole('button', { name: 'Test it against your books' }));
    expect(await within(form).findByText('It matches 6 transactions already booked; 6 of them went to the account it names.')).toBeTruthy();
    expect(within(form).getAllByText('BISTRO NOVO').length).toBe(6);
    expect(json(api.to('/v1/rules/test', 'POST')[0]?.body ?? '{}')).toEqual({
      name: 'Bistro Novo is eating out',
      conditions: [{ field: 'description', operator: 'contains', value: 'BISTRO' }],
      actions: { account_id: 'out', category: 'eating-out', need: 'discretionary' },
      priority: 100,
      match_all: true,
      enabled: true,
    });
    await click(within(form).getByRole('button', { name: 'Save the rule' }));
    expect(await screen.findByText(/Saved: Bistro Novo is eating out\./)).toBeTruthy();
    expect(api.to('/v1/rules', 'POST')).toHaveLength(1);
    expect(await within(screen.getByRole('region', { name: 'Your rules' })).findByText('Bistro Novo is eating out')).toBeTruthy();
  });

  it('shows what Salli refused, and asks for a name and a value first', async () => {
    const { api } = await setup({ path: '/console/books/rules' });
    const form = await screen.findByRole('region', { name: 'Add a rule' });
    await click(await within(form).findByRole('button', { name: 'Save the rule' }));
    expect(within(form).getAllByText('A rule needs a name.').length).toBeGreaterThan(0);
    expect(within(form).getAllByText('Give the value it compares with.').length).toBeGreaterThan(0);
    expect(api.to('/v1/rules', 'POST')).toHaveLength(0);
    fireEvent.change(within(form).getByRole('textbox', { name: /Its name/ }), { target: { value: 'Anything in brackets' } });
    fireEvent.change(within(form).getByRole('combobox', { name: 'How' }), { target: { value: 'matches' } });
    fireEvent.change(within(form).getByRole('textbox', { name: /^Value/ }), { target: { value: '(UNCLOSED' } });
    await click(within(form).getByRole('button', { name: 'Save the rule' }));
    expect(await within(form).findByText(/Not a valid pattern: missing \), unterminated subpattern/)).toBeTruthy();
  });

  it('reads an amount in the locale’s marks and sends a decimal string', async () => {
    const { api } = await setup({ path: '/console/books/rules' });
    const form = await screen.findByRole('region', { name: 'Add a rule' });
    fireEvent.change(await within(form).findByRole('textbox', { name: /Its name/ }), { target: { value: 'Big ones' } });
    fireEvent.change(within(form).getByRole('combobox', { name: 'What it looks at' }), { target: { value: 'amount' } });
    fireEvent.change(within(form).getByRole('combobox', { name: 'How' }), { target: { value: 'gte' } });
    fireEvent.change(within(form).getByRole('textbox', { name: /^Value/ }), { target: { value: '9,007,199,254,740,993.01' } });
    await click(within(form).getByRole('button', { name: 'Save the rule' }));
    await waitFor(() => expect(api.to('/v1/rules', 'POST')).toHaveLength(1));
    const sent = json(api.to('/v1/rules', 'POST')[0]?.body ?? '{}') as { conditions: Array<{ value: string }> };
    expect(sent.conditions[0]?.value).toBe('9007199254740993.01');
  });

  it('edits a rule and deletes one after a confirmation', async () => {
    const { api } = await setup({ path: '/console/books/rules' });
    const yours = await screen.findByRole('region', { name: 'Your rules' });
    await click(await within(yours).findByRole('button', { name: 'Edit FreshMart is groceries' }));
    const form = await screen.findByRole('region', { name: 'Edit: FreshMart is groceries' });
    fireEvent.change(within(form).getByRole('textbox', { name: /Its name/ }), { target: { value: 'FreshMart: groceries' } });
    fireEvent.change(within(form).getByRole('textbox', { name: /^Order/ }), { target: { value: '10' } });
    await click(within(form).getByRole('button', { name: 'Save the rule' }));
    await waitFor(() => expect(api.to(`/v1/rules/${books.RULES[0]!.id}`, 'PATCH')).toHaveLength(1));
    expect(json(api.to(`/v1/rules/${books.RULES[0]!.id}`, 'PATCH')[0]?.body ?? '{}')).toMatchObject({ name: 'FreshMart: groceries', priority: 10 });
    expect(await within(yours).findByText('FreshMart: groceries')).toBeTruthy();

    await click(within(yours).getByRole('button', { name: 'Delete FreshMart: groceries' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Delete this rule?' });
    expect(within(dialog).getByText(/What it already sorted stays as it is/)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Delete it' }));
    await waitFor(() => expect(api.to(`/v1/rules/${books.RULES[0]!.id}`, 'DELETE')).toHaveLength(1));
    expect(await within(yours).findByText(/Deleted: FreshMart: groceries\./)).toBeTruthy();
  });

  it('makes a suggestion a rule as it is, or loads it into the form first', async () => {
    const { api } = await setup({ path: '/console/books/rules' });
    const suggestions = await screen.findByRole('region', { name: 'Suggestions' });
    const acme = (await within(suggestions).findByText('Acme')).closest('li') as HTMLElement;
    expect(within(acme).getByText('Would have decided 7 booked transactions; 7 went to that account.')).toBeTruthy();
    expect(within(acme).getByText('For example: ACME LTD SALARY')).toBeTruthy();
    await click(within(acme).getByRole('button', { name: 'Make “Acme” a rule' }));
    await waitFor(() => expect(api.to('/v1/rules', 'POST')).toHaveLength(1));
    expect(json(api.to('/v1/rules', 'POST')[0]?.body ?? '{}')).toMatchObject({ name: 'Acme', actions: { account_id: 'sal' } });
    const city = (within(suggestions).getByText('City').closest('li')) as HTMLElement;
    await click(within(city).getByRole('button', { name: 'Edit “City” before making it a rule' }));
    expect((within(screen.getByRole('region', { name: 'Add a rule' })).getByRole('textbox', { name: /Its name/ }) as HTMLInputElement).value).toBe('City');
  });
});
