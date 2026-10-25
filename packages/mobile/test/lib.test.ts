import { describe, expect, it } from 'vitest';
import { addDays, addMonths, amountParts, displayDate, displayDateTime, displayDay, displayMoment, displayRange, monthGrid, monthNameOf, monthOf, todayIso } from '../src/lib/display';
import { authorizationUrlOf, base64UrlOf, callbackOf, tokenOf } from '../src/lib/pkce';
import { monthBars, placeLabels, shareOf, stepChart } from '../src/lib/chart';
import { checkServer, invitationOf, isThisMachine, serverUrlOf } from '../src/lib/server';
import { groupsOf } from '../src/lib/accounts';
import { blocksOfMarkdown, spansOf } from '../src/lib/markdown';
import { blocksOf, changeOf, keepNewest, modelsOf, pendingOf, providerOf, readsOf, titleOf } from '../src/lib/ai';
import { amountOf, dateOf, read, readWith, type AutomationRule } from '../src/lib/automations';
import { keepUnread, queueOf, sortInbox, type QueuedMessage } from '../src/lib/inbox';
import { glanceOf, type GlanceReads } from '../src/lib/glance';
import { forgotten, labelOf, listOf, named, LOCK_AFTER_MS, lockDue, remembered, storeKeyOf, withoutServer, withServer } from '../src/lib/servers';

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

