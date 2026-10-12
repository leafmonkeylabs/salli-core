/**
 * The rest of Settings (C4) on what the real server answers
 * (fixtures/settings.ts): tokens made and revoked, one with tax:activate
 * behind the step-up; MCP switched and a client revoked; model keys set and
 * removed; digests; your data saved on this device.
 *
 * A token or a key appears once and is kept nowhere after: not in the page
 * once it is left, not in sessionStorage or localStorage, not in the
 * query or mutation caches.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { KEYS } from '../src/auth/session';
import { MockApi } from './fixtures/api';
import * as settings from './fixtures/settings';
import { setup, type Harness } from './harness';

const TOKEN = settings.TOKEN_MADE.token;
const KEY = 'sk-ant-console-test-not-a-key-9c4e';

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

function type(element: HTMLElement, value: string): void {
  fireEvent.change(element, { target: { value } });
}

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

/** Everything this tab keeps or shows, as text: the page, both storages and both caches. */
function everythingKept(h: Harness): string {
  return [
    document.body.innerHTML,
    JSON.stringify(h.storage.entries()),
    JSON.stringify({ ...window.sessionStorage }),
    JSON.stringify({ ...window.localStorage }),
    JSON.stringify(h.app.queryClient.getQueryCache().getAll().map((q) => q.state.data)),
    JSON.stringify(h.app.queryClient.getMutationCache().getAll().map((m) => [m.state.variables, m.state.data])),
  ].join('\n');
}

/** Leaves the page for Settings' first page, by its own link. */
async function leave(): Promise<void> {
  await click(screen.getByRole('navigation', { name: 'Settings' }).querySelector('a[href="/console/settings"]') as HTMLElement);
  await screen.findByRole('heading', { level: 1, name: 'Settings' });
}

