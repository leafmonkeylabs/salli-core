import { describe, expect, it } from 'vitest';
import { amountParts, displayDate, monthNameOf, monthOf, todayIso } from '../src/lib/display';
import { authorizationUrlOf, base64UrlOf, callbackOf, tokenOf } from '../src/lib/pkce';
import { checkServer, isThisMachine, serverUrlOf } from '../src/lib/server';

const REDIRECT = 'money.salli.app:/oauth/callback';

function meta(oauth: Record<string, string> = {}, apiVersion = '1') {
  const base = 'https://money.example.org';
  return {
    api_version: apiVersion,
    server_version: '0.5.0',
    extensions: [],
    default_currency: 'EUR',
    console_url: `${base}/console`,
    oauth: {
      issuer: base,
      authorization_endpoint: `${base}/mcp/oauth/authorize`,
      token_endpoint: `${base}/mcp/oauth/token`,
      registration_endpoint: `${base}/mcp/oauth/register`,
      revocation_endpoint: `${base}/mcp/oauth/revoke`,
      device_authorization_endpoint: `${base}/mcp/oauth/device_authorization`,
      api_resource: `${base}/v1`,
      device_verification_uri: `${base}/mcp/oauth/device`,
      cli_client_id: 'salli-cli',
      console_client_id: 'salli-console',
      mobile_client_id: 'salli-mobile',
      mobile_redirect_uri: REDIRECT,
      ...oauth,
    },
  };
}

describe('a typed address', () => {
  it('gains https:// and loses /console and slashes', () => {
    expect(serverUrlOf(' money.example.org ')).toBe('https://money.example.org');
    expect(serverUrlOf('https://money.example.org/console/')).toBe('https://money.example.org');
    expect(serverUrlOf('http://localhost:8000')).toBe('http://localhost:8000');
    expect(serverUrlOf('localhost:8000')).toBe('http://localhost:8000');
    expect(serverUrlOf('https://localhost:8443')).toBe('https://localhost:8443');
    expect(serverUrlOf('money.example.org/salli')).toBe('https://money.example.org/salli');
  });

  it('is refused when it is no address', () => {
    expect(serverUrlOf('')).toBeUndefined();
    expect(serverUrlOf('ftp://money.example.org')).toBeUndefined();
    expect(serverUrlOf('https://')).toBeUndefined();
  });

  it('knows this machine from another', () => {
    expect(isThisMachine('http://localhost:8000')).toBe(true);
    expect(isThisMachine('http://127.0.0.1:8000')).toBe(true);
    expect(isThisMachine('http://[::1]:8000')).toBe(true);
    expect(isThisMachine('http://salli.localhost')).toBe(true);
    expect(isThisMachine('http://192.168.1.20:8000')).toBe(false);
  });
});

describe('checking a server', () => {
  it('finds the app sign-in in /v1/meta', () => {
    const check = checkServer('https://money.example.org', meta());
    expect(check.ok && check.signIn).toEqual({
      authorizationEndpoint: 'https://money.example.org/mcp/oauth/authorize',
      tokenEndpoint: 'https://money.example.org/mcp/oauth/token',
      revocationEndpoint: 'https://money.example.org/mcp/oauth/revoke',
      clientId: 'salli-mobile',
      redirectUri: REDIRECT,
      resource: 'https://money.example.org/v1',
    });
  });

  it('says what stops a sign-in', () => {
    const problem = (url: string, answer: unknown) => {
      const check = checkServer(url, answer);
      return check.ok ? undefined : check.problem;
    };
    expect(problem('https://example.org', '<html>')).toBe('not-salli');
    expect(problem('https://example.org', { hello: 'world' })).toBe('not-salli');
    expect(problem('https://money.example.org', meta({}, '2'))).toBe('version');
    expect(problem('https://money.example.org', meta({ mobile_client_id: '' }))).toBe('no-app-sign-in');
    expect(problem('http://192.168.1.20:8000', meta())).toBe('insecure');
    expect(problem('http://localhost:8000', meta())).toBeUndefined();
  });
});

describe('PKCE and the redirect', () => {
  it('writes base64url without padding', () => {
    expect(base64UrlOf('ab+c/d==')).toBe('ab-c_d');
    expect(tokenOf(new Uint8Array([251, 255, 191]))).toBe('-_-_');
  });

  it('builds the authorization URL', () => {
    const url = authorizationUrlOf({
      authorizationEndpoint: 'https://money.example.org/mcp/oauth/authorize',
      clientId: 'salli-mobile',
      redirectUri: REDIRECT,
      challenge: 'c',
      state: 's',
      resource: 'https://money.example.org/v1',
    });
    const query = new URLSearchParams(url.split('?')[1]);
    expect(Object.fromEntries(query)).toEqual({
      response_type: 'code',
      client_id: 'salli-mobile',
      redirect_uri: REDIRECT,
      code_challenge: 'c',
      code_challenge_method: 'S256',
      state: 's',
      resource: 'https://money.example.org/v1',
    });
  });

  it('reads the code, and refuses another sign-in’s answer', () => {
    expect(callbackOf(`${REDIRECT}?code=abc&state=s`, REDIRECT, 's')).toEqual({ code: 'abc' });
    expect(callbackOf(`${REDIRECT}?code=abc&state=t`, REDIRECT, 's')).toEqual({ error: 'state' });
    expect(callbackOf(`${REDIRECT}?error=access_denied&state=s`, REDIRECT, 's')).toEqual({ error: 'access_denied' });
    expect(callbackOf('money.salli.evil:/oauth/callback?code=abc&state=s', REDIRECT, 's')).toEqual({ error: 'invalid' });
  });
});

describe('figures on a screen', () => {
  it('shows an amount exactly, unsigned, with the sign said', () => {
    expect(amountParts('15727.02', 'EUR', 'en')).toEqual({ digits: '15,727.02', negative: false, spoken: '15,727.02 euros' });
    expect(amountParts('-1500.00', 'EUR', 'en')).toEqual({ digits: '1,500.00', negative: true, spoken: 'minus 1,500.00 euros' });
    expect(amountParts('0.1', 'USD', 'en').digits).toBe('0.10');
    expect(amountParts('1234567890123456.78', 'EUR', 'en').digits).toBe('1,234,567,890,123,456.78');
  });

  it('writes dates as the brand does', () => {
    expect(displayDate('2026-10-25')).toBe('Oct 25, 2026');
    expect(displayDate('2026-09-05T09:00:00Z')).toBe('Sep 5, 2026');
    expect(displayDate('soon')).toBe('soon');
    expect(monthNameOf('2026-10-11')).toBe('October');
    expect(monthOf('2026-10-11')).toEqual({ from: '2026-10-01', to: '2026-10-11' });
    expect(todayIso(new Date(2026, 9, 11, 9, 41))).toBe('2026-10-11');
  });
});
