import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli } from './helpers/mock-server';
import { PREVIEW } from './helpers/notifications';
import { runCli, tempConfigDir, type RunOptions } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
let signedIn: string;

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  signedIn = mock.issueTokens().access_token;
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

const run = (args: string[], options: Partial<RunOptions> = {}) =>
  runCli(args, {
    configDir: dir,
    ...options,
    env: { SALLI_SERVER: mock.url, SALLI_TOKEN: signedIn, ...options.env },
  });

describe('salli notifications', () => {
  it('shows the digest as off until it is turned on', async () => {
    const result = await run(['notifications', 'show']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Digest');
    expect(result.stdout).toContain('off');
    expect(result.stdout).toContain('decisions ready for review, your reminders due');
    expect(result.stdout).toContain('not set');

    const json = await run(['notifications', '--json']);
    expect(JSON.parse(json.stdout)).toMatchObject({ enabled: false, cadence: 'weekly', hour: 9, time_zone: null });
  });

  it('turns it on with a time zone and says when it goes', async () => {
    const result = await run(['notifications', 'set', '--on', '--time-zone', 'Europe/Lisbon', '--day', 'mon', '--hour', '9']);
    expect(result.code).toBe(0);
    expect(mock.notifications.bodies).toEqual([{ enabled: true, weekday: 'monday', hour: 9, time_zone: 'Europe/Lisbon' }]);
    expect(result.stderr).toContain('Your digest is on: weekly on Monday at 09:00 (Europe/Lisbon).');
    expect(result.stdout).toContain('2026-10-12 09:00');
  });

  it('asks for a time zone before turning it on without one, naming the computer’s', async () => {
    const result = await run(['notifications', 'set', '--on']);
    expect(result.code).toBe(2);
    expect(result.stderr).toContain('needs your time zone');
    expect(result.stderr).toContain('salli notifications set --on --time-zone');
    expect(mock.notifications.bodies).toEqual([]);
  });

  it('passes the server’s refusal of a time zone that is not one', async () => {
    const result = await run(['notifications', 'set', '--time-zone', 'Mars']);
    expect(result.code).toBe(5);
    expect(result.stderr).toContain('not an IANA time zone');
  });

  it('changes the rhythm and the items, and refuses what is not one', async () => {
    const ok = await run(['notifications', 'set', '--monthly', '--items', 'filing_deadline,decision_review_due', '--json']);
    expect(ok.code).toBe(0);
    expect(mock.notifications.bodies.at(-1)).toEqual({ cadence: 'monthly', items: ['filing_deadline', 'decision_review_due'] });
    expect(JSON.parse(ok.stdout)).toMatchObject({ cadence: 'monthly' });

    for (const bad of [
      ['--items', 'spending_spike'],
      ['--hour', '24'],
      ['--day', 'someday'],
      ['--weekly', '--monthly'],
      ['--on', '--off'],
    ]) {
      const result = await run(['notifications', 'set', ...bad]);
      expect(result.code, bad.join(' ')).toBe(2);
    }
    const nothing = await run(['notifications', 'set']);
    expect(nothing.code).toBe(2);
    expect(nothing.stderr).toContain('Nothing to change');
  });

  it('previews the digest exactly as it would read, sending nothing', async () => {
    const result = await run(['notifications', 'preview']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Salli: what is waiting, week of 2026-10-12');
    expect(result.stdout).toContain('- 1 decision ready for review (since 2026-10-05)');
    expect(result.stdout).toContain('- Your cash forecast goes below zero on 2026-11-02');
    expect(result.stderr).toContain('This is the digest that would go if it went now.');

    const json = await run(['notifications', 'preview', '--json']);
    expect(JSON.parse(json.stdout)).toEqual(PREVIEW);
  });

  it('says when nothing would go', async () => {
    mock.notifications.preview = { ...PREVIEW, digest: null, note: 'Nothing is waiting, so no digest would go.' };
    const result = await run(['notifications', 'preview']);
    expect(result.code).toBe(0);
    expect(result.stdout).toBe('');
    expect(result.stderr).toContain('Nothing is waiting');
  });

  it('lists what was delivered, without the message', async () => {
    const result = await run(['notifications', 'log']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('2026-W42');
    expect(result.stdout).toContain('sent');
    expect(result.stdout).toContain('1 decisions ready for review');

    const ndjson = await run(['notifications', 'log', '--output', 'ndjson', '--limit', '1']);
    expect(mock.requestsTo('GET', '/v1/notifications/deliveries').at(-1)?.query.get('limit')).toBe('1');
    expect(JSON.parse(ndjson.stdout.trim())).toMatchObject({ period: '2026-W42', status: 'sent' });

    mock.notifications.deliveries = { deliveries: [] };
    const none = await run(['notifications', 'log']);
    expect(none.stderr).toContain('No digest has been delivered to you yet.');
  });

  it('warns when the server has no notifier', async () => {
    mock.notifications.preferences = { ...mock.notifications.preferences, sender_enabled: false };
    const result = await run(['notifications', 'show']);
    expect(result.stderr).toContain('no notifier enabled');
  });
});
