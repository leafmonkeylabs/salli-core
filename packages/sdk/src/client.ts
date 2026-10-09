/**
 * A client for one Salli server.
 *
 * The generated functions (`accountsList`, `entriesCreate`, …) take a
 * `client`; this module builds that client with what every caller needs:
 * the server's base URL, a bearer token with one refresh-and-retry on 401,
 * errors as `SalliApiError` / `SalliNetworkError`, and a timeout.
 *
 *     const salli = createClient({ server: 'http://localhost:8000', auth: token });
 *     const accounts = await salli.call(accountsList);
 *     const account = await salli.call(accountsGet, { path: { account_id: id } });
 */
import { createClient as createFetchClient, type Client } from './generated/client';
import { metaGet } from './generated/sdk.gen';
import type { Meta } from './generated/types.gen';
import { isAbortError, SalliApiError, SalliNetworkError } from './errors';
import { withRawJson } from './json';
import { readServerSentEvents, type EventSourceMessage } from './sse';

/** Supplies the bearer token, and a fresh one when the server refuses it. */
export interface TokenProvider {
  /** The token for the next request, or undefined to send none. */
  getToken(): string | undefined | Promise<string | undefined>;
  /**
   * Called once when a request comes back 401. `failedToken` is the token
   * that request carried; return a token to retry with (a refreshed one, or
   * the current one if another request already refreshed), or undefined to
   * let the 401 stand.
   */
  refresh?(failedToken: string | undefined): Promise<string | undefined>;
}

/** What `onResponse` is told about each request. */
export interface RequestLog {
  method: string;
  url: string;
  status?: number;
  durationMs: number;
  error?: unknown;
}

export interface SalliClientOptions {
  /** The server's base URL, e.g. `https://salli.example.com`. */
  server: string;
  /** A bearer token, or a provider of one. Omit for public endpoints. */
  auth?: string | TokenProvider | undefined;
  /** A fetch implementation. Default: the global one. */
  fetch?: typeof globalThis.fetch;
  /** Sent as `User-Agent`. */
  userAgent?: string;
  /** Extra headers on every request. */
  headers?: Record<string, string>;
  /** Abandon a request after this long; 0 for never. Default 30 seconds. */
  timeoutMs?: number;
  /** Aborts every request (e.g. on Ctrl-C). The abort's reason is what the call throws. */
  signal?: AbortSignal;
  /** Called after every request (for logging). */
  onResponse?: (log: RequestLog) => void;
}

// The generated functions are generic in whether they throw, which makes
// their exact types awkward to name; `call` only needs their shape.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SdkFunction = (options: any) => Promise<any>;

/** The options a generated function takes, minus the client `call` supplies. */
export type CallOptions<F extends SdkFunction> = Omit<NonNullable<Parameters<F>[0]>, 'client'> & {
  /** Overrides the client's timeout for this call; 0 for none. */
  timeoutMs?: number;
};

type CallArgs<F extends SdkFunction> = undefined extends Parameters<F>[0]
  ? [options?: CallOptions<F>]
  : [options: CallOptions<F>];

/** What a generated function's successful response parses to. */
export type DataOf<F extends SdkFunction> =
  Awaited<ReturnType<F>> extends infer R ? (R extends { data: infer D } ? Exclude<D, undefined> : never) : never;

export interface SalliClient {
  /** The server's base URL, without a trailing slash. */
  readonly server: string;
  /** The underlying client, for calling a generated function directly. */
  readonly client: Client;
  /**
   * Calls a generated function and returns its data, or throws
   * `SalliApiError` (an error response) or `SalliNetworkError` (no response).
   */
  call<F extends SdkFunction>(fn: F, ...args: CallArgs<F>): Promise<DataOf<F>>;
  /** Calls an operation that streams server-sent events, yielding each one. */
  events<F extends SdkFunction>(fn: F, ...args: CallArgs<F>): AsyncGenerator<EventSourceMessage, void, undefined>;
  /** `GET /v1/meta`: what the server is and how to sign in to it. */
  meta(options?: { signal?: AbortSignal; timeoutMs?: number }): Promise<Meta>;
}