describe('an invitation link', () => {
  it('opens the join page and signs in to its server', () => {
    expect(invitationOf(' https://money.example.org/join?t=abc ')).toEqual({ link: 'https://money.example.org/join?t=abc', server: 'https://money.example.org' });
    expect(invitationOf('money.example.org/salli/join?t=abc')).toEqual({ link: 'https://money.example.org/salli/join?t=abc', server: 'https://money.example.org/salli' });
    expect(invitationOf('localhost:8000/join?t=abc')).toEqual({ link: 'http://localhost:8000/join?t=abc', server: 'http://localhost:8000' });
  });

  it('refuses what is not one', () => {
    expect(invitationOf('')).toBeUndefined();
    expect(invitationOf('money.example.org')).toBeUndefined();
    expect(invitationOf('https://money.example.org/join')).toBeUndefined();
    expect(invitationOf('https://money.example.org/joined?t=abc')).toBeUndefined();
  });
});

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
    expect(two.current).toBe('https://b.example');
    expect(two.servers).toEqual(['https://a.example', 'https://b.example']);
    expect(withServer(two, 'https://a.example').servers).toEqual(['https://a.example', 'https://b.example']);
  });

  it('keeps a server signed out of listed, and forgets it only when asked', () => {
    const index = remembered(withServer(withServer(undefined, 'https://a.example'), 'https://b.example'), 'https://b.example', { email: 'you@example.org', currency: 'EUR' });
    const out = withoutServer(index, 'https://b.example');
    expect(out.current).toBe('https://a.example');
    expect(out.servers).toEqual(['https://a.example']);
    expect(listOf(out)).toEqual([
      { server: 'https://a.example', signedIn: true },
      { server: 'https://b.example', signedIn: false, email: 'you@example.org', currency: 'EUR' },
    ]);
    const none = withoutServer(out, 'https://a.example');
    expect(none.current).toBe('');
    expect(listOf(forgotten(none, 'https://b.example')).map((r) => r.server)).toEqual(['https://a.example']);
    // Signing in again brings it back with what was remembered.
    expect(listOf(withServer(out, 'https://b.example'))[1]).toEqual({ server: 'https://b.example', signedIn: true, email: 'you@example.org', currency: 'EUR' });
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

describe('moments', () => {
  it('says a time today as a time, and another day with its date', () => {
    const now = new Date(2026, 9, 24, 12, 0);
    expect(displayMoment(new Date(2026, 9, 24, 9, 41), now)).toBe('09:41 today');
    expect(displayMoment(new Date(2026, 9, 23, 14, 5), now)).toBe('Oct 23, 2026, 14:05');
    expect(displayDateTime(new Date(2026, 9, 24, 7, 1))).toBe('Oct 24, 2026, 07:01');
  });
});

describe('chart labels', () => {
  it('finds the highest day by its digits, and every point', () => {
    const days = [
      { date: '2026-10-01', balance: '100.00' },
      { date: '2026-10-02', balance: '250.10' },
      { date: '2026-10-03', balance: '250.09' },
    ];
    const chart = stepChart(days, days[0]!, 200, 100);
    expect(chart.highIndex).toBe(1);
    expect(chart.lowIndex).toBe(0);
    expect(chart.points).toHaveLength(3);
  });

  it('hangs a label at an edge inward, and keeps it inside the chart', () => {
    const [atStart] = placeLabels([{ key: 'low', x: 2, y: 96, text: 'Lowest, Oct 24: 18,505.77', below: true }], 300, 100, 12);
    expect(atStart?.anchor).toBe('start');
    expect(atStart?.y).toBeLessThanOrEqual(98);
    const [atEnd] = placeLabels([{ key: 'end', x: 298, y: 40, text: '21,946.94' }], 300, 100, 12);
    expect(atEnd?.anchor).toBe('end');
  });

  it('leaves out a label that would overlap one placed before it', () => {
    const labels = placeLabels(
      [
        { key: 'low', x: 150, y: 50, text: 'Lowest, Oct 18: 15,727.02' },
        { key: 'start', x: 152, y: 52, text: '15,801.47' },
        { key: 'end', x: 290, y: 10, text: '19,626.59' },
      ],
      300,
      100,
      12,
    );
    expect(labels.map((l) => l.key)).toEqual(['low', 'end']);
  });
});

describe('the account picker', () => {
  const account = (id: string, name: string, type: 'asset' | 'liability' | 'equity' | 'income' | 'expense', code = id, is_active = true) => ({ id, name, code, type, is_active });
  const accounts = [
    account('1', 'Salary', 'income'),
    account('2', 'Groceries', 'expense', '6100'),
    account('3', 'Savings', 'asset'),
    account('4', 'Checking', 'asset'),
    account('5', 'Opening Equity', 'equity'),
    account('6', 'Old card', 'liability', '2100', false),
  ];

  it('puts the likely kinds first, folds the rest, and never offers equity or what is closed', () => {
    const groups = groupsOf(accounts, { typeNames: {}, likely: ['income', 'expense'], others: 'Your other accounts', except: '3' });
    expect(groups.map((g) => [g.key, g.rows.map((a) => a.name)])).toEqual([
      ['income', ['Salary']],
      ['expense', ['Groceries']],
      ['others', ['Checking']],
    ]);
  });

  it('narrows by words in the name or the code', () => {
    expect(groupsOf(accounts, { typeNames: {}, likely: ['income', 'expense'], others: 'x', words: 'SAL' }).flatMap((g) => g.rows.map((a) => a.name))).toEqual(['Salary']);
    expect(groupsOf(accounts, { typeNames: {}, likely: ['expense'], words: '6100' }).flatMap((g) => g.rows.map((a) => a.name))).toEqual(['Groceries']);
    expect(groupsOf(accounts, { typeNames: {}, likely: ['expense'], others: 'x', words: 'nothing like it' })).toEqual([]);
  });
});

describe('the widgets\' snapshot', () => {
  // Only the fields glanceOf reads; the rest of each response doesn't matter here.
  const reads = (over: Partial<Record<keyof GlanceReads, unknown>> = {}): GlanceReads =>
    ({
      safe: { amount: '-1234.50', currency: 'EUR', until: '2026-10-25', next_income: { description: 'Salary' } },
      reviews: { reviews: [{ id: 'd1', question: 'Move to the coast?' }] },
      reminders: {
        reminders: [
          { id: 'r1', kind: 'Pay the plumber Ana', due_date: '2026-10-20', source_domain: null },
          { id: 'r2', kind: 'Later', due_date: '2026-11-02', source_domain: null },
          { id: 'r3', kind: 'Review', due_date: '2026-10-01', source_domain: 'decision' },
        ],
      },
      statements: { statements: [{ status: 'pending' }, { status: 'pending' }, { status: 'posted' }] },
      signals: { signals: [{ kind: 'low_balance_ahead', severity: 'high' }] },
      ...over,
    }) as unknown as GlanceReads;
  const palette = { paper: '#F6F3EC', ink: '#1C1B19', muted: '#57524A', rule: '#DCD4C4', accent: '#173B33', tile: '#173B33', tileText: '#F2ECDF' };
  const options = { host: 'money.example.org', showAmounts: false, at: 1, today: '2026-10-24', colors: { light: palette, dark: palette } };

  it('hides the amount unless amounts outside the app are allowed', () => {
    const hidden = glanceOf(reads(), options);
    expect(hidden.safe).toEqual({ label: 'Free until payday', figure: 'Amount hidden', currency: '', spoken: 'Amount hidden', until: 'until Oct 25, 2026' });
    expect(JSON.stringify(hidden)).not.toMatch(/1,?234/);
    const shown = glanceOf(reads(), { ...options, showAmounts: true });
    expect(shown.safe.figure).toBe('(1,234.50)');
    expect(shown.safe.currency).toBe('EUR');
    expect(shown.safe.spoken).toMatch(/^minus 1,234\.50/);
  });

  it('counts what is waiting, and carries nothing from the ledger', () => {
    const glance = glanceOf(reads(), options);
    expect(glance.waiting.lines).toEqual(['1 decision to review', '1 reminder due', '2 statements to review', 'Cash below zero ahead']);
    expect(glance.waiting.more).toBe('and 2 more');
    expect(JSON.stringify(glance)).not.toMatch(/plumber|coast|Salary/);
  });

  it('says when nothing is waiting, and when no income is expected', () => {
    const glance = glanceOf(
      reads({ safe: { amount: '0.00', currency: 'EUR', until: '2026-10-25', next_income: null }, reviews: { reviews: [] }, reminders: { reminders: [] }, statements: { statements: [] }, signals: { signals: [{ kind: 'low_balance_ahead', severity: 'medium' }] } }),
      options,
    );
    expect(glance.waiting).toEqual({ label: 'Waiting', lines: ['Nothing waiting'], more: '' });
    expect(glance.safe.until).toBe('No income expected');
  });

  it('adds the forecast, spending, net worth and days to income, hiding every amount unless allowed', () => {
    const more = reads({
      forecast: { currency: 'EUR', lowest: '16312.40', lowest_date: '2026-11-19', flows: [
        { date: '2026-10-25', description: 'Acme Salary', amount: '4000.00', currency: 'EUR' },
        { date: '2026-11-01', description: 'Rent', amount: '-1450.00', currency: 'EUR' },
      ], daily: [
        { date: '2026-10-24', balance: '18503.37' },
        { date: '2026-11-19', balance: '16312.40' },
        { date: '2026-12-23', balance: '21944.54' },
      ] },
      spent: { currency: 'EUR', total_expenses: '1795.94' },
      spentBefore: { currency: 'EUR', total_expenses: '1806.10' },
      history: { currency: 'EUR', points: [{ net_worth: '30000.00' }, { net_worth: '33567.52' }] },
    });
    const hidden = glanceOf(more, options);
    expect(hidden.v).toBe(2);
    expect(hidden.forecast).toMatchObject({ low: 'low · Nov 19', points: [0.389, 0, 1].map((x) => expect.closeTo(x, 3)), lowIndex: 1 });
    expect(hidden.spent).toMatchObject({ label: 'Spent · Oct', figure: 'Amount hidden', then: '' });
    expect(hidden.netWorth?.figure).toBe('Amount hidden');
    expect(JSON.stringify(hidden)).not.toMatch(/16,?312|1,?795|33,?567|1,?806/);
    expect(hidden.payday).toMatchObject({ days: 1, unit: 'day', spoken: '1 day until income' });
    const shown = glanceOf(more, { ...options, showAmounts: true });
    expect(shown.forecast?.low).toBe('low 16,312 · Nov 19');
    expect(shown.spent).toMatchObject({ figure: '1,795', then: '↓ Sep 1,806' });
    expect(shown.netWorth?.figure).toBe('33,567');
    expect(shown.comingUp?.rows).toEqual([
      { day: 'Oct 25', title: 'Acme Salary', amount: '+4,000.00', in: true },
      { day: 'Nov 1', title: 'Rent', amount: '−1,450.00', in: false },
    ]);
  });
});

describe('automation rules', () => {
  const card: AutomationRule = {
    id: 'r1',
    name: 'Card spend',
    senders: ['EXAMPLEBANK'],
    pattern: 'Your card ending 4821 was debited {currency} {amount} at {payee} on {date}. Ref {ref}.',
    kind: 'template',
    direction: 'out',
    accountId: 'checking',
    dateOrder: 'DMY',
    decimalMark: '.',
  };
  // {currency} isn't a part: a template's unknown braces are words to match.
  const rule = { ...card, pattern: 'debited EUR {amount} at {payee} on {date}. Ref {ref}' };
  const message = 'Your card ending 4821 was debited EUR 1,245.50 at CORNER BAKERY on 05/10/26. Ref 662718. Not you? Call us.';

  it('reads a draft out of a message, the amount as written', () => {
    expect(readWith(rule, message, '2026-10-24')).toEqual({
      date: '2026-10-05',
      description: 'CORNER BAKERY',
      amount: '1245.50',
      credit_flag: false,
      bank_ref: '662718',
    });
  });

  it('runs a part at the end to the sentence, and takes the day it arrived without a date', () => {
    const credit = { ...rule, direction: 'in' as const, pattern: 'credited with {amount} from {payee}' };
    expect(readWith(credit, 'Your account was credited with 2,400.00 from NORTHWIND PAYROLL. Balance follows.', '2026-10-24')).toEqual({
      date: '2026-10-24',
      description: 'NORTHWIND PAYROLL',
      amount: '2400.00',
      credit_flag: true,
    });
  });

  it('reads amounts grouped every way, and dates in the rule’s order or by name', () => {
    expect(amountOf('1,23,455.00', '.')).toBe('123455.00');
    expect(amountOf('1.245,50', ',')).toBe('1245.50');
    expect(amountOf('8 400', '.')).toBe('8400');
    expect(amountOf('1,245.50', ',')).toBeUndefined();
    expect(dateOf('05/10/26', 'DMY')).toBe('2026-10-05');
    expect(dateOf('10/05/26', 'MDY')).toBe('2026-10-05');
    expect(dateOf('2026-10-05', 'DMY')).toBe('2026-10-05');
    expect(dateOf('5-Oct-2026', 'MDY')).toBe('2026-10-05');
    expect(dateOf('Oct 5, 2026', 'DMY')).toBe('2026-10-05');
    expect(dateOf('31/02/26', 'DMY')).toBeUndefined();
  });

  it('takes a regular expression with named groups, under Advanced', () => {
    const regex = { ...rule, kind: 'regex' as const, pattern: 'EUR (?<amount>[\\d,.]+) at (?<payee>.+?) on' };
    expect(readWith(regex, message, '2026-10-24')).toMatchObject({ amount: '1245.50', description: 'CORNER BAKERY', date: '2026-10-24' });
    expect(readWith({ ...regex, pattern: 'EUR ([\\d' }, message, '2026-10-24')).toBe('This regular expression doesn’t read.');
    expect(readWith({ ...regex, pattern: 'at (?<payee>.+?) on' }, message, '2026-10-24')).toBe('Name a group amount: (?<amount>…).');
  });

  it('tries only the rules watching the sender, and ignores everyone else', () => {
    const today = '2026-10-24';
    expect(read([rule], { text: message, sender: 'examplebank' }, today)).toMatchObject({ kind: 'draft', rule: { id: 'r1' } });
    expect(read([rule], { text: 'Your code is 4471', sender: 'EXAMPLEBANK' }, today)).toEqual({ kind: 'unread', rules: [rule] });
    expect(read([rule], { text: message, sender: '+15550100' }, today)).toEqual({ kind: 'ignored' });
    // Pasted by hand: every rule is tried.
    expect(read([rule], { text: message }, today)).toMatchObject({ kind: 'draft' });
  });
});

describe('the automations inbox', () => {
  const rule: AutomationRule = {
    id: 'r1',
    name: 'Card spend',
    senders: ['EXAMPLEBANK'],
    pattern: 'debited EUR {amount} at {payee}',
    kind: 'template',
    direction: 'out',
    accountId: 'checking',
    dateOrder: 'DMY',
    decimalMark: '.',
  };
  const message = (id: string, text: string, sender = 'EXAMPLEBANK', at = '2026-10-23T12:00:00Z'): QueuedMessage => ({ id, text, sender, at });

  it('drafts by account on the day each arrived, keeps the unread, drops the unwatched', () => {
    const sorted = sortInbox(
      [rule],
      [
        message('m1', 'Your card was debited EUR 8.40 at CORNER BAKERY.'),
        message('m2', 'Your one-time code is 4471.'),
        message('m3', 'Lunch at noon?', '+15550100'),
        message('m4', 'Your card was debited EUR 2.75 at CITY TRANSIT.', 'examplebank', '2026-10-24T12:00:00Z'),
      ],
    );
    expect([...sorted.drafts.keys()]).toEqual(['checking']);
    expect(sorted.drafts.get('checking')).toEqual({
      ids: ['m1', 'm4'],
      drafts: [
        { date: '2026-10-23', description: 'CORNER BAKERY', amount: '8.40', credit_flag: false },
        { date: '2026-10-24', description: 'CITY TRANSIT', amount: '2.75', credit_flag: false },
      ],
    });
    expect(sorted.unread.map((m) => m.id)).toEqual(['m2']);
    expect(sorted.ignored).toEqual(['m3']);
  });

  it('reads the queue leniently and keeps the newest unread once each', () => {
    expect(queueOf('not json')).toEqual([]);
    expect(queueOf('{"id":"x"}')).toEqual([]);
    expect(queueOf(JSON.stringify([{ id: 'a', text: 't', at: '2026-10-24T08:00:00Z' }, { id: 1 }]))).toEqual([{ id: 'a', text: 't', at: '2026-10-24T08:00:00Z', sender: '' }]);
    const old = message('a', 'x', 'EXAMPLEBANK', '2026-10-01T00:00:00Z');
    const fresh = message('b', 'y', 'EXAMPLEBANK', '2026-10-20T00:00:00Z');
    expect(keepUnread([old], [fresh, old], 1)).toEqual([fresh]);
  });
});

describe('your AI', () => {
  it('reads every provider’s models list, chat models only', () => {
    expect(modelsOf({ data: [{ id: 'claude-opus-5-5', display_name: 'Claude Opus 5.5' }, { id: 'claude-haiku-5-5' }] })).toEqual([
      { id: 'claude-opus-5-5', name: 'Claude Opus 5.5' },
      { id: 'claude-haiku-5-5', name: 'claude-haiku-5-5' },
    ]);
    expect(modelsOf({ data: [{ id: 'gpt-x' }, { id: 'text-embedding-3' }, { id: 'whisper-1' }] }).map((m) => m.id)).toEqual(['gpt-x']);
    expect(modelsOf({ data: [{ id: 'meta/llama', name: 'Llama' }] })).toEqual([{ id: 'meta/llama', name: 'Llama' }]);
    expect(modelsOf('nonsense')).toEqual([]);
    expect(providerOf('anthropic')?.defaultModel).toBe('claude-opus-5-5');
    expect(providerOf('elsewhere')).toBeUndefined();
  });

  it('runs unasked only the tools the server marks read-only: anything else waits for approval', () => {
    const reads = readsOf([
      { name: 'get_overview', annotations: { readOnlyHint: true } },
      { name: 'run_scenario', annotations: { readOnlyHint: true } },
      { name: 'suggested_tax_accounts', annotations: { readOnlyHint: true } },
      { name: 'apply_suggested_tax_accounts', annotations: { readOnlyHint: false } },
      { name: 'post_journal_entry', annotations: { readOnlyHint: false } },
      // Named like a read, but the server says nothing: it is asked about.
      { name: 'get_something_new' },
      { name: 'list_things', annotations: {} },
    ]);
    expect([...reads].sort()).toEqual(['get_overview', 'run_scenario', 'suggested_tax_accounts']);
  });

  it('says a change in one line, amounts as given', () => {
    expect(changeOf('create_reminder', { kind: 'Send the landlord the lease', due_date: '2026-10-12' })).toBe('Add a reminder: Send the landlord the lease, Oct 12, 2026');
    expect(changeOf('post_journal_entry', { description: 'Corner Bakery', amount: '8.40', currency: 'EUR', entry_date: '2026-10-24' })).toBe('Book an entry: Corner Bakery, EUR 8.40, Oct 24, 2026');
    expect(changeOf('a_new_tool', {})).toBe('A new tool');
  });

  it('titles a conversation by its first question and keeps the newest 20', () => {
    expect(titleOf('  Where do I   stand today? ')).toBe('Where do I stand today?');
    expect(titleOf('Can I afford a new bike before the holidays if I also keep my buffer?')).toBe('Can I afford a new bike before the holidays if…');
    const old = Array.from({ length: 20 }, (_, i) => ({ id: `c${i}`, at: `2026-10-${String(i + 1).padStart(2, '0')}T00:00:00Z` }));
    const kept = keepNewest(old, { id: 'new', at: '2026-10-24T00:00:00Z' });
    expect(kept).toHaveLength(20);
    expect(kept[0]?.id).toBe('new');
    expect(kept.some((c) => c.id === 'c0')).toBe(false);
  });
});

describe('a conversation with your AI', () => {
  // As the AI SDK keeps it: the person, the AI's tool calls and answers, approvals asked and met.
  const asked = [
    { role: 'user', content: 'Where do I stand today?' },
    { role: 'assistant', content: [{ type: 'tool-call', toolCallId: 't1', toolName: 'get_safe_to_spend', input: {} }, { type: 'tool-call', toolCallId: 't2', toolName: 'get_signals', input: {} }] },
    { role: 'tool', content: [{ type: 'tool-result', toolCallId: 't1', toolName: 'get_safe_to_spend', output: { type: 'json', value: {} } }] },
    { role: 'assistant', content: [{ type: 'text', text: 'EUR 15,727.02 is safe to spend.' }] },
    { role: 'user', content: 'Remind me about the lease tomorrow.' },
    {
      role: 'assistant',
      content: [
        { type: 'text', text: 'That changes your reminders. Approve it?' },
        { type: 'tool-call', toolCallId: 't3', toolName: 'create_reminder', input: { kind: 'Send the lease', due_date: '2026-10-12' } },
        { type: 'tool-approval-request', approvalId: 'a1', toolCallId: 't3' },
      ],
    },
  ] as unknown as Parameters<typeof blocksOf>[0];

  it('shows each answer with how much it read, and what waits for approval', () => {
    expect(blocksOf(asked)).toEqual([
      { kind: 'you', text: 'Where do I stand today?' },
      { kind: 'ai', reads: 2, text: 'EUR 15,727.02 is safe to spend.' },
      { kind: 'you', text: 'Remind me about the lease tomorrow.' },
      { kind: 'ai', reads: 0, text: 'That changes your reminders. Approve it?' },
    ]);
    expect(pendingOf(asked)).toEqual([{ approvalId: 'a1', tool: 'create_reminder', input: { kind: 'Send the lease', due_date: '2026-10-12' } }]);
    const met = [...asked, { role: 'tool', content: [{ type: 'tool-approval-response', approvalId: 'a1', approved: true }] }] as unknown as Parameters<typeof pendingOf>[0];
    expect(pendingOf(met)).toEqual([]);
  });
});

describe('an answer’s Markdown', () => {
  it('reads bold, italic and code within a line, and leaves the rest as text', () => {
    expect(spansOf('**Cash:** 18,567.52 EUR')).toEqual([{ text: 'Cash:', bold: true }, { text: ' 18,567.52 EUR' }]);
    expect(spansOf('a *real* return, `get_signals` and __all__')).toEqual([
      { text: 'a ' },
      { text: 'real', italic: true },
      { text: ' return, ' },
      { text: 'get_signals', code: true },
      { text: ' and ' },
      { text: 'all', bold: true },
    ]);
    // Snake case and lone stars are words, not emphasis.
    expect(spansOf('get_safe_to_spend at 5 * 3')).toEqual([{ text: 'get_safe_to_spend at 5 * 3' }]);
    expect(spansOf('[a link](https://example.org)')).toEqual([{ text: '[a link](https://example.org)' }]);
  });

  it('reads paragraphs, headings and lists, a wrapped item carrying on', () => {
    const answer = [
      "You're in a strong position today:",
      '',
      '## Where you stand',
      '- **Cash:** 18,567.52 EUR',
      '- **Safe to spend:** 18,503.37 EUR until',
      '  25 October 2026.',
      '',
      '1. Review the decision',
      '2) Send the lease',
      '---',
      'Where would you like to start?',
      'Line two.',
    ].join('\n');
    expect(blocksOfMarkdown(answer)).toEqual([
      { kind: 'paragraph', lines: [[{ text: "You're in a strong position today:" }]] },
      { kind: 'heading', spans: [{ text: 'Where you stand' }] },
      {
        kind: 'list',
        ordered: false,
        items: [
          { marker: '•', spans: [{ text: 'Cash:', bold: true }, { text: ' 18,567.52 EUR' }] },
          { marker: '•', spans: [{ text: 'Safe to spend:', bold: true }, { text: ' 18,503.37 EUR until' }, { text: ' ' }, { text: '25 October 2026.' }] },
        ],
      },
      {
        kind: 'list',
        ordered: true,
        items: [
          { marker: '1.', spans: [{ text: 'Review the decision' }] },
          { marker: '2.', spans: [{ text: 'Send the lease' }] },
        ],
      },
      { kind: 'paragraph', lines: [[{ text: 'Where would you like to start?' }], [{ text: 'Line two.' }]] },
    ]);
  });
});

describe('server names', () => {
  it('names a server on this phone, and goes back to its address when cleared', () => {
    const index = withServer(undefined, 'https://money.example.org');
    const home = named(index, 'https://money.example.org', '  Home ');
    expect(listOf(home)[0]?.name).toBe('Home');
    expect(labelOf('https://money.example.org', 'Home')).toBe('Home');
    const cleared = named(home, 'https://money.example.org', '');
    expect(listOf(cleared)[0]?.name).toBeUndefined();
    expect(labelOf('https://money.example.org', undefined)).toBe('money.example.org');
  });
});

describe('a calendar', () => {
  it('starts on Monday with blanks before the 1st', () => {
    const grid = monthGrid('2026-10');
    expect(grid.slice(0, 4)).toEqual([null, null, null, '2026-10-01']);
    expect(grid.at(-1)).toBe('2026-10-31');
    expect(monthGrid('2026-02').filter(Boolean)).toHaveLength(28);
  });

  it('steps days and months across their ends', () => {
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addMonths('2026-01', -1)).toBe('2025-12');
    expect(addMonths('2026-12', 1)).toBe('2027-01');
  });
});

describe('budget bars', () => {
  it('reach a share of the whole, never past it', () => {
    expect(shareOf('50.00', '200.00')).toBe(0.25);
    expect(shareOf('300.00', '200.00')).toBe(1);
    expect(shareOf('5.00', '0.00')).toBe(1);
  });

  it('size each month against the tallest', () => {
    expect(monthBars([{ spent: ['10.00', '20.00'] }, { spent: ['10.00', '20.00'] }], 2)).toEqual([0.5, 1]);
  });
});
