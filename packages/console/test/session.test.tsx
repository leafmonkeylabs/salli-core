/**
 * Signing in (decisions 3 to 6): PKCE through Salli's own sign-in page, the
 * access token in memory and the refresh token in the tab, one sign-in per
 * tab, the step-up that checks it is the same person, and signing out.
 */
import { act, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KEYS } from '../src/auth/session';
import { MockApi, STEP_UP } from './fixtures/api';
import { metaAt, ORIGIN, SOMEONE_ELSE } from './fixtures/auth';
import { keepSignIn, MemoryStorage, setup } from './harness';

const form = (body: string): Record<string, string> => Object.fromEntries(new URLSearchParams(body));

describe('signing in', () => {
  it('sends a new tab to Salli’s sign-in page with PKCE, keeping only the state and verifier', async () => {
    const { assigned, storage } = await setup({ signedIn: false, path: '/console/settings?x=1' });
    expect(assigned).toHaveLength(1);
    const url = new URL(assigned[0] as string);
    expect(`${url.origin}${url.pathname}`).toBe(`${ORIGIN}/mcp/oauth/authorize`);
    const params = Object.fromEntries(url.searchParams);
    expect(params).toMatchObject({
      response_type: 'code',
      client_id: 'salli-console',
      redirect_uri: `${ORIGIN}/console/callback`,
      code_challenge_method: 'S256',
      resource: `${ORIGIN}/v1`,
    });
    expect(params.prompt).toBeUndefined();
    const pending = JSON.parse(storage.getItem(KEYS.pending) ?? '{}') as Record<string, unknown>;
    expect(pending.state).toBe(params.state);
    expect(pending.return_to).toBe('/console/settings?x=1');
    expect(storage.getItem(KEYS.refresh)).toBeNull();
    expect(screen.getByText(/Taking you to Salli’s sign-in page/)).toBeTruthy();
  });

  it('exchanges the code on return, keeps the refresh token in the tab and the access token in memory only', async () => {
    const first = await setup({ signedIn: false });
    const state = new URL(first.assigned[0] as string).searchParams.get('state');
    first.view.unmount();

    // The browser comes back to /console/callback in the same tab.
    const { api, storage, location } = await setup({
      signedIn: false,
      storage: first.storage,
      path: `/console/callback?code=the-code&state=${state}`,
    });
    const exchange = api.to('/mcp/oauth/token')[0];
    expect(form(exchange?.body ?? '')).toMatchObject({
      grant_type: 'authorization_code',
      code: 'the-code',
      client_id: 'salli-console',
      redirect_uri: `${ORIGIN}/console/callback`,
      resource: `${ORIGIN}/v1`,
    });
    expect(form(exchange?.body ?? '').code_verifier).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(location.pathname).toBe('/console/');
    expect(storage.getItem(KEYS.refresh)).toBe('rt-1');
    expect(Object.values(storage.entries()).join(' ')).not.toContain('at-1');
    expect(storage.getItem(KEYS.pending)).toBeNull();
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeTruthy();
    await waitFor(() => expect(api.to('/v1/reports/balance-sheet')[0]?.authorization).toBe('Bearer at-1'));
  });

  it('refuses a callback whose state it did not send', async () => {
    const storage = new MemoryStorage();
    storage.setItem(KEYS.pending, JSON.stringify({ state: 'mine', verifier: 'v', return_to: '/console/', step_up: false }));
    const { api } = await setup({ signedIn: false, storage, path: '/console/callback?code=c&state=forged' });
    expect(api.to('/mcp/oauth/token')).toHaveLength(0);
    expect(screen.getByRole('heading', { name: 'That sign-in can’t be used' })).toBeTruthy();
  });

  it('keeps the sign-in across a reload, refreshing first under its lock', async () => {
    const { api, storage } = await setup();
    await screen.findByRole('heading', { level: 1, name: 'Home' });
    const refresh = api.to('/mcp/oauth/token')[0];
    expect(form(refresh?.body ?? '')).toMatchObject({ grant_type: 'refresh_token', refresh_token: 'rt-0', client_id: 'salli-console' });
    expect(storage.getItem(KEYS.refresh)).toBe('rt-1');
  });

  it('drops a duplicated tab’s copy and signs in afresh, so two tabs never rotate one token', async () => {
    const { api, storage, assigned } = await setup({ claim: async () => null });
    expect(api.to('/mcp/oauth/token')).toHaveLength(0);
    expect(storage.getItem(KEYS.refresh)).toBeNull();
    expect(assigned[0]).toContain('/mcp/oauth/authorize');
  });

  it('moves to SALLI_PUBLIC_URL’s origin before signing in', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.path === '/v1/meta' ? { status: 200, body: metaAt('https://money.example.org') } : undefined));
    const { assigned } = await setup({ api, signedIn: false, path: '/console/settings' });
    expect(assigned).toEqual(['https://money.example.org/console/settings']);
  });
});

