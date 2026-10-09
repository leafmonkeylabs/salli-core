/**
 * The loopback redirect of a native app's sign-in (RFC 8252 §7.3): a tiny
 * HTTP server on 127.0.0.1, on a port the OS picks, that receives the
 * browser's redirect with the authorization code, checks `state`, and shows
 * a page saying the user can go back to the terminal.
 */
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { SalliOAuthError } from '@leafmonkeylabs/salli-sdk';
import { CliError, ExitCode, InterruptedError } from '../errors';

export interface LoopbackServer {
  /** `http://127.0.0.1:<port>/callback` */
  readonly redirectUri: string;
  /** Resolves with the authorization code when the browser comes back. */
  waitForCode(options: { state: string; signal: AbortSignal; timeoutMs: number }): Promise<string>;
  close(): Promise<void>;
}

const escapeHtml = (text: string): string =>
  text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c);

/** The page the browser shows after the redirect. Self-contained: no scripts, no requests. */
export function callbackPage(ok: boolean, message: string): string {
  const title = ok ? 'Signed in to Salli' : 'Sign-in did not finish';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<style>
  :root { color-scheme: light dark; --bg: #f6f5f1; --fg: #1d2420; --muted: #5d6862; --accent: ${ok ? '#2f7d4f' : '#b3412e'}; --card: #ffffff; }
  @media (prefers-color-scheme: dark) { :root { --bg: #141816; --fg: #e8ece9; --muted: #9aa5a0; --card: #1d2320; } }
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--fg);
         font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; padding: 16px; }
  main { max-width: 420px; width: 100%; background: var(--card); border-radius: 14px; padding: 32px 28px;
         box-shadow: 0 1px 2px rgba(0,0,0,.06), 0 8px 24px rgba(0,0,0,.06); text-align: center; }
  .mark { width: 48px; height: 48px; border-radius: 50%; margin: 0 auto 16px; display: grid; place-items: center;
          background: var(--accent); color: #fff; font-size: 26px; font-weight: 700; }
  h1 { font-size: 20px; margin: 0 0 8px; }
  p { margin: 0; color: var(--muted); }
  code { font: 14px ui-monospace, SFMono-Regular, Menlo, monospace; }
</style>
</head>
<body>
<main>
  <div class="mark" aria-hidden="true">${ok ? '✓' : '!'}</div>
  <h1>${title}</h1>
  <p>${escapeHtml(message)}</p>
</main>
</body>
</html>
`;
}

export async function startLoopbackServer(): Promise<LoopbackServer> {
  let settle: { resolve: (code: string) => void; reject: (error: unknown) => void } | undefined;
  let expectedState: string | undefined;
  let outcome: { code?: string; error?: unknown } | undefined;

  const finish = (result: { code?: string; error?: unknown }): void => {
    if (outcome) return;
    outcome = result;
    if (result.code !== undefined) settle?.resolve(result.code);
    else settle?.reject(result.error);
  };

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://127.0.0.1');
    const respond = (status: number, ok: boolean, message: string): void => {
      res.writeHead(status, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
        'Referrer-Policy': 'no-referrer',
      });
      res.end(callbackPage(ok, message));
    };
    if (req.method !== 'GET' || url.pathname !== '/callback') {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not found');
      return;
    }
    if (outcome) {
      respond(200, outcome.code !== undefined, 'This sign-in has already finished. You can close this tab.');
      return;
    }
    const params = url.searchParams;
    if (expectedState === undefined || params.get('state') !== expectedState) {
      respond(400, false, 'This sign-in link does not match the one salli started. Run salli login again.');
      finish({
        error: new CliError('Sign-in failed: the browser returned with a different state than salli sent.', {
          exitCode: ExitCode.NOT_SIGNED_IN,
          kind: 'not-signed-in',
          hint: 'Run `salli login` again.',
        }),
      });
      return;
    }
    const error = params.get('error');
    if (error) {
      const description = params.get('error_description') ?? undefined;
      respond(
        200,
        false,
        error === 'access_denied' ? 'You declined the request. You can close this tab.' : `The server said: ${description ?? error}`,
      );
      finish({ error: new SalliOAuthError(error, description ?? (error === 'access_denied' ? 'you declined in the browser' : undefined)) });
      return;
    }
    const code = params.get('code');
    if (!code) {
      respond(400, false, 'The server sent no authorization code. Run salli login again.');
      finish({ error: new SalliOAuthError('invalid_request', 'no authorization code in the redirect') });
      return;
    }
    respond(200, true, 'You can close this tab and go back to your terminal.');
    finish({ code });
  });

  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => resolve());
  });
  const { port } = server.address() as AddressInfo;

  return {
    redirectUri: `http://127.0.0.1:${port}/callback`,
    waitForCode({ state, signal, timeoutMs }) {
      expectedState = state;
      return new Promise<string>((resolve, reject) => {
        const timer = setTimeout(() => {
          finish({
            error: new CliError('Sign-in timed out waiting for the browser.', {
              exitCode: ExitCode.NOT_SIGNED_IN,
              kind: 'not-signed-in',
              hint: 'Run `salli login` again, or `salli login --device` to sign in from another device.',
            }),
          });
        }, timeoutMs);
        const onAbort = (): void => finish({ error: new InterruptedError() });
        signal.addEventListener('abort', onAbort, { once: true });
        settle = {
          resolve: (code) => {
            clearTimeout(timer);
            signal.removeEventListener('abort', onAbort);
            resolve(code);
          },
          reject: (error) => {
            clearTimeout(timer);
            signal.removeEventListener('abort', onAbort);
            reject(error);
          },
        };
        if (signal.aborted) onAbort();
      });
    },
    close: () =>
      new Promise<void>((resolve) => {
        // Let the page finish sending, then drop whatever the browser keeps open.
        const force = setTimeout(() => server.closeAllConnections(), 1000);
        server.close(() => {
          clearTimeout(force);
          resolve();
        });
        server.closeIdleConnections();
      }),
  };
}
