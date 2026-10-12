/**
 * The fixture server behind Playwright's `page.route`: the console's own
 * files come from the build (serve.mjs, with the server's headers), and the
 * API and the sign-in from MockApi, which answers Home's reads with what the
 * real server answers on the golden household.
 */
import type { Page } from '@playwright/test';
import { MockApi } from '../test/fixtures/api';

const API = /^\/(v1|mcp|\.well-known|healthz)(\/|$)/;

/** Answers the API for `page` from fixtures. Signing in goes straight back with a code. */
export async function mockSalli(page: Page, origin: string, api: MockApi = new MockApi(origin)): Promise<MockApi> {
  await page.route(`${origin}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!API.test(url.pathname)) return route.continue();
    if (url.pathname === '/mcp/oauth/authorize') {
      // Salli's sign-in page, approved: back to the console with a code.
      const back = new URL(url.searchParams.get('redirect_uri') ?? `${origin}/console/callback`);
      back.searchParams.set('code', 'fixture-code');
      back.searchParams.set('state', url.searchParams.get('state') ?? '');
      return route.fulfill({ status: 302, headers: { location: back.toString() } });
    }
    const answer = api.answer({
      method: request.method(),
      path: url.pathname,
      search: url.search,
      body: request.postData() ?? '',
      authorization: (await request.allHeaders()).authorization ?? null,
    }) ?? { status: 404, body: { type: 'about:blank', title: 'Not Found', status: 404 } };
    if (answer.text !== undefined) {
      return route.fulfill({ status: answer.status, headers: { 'content-type': 'text/plain', 'cache-control': 'no-store', ...answer.headers }, body: answer.text });
    }
    const json = answer.body !== undefined && answer.status !== 204;
    return route.fulfill({
      status: answer.status,
      headers: { 'content-type': answer.status >= 400 ? 'application/problem+json' : 'application/json', 'cache-control': 'no-store', ...answer.headers },
      ...(json ? { body: JSON.stringify(answer.body) } : {}),
    });
  });
  return api;
}