describe('personal access tokens', () => {
  it('lists the tokens with what each may do, and revokes one after a confirmation', async () => {
    const { api } = await setup({ path: '/console/settings/tokens' });
    const yours = await screen.findByRole('region', { name: 'Your tokens' });
    const backups = (await within(yours).findByText('Backups')).closest('tr') as HTMLElement;
    expect(within(backups).getByText('Nov 30, 2026')).toBeTruthy();
    expect(within(backups).getByText('Read and write your data')).toBeTruthy();
    expect(within(backups).getByText('salli_pat_fixt…')).toBeTruthy();
    await click(within(backups).getByRole('button', { name: 'Revoke Backups' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Revoke this token?' });
    expect(within(dialog).getByText(/Whatever uses it is refused from now on/)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Revoke it' }));
    const id = settings.TOKENS.find((t) => t.name === 'Backups')!.id;
    await waitFor(() => expect(api.to(`/v1/tokens/${id}`, 'DELETE')).toHaveLength(1));
    expect(await within(yours).findByText(/Revoked: Backups\./)).toBeTruthy();
    await waitFor(() => expect(within(yours).queryByText('Backups')).toBeNull());
  });

  it('shows a new token once, with copy, and keeps it nowhere once the page is left', async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const h = await setup({ path: '/console/settings/tokens' });
    const make = await screen.findByRole('region', { name: 'Make a token' });
    type(await within(make).findByRole('textbox', { name: /Its name/ }), 'Backups again');
    await click(within(make).getByRole('button', { name: 'Make the token' }));
    // No tax:activate asked for: no confirmation, made at once.
    const shown = (await within(make).findByLabelText('Your new token')) as HTMLInputElement;
    expect(shown.value).toBe(TOKEN);
    expect(shown.readOnly).toBe(true);
    expect(JSON.parse(h.api.to('/v1/tokens', 'POST')[0]?.body ?? '{}')).toEqual({ name: 'Backups again', permissions: [] });
    expect(within(make).getByText(/Shown this once\. Copy it now/)).toBeTruthy();
    await click(within(make).getByRole('button', { name: 'Copy it' }));
    expect(writeText).toHaveBeenCalledWith(TOKEN);
    expect(await within(make).findByText('Copied.')).toBeTruthy();
    // Kept nowhere but the page that shows it…
    expect(JSON.stringify(h.storage.entries())).not.toContain(TOKEN);
    // …and nowhere at all once it is left.
    await leave();
    await waitFor(() => expect(everythingKept(h)).not.toContain(TOKEN));
    expect(everythingKept(h)).not.toContain('fixture-tax-helper');
  });

  it('says where copying isn’t possible, with the text selected to copy by keyboard', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn(async () => Promise.reject(new Error('denied'))) }, configurable: true });
    await setup({ path: '/console/settings/tokens' });
    const make = await screen.findByRole('region', { name: 'Make a token' });
    type(await within(make).findByRole('textbox', { name: /Its name/ }), 'Spare');
    await click(within(make).getByRole('button', { name: 'Make the token' }));
    const shown = (await within(make).findByLabelText('Your new token')) as HTMLInputElement;
    await click(within(make).getByRole('button', { name: 'Copy it' }));
    expect(await within(make).findByText(/Couldn’t copy here\. The text above is selected/)).toBeTruthy();
    expect(document.activeElement).toBe(shown);
    await click(within(make).getByRole('button', { name: 'I have copied it' }));
    expect(within(make).queryByLabelText('Your new token')).toBeNull();
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });

  it('asks first for a token that may activate tax rules, and past five minutes signs in again before making it', async () => {
    const api = new MockApi();
    api.settings.stepUps = 1;
    const first = await setup({ api, path: '/console/settings/tokens' });
    const make = await screen.findByRole('region', { name: 'Make a token' });
    type(await within(make).findByRole('textbox', { name: /Its name/ }), 'Tax helper');
    await click(within(make).getByRole('checkbox', { name: /It may activate tax rules/ }));
    await click(within(make).getByRole('button', { name: 'Make the token' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Make a token that may activate tax rules?' });
    expect(within(dialog).getByText(/an AI holding it could activate rules/)).toBeTruthy();
    expect(api.to('/v1/tokens', 'POST')).toHaveLength(0);
    await click(within(dialog).getByRole('button', { name: 'Make it' }));
    await waitFor(() => expect(first.assigned).toHaveLength(1));
    const url = new URL(first.assigned[0] as string);
    expect(url.searchParams.get('prompt')).toBe('login');
    const pending = JSON.parse(first.storage.getItem(KEYS.pending) ?? '{}') as { write: unknown };
    expect(pending.write).toEqual({ name: 'tokens.create', input: { name: 'Tax helper', permissions: ['tax:activate'] } });
    first.view.unmount();

    const back = await setup({ api, storage: first.storage, signedIn: false, path: `/console/callback?code=again&state=${url.searchParams.get('state') ?? ''}` });
    const shown = (await screen.findByLabelText('Your new token')) as HTMLInputElement;
    expect(shown.value).toBe(TOKEN);
    expect(api.to('/v1/tokens', 'POST')).toHaveLength(2);
    expect(JSON.parse(api.to('/v1/tokens', 'POST')[1]?.body ?? '{}')).toEqual({ name: 'Tax helper', permissions: ['tax:activate'] });
    expect(JSON.stringify(first.storage.entries())).not.toContain(TOKEN);
    await leave();
    await waitFor(() => expect(everythingKept(back)).not.toContain(TOKEN));
  });

  it('asks for a name, and shows Salli’s refusals at their fields', async () => {
    const { api } = await setup({ path: '/console/settings/tokens' });
    const make = await screen.findByRole('region', { name: 'Make a token' });
    await click(await within(make).findByRole('button', { name: 'Make the token' }));
    expect(within(make).getAllByText('A token needs a name.').length).toBeGreaterThan(0);
    type(within(make).getByRole('textbox', { name: /Its name/ }), 'Later');
    type(within(make).getByRole('textbox', { name: /Expires after/ }), '0');
    await click(within(make).getByRole('button', { name: 'Make the token' }));
    expect(within(make).getAllByText('A whole number of days from 1 to 3650.').length).toBeGreaterThan(0);
    expect(api.to('/v1/tokens', 'POST')).toHaveLength(0);
  });
});

describe('AI connections', () => {
  it('turns MCP off only after asking, and on again at once', async () => {
    const { api } = await setup({ path: '/console/settings/ai' });
    const mcp = await screen.findByRole('region', { name: 'MCP' });
    expect(await within(mcp).findByText('On: connected AI clients can use Salli.')).toBeTruthy();
    await click(within(mcp).getByRole('button', { name: 'Turn MCP off' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Turn MCP off?' });
    expect(within(dialog).getByText(/Salli will refuse every AI client over MCP until you turn it on again/)).toBeTruthy();
    expect(api.to('/v1/mcp/connections/enabled', 'PUT')).toHaveLength(0);
    await click(within(dialog).getByRole('button', { name: 'Turn it off' }));
    expect(await within(mcp).findByText(/MCP is off\./)).toBeTruthy();
    expect(JSON.parse(api.to('/v1/mcp/connections/enabled', 'PUT')[0]?.body ?? '{}')).toEqual({ enabled: false });
    await click(await within(mcp).findByRole('button', { name: 'Turn MCP on' }));
    expect(await within(mcp).findByText(/MCP is on\./)).toBeTruthy();
    expect(JSON.parse(api.to('/v1/mcp/connections/enabled', 'PUT')[1]?.body ?? '{}')).toEqual({ enabled: true });
  });

  it('revokes a connected client after a confirmation', async () => {
    const { api } = await setup({ path: '/console/settings/ai' });
    const clients = await screen.findByRole('region', { name: 'Connected clients' });
    await click(await within(clients).findByRole('button', { name: 'Revoke Claude' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Revoke this connection?' });
    expect(within(dialog).getByText(/Salli will end every sign-in Claude holds over MCP, on every device/)).toBeTruthy();
    await click(within(dialog).getByRole('button', { name: 'Revoke it' }));
    await waitFor(() => expect(api.to('/v1/mcp/connections/mcp-token-1', 'DELETE')).toHaveLength(1));
    expect(await within(clients).findByText('No AI client is connected.')).toBeTruthy();
  });

  it('saves a key, never shows it again, and keeps it nowhere', async () => {
    const h = await setup({ path: '/console/settings/ai' });
    const keys = await screen.findByRole('region', { name: 'Model keys' });
    expect(await within(keys).findByText('Salli’s features use Anthropic, with your key.')).toBeTruthy();
    expect(within(keys).getByText(/A key ending 7f3a, checked Sep 15, 2026/)).toBeTruthy();
    const field = within(keys).getByLabelText('Anthropic key') as HTMLInputElement;
    expect(field.type).toBe('password');
    type(field, KEY);
    await click(within(keys).getByRole('button', { name: 'Save the Anthropic key' }));
    expect(await within(keys).findByText(/Saved the Anthropic key\./)).toBeTruthy();
    expect(JSON.parse(h.api.to('/v1/llm-keys/anthropic', 'PUT')[0]?.body ?? '{}')).toEqual({ key: KEY });
    expect(await within(keys).findByText(/A key ending 9c4e/)).toBeTruthy();
    expect((within(keys).getByLabelText('Anthropic key') as HTMLInputElement).value).toBe('');
    // Never shown, never kept: not even while the page is open.
    await waitFor(() => expect(everythingKept(h)).not.toContain(KEY));
    await leave();
    await waitFor(() => expect(everythingKept(h)).not.toContain(KEY));
  });

  it('shows a key the provider refuses, never keeping it for a sign-in', async () => {
    const h = await setup({ path: '/console/settings/ai' });
    const keys = await screen.findByRole('region', { name: 'Model keys' });
    type(await within(keys).findByLabelText('OpenAI key'), 'sk-console-test-wrong-1111');
    await click(within(keys).getByRole('button', { name: 'Save the OpenAI key' }));
    expect(await within(keys).findByText(/OpenAI rejected this key/)).toBeTruthy();
    expect(JSON.stringify(h.storage.entries())).not.toContain('sk-console-test-wrong-1111');
    expect(h.assigned).toHaveLength(0);
    await leave();
    await waitFor(() => expect(everythingKept(h)).not.toContain('sk-console-test-wrong-1111'));
  });

  it('removes a key after a confirmation', async () => {
    const { api } = await setup({ path: '/console/settings/ai' });
    const keys = await screen.findByRole('region', { name: 'Model keys' });
    await click(await within(keys).findByRole('button', { name: 'Remove the Anthropic key' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Remove the Anthropic key?' });
    await click(within(dialog).getByRole('button', { name: 'Remove it' }));
    await waitFor(() => expect(api.to('/v1/llm-keys/anthropic', 'DELETE')).toHaveLength(1));
    expect(await within(keys).findByText(/Removed the Anthropic key\./)).toBeTruthy();
  });
});

describe('digests', () => {
  it('saves only what changed, previews the digest and lists what went', async () => {
    const { api } = await setup({ path: '/console/settings/digests' });
    const when = await screen.findByRole('region', { name: 'When' });
    expect(((await within(when).findByRole('checkbox', { name: 'Send me a digest' })) as HTMLInputElement).checked).toBe(true);
    await click(within(when).getByRole('radio', { name: 'Every month' }));
    fireEvent.change(within(when).getByRole('combobox', { name: 'At' }), { target: { value: '7' } });
    await click(within(when).getByRole('checkbox', { name: 'Imported transactions waiting for review' }));
    await click(within(when).getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(api.to('/v1/notifications/preferences', 'PATCH')).toHaveLength(1));
    expect(JSON.parse(api.to('/v1/notifications/preferences', 'PATCH')[0]?.body ?? '{}')).toEqual({
      cadence: 'monthly',
      hour: 7,
      items: ['decision_review_due', 'reminder_due', 'filing_deadline', 'cash_below_zero_ahead', 'transactions_to_review'],
    });
    expect(await within(screen.getByRole('region', { name: 'When' })).findByText(/Saved\./)).toBeTruthy();
    const preview = screen.getByRole('region', { name: 'Preview' });
    expect(within(preview).getByText('Salli: what is waiting, week of 2026-10-05')).toBeTruthy();
    expect(within(preview).getByText(/1 decision ready for review \(since 2026-09-30\)/)).toBeTruthy();
    const sent = screen.getByRole('region', { name: 'Digests sent' });
    const row = within(sent).getByText('2026-W41').closest('tr') as HTMLElement;
    expect(within(row).getByText('Sent')).toBeTruthy();
    expect(within(row).getByText(/Decisions ready for review: 1 \(Sep 30, 2026\)/)).toBeTruthy();
  });

  it('asks for a time zone before turning digests on', async () => {
    const api = new MockApi();
    api.settings.preferences = { ...api.settings.preferences, enabled: false, time_zone: null, next_at: null };
    await setup({ api, path: '/console/settings/digests' });
    const when = await screen.findByRole('region', { name: 'When' });
    await click(await within(when).findByRole('checkbox', { name: 'Send me a digest' }));
    await click(within(when).getByRole('button', { name: 'Save' }));
    expect(within(when).getAllByText('A digest needs your time zone to know when to go.').length).toBeGreaterThan(0);
    expect(api.to('/v1/notifications/preferences', 'PATCH')).toHaveLength(0);
  });
});

describe('your data', () => {
  it('saves the books as Beancount and hledger, and everything as exact JSON, on this device', async () => {
    const saved: Array<{ blob: Blob; name: string }> = [];
    vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      saved.push({ blob: blob as Blob, name: '' });
      return 'blob:fixture';
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      const last = saved[saved.length - 1];
      if (last) last.name = this.download;
    });
    await setup({ path: '/console/settings/data' });
    await click(await screen.findByRole('button', { name: 'Save as Beancount' }));
    await waitFor(() => expect(saved).toHaveLength(1));
    await click(screen.getByRole('button', { name: 'Save as hledger' }));
    await waitFor(() => expect(saved).toHaveLength(2));
    await click(screen.getByRole('button', { name: 'Save all of it (JSON)' }));
    await waitFor(() => expect(saved).toHaveLength(3));
    expect(saved.map((s) => s.name)).toEqual(['salli-2026-10-11.beancount', 'salli-2026-10-11.journal', 'salli-2026-10-11.json']);
    expect(await saved[0]?.blob.text()).toBe(settings.BEANCOUNT);
    expect(await saved[1]?.blob.text()).toBe(settings.HLEDGER);
    // The amount a float can't hold, digit for digit.
    expect(await saved[2]?.blob.text()).toContain('"amount": "9007199254740993.01"');
    expect(await screen.findByText(/Saved salli-2026-10-11\.json\./)).toBeTruthy();
  });
});
