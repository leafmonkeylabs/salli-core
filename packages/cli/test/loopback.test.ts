import { SalliOAuthError } from '@leafmonkeylabs/salli-sdk';
import { describe, expect, it } from 'vitest';
import { callbackPage, startLoopbackServer } from '../src/auth/loopback';
import { CliError } from '../src/errors';

const never = new AbortController().signal;

describe('the loopback redirect listener', () => {
  it('listens on 127.0.0.1 on a port the OS picks', async () => {
    const server = await startLoopbackServer('s1');
    expect(server.redirectUri).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/callback$/);
    await server.close();
  });

  it('takes the code when the state matches, even if the browser came back first', async () => {
    const server = await startLoopbackServer('s1');
    const page = await fetch(`${server.redirectUri}?code=abc&state=s1`).then((r) => r.text());
    expect(page).toContain('Signed in to Salli');
    await expect(server.waitForCode({ signal: never, timeoutMs: 1000 })).resolves.toBe('abc');
    await server.close();
  });

  it('refuses a redirect with another state', async () => {
    const server = await startLoopbackServer('s1');
    const waiting = server.waitForCode({ signal: never, timeoutMs: 1000 }).catch((e: unknown) => e);
    const response = await fetch(`${server.redirectUri}?code=abc&state=forged`);
    expect(response.status).toBe(400);
    expect(await waiting).toBeInstanceOf(CliError);
    await server.close();
  });

  it('reports a declined sign-in', async () => {
    const server = await startLoopbackServer('s1');
    const waiting = server.waitForCode({ signal: never, timeoutMs: 1000 }).catch((e: unknown) => e);
    await fetch(`${server.redirectUri}?error=access_denied&state=s1`);
    const error = await waiting;
    expect(error).toBeInstanceOf(SalliOAuthError);
    expect((error as SalliOAuthError).error).toBe('access_denied');
    await server.close();
  });

  it('gives up after the timeout, and on Ctrl-C', async () => {
    const server = await startLoopbackServer('s1');
    await expect(server.waitForCode({ signal: never, timeoutMs: 20 })).rejects.toThrow(/timed out/);
    await server.close();

    const again = await startLoopbackServer('s2');
    const controller = new AbortController();
    const waiting = again.waitForCode({ signal: controller.signal, timeoutMs: 5000 });
    controller.abort();
    await expect(waiting).rejects.toMatchObject({ exitCode: 130 });
    await again.close();
  });

  it('answers anything else with 404', async () => {
    const server = await startLoopbackServer('s1');
    expect((await fetch(`${server.redirectUri.replace('/callback', '/favicon.ico')}`)).status).toBe(404);
    await server.close();
  });

  it('escapes what the server says on the page', () => {
    expect(callbackPage(false, '<script>alert(1)</script>')).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });
});
