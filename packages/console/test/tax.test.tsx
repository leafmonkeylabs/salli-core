/**
 * Tax (docs/design/console.md, section 5, C4; docs/taxrules.md) on what the
 * real server answers for the fictional rules XA 2031 (fixtures/tax.ts):
 * the year and the last computation line by line, a line explained,
 * computing again; a rule set's versions; a version reviewed (what is new
 * with its sources, every worked example, its sources and deadlines) and
 * activated after a confirmation. Past five minutes from the password, the
 * server answers activating with its step-up problem: the console sends the
 * person through Salli's sign-in page with `prompt=login`, and activates on
 * their return, once. Only a person activates: the pages say so.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { KEYS } from '../src/auth/session';
import { MockApi } from './fixtures/api';
import * as tax from './fixtures/tax';
import { setup } from './harness';

const SET = tax.RULE_SET.id;
const VERSION = (id: string): string => `/console/tax/rules/${SET}/versions/${id}`;
const region = (name: string | RegExp): HTMLElement => screen.getByRole('region', { name });

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

describe('your tax', () => {
  it('shows the year, the rules computing it, and the last computation line by line', async () => {
    await setup({ path: '/console/tax' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Tax' })).toBeTruthy();
    const year = await screen.findByRole('region', { name: 'This tax year' });
    expect(await within(year).findByText('XA, from your tax residency')).toBeTruthy();
    expect(within(year).getByText('2031: Jan 1 – Dec 31, 2031')).toBeTruthy();
    expect(within(year).getByRole('link', { name: 'XA 2031, version 1' }).getAttribute('href')).toBe(VERSION(tax.VERSION_1.id));
    const latest = await screen.findByRole('region', { name: 'The last computation' });
    expect(await within(latest).findByText('Tax to pay')).toBeTruthy();
    expect(within(latest).getAllByText('NZD 2,400.00').length).toBeGreaterThan(0);
    const table = within(latest).getAllByRole('table')[0] as HTMLElement;
    const relief = within(table).getByText('Relief').closest('tr') as HTMLElement;
    expect(within(relief).getByText('min(12000, max(0, line.taxable_income))')).toBeTruthy();
    expect(within(relief).getByText('12,000.00')).toBeTruthy();
    expect(within(latest).getByText(/Computed by Salli's engine from rules you or your agent entered/)).toBeTruthy();
    // From the books: the salary's total and its postings.
    const salary = within(latest).getAllByText('Salary').map((e) => e.closest('tr')).find(Boolean) as HTMLElement;
    expect(within(salary).getByText('24,000.00')).toBeTruthy();
    const deadlines = await screen.findByRole('region', { name: 'Deadlines' });
    expect(await within(deadlines).findByText('Apr 30, 2032')).toBeTruthy();
    expect(within(deadlines).getByText('Return due')).toBeTruthy();
    expect(screen.getAllByText(/Only a person activates tax rules, never an AI/).length).toBeGreaterThan(0);
  });

  it('explains a line from the rules, nothing stored', async () => {
    const { api } = await setup({ path: '/console/tax' });
    const latest = await screen.findByRole('region', { name: 'The last computation' });
    await click(await within(latest).findByRole('button', { name: 'Explain Income tax' }));
    const explained = await within(latest).findByRole('region', { name: 'Where Income tax comes from' });
    expect(within(explained).getByText('line.income_tax.band_1.tax + line.income_tax.band_2.tax')).toBeTruthy();
    expect(within(explained).getByText('Income tax: band 1 tax')).toBeTruthy();
    expect(within(explained).getByText('Used by balance.')).toBeTruthy();
    const sent = api.to('/v1/tax/explain', 'POST');
    expect(JSON.parse(sent[0]?.body ?? '{}')).toEqual({ line_key: 'income_tax', answers: {} });
    expect(new URLSearchParams(sent[0]?.search).get('year')).toBe('2031');
  });

  it('computes again and keeps the result', async () => {
    const { api } = await setup({ path: '/console/tax' });
    const latest = await screen.findByRole('region', { name: 'The last computation' });
    await click(await within(latest).findByRole('button', { name: 'Compute now' }));
    expect(await within(latest).findByText(/Computed again, and kept\./)).toBeTruthy();
    expect(api.to('/v1/tax/compute', 'POST')).toHaveLength(1);
    // Version 2's computation, read back.
    expect(await within(latest).findByRole('link', { name: 'XA 2031, version 2' })).toBeTruthy();
  });

  it('says plainly when Salli has no rules to compute with, and asks the server for nothing it can’t answer', async () => {
    const api = new MockApi();
    api.tax.year = { country: null, country_source: null, year: null, region: null, start: null, end: null, rule_set_id: null, rule_set_version_id: null, version: null, latest_year: null, latest_rule_set_version_id: null };
    await setup({ api, path: '/console/tax' });
    const year = await screen.findByRole('region', { name: 'This tax year' });
    expect(await within(year).findByText(/Salli doesn’t know your tax residency/)).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'The last computation' })).toBeNull();
    expect(api.to('/v1/tax/latest')).toHaveLength(0);
    expect(document.querySelector('.problem')).toBeNull();
  });

  it('lists every version of a rule set with who wrote it', async () => {
    await setup({ path: `/console/tax/rules/${SET}` });
    expect(await screen.findByRole('heading', { level: 1, name: 'XA 2031' })).toBeTruthy();
    const versions = await screen.findByRole('region', { name: 'Versions' });
    const rows = (await within(versions).findAllByRole('row')).slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining('XA 2031, version 3DraftAn agent: ClaudeRounding the examples.'),
      expect.stringContaining('XA 2031, version 2ProposedAn agent: ClaudeThe 2031 budget raises the relief to 12,500.'),
      expect.stringContaining('XA 2031, version 1ActiveYouFrom the Act'),
    ]);
  });
});

describe('a version, reviewed', () => {
  it('shows what is new against the active version, each figure with the source it cites', async () => {
    await setup({ path: VERSION(tax.VERSION_2.id) });
    expect(await screen.findByRole('heading', { level: 1, name: 'XA 2031, version 2' })).toBeTruthy();
    expect(screen.getByText(/Added by an agent, Claude, on Jun 20, 2031/)).toBeTruthy();
    const changes = await screen.findByRole('region', { name: 'What is new' });
    const relief = (await within(changes).findByText('blocks[key=relief].amount')).closest('li') as HTMLElement;
    expect(within(relief).getByText('A figure')).toBeTruthy();
    expect(within(relief).getByText('12000')).toBeTruthy();
    expect(within(relief).getByText('12500')).toBeTruthy();
    const source = within(relief).getByRole('link', { name: 'XA Budget 2031 (fictional)' });
    expect(source.getAttribute('href')).toBe('https://example.org/xa/budget-2031');
    expect(source.getAttribute('rel')).toBe('noopener noreferrer');
    const examples = region('Worked examples');
    expect(within(examples).getAllByText('Passes')).toHaveLength(4);
    const sources = region('Sources');
    expect(within(sources).getByText('https://example.org/xa/income-tax-act')).toBeTruthy();
    expect(within(region('Deadlines')).getByText('Return due')).toBeTruthy();
  });

  it('shows a worked example that fails, and that the version can’t be activated', async () => {
    const { api } = await setup({ path: VERSION(tax.VERSION_3.id) });
    const examples = await screen.findByRole('region', { name: 'Worked examples' });
    const failing = (await within(examples).findByText('54,000')).closest('li') as HTMLElement;
    expect(within(failing).getByText('Fails')).toBeTruthy();
    expect(within(failing).getByText('payable: expected 8800, got 8600 (from line.balance)')).toBeTruthy();
    const activating = region('Activating');
    expect(within(activating).getByText(/can’t be activated until it compiles and every worked example passes/)).toBeTruthy();
    expect(within(activating).queryByRole('button', { name: /^Activate/ })).toBeNull();
    await click(within(activating).getByRole('button', { name: 'Check it again' }));
    expect(await within(activating).findByText(/Checked: Draft\./)).toBeTruthy();
    expect(api.to(`/v1/tax/rule-sets/${SET}/versions/${tax.VERSION_3.id}/validate`, 'POST')).toHaveLength(1);
  });

  it('saves the canonical document on this device', async () => {
    const saved: Blob[] = [];
    const names: string[] = [];
    const created = vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      saved.push(blob as Blob);
      return 'blob:fixture';
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    await setup({ path: VERSION(tax.VERSION_2.id) });
    const document_ = await screen.findByRole('region', { name: 'The document' });
    expect(within(document_).getByText(`Content hash ${tax.VERSION_2.content_hash}`)).toBeTruthy();
    await click(within(document_).getByRole('button', { name: 'Save it on this device' }));
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(names).toEqual([tax.EXPORT_2.filename]);
    expect(await saved[0]?.text()).toBe(tax.EXPORT_2.text);
    created.mockRestore();
    clicked.mockRestore();
  });
});

describe('activating, a person only', () => {
  it('activates a version after a confirmation that says what Salli will do and who wrote it', async () => {
    const { api, assigned } = await setup({ path: VERSION(tax.VERSION_2.id) });
    const activating = await screen.findByRole('region', { name: 'Activating' });
    expect(within(activating).getByText(/Only a person activates tax rules, never an AI/)).toBeTruthy();
    await click(within(activating).getByRole('button', { name: 'Activate version 2' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Activate version 2?' });
    expect(within(dialog).getByText(/Salli will compute your XA 2031 tax with version 2 from now on\. XA 2031, version 1 stays as history, unchanged\./)).toBeTruthy();
    expect(within(dialog).getByText(/Written by: An agent: Claude\./)).toBeTruthy();
    expect(within(dialog).getByText(/asks for your password on its own sign-in page first/)).toBeTruthy();
    expect(api.to(`/v1/tax/rule-sets/${SET}/versions/${tax.VERSION_2.id}/activate`)).toHaveLength(0);
    await click(within(dialog).getByRole('button', { name: 'Activate it' }));
    expect(await within(activating).findByText(/Activated\. Salli computes XA 2031 with version 2\./)).toBeTruthy();
    expect(api.to(`/v1/tax/rule-sets/${SET}/versions/${tax.VERSION_2.id}/activate`, 'POST')).toHaveLength(1);
    expect(assigned).toHaveLength(0);
    expect(await within(activating).findByText('This is the version Salli computes with.')).toBeTruthy();
  });

  it('past five minutes from the password, signs in again on Salli’s page (prompt=login) and activates on return, once', async () => {
    const api = new MockApi();
    api.tax.stepUps = 1;
    const first = await setup({ api, path: VERSION(tax.VERSION_2.id) });
    const activating = await screen.findByRole('region', { name: 'Activating' });
    await click(within(activating).getByRole('button', { name: 'Activate version 2' }));
    await click(within(await screen.findByRole('alertdialog', { name: 'Activate version 2?' })).getByRole('button', { name: 'Activate it' }));
    // Salli's answer: the step-up problem, as the real server writes it.
    await waitFor(() => expect(first.assigned).toHaveLength(1));
    const url = new URL(first.assigned[0] as string);
    expect(url.pathname).toBe('/mcp/oauth/authorize');
    expect(url.searchParams.get('prompt')).toBe('login');
    expect(url.searchParams.get('client_id')).toBe('salli-console');
    const pending = JSON.parse(first.storage.getItem(KEYS.pending) ?? '{}') as { return_to: string; step_up: boolean; write: unknown };
    expect(pending.return_to).toBe(VERSION(tax.VERSION_2.id));
    expect(pending.step_up).toBe(true);
    expect(pending.write).toEqual({ name: 'tax.ruleSets.versions.activate', input: { ruleSet: SET, version: tax.VERSION_2.id } });
    first.view.unmount();

    // Back from Salli's sign-in page: the same person, so the grant is swapped and the activation runs once more.
    const before = first.storage.getItem(KEYS.refresh);
    const back = await setup({ api, storage: first.storage, signedIn: false, path: `/console/callback?code=again&state=${url.searchParams.get('state') ?? ''}` });
    expect(await screen.findByRole('heading', { level: 1, name: 'XA 2031, version 2' })).toBeTruthy();
    expect(back.location.pathname).toBe(VERSION(tax.VERSION_2.id));
    expect(await screen.findByText(/Activated\. Salli computes XA 2031 with version 2\./)).toBeTruthy();
    expect(api.to(`/v1/tax/rule-sets/${SET}/versions/${tax.VERSION_2.id}/activate`, 'POST')).toHaveLength(2);
    expect(first.storage.getItem(KEYS.refresh)).not.toBe(before);
    expect(first.storage.getItem(KEYS.retry)).toBeNull();
  });

  it('retries once only: a second step-up answer is said, not followed', async () => {
    const api = new MockApi();
    api.tax.stepUps = 1;
    const first = await setup({ api, path: VERSION(tax.VERSION_2.id) });
    await click(await within(await screen.findByRole('region', { name: 'Activating' })).findByRole('button', { name: 'Activate version 2' }));
    await click(within(await screen.findByRole('alertdialog', { name: 'Activate version 2?' })).getByRole('button', { name: 'Activate it' }));
    await waitFor(() => expect(first.assigned).toHaveLength(1));
    const state = new URL(first.assigned[0] as string).searchParams.get('state') ?? '';
    first.view.unmount();
    api.tax.stepUps = 1;
    const back = await setup({ api, storage: first.storage, signedIn: false, path: `/console/callback?code=again&state=${state}` });
    const activating = await screen.findByRole('region', { name: 'Activating' });
    expect(await within(activating).findByText(/Salli still asks for your password before activating/)).toBeTruthy();
    expect(back.assigned).toHaveLength(0);
    expect(api.to(`/v1/tax/rule-sets/${SET}/versions/${tax.VERSION_2.id}/activate`, 'POST')).toHaveLength(2);
  });
});
