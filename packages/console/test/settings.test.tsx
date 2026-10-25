/**
 * Settings: the profile (what the API lets a person change) and every
 * sign-in, each of which can be ended after a confirmation.
 */
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MockApi } from './fixtures/api';
import { setup } from './harness';

const region = (name: string): HTMLElement => screen.getByRole('region', { name });

describe('the profile', () => {
  it('shows the profile and sends only what changed, codes in capitals', async () => {
    const { api } = await setup({ path: '/console/settings' });
    const profile = await screen.findByRole('region', { name: 'Profile' });
    const name = await within(profile).findByRole('textbox', { name: 'Name' });
    expect((name as HTMLInputElement).value).toBe('Ana');
    expect(within(profile).getByText('ana@example.org')).toBeTruthy();
    fireEvent.change(name, { target: { value: 'Ana Pereira' } });
    fireEvent.change(within(profile).getByRole('textbox', { name: 'Tax residency' }), { target: { value: 'nz' } });
    fireEvent.change(within(profile).getByRole('combobox', { name: 'Time zone' }), { target: { value: 'Pacific/Auckland' } });
    await act(async () => {
      fireEvent.click(within(profile).getByRole('button', { name: 'Save the profile' }));
    });
    expect(await within(profile).findByText(/Saved\./)).toBeTruthy();
    const patch = api.to('/v1/onboarding/profile', 'PATCH');
    expect(patch).toHaveLength(1);
    expect(JSON.parse(patch[0]?.body ?? '{}')).toEqual({ display_name: 'Ana Pereira', tax_residency: 'NZ' });
    expect(JSON.parse(api.to('/v1/notifications/preferences', 'PATCH')[0]?.body ?? '{}')).toEqual({ time_zone: 'Pacific/Auckland' });
  });

  it('shows what Salli refused, field by field', async () => {
    const api = new MockApi();
    api.overrides.push((r) =>
      r.method === 'PATCH' && r.path === '/v1/onboarding/profile'
        ? {
            status: 409,
            body: {
              type: '/problems/base-currency-locked',
              title: 'Base currency can no longer change',
              status: 409,
              detail: 'Entries are already stored in EUR.',
            },
          }
        : undefined,
    );
    await setup({ api, path: '/console/settings' });
    const profile = await screen.findByRole('region', { name: 'Profile' });
    fireEvent.change(await within(profile).findByRole('textbox', { name: 'Base currency' }), { target: { value: 'usd' } });
    await act(async () => {
      fireEvent.click(within(profile).getByRole('button', { name: 'Save the profile' }));
    });
    expect(await within(profile).findByText('Base currency can no longer change')).toBeTruthy();
    expect(within(profile).getByText('Entries are already stored in EUR.')).toBeTruthy();
    expect(JSON.parse(api.to('/v1/onboarding/profile', 'PATCH')[0]?.body ?? '{}')).toEqual({ base_currency: 'USD' });
  });
});

describe('sign-ins', () => {
  it('lists every way in, marks this tab, and ends one after saying what will happen', async () => {
    const { api } = await setup({ path: '/console/settings' });
    const signIns = await screen.findByRole('region', { name: 'Sign-ins' });
    const table = await within(signIns).findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[0] as HTMLElement).getByText('This tab')).toBeTruthy();
    expect(within(table).getByText('salli command')).toBeTruthy();
    expect(within(table).getByText('Session · curl/8.7.1')).toBeTruthy();

    fireEvent.click(within(rows[1] as HTMLElement).getByRole('button', { name: /Sign out salli command/ }));
    const dialog = await screen.findByRole('alertdialog');
    expect(within(dialog).getByText(/Salli will end the salli command sign-in started Sep 1, 2026/)).toBeTruthy();
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Sign out' }));
    });
    await waitFor(() => expect(api.to('/v1/auth/sign-ins/grant-cli-1', 'DELETE')).toHaveLength(1));
    expect(await within(region('Sign-ins')).findByText(/Signed out\./)).toBeTruthy();
    await waitFor(() => expect(within(region('Sign-ins')).getAllByRole('row')).toHaveLength(3));
  });

  it('ending this tab’s own sign-in signs out here', async () => {
    const { api } = await setup({ path: '/console/settings' });
    const signIns = await screen.findByRole('region', { name: 'Sign-ins' });
    const table = await within(signIns).findByRole('table');
    fireEvent.click(within(table).getAllByRole('button', { name: /Sign out Console/ })[0] as HTMLElement);
    const dialog = await screen.findByRole('alertdialog');
    expect(within(dialog).getByText(/This is the tab you are using/)).toBeTruthy();
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Sign out' }));
    });
    expect(await screen.findByRole('heading', { name: 'Signed out' })).toBeTruthy();
    await waitFor(() => expect(api.to('/mcp/oauth/revoke')).toHaveLength(1));
  });
});

