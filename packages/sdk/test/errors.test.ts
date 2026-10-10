import { describe, expect, it } from 'vitest';
import { describeDetail, SalliApiError, SalliNetworkError } from '../src/errors';

function response(status: number, headers: Record<string, string> = {}): Response {
  return new Response(null, { status, headers });
}

describe('describeDetail', () => {
  it('keeps a sentence as it is', () => {
    expect(describeDetail('Account not found')).toBe('Account not found');
  });

  it('lists each failed field', () => {
    expect(
      describeDetail([
        { loc: ['body', 'postings', 0, 'amount'], msg: 'Field required', type: 'missing' },
        { loc: ['query', 'from_date'], msg: 'Field required', type: 'missing' },
      ]),
    ).toBe('postings[0].amount: Field required; query.from_date: Field required');
  });

  it('reads a message out of a structured detail', () => {
    expect(describeDetail({ error: 'invalid_key', message: 'Anthropic rejected this key.' })).toBe(
      'Anthropic rejected this key.',
    );
  });

  it('joins a list of plain messages', () => {
    expect(describeDetail(['Row 3: no date', 'Row 9: no amount'])).toBe('Row 3: no date; Row 9: no amount');
  });

  it('is empty for no detail', () => {
    expect(describeDetail(null)).toBe('');
    expect(describeDetail(undefined)).toBe('');
  });
});

describe('SalliApiError.fromResponse', () => {
  it('reads RFC 9457 problem details', () => {
    const error = SalliApiError.fromResponse(
      response(422, { 'x-request-id': 'req-1' }),
      {
        type: '/problems/fx-rate-unavailable',
        title: 'No exchange rate',
        status: 422,
        detail: 'No USD→LKR rate for 2026-01-01. Send the exchange rate (fx_rate) with the amount.',
      },
      new Request('http://salli.test/v1/entries/', { method: 'POST' }),
    );
    expect(error.status).toBe(422);
    expect(error.kind).toBe('fx-rate-unavailable');
    expect(error.requestId).toBe('req-1');
    expect(error.method).toBe('POST');
    expect(error.message).toBe(
      'No exchange rate: No USD→LKR rate for 2026-01-01. Send the exchange rate (fx_rate) with the amount.',
    );
    expect(error.toProblem()).toEqual({
      type: '/problems/fx-rate-unavailable',
      title: 'No exchange rate',
      status: 422,
      detail: 'No USD→LKR rate for 2026-01-01. Send the exchange rate (fx_rate) with the amount.',
    });
  });

  it('renders a validation problem as one line', () => {
    const error = SalliApiError.fromResponse(response(422), {
      type: '/problems/validation',
      title: 'Request validation failed',
      status: 422,
      detail: [{ loc: ['body', 'entry_date'], msg: 'Field required', type: 'missing' }],
    });
    expect(error.message).toBe('Request validation failed: entry_date: Field required');
  });

  it("reads the server's bare 500 body and its request id", () => {
    const error = SalliApiError.fromResponse(response(500), {
      detail: 'Internal server error',
      request_id: 'abc-123',
    });
    expect(error.title).toBe('Internal Server Error');
    expect(error.requestId).toBe('abc-123');
    expect(error.message).toBe('Internal Server Error: Internal server error');
    expect(error.toProblem()).toMatchObject({ status: 500, request_id: 'abc-123' });
  });

  it('reads an OAuth error body', () => {
    const error = SalliApiError.fromResponse(response(400), {
      error: 'invalid_grant',
      error_description: 'invalid or expired refresh token',
    });
    expect(error.kind).toBe('oauth-invalid_grant');
    expect(error.message).toBe('invalid_grant: invalid or expired refresh token');
  });

  it('does not repeat a detail that only restates the title', () => {
    const error = SalliApiError.fromResponse(response(404), { type: 'about:blank', title: 'Not Found', status: 404, detail: 'Not Found' });
    expect(error.message).toBe('Not Found');
    expect(error.kind).toBeUndefined();
  });

  it('ignores an HTML error page from a proxy', () => {
    const error = SalliApiError.fromResponse(response(502), '<html><body>Bad gateway</body></html>');
    expect(error.message).toBe('Bad Gateway');
  });
});

describe('SalliNetworkError', () => {
  it('names a refused connection plainly', () => {
    const cause = Object.assign(new Error('connect ECONNREFUSED 127.0.0.1:9'), { code: 'ECONNREFUSED' });
    const error = SalliNetworkError.fromFetchError(
      Object.assign(new TypeError('fetch failed'), { cause }),
      'http://127.0.0.1:9/v1/meta',
    );
    expect(error.message).toBe('Could not reach http://127.0.0.1:9 (connection refused)');
    expect(error.code).toBe('ECONNREFUSED');
  });
});
