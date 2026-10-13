/**
 * `createConsole({ extensions })` (decision 19): a test extension adds a
 * page, a place in the navigation and a panel in Settings, each shown only
 * when /v1/meta lists the server extension it requires.
 */
import { act, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useRead } from '../src/api';
import type { ConsoleExtension } from '../src/extensions';
import { Page } from '../src/kit/layout';
import { Money } from '../src/kit/Money';
import { MockApi } from './fixtures/api';
import { setup } from './harness';
import { reportsBalanceSheet } from '@leafmonkeylabs/salli-sdk';

/** A page built from the kit, reading through the SDK like the console's own. */
function ExamplePage() {
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  return (
    <Page title="Example">
      <p>{sheet.data ? <Money amount={sheet.data.net_worth} currency={sheet.data.currency} /> : null}</p>
    </Page>
  );
}

const example: ConsoleExtension = {
  requires: 'example',
  routes: [{ path: '/example', component: ExamplePage }, { path: '/example/later', load: async () => ({ default: () => <Page title="Later">{null}</Page> }) }],
  navigation: [{ to: '/example', label: 'Example' }],
  settingsPanels: [{ id: 'example', title: 'Example settings', component: () => <p>Set by the example extension.</p> }],
};

const places = (): HTMLElement => screen.getAllByRole('navigation', { name: 'Places' })[0] as HTMLElement;

describe('a console extension', () => {
  it('adds its page, navigation and settings panel when the server runs its half', async () => {
    const api = new MockApi();
    api.extensions = ['example'];
    await setup({ api, extensions: [example], path: '/console/example' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Example' })).toBeTruthy();
    expect(await screen.findByText('EUR 344,026.47')).toBeTruthy();
    expect(within(places()).getByRole('link', { name: 'Example' })).toBeTruthy();
    await act(async () => {
      within(places()).getByRole('link', { name: 'Settings' }).click();
    });
    expect(await screen.findByRole('region', { name: 'Example settings' })).toBeTruthy();
    expect(screen.getByText('Set by the example extension.')).toBeTruthy();
  });

  it('loads a page from its own chunk', async () => {
    const api = new MockApi();
    api.extensions = ['example'];
    await setup({ api, extensions: [example], path: '/console/example/later' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Later' })).toBeTruthy();
  });

  it('is the open console on a server without it', async () => {
    await setup({ extensions: [example], path: '/console/example' });
    expect(await screen.findByRole('heading', { level: 1, name: 'No such page' })).toBeTruthy();
    expect(within(places()).queryByRole('link', { name: 'Example' })).toBeNull();
    await act(async () => {
      within(places()).getByRole('link', { name: 'Settings' }).click();
    });
    await screen.findByRole('region', { name: 'Profile' });
    expect(screen.queryByRole('region', { name: 'Example settings' })).toBeNull();
  });
});
