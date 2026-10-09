/**
 * Errors the SDK raises.
 *
 * Every error the Salli API returns is RFC 9457 problem details
 * (`application/problem+json`): `type` names the kind of problem, `title`
 * summarises it, `status` repeats the HTTP status and `detail` explains this
 * occurrence — a sentence for most errors, a field-by-field list when a
 * request failed validation.
 */

/** RFC 9457 problem details, the shape of every Salli API error. */
export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: unknown;
  [extension: string]: unknown;
}

/** One entry of a validation error's `detail` (FastAPI's shape). */
export interface ValidationIssue {
  loc: Array<string | number>;
  msg: string;
  type?: string;
}

export function isProblemDetails(value: unknown): value is ProblemDetails {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.type === 'string' && typeof v.title === 'string' && typeof v.status === 'number';
}

function isValidationIssue(value: unknown): value is ValidationIssue {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return Array.isArray(v.loc) && typeof v.msg === 'string';
}

/** `["body", "postings", 0, "amount"]` → `postings[0].amount`. */
function fieldPath(loc: Array<string | number>): string {
  const parts = loc[0] === 'body' && loc.length > 1 ? loc.slice(1) : loc;
  let out = '';
  for (const part of parts) {
    if (typeof part === 'number') out += `[${part}]`;
    else out += out ? `.${part}` : part;
  }
  return out;
}

/**
 * A problem's `detail`, as one line of text: the sentence itself, each
 * failed field as `field: message`, or a compact rendering of anything else.
 */
export function describeDetail(detail: unknown): string {
  if (detail === undefined || detail === null) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (isValidationIssue(item)) {
          const where = fieldPath(item.loc);
          return where ? `${where}: ${item.msg}` : item.msg;
        }
        return typeof item === 'string' ? item : JSON.stringify(item);
      })
      .join('; ');
  }
  if (typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === 'string') return d.message;
    if (typeof d.detail === 'string') return d.detail;
  }
  const text = JSON.stringify(detail);
  return text.length > 300 ? `${text.slice(0, 297)}...` : text;
}

const STATUS_TITLES: Record<number, string> = {
  400: 'Bad Request',
  401: 'Unauthorized',
  402: 'Payment Required',
  403: 'Forbidden',
  404: 'Not Found',
  409: 'Conflict',
  413: 'Content Too Large',
  422: 'Unprocessable Content',
  429: 'Too Many Requests',
  500: 'Internal Server Error',
  502: 'Bad Gateway',
  503: 'Service Unavailable',
  504: 'Gateway Timeout',
};

export interface SalliApiErrorInit {
  status: number;
  type?: string;
  title?: string;
  detail?: unknown;
  body?: unknown;
  requestId?: string | undefined;
  method?: string | undefined;
  url?: string | undefined;
}

/** The API answered with an error status. */
export class SalliApiError extends Error {
  override readonly name = 'SalliApiError';
  /** The HTTP status. */
  readonly status: number;
  /** The problem type: a path under `/problems/`, or `about:blank`. */
  readonly type: string;
  readonly title: string;
  readonly detail: unknown;
  /** The response body as received (parsed JSON, or text). */
  readonly body: unknown;
  /** The server's `X-Request-Id`, to quote in a bug report. */
  readonly requestId: string | undefined;
  readonly method: string | undefined;
  readonly url: string | undefined;

  constructor(init: SalliApiErrorInit) {
    const title = init.title || STATUS_TITLES[init.status] || `HTTP ${init.status}`;
    const detailText = describeDetail(init.detail);
    super(detailText && detailText !== title ? `${title}: ${detailText}` : title);
    this.status = init.status;
    this.type = init.type || 'about:blank';
    this.title = title;
    this.detail = init.detail;
    this.body = init.body;
    this.requestId = init.requestId;
    this.method = init.method;
    this.url = init.url;
  }

