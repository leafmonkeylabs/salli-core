/**
 * Panels the server describes (`salli.panel/1`): listed in the navigation,
 * drawn as sent, an action that asks first and then reads the page again, a
 * form that sends what was typed, a refusal shown in its row, and a server
 * with none.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MockApi, problem } from './fixtures/api';
import { PanelsState } from './fixtures/panels';
import { setup } from './harness';

const places = (): HTMLElement => screen.getAllByRole('navigation', { name: 'Places' })[0] as HTMLElement;

async function click(element: HTMLElement): Promise<void> {
  await act(async () => {
    fireEvent.click(element);
  });
}

function withPanels(): MockApi {
  const api = new MockApi();
  api.panels = new PanelsState();
  return api;
}

describe('a panel', () => {
  it('is in the navigation, titled by the server, and draws its sections', async () => {
    await setup({ api: withPanels(), path: '/console/panel/account' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Your account' })).toBeTruthy();
    expect(within(places()).getByRole('link', { name: 'Your account' })).toBeTruthy();
    expect(within(places()).getByRole('link', { name: 'Move your books' })).toBeTruthy();
    const now = await screen.findByRole('region', { name: 'Now' });
    expect(within(now).getByText('Standing')).toBeTruthy();
    expect(within(now).getByText('Starter')).toBeTruthy();
    const more = screen.getByRole('region', { name: 'More room' });
    const link = within(more).getByRole('link', { name: /What is included/ });
    expect(link.getAttribute('href')).toBe('https://example.org/included');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(within(more).getByText('Nothing changes until we reply.')).toBeTruthy();
  });

  it('asks before an action, sends it, and reads the page again', async () => {
    const api = withPanels();
    await setup({ api, path: '/console/panel/account' });
    await click(await screen.findByRole('button', { name: 'Ask for more room' }));
    const dialog = await screen.findByRole('alertdialog', { hidden: true });
    expect(within(dialog).getByText('Ask for more room?')).toBeTruthy();
    // Not now: nothing is sent.
    await click(within(dialog).getByRole('button', { name: 'Not now', hidden: true }));
    expect(api.to('/v1/example/requests', 'POST')).toHaveLength(0);
    await click(screen.getByRole('button', { name: 'Ask for more room' }));
    await click(within(await screen.findByRole('alertdialog', { hidden: true })).getByRole('button', { name: 'Ask for more room', hidden: true }));
    await waitFor(() => expect(api.to('/v1/example/requests', 'POST')).toHaveLength(1));
    // The page, read again, shows what the server now says.
    expect(await screen.findByText('Waiting for a reply')).toBeTruthy();
    expect(screen.getByText('We will reply by email.')).toBeTruthy();
  });

  it('sends a form’s fields, the empty ones left out, and holds a required one back', async () => {
    const api = withPanels();
    await setup({ api, path: '/console/panel/account' });
    const send = await screen.findByRole('button', { name: 'Send' });
    await click(send);
    expect(await screen.findByText('Required')).toBeTruthy();
    expect(api.to('/v1/example/requests', 'POST')).toHaveLength(0);
    fireEvent.change(screen.getByRole('textbox', { name: /People/ }), { target: { value: '3' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Kind' }), { target: { value: 'Practice' } });
    await click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(api.to('/v1/example/requests', 'POST')).toHaveLength(1));
    expect(JSON.parse(api.to('/v1/example/requests', 'POST')[0]?.body ?? '{}')).toEqual({ size: '3', kind: 'Practice' });
  });

  it('shows a refusal in the row that asked', async () => {
    const api = withPanels();
    (api.panels as PanelsState).refuse = { status: 409, body: problem(409, 'Already requested') };
    await setup({ api, path: '/console/panel/account' });
    fireEvent.change(await screen.findByRole('textbox', { name: /People/ }), { target: { value: '2' } });
    await click(screen.getByRole('button', { name: 'Send' }));
    expect(within(await screen.findByRole('alert')).getByText(/Already requested/, { selector: '.problem-title' })).toBeTruthy();
  });

  it('says so for a page with nothing in it, and for one that does not exist', async () => {
    await setup({ api: withPanels(), path: '/console/panel/move' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Move your books' })).toBeTruthy();
    expect(screen.getByText('Nothing to show yet.')).toBeTruthy();
  });

  it('shows the server’s problem for a panel it does not have', async () => {
    await setup({ api: withPanels(), path: '/console/panel/nothing' });
    expect(await screen.findByRole('alert')).toBeTruthy();
  });

  it('is not asked for on a server with none', async () => {
    const api = new MockApi();
    await setup({ api, path: '/console/' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeTruthy();
    expect(api.to('/v1/panels')).toHaveLength(0);
  });

  it('cannot draw a document that is not a panel', async () => {
    const api = withPanels();
    api.overrides.push(({ path }) => (path === '/v1/panels/account' ? { status: 200, body: { schema: 'something/else' } } : undefined));
    await setup({ api, path: '/console/panel/account' });
    expect(await screen.findByRole('heading', { level: 1, name: 'This page can’t be shown.' })).toBeTruthy();
  });
});
