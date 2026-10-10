import { SalliApiError, SalliNetworkError, SalliOAuthError } from '@leafmonkeylabs/salli-sdk';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CliError, exitCodeFor, IncompatibleServerError, InterruptedError, messageFor, NotFoundError, NotSignedInError, problemFor, UsageError } from '../src/errors';
import { MockSalli } from './helpers/mock-server';
import { closedServerUrl, runCli, tempConfigDir } from './helpers/run';

const apiError = (status: number, body: unknown = { type: 'about:blank', title: 'X', status }) =>
  SalliApiError.fromResponse(new Response(null, { status }), body);

describe('exitCodeFor', () => {
  it('maps every kind of failure to its documented code', () => {
    expect(exitCodeFor(new CliError('boom'))).toBe(1);
    expect(exitCodeFor(new UsageError('bad flag'))).toBe(2);
    expect(exitCodeFor(new NotSignedInError('who?'))).toBe(3);
    expect(exitCodeFor(apiError(401))).toBe(3);
    expect(exitCodeFor(new SalliOAuthError('invalid_grant'))).toBe(3);
    expect(exitCodeFor(new NotFoundError('gone'))).toBe(4);
    expect(exitCodeFor(apiError(404))).toBe(4);
    expect(exitCodeFor(apiError(422))).toBe(5);
    expect(exitCodeFor(apiError(409))).toBe(5);
    expect(exitCodeFor(apiError(400))).toBe(5);
    expect(exitCodeFor(apiError(500))).toBe(1);
    expect(exitCodeFor(new IncompatibleServerError('v2'))).toBe(6);
    expect(exitCodeFor(new SalliNetworkError('down'))).toBe(7);
    expect(exitCodeFor(new InterruptedError())).toBe(130);
    expect(exitCodeFor(new DOMException('aborted', 'AbortError'))).toBe(130);
    expect(exitCodeFor(new Error('bug'))).toBe(1);
  });
});

describe('problem rendering', () => {
  it('passes the API problem through for --json, with the exit code', () => {
    const error = apiError(409, {
      type: '/problems/base-currency-locked',
      title: 'Base currency is fixed',
      status: 409,
      detail: 'Your ledger already has entries in USD.',
    });
    expect(messageFor(error)).toBe('Base currency is fixed: Your ledger already has entries in USD.');
    expect(problemFor(error)).toEqual({
      type: '/problems/base-currency-locked',
      title: 'Base currency is fixed',
      status: 409,
      detail: 'Your ledger already has entries in USD.',
      exit_code: 5,
    });
  });

  it('describes CLI errors as problems too', () => {
    expect(problemFor(new UsageError('--month must be YYYY-MM', 'e.g. 2026-10'))).toEqual({
      type: '/problems/cli/usage',
      title: '--month must be YYYY-MM',
      status: 0,
      detail: 'e.g. 2026-10',
      exit_code: 2,
    });
  });
});