/** The server URL as the client uses it: validated, without a trailing slash. */
export function normalizeServerUrl(server: string): string {
  const trimmed = server.trim();
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new TypeError(`Not a server URL: ${server}`);
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new TypeError(`A server URL starts with http:// or https:// (got ${server})`);
  }
  url.hash = '';
  url.search = '';
  return url.toString().replace(/\/+$/, '');
}

function tokenProviderOf(auth: SalliClientOptions['auth']): TokenProvider | undefined {
  if (auth === undefined) return undefined;
  if (typeof auth === 'string') return { getToken: () => auth };
  return auth;
}

const NULL_BODY_STATUSES = new Set([101, 204, 205, 304]);
const rawBodies = new WeakMap<Response, string>();

/** Reads a JSON response's text once, so it can be kept beside the parsed value. */
async function keepRawJson(response: Response): Promise<Response> {
  const type = response.headers.get('content-type') ?? '';
  if (!/json/i.test(type) || response.body === null || NULL_BODY_STATUSES.has(response.status)) {
    return response;
  }
  const text = await response.text();
  const copy = new Response(text, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
  rawBodies.set(copy, text);
  return copy;
}

function isTimeoutError(error: unknown): boolean {
  return typeof error === 'object' && error !== null && (error as { name?: unknown }).name === 'TimeoutError';
}

function createSalliFetch(options: SalliClientOptions): typeof globalThis.fetch {
  const baseFetch = options.fetch ?? globalThis.fetch;
  const provider = tokenProviderOf(options.auth);
  let refreshing: Promise<string | undefined> | undefined;

  const refreshOnce = (failed: string | undefined): Promise<string | undefined> => {
    if (!provider?.refresh) return Promise.resolve(undefined);
    refreshing ??= provider.refresh(failed).finally(() => {
      refreshing = undefined;
    });
    return refreshing;
  };

  const send = async (request: Request): Promise<Response> => {
    const started = performance.now();
    try {
      const response = await baseFetch(request);
      options.onResponse?.({
        method: request.method,
        url: request.url,
        status: response.status,
        durationMs: performance.now() - started,
      });
      return response;
    } catch (error) {
      options.onResponse?.({
        method: request.method,
        url: request.url,
        durationMs: performance.now() - started,
        error,
      });
      // A request the caller aborted ends with the reason it was aborted for.
      if (request.signal.aborted) throw request.signal.reason ?? error;
      if (isAbortError(error) || isTimeoutError(error)) throw error;
      throw SalliNetworkError.fromFetchError(error, request.url);
    }
  };

  const salliFetch = async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const request = input instanceof Request && init === undefined ? input : new Request(input, init);
    if (options.userAgent) request.headers.set('User-Agent', options.userAgent);
    for (const [name, value] of Object.entries(options.headers ?? {})) request.headers.set(name, value);
    if (!request.headers.has('Accept')) request.headers.set('Accept', 'application/json');

    const token = provider ? await provider.getToken() : undefined;
    // Kept unsent, so the request can go again with a refreshed token.
    const retry = provider?.refresh ? request.clone() : undefined;
    if (token) request.headers.set('Authorization', `Bearer ${token}`);

    let response = await send(request);
    if (response.status === 401 && retry) {
      const fresh = await refreshOnce(token);
      if (fresh && fresh !== token) {
        await response.body?.cancel().catch(() => undefined);
        retry.headers.set('Authorization', `Bearer ${fresh}`);
        response = await send(retry);
      }
    }
    return keepRawJson(response);
  };
  return salliFetch as typeof globalThis.fetch;
}

interface Settled {
  data?: unknown;
  error?: unknown;
  request?: Request;
  response?: Response;
}

