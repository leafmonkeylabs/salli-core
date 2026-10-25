import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { MockSalli } from './helpers/mock-server';
import { runCli, tempConfigDir } from './helpers/run';

let dir: string;
let cleanup: () => Promise<void>;
let mock: MockSalli;
let signedIn: string;

const GRANT = { id: '3fa85f64-0000-0000-0000-000000000001', member_id: 'u-ada', member_email: 'ada@example.org', created_at: '2026-10-25T09:00:00Z' };

beforeEach(async () => {
  ({ dir, cleanup } = await tempConfigDir());
  mock = await MockSalli.start();
  signedIn = mock.issueTokens().access_token;
  mock.on('GET', '/v1/access-grants', () => ({ status: 200, body: { given: [], received: [GRANT] } }));
  mock.on('POST', '/v1/access-grants', () => ({ status: 201, body: GRANT }));
  mock.on('DELETE', '/v1/access-grants/{id}', () => ({ status: 204 }));
});
afterEach(async () => {
  await mock.close();
  await cleanup();
});

const run = (args: string[]) => runCli(args, { configDir: dir, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: signedIn } });

describe('salli access', () => {
  it('gives, lists and ends access', async () => {
    const given = await run(['access', 'grant', 'ada@example.org']);
    expect(given.code).toBe(0);
    expect(mock.requestsTo('POST', '/v1/access-grants')[0]?.json).toEqual({ email: 'ada@example.org' });
    const listed = await run(['access', 'list']);
    expect(listed.stdout).toContain('yours to read');
    const ended = await run(['access', 'revoke', '3fa85f64', '--yes']);
    expect(ended.code).toBe(0);
    expect(mock.requestsTo('DELETE', `/v1/access-grants/${GRANT.id}`)).toHaveLength(1);
  });

  it('names the books to read with --books', async () => {
    await run(['--books', 'u-ada', 'access', 'list']);
    expect(mock.requestsTo('GET', '/v1/access-grants')[0]?.headers['salli-books']).toBe('u-ada');
  });
});