describe('support access', () => {
  it('shows each support session beside the sign-ins, and ends an open one', async () => {
    const api = new MockApi();
    api.supportSessions = [
      {
        id: 'support-1',
        reason: 'Ticket 42: the import stopped',
        opened_at: '2026-10-26T09:00:00Z',
        expires_at: '2026-10-26T10:00:00Z',
        ended_at: null,
        ended_by: null,
        open: true,
        reads: [{ at: '2026-10-26T09:05:00Z', path: '/accounts' }],
      },
    ];
    await setup({ path: '/console/settings', api });
    const signIns = await screen.findByRole('region', { name: 'Sign-ins' });
    expect(await within(signIns).findByText('Ticket 42: the import stopped')).toBeTruthy();
    await act(async () => {
      fireEvent.click(within(signIns).getByRole('button', { name: 'End it' }));
    });
    await waitFor(() => expect(api.to('/v1/auth/support-access/support-1', 'DELETE')).toHaveLength(1));
    expect(await within(region('Sign-ins')).findByText('Ended by you')).toBeTruthy();
  });
});

describe('this device', () => {
  it('keeps the theme and the locale in this browser only', async () => {
    const { api } = await setup({ path: '/console/settings' });
    const device = await screen.findByRole('region', { name: 'On this device' });
    const before = api.requests.length;
    fireEvent.click(within(device).getByRole('radio', { name: 'Dark' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem('salli-console:theme')).toBe('dark');
    fireEvent.click(within(device).getByRole('radio', { name: 'As the system' }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(api.requests.length).toBe(before);
  });
});

describe('two-step sign-in', () => {
  const URI = 'otpauth://totp/Salli%3Aana%40example.org?secret=JBSWY3DPEHPK3PXP&issuer=Salli';
  const CODES = ['k7m2p-x9qrt', 'a2b3c-d4e5f'];

  it('turns it on: the link once, a code from the app, then the recovery codes once', async () => {
    const api = new MockApi();
    api.overrides.push((r) => {
      if (r.method === 'POST' && r.path === '/v1/auth/totp') return { status: 201, body: { secret: 'JBSWY3DPEHPK3PXP', uri: URI } };
      if (r.method === 'POST' && r.path === '/v1/auth/totp/confirm') {
        api.me = { ...api.me, totp_enabled: true };
        return { status: 200, body: { recovery_codes: CODES } };
      }
      return undefined;
    });
    await setup({ api, path: '/console/settings' });
    const panel = await screen.findByRole('region', { name: 'Two-step sign-in' });
    expect(await within(panel).findByText(/Off\. Your password alone signs you in\./)).toBeTruthy();
    await act(async () => {
      fireEvent.click(within(panel).getByRole('button', { name: 'Turn on two-step sign-in' }));
    });
    const link = (await within(panel).findByRole('textbox', { name: 'For your authenticator app' })) as HTMLInputElement;
    expect(link.value).toBe(URI);
    expect(within(panel).getByText('JBSWY3DPEHPK3PXP')).toBeTruthy();

    // No code: said, and nothing sent.
    await act(async () => {
      fireEvent.click(within(panel).getByRole('button', { name: 'Turn it on' }));
    });
    expect(api.to('/v1/auth/totp/confirm', 'POST')).toHaveLength(0);
    fireEvent.change(within(panel).getByRole('textbox', { name: /The code your app shows now/ }), { target: { value: ' 123456 ' } });
    await act(async () => {
      fireEvent.click(within(panel).getByRole('button', { name: 'Turn it on' }));
    });
    await waitFor(() => expect(api.to('/v1/auth/totp/confirm', 'POST')).toHaveLength(1));
    expect(JSON.parse(api.to('/v1/auth/totp/confirm', 'POST')[0]?.body ?? '{}')).toEqual({ code: '123456' });
    const codes = (await within(panel).findByRole('textbox', { name: /Recovery codes/ })) as HTMLInputElement;
    expect(codes.value).toBe(CODES.join(' '));
    expect(within(panel).queryByText('JBSWY3DPEHPK3PXP')).toBeNull();

    await act(async () => {
      fireEvent.click(within(panel).getByRole('button', { name: 'I have copied it' }));
    });
    expect(await within(panel).findByText(/On\. Every sign-in with your password also asks for a code\./)).toBeTruthy();
    expect(document.body.innerHTML).not.toContain(CODES[0]);
  });

  it('when on, says how to turn it off, and never asks for the password', async () => {
    const api = new MockApi();
    api.me = { ...api.me, totp_enabled: true };
    await setup({ api, path: '/console/settings' });
    const panel = await screen.findByRole('region', { name: 'Two-step sign-in' });
    expect(await within(panel).findByText(/salli totp disable/)).toBeTruthy();
    expect(within(panel).queryByRole('button')).toBeNull();
    expect(document.querySelector('input[type=password]')).toBeNull();
  });
});
