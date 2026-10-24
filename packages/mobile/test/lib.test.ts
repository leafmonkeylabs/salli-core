import { describe, expect, it } from 'vitest';
import { amountParts, displayDate, displayDay, displayRange, monthNameOf, monthOf, todayIso } from '../src/lib/display';
import { authorizationUrlOf, base64UrlOf, callbackOf, tokenOf } from '../src/lib/pkce';
import { stepChart } from '../src/lib/chart';
import { checkServer, isThisMachine, serverUrlOf } from '../src/lib/server';
import { LOCK_AFTER_MS, lockDue, storeKeyOf, withoutServer, withServer } from '../src/lib/servers';

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

describe('the forecast chart', () => {
  it('steps through each day and finds the lowest and the end', () => {
    const days = [
      { date: '2026-10-24', balance: '100.00' },
      { date: '2026-10-25', balance: '50.00' },
      { date: '2026-10-26', balance: '150.00' },
    ];
    const chart = stepChart(days, { date: '2026-10-25', balance: '50.00' }, 200, 100, 0);
    // 40 to 160 with the margin: 100 is halfway, 50 near the bottom, 150 near the top.
    expect(chart.path).toBe('M0.0 50.0 H100.0 V91.7 H200.0 V8.3');
    expect(chart.low.x).toBe(100);
    expect(chart.end.x).toBe(200);
    expect(chart.zero).toBeUndefined();
  });

  it('marks zero when the line goes below it', () => {
    const chart = stepChart(
      [
        { date: '2026-10-24', balance: '100' },
        { date: '2026-10-25', balance: '-100' },
      ],
      { date: '2026-10-25', balance: '-100' },
      100,
      100,
      0,
    );
    expect(chart.zero).toBeCloseTo(50);
  });
});

describe('the servers on this phone', () => {
  it('gives each server a keychain key of its own, in the characters a key takes', () => {
    const a = storeKeyOf('https://money.example.org');
    const b = storeKeyOf('http://localhost:8000');
    expect(a).toBe('salli.sign-in.https-3a-2f-2fmoney.example.org');
    expect(b).toMatch(/^[A-Za-z0-9._-]+$/);
    expect(storeKeyOf('https://a-b.example')).not.toBe(storeKeyOf('https://a-2db.example'));
  });

  it('adds a server and puts it on screen; signing in again keeps its place', () => {
    const one = withServer(undefined, 'https://a.example');
    const two = withServer(one, 'https://b.example');
    expect(two).toEqual({ current: 'https://b.example', servers: ['https://a.example', 'https://b.example'] });
    expect(withServer(two, 'https://a.example')).toEqual({ current: 'https://a.example', servers: ['https://a.example', 'https://b.example'] });
  });

  it('moves to the first left when the one on screen goes, and to none after the last', () => {
    const index = { current: 'https://b.example', servers: ['https://a.example', 'https://b.example'] };
    expect(withoutServer(index, 'https://b.example')).toEqual({ current: 'https://a.example', servers: ['https://a.example'] });
    expect(withoutServer(index, 'https://a.example')).toEqual({ current: 'https://b.example', servers: ['https://b.example'] });
    expect(withoutServer({ current: 'https://a.example', servers: ['https://a.example'] }, 'https://a.example')).toBeUndefined();
  });

  it('asks to be unlocked only when the lock is on and the app was away a minute', () => {
    expect(lockDue(true, LOCK_AFTER_MS)).toBe(true);
    expect(lockDue(true, LOCK_AFTER_MS - 1)).toBe(false);
    expect(lockDue(false, LOCK_AFTER_MS * 10)).toBe(false);
  });
});

describe('periods', () => {
  it('says a day under its year, and a period with its year once', () => {
    expect(displayDay('2026-10-01')).toBe('Oct 1');
    expect(displayRange('2026-10-01', '2026-10-10')).toBe('Oct 1 to Oct 10, 2026');
    expect(displayRange('2025-12-20', '2026-01-05')).toBe('Dec 20, 2025 to Jan 5, 2026');
  });
});