describe('errors from the real entry point', () => {
  let dir: string;
  let cleanup: () => Promise<void>;
  let mock: MockSalli;

  beforeEach(async () => {
    ({ dir, cleanup } = await tempConfigDir());
    mock = await MockSalli.start();
  });
  afterEach(async () => {
    await mock.close();
    await cleanup();
  });

  const run = (args: string[], signal?: AbortSignal) =>
    runCli(args, { configDir: dir, env: { SALLI_SERVER: mock.url, SALLI_TOKEN: 'pat-valid' }, ...(signal ? { signal } : {}) });

  it('renders a problem as one line, and as JSON on stderr with --json', async () => {
    mock.on('GET', '/v1/accounts/', () => ({
      status: 422,
      body: {
        type: '/problems/validation',
        title: 'Request validation failed',
        status: 422,
        detail: [{ loc: ['query', 'from_date'], msg: 'Input should be a valid date', type: 'date_from_datetime_parsing' }],
      },
      headers: { 'Content-Type': 'application/problem+json' },
    }));
    const human = await run(['accounts', 'list']);
    expect(human.code).toBe(5);
    expect(human.stdout).toBe('');
    expect(human.stderr).toBe('✗ Request validation failed: query.from_date: Input should be a valid date\n');

    const json = await run(['accounts', 'list', '--json']);
    expect(json.code).toBe(5);
    expect(json.stdout).toBe('');
    expect(JSON.parse(json.stderr)).toEqual({
      type: '/problems/validation',
      title: 'Request validation failed',
      status: 422,
      detail: [{ loc: ['query', 'from_date'], msg: 'Input should be a valid date', type: 'date_from_datetime_parsing' }],
      exit_code: 5,
    });
  });

  it('never lets text from the server drive the terminal', async () => {
    const esc = String.fromCharCode(27);
    const bel = String.fromCharCode(7);
    mock.data.accounts[0]!.name = `Cash${esc}]0;pwned${bel}${esc}[2J`;
    const list = await run(['accounts', 'show', '1000']);
    expect(list.stdout).toContain('1000 Cash');
    expect(list.stdout).not.toContain(esc);
    mock.on('GET', '/v1/accounts/', () => ({
      status: 409,
      body: { type: '/problems/x', title: `Conflict${esc}[31m`, status: 409, detail: `bad${esc}[2J news` },
      headers: { 'Content-Type': 'application/problem+json' },
    }));
    const failed = await run(['accounts', 'list']);
    expect(failed.stderr).toBe('✗ Conflict: bad news\n');
  });

  it('quotes the request id of a server error', async () => {
    mock.on('GET', '/v1/accounts/', () => ({ status: 500, body: { detail: 'Internal server error', request_id: 'rid-42' } }));
    const result = await run(['accounts', 'list']);
    expect(result.code).toBe(1);
    expect(result.stderr).toContain('Internal Server Error: Internal server error');
    expect(result.stderr).toContain('Request id: rid-42');
  });

  it('exits 4 for something that is not there', async () => {
    const result = await run(['accounts', 'show', 'ffffffff-0000-4000-8000-999999999999']);
    expect(result.code).toBe(4);
  });

  it('exits 2 for usage errors, with --json too', async () => {
    const unknown = await run(['acounts', 'list']);
    expect(unknown.code).toBe(2);
    expect(unknown.stderr).toContain("Unknown command 'acounts'");
    expect(unknown.stderr).toContain('accounts');

    const badFlag = await run(['accounts', 'list', '--bogus', '--json']);
    expect(badFlag.code).toBe(2);
    expect(JSON.parse(badFlag.stderr)).toMatchObject({ type: '/problems/cli/usage', exit_code: 2 });

    const badFormat = await run(['accounts', 'list', '--output', 'xml']);
    expect(badFormat.code).toBe(2);
    expect(badFormat.stderr).toContain('--output must be one of: table, json, ndjson, csv');
  });

  it('prints help and the version with exit code 0', async () => {
    const help = await run(['--help']);
    expect(help.code).toBe(0);
    expect(help.stdout).toContain('Usage: salli');
    const bare = await run([]);
    expect(bare.code).toBe(0);
    expect(bare.stdout).toContain('Usage: salli');
    const version = await run(['--version']);
    expect(version.code).toBe(0);
    expect(version.stdout).toBe('0.1.0-test\n');
  });

  it('exits 130 when interrupted mid-request', async () => {
    mock.on('GET', '/v1/accounts/', () => new Promise(() => undefined)); // never answers
    const controller = new AbortController();
    setTimeout(() => controller.abort(new InterruptedError()), 50);
    const result = await run(['accounts', 'list'], controller.signal);
    expect(result.code).toBe(130);
    expect(result.stderr).toBe('✗ Cancelled.\n');
  });

  it('exits 7 when the server cannot be reached', async () => {
    const closed = await closedServerUrl();
    const result = await runCli(['accounts', 'list'], { configDir: dir, env: { SALLI_SERVER: closed, SALLI_TOKEN: 'x' } });
    expect(result.code).toBe(7);
    expect(result.stderr).toContain(`Could not reach ${closed} (connection refused)`);
  });
});
