/**
 * Exit codes and the errors that carry them.
 *
 * The exit code is part of the CLI's contract with scripts:
 *
 *   0    success
 *   1    an error (the server failed, or something unexpected)
 *   2    usage: a bad command, flag or argument
 *   3    not signed in, or the session expired
 *   4    not found
 *   5    the server refused the request (validation, conflict: a 4xx with problem details)
 *   6    the server speaks an API version this CLI does not
 *   7    network: the server could not be reached
 *   130  interrupted (Ctrl-C)
 */
import {
  isAbortError,
  SalliApiError,
  SalliNetworkError,
  SalliOAuthError,
  type ProblemDetails,
} from '@leafmonkeylabs/salli-sdk';

export const ExitCode = {
  OK: 0,
  ERROR: 1,
  USAGE: 2,
  NOT_SIGNED_IN: 3,
  NOT_FOUND: 4,
  REFUSED: 5,
  INCOMPATIBLE: 6,
  NETWORK: 7,
  INTERRUPTED: 130,
} as const;

export type ExitCodeValue = (typeof ExitCode)[keyof typeof ExitCode];

/** An error the CLI reports in one line, with an exit code and maybe a hint. */
export class CliError extends Error {
  override readonly name: string = 'CliError';
  readonly exitCode: number;
  /** A next step for the user, e.g. "Run `salli login`." */
  readonly hint: string | undefined;
  /** The problem type when reported as JSON: `/problems/cli/<kind>`. */
  readonly kind: string;
  /** Already reported (e.g. doctor's checklist): set the exit code, print nothing more. */
  readonly quiet: boolean;

  constructor(
    message: string,
    options: { exitCode?: number; hint?: string; kind?: string; cause?: unknown; quiet?: boolean } = {},
  ) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause });
    this.exitCode = options.exitCode ?? ExitCode.ERROR;
    this.hint = options.hint;
    this.kind = options.kind ?? 'error';
    this.quiet = options.quiet ?? false;
  }
}

export class UsageError extends CliError {
  override readonly name = 'UsageError';
  constructor(message: string, hint?: string) {
    super(message, { exitCode: ExitCode.USAGE, kind: 'usage', ...(hint ? { hint } : {}) });
  }
}

export class NotSignedInError extends CliError {
  override readonly name = 'NotSignedInError';
  constructor(message: string, hint = 'Run `salli login` to sign in.') {
    super(message, { exitCode: ExitCode.NOT_SIGNED_IN, kind: 'not-signed-in', hint });
  }
}

export class NotFoundError extends CliError {
  override readonly name = 'NotFoundError';
  constructor(message: string, hint?: string) {
    super(message, { exitCode: ExitCode.NOT_FOUND, kind: 'not-found', ...(hint ? { hint } : {}) });
  }
}

export class IncompatibleServerError extends CliError {
  override readonly name = 'IncompatibleServerError';
  constructor(message: string, hint?: string) {
    super(message, { exitCode: ExitCode.INCOMPATIBLE, kind: 'incompatible-server', ...(hint ? { hint } : {}) });
  }
}

export class InterruptedError extends CliError {
  override readonly name = 'InterruptedError';
  constructor(message = 'Cancelled.') {
    super(message, { exitCode: ExitCode.INTERRUPTED, kind: 'interrupted' });
  }
}

/** The exit code an error ends the process with. */
export function exitCodeFor(error: unknown): number {
  if (error instanceof CliError) return error.exitCode;
  if (error instanceof SalliApiError) {
    if (error.status === 401) return ExitCode.NOT_SIGNED_IN;
    if (error.status === 404) return ExitCode.NOT_FOUND;
    if (error.status >= 400 && error.status < 500) return ExitCode.REFUSED;
    return ExitCode.ERROR;
  }
  if (error instanceof SalliNetworkError) return ExitCode.NETWORK;
  if (error instanceof SalliOAuthError) return ExitCode.NOT_SIGNED_IN;
  if (isAbortError(error)) return ExitCode.INTERRUPTED;
  return ExitCode.ERROR;
}

/** A next step to suggest for an error, if there is an obvious one. */
export function hintFor(error: unknown): string | undefined {
  if (error instanceof CliError) return error.hint;
  if (error instanceof SalliApiError) {
    if (error.status === 401) return 'Your session may have expired. Run `salli login` to sign in again.';
    if (error.status >= 500 && error.requestId) return `Request id: ${error.requestId} (quote it when reporting this)`;
  }
  if (error instanceof SalliNetworkError) {
    return 'Is the server running? Check the address with `salli context current`, or run `salli doctor`.';
  }
  return undefined;
}

/** The one line the user sees for an error. */
export function messageFor(error: unknown): string {
  if (error instanceof SalliApiError) {
    if (error.status === 401) return 'Not signed in, or your session has expired.';
    return error.message;
  }
  if (error instanceof SalliOAuthError) return `Sign-in failed: ${error.message}`;
  if (isAbortError(error)) return 'Cancelled.';
  if (error instanceof Error) return error.message || error.name;
  return String(error);
}

/** An error as RFC 9457 problem details, for `--json` on stderr. */
export function problemFor(error: unknown): ProblemDetails & { exit_code: number } {
  const exit_code = exitCodeFor(error);
  if (error instanceof SalliApiError) return { ...error.toProblem(), exit_code };
  if (error instanceof SalliNetworkError) {
    return { type: '/problems/cli/network', title: 'Server unreachable', status: 0, detail: error.message, exit_code };
  }
  if (error instanceof SalliOAuthError) {
    return {
      type: `/problems/cli/oauth-${error.error}`,
      title: 'Sign-in failed',
      status: error.status ?? 0,
      detail: error.errorDescription ?? error.error,
      exit_code,
    };
  }
  if (error instanceof CliError) {
    return {
      type: `/problems/cli/${error.kind}`,
      title: error.message,
      status: 0,
      detail: error.hint ?? null,
      exit_code,
    };
  }
  return { type: '/problems/cli/error', title: messageFor(error), status: 0, detail: null, exit_code };
}