function toError(result: Settled, timeout: AbortSignal | undefined, timeoutMs: number, cancel: AbortSignal | undefined): unknown {
  const { error, request, response } = result;
  if (cancel?.aborted) return cancel.reason ?? error;
  if (error instanceof SalliApiError || error instanceof SalliNetworkError) return error;
  if (isTimeoutError(error) || (timeout?.aborted && isAbortError(error))) {
    return new SalliNetworkError(
      `${request?.url ? new URL(request.url).origin : 'The server'} did not answer within ${Math.round(timeoutMs / 1000)}s`,
      { ...(request?.url ? { url: request.url } : {}), code: 'ETIMEDOUT', cause: error },
    );
  }
  if (isAbortError(error)) return error;
  if (response && !response.ok) return SalliApiError.fromResponse(response, error, request);
  if (response === undefined) return SalliNetworkError.fromFetchError(error, request?.url ?? '');
  return error;
}

/** Creates a client for one Salli server. */
export function createClient(options: SalliClientOptions): SalliClient {
  const server = normalizeServerUrl(options.server);
  const defaultTimeout = options.timeoutMs ?? 30_000;
  const client = createFetchClient({ baseUrl: server, fetch: createSalliFetch(options) });

  async function invoke(
    fn: SdkFunction,
    args: unknown[],
    extra: { parseAs?: 'stream'; timeoutMs?: number; headers?: Record<string, string> },
  ): Promise<Settled> {
    const given = (args[0] ?? {}) as Record<string, unknown> & { timeoutMs?: number; signal?: AbortSignal; headers?: Record<string, string> };
    const { timeoutMs = extra.timeoutMs ?? defaultTimeout, signal, headers, ...rest } = given;
    const ms = typeof timeoutMs === 'number' && timeoutMs > 0 ? timeoutMs : 0;
    const timeout = ms > 0 ? AbortSignal.timeout(ms) : undefined;
    const cancels = [options.signal, signal].filter((s): s is AbortSignal => s !== undefined);
    const cancel = cancels.length > 1 ? AbortSignal.any(cancels) : cancels[0];
    const all = [cancel, timeout].filter((s): s is AbortSignal => s !== undefined);
    const combined = all.length > 1 ? AbortSignal.any(all) : all[0];
    if (cancel?.aborted) throw cancel.reason ?? new DOMException('Aborted', 'AbortError');
    const result = (await fn({
      ...rest,
      ...(extra.parseAs ? { parseAs: extra.parseAs } : {}),
      ...(extra.headers || headers ? { headers: { ...extra.headers, ...headers } } : {}),
      ...(combined ? { signal: combined } : {}),
      client,
    })) as Settled;
    if (result.error !== undefined) throw toError(result, timeout, ms, cancel);
    return result;
  }

  return {
    server,
    client,

    async call(fn, ...args) {
      const result = await invoke(fn, args, {});
      // No content: there is nothing to return.
      if (result.response?.status === 204) return undefined as never;
      const raw = result.response ? rawBodies.get(result.response) : undefined;
      return withRawJson(result.data, raw) as never;
    },

    async *events(fn, ...args) {
      // A stream runs as long as the conversation does: no timeout.
      const result = await invoke(fn, args, { parseAs: 'stream', timeoutMs: 0, headers: { Accept: 'text/event-stream' } });
      const stream = result.data as ReadableStream<Uint8Array> | null | undefined;
      if (!stream || typeof (stream as { getReader?: unknown }).getReader !== 'function') return;
      const signals = [options.signal, (args[0] as { signal?: AbortSignal } | undefined)?.signal].filter(
        (s): s is AbortSignal => s !== undefined,
      );
      yield* readServerSentEvents(stream, signals.length > 1 ? AbortSignal.any(signals) : signals[0]);
    },

    meta(metaOptions = {}) {
      return this.call(metaGet, metaOptions);
    },
  };
}
