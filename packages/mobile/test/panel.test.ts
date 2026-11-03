import type { PanelEntry } from '@leafmonkeylabs/salli-sdk';
import { describe, expect, it } from 'vitest';
import { announceOffer, onOffer, type Offered } from '../src/offer-store';
import { offerIsFor, panelPathOf, placesOf } from '../src/lib/panel';
import { hostedServerOf } from '../src/lib/server';
import { authorizationUrlOf } from '../src/lib/pkce';

const offer = { title: 'T', detail: 'D', label: 'L', panel: 'upgrade' };

describe('panel places', () => {
  const list: PanelEntry[] = [
    { id: 'a', title: 'A', entry: 'more' },
    { id: 'b', title: 'B', entry: 'settings' },
    { id: 'c', title: 'C', entry: null },
    { id: 'd', title: 'D', entry: 'more' },
  ];
  it('lists each entry’s panels in the server’s order', () => {
    expect(placesOf(list, 'more').map((p) => p.id)).toEqual(['a', 'd']);
    expect(placesOf(list, 'settings').map((p) => p.id)).toEqual(['b']);
    expect(placesOf([], 'more')).toEqual([]);
  });

  it('opens only an id that can sit in a path', () => {
    expect(panelPathOf('status')).toBe('/panel/status');
    expect(panelPathOf('../x')).toBeUndefined();
    expect(panelPathOf('')).toBeUndefined();
  });
});

describe('the offer sheet’s feed', () => {
  it('hands an announced offer to the sheet, once subscribed, and to nobody after', () => {
    const seen: Offered[] = [];
    announceOffer('https://a.example', offer);
    const end = onOffer((o) => seen.push(o));
    announceOffer('https://a.example', offer);
    end();
    announceOffer('https://a.example', offer);
    expect(seen).toEqual([{ server: 'https://a.example', offer }]);
  });

  it('is for the server on screen only', () => {
    expect(offerIsFor({ server: 'https://a.example', offer }, 'https://a.example')).toBe(true);
    expect(offerIsFor({ server: 'https://a.example', offer }, 'https://b.example')).toBe(false);
    expect(offerIsFor({ server: 'https://a.example', offer }, undefined)).toBe(false);
  });
});

describe('Salli’s own server', () => {
  it('is whatever the build names, or nothing', () => {
    expect(hostedServerOf(undefined)).toBeUndefined();
    expect(hostedServerOf('')).toBeUndefined();
    expect(hostedServerOf('not a url with spaces ://')).toBeUndefined();
    expect(hostedServerOf('hosted.example.org/')).toBe('https://hosted.example.org');
  });

  it('carries the sign-in request through its sign-up page', () => {
    const url = authorizationUrlOf({ authorizationEndpoint: 'https://hosted.example.org/signup', clientId: 'app', redirectUri: 'money.salli.app:/oauth/callback', challenge: 'c', state: 's', resource: 'https://hosted.example.org/mcp' });
    expect(url.startsWith('https://hosted.example.org/signup?response_type=code&client_id=app')).toBe(true);
    expect(url).toContain('code_challenge_method=S256');
  });
});