describe('signing out', () => {
  it('revokes the tab’s grant and clears the tab', async () => {
    const { api, app, storage } = await setup();
    await screen.findByRole('heading', { level: 1, name: 'Home' });
    // Sign out is under who is signed in, in the top bar.
    await act(async () => {
      screen.getByRole('button', { name: /signed in as ana@example\.org/ }).click();
    });
    await act(async () => {
      screen.getByRole('button', { name: 'Sign out' }).click();
    });
    await screen.findByRole('heading', { name: 'Signed out' });
    expect(screen.getByText(/You signed out/)).toBeTruthy();
    await waitFor(() => expect(api.to('/mcp/oauth/revoke')).toHaveLength(1));
    expect(form(api.to('/mcp/oauth/revoke')[0]?.body ?? '')).toMatchObject({ token: 'rt-1', token_type_hint: 'refresh_token' });
    expect(storage.entries()).toEqual({});
    expect(app.queryClient.getQueryCache().getAll()).toHaveLength(0);
  });

  it('says so when Salli has ended the sign-in', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.path === '/mcp/oauth/token' ? { status: 400, body: { error: 'invalid_grant', error_description: 'already used' } } : undefined));
    const { storage } = await setup({ api });
    expect(await screen.findByText(/This sign-in has ended/)).toBeTruthy();
    expect(storage.getItem(KEYS.refresh)).toBeNull();
    expect(api.to('/mcp/oauth/revoke')).toHaveLength(0);
  });
});

describe('step-up', () => {
  async function stepUpFrom(api: MockApi) {
    // A write Salli refuses until the password is entered again.
    const { app, storage, assigned } = await setup({ api, path: '/console/settings' });
    await screen.findByRole('heading', { level: 1, name: 'Settings' });
    await act(async () => {
      await app.session.stepUp({ name: 'profile.update', input: { profile: { display_name: 'Ana P' } } });
    });
    const url = new URL(assigned.at(-1) as string);
    expect(url.searchParams.get('prompt')).toBe('login');
    const state = url.searchParams.get('state');
    return { storage, state };
  }

  it('signs in again with prompt=login, checks it is the same person, swaps grants and retries the write once', async () => {
    const api = new MockApi();
    const { storage, state } = await stepUpFrom(api);
    const before = storage.getItem(KEYS.refresh);
    const { api: after } = await setup({ api, storage, signedIn: false, path: `/console/callback?code=c2&state=${state}` });
    // The old grant is revoked; the new one is the tab's.
    await waitFor(() => expect(after.to('/mcp/oauth/revoke').map((r) => form(r.body).token)).toContain(before));
    expect(storage.getItem(KEYS.refresh)).not.toBe(before);
    // Back where the person was, and the write ran again, once.
    expect(await screen.findByRole('heading', { level: 1, name: 'Settings' })).toBeTruthy();
    await waitFor(() => expect(after.to('/v1/onboarding/profile', 'PATCH')).toHaveLength(1));
    expect(JSON.parse(after.to('/v1/onboarding/profile', 'PATCH')[0]?.body ?? '{}')).toEqual({ display_name: 'Ana P' });
    expect(storage.getItem(KEYS.retry)).toBeNull();
  });

  it('keeps the sign-in that asked when someone else types their password, and changes nothing', async () => {
    const api = new MockApi();
    const { storage, state } = await stepUpFrom(api);
    const kept = storage.getItem(KEYS.refresh);
    api.overrides.push((r) => (r.path === '/v1/auth/me' && r.authorization === `Bearer at-${api.issued}` && r.method === 'GET' ? { status: 200, body: SOMEONE_ELSE } : undefined));
    await setup({ api, storage, signedIn: false, path: `/console/callback?code=c2&state=${state}` });
    expect(await screen.findByText(/That was a different account, so nothing was changed/)).toBeTruthy();
    expect(api.to('/v1/onboarding/profile', 'PATCH')).toHaveLength(0);
    // The stranger's new grant is revoked; the person's own is kept.
    const revoked = api.to('/mcp/oauth/revoke').map((r) => form(r.body).token);
    expect(revoked).not.toContain(kept);
    expect(revoked).toHaveLength(1);
    expect(storage.getItem(KEYS.retry)).toBeNull();
  });

  it('retries once only: a second step-up answer is shown, not followed', async () => {
    const api = new MockApi();
    api.overrides.push((r) => (r.method === 'PATCH' && r.path === '/v1/onboarding/profile' ? STEP_UP : undefined));
    const storage = new MemoryStorage();
    keepSignIn(storage);
    storage.setItem(KEYS.retry, JSON.stringify({ name: 'profile.update', input: { profile: { display_name: 'Ana P' } } }));
    const { assigned } = await setup({ api, storage, signedIn: false, path: '/console/settings' });
    expect(await screen.findByText('Sign in again')).toBeTruthy();
    expect(api.to('/v1/onboarding/profile', 'PATCH')).toHaveLength(1);
    expect(assigned).toHaveLength(0);
  });
});