  /** The problem's kind without its prefix: `/problems/fx-rate-unavailable` → `fx-rate-unavailable`. */
  get kind(): string | undefined {
    if (this.type === 'about:blank') return undefined;
    return this.type.replace(/^.*\/problems\//, '') || undefined;
  }

  /** The error as RFC 9457 problem details. */
  toProblem(): ProblemDetails {
    if (isProblemDetails(this.body)) return this.body;
    const problem: ProblemDetails = {
      type: this.type,
      title: this.title,
      status: this.status,
      detail: this.detail ?? null,
    };
    if (this.requestId) problem.request_id = this.requestId;
    return problem;
  }

  /** Builds the error from a response and its (already read) body. */
  static fromResponse(response: Response, body: unknown, request?: Request): SalliApiError {
    const requestId = response.headers.get('x-request-id') ?? undefined;
    const common = {
      status: response.status,
      body,
      requestId,
      method: request?.method,
      url: request?.url ?? (response.url || undefined),
    };
    if (isProblemDetails(body)) {
      return new SalliApiError({
        ...common,
        type: body.type,
        title: body.title,
        detail: body.detail,
      });
    }
    if (typeof body === 'object' && body !== null) {
      const b = body as Record<string, unknown>;
      // OAuth endpoints (RFC 6749 §5.2) and pre-problem-details bodies.
      if (typeof b.error === 'string') {
        return new SalliApiError({
          ...common,
          type: `/problems/oauth-${b.error}`,
          title: b.error,
          detail: b.error_description ?? null,
        });
      }
      return new SalliApiError({
        ...common,
        detail: b.detail ?? body,
        requestId: requestId ?? (typeof b.request_id === 'string' ? b.request_id : undefined),
      });
    }
    const text = typeof body === 'string' ? body.trim() : '';
    return new SalliApiError({
      ...common,
      // A proxy's HTML error page says nothing useful in one line.
      detail: text && !text.startsWith('<') ? text.split('\n')[0]?.slice(0, 300) : undefined,
    });
  }
}

/** The server could not be reached, or did not answer in time. */
export class SalliNetworkError extends Error {
  override readonly name = 'SalliNetworkError';
  readonly url: string | undefined;
  readonly code: string | undefined;

  constructor(message: string, options: { url?: string; code?: string; cause?: unknown } = {}) {
    super(message, { cause: options.cause });
    this.url = options.url;
    this.code = options.code;
  }

  /** Describes a failed `fetch`, naming the usual causes plainly. */
  static fromFetchError(error: unknown, url: string): SalliNetworkError {
    const cause = (error as { cause?: { code?: string; message?: string } } | undefined)?.cause;
    const code = cause?.code ?? (error as { code?: string } | undefined)?.code;
    let origin = url;
    try {
      origin = new URL(url).origin;
    } catch {
      // keep the url as given
    }
    const reason =
      code === 'ECONNREFUSED'
        ? 'connection refused'
        : code === 'ENOTFOUND' || code === 'EAI_AGAIN'
          ? 'host not found'
          : code === 'ECONNRESET'
            ? 'connection reset'
            : code === 'ETIMEDOUT' || code === 'UND_ERR_CONNECT_TIMEOUT'
              ? 'connection timed out'
              : code === 'CERT_HAS_EXPIRED' || code?.startsWith('ERR_TLS') || code?.includes('CERT')
                ? 'TLS certificate problem'
                : (cause?.message ?? (error instanceof Error ? error.message : String(error)));
    return new SalliNetworkError(`Could not reach ${origin} (${reason})`, {
      url,
      ...(code ? { code } : {}),
      cause: error,
    });
  }
}

/** An OAuth endpoint refused a request (RFC 6749 §5.2 / RFC 8628 §3.5). */
export class SalliOAuthError extends Error {
  override readonly name = 'SalliOAuthError';
  /** The OAuth error code: `invalid_grant`, `access_denied`, `expired_token`… */
  readonly error: string;
  readonly errorDescription: string | undefined;
  readonly status: number | undefined;

  constructor(error: string, errorDescription?: string, status?: number) {
    super(errorDescription ? `${error}: ${errorDescription}` : error);
    this.error = error;
    this.errorDescription = errorDescription;
    this.status = status;
  }
}

/** Whether an error is the abort of a request the caller cancelled. */
export function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { name?: unknown }).name === 'AbortError'
  );
}
