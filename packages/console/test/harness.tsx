/**
 * The console in a test: `createConsole` over a fixture server (MockApi),
 * an in-memory sessionStorage, a memory history and a recorded address bar.
 */
import { createMemoryHistory } from '@tanstack/react-router';
import { act, cleanup, render, type RenderResult } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import { KEYS, type SessionEnvironment } from '../src/auth/session';
import type { Release } from '../src/auth/claim';
import { createConsole, type SalliConsole } from '../src/console';
import type { ConsoleExtension } from '../src/extensions';
import { ORIGIN } from './fixtures/auth';
import { MockApi } from './fixtures/api';

/** The golden household's date: Home's fixtures are as of this day. */
export const TODAY = new Date('2026-10-11T10:00:00Z');

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

export class MemoryStorage implements Storage {
  private items = new Map<string, string>();
  get length(): number {
    return this.items.size;
  }
  clear(): void {
    this.items.clear();
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null;
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
  setItem(key: string, value: string): void {
    this.items.set(key, String(value));
  }
  entries(): Record<string, string> {
    return Object.fromEntries(this.items);
  }
}

export interface Harness {
  api: MockApi;
  app: SalliConsole;
  storage: MemoryStorage;
  /** Where the console sent the browser (the sign-in page). */
  assigned: string[];
  /** The address bar, as the console set it. */
  location: { origin: string; pathname: string; search: string; hash: string; href: string };
  view: RenderResult;
}

export interface SetupOptions {
  api?: MockApi;
  /** Start with a sign-in kept in the tab (a reload). Default true. */
  signedIn?: boolean;
  /** The address the console opens at. */
  path?: string;
  extensions?: ConsoleExtension[];
  storage?: MemoryStorage;
  claim?: (id: string) => Promise<Release | null>;
  /** Don't start the session (the test starts it). */
  manualStart?: boolean;
}

export function keepSignIn(storage: Storage, refresh = 'rt-0'): void {
  storage.setItem(KEYS.signIn, JSON.stringify({ id: 'tab-1', user_id: 'household', email: 'ana@example.org' }));
  storage.setItem(KEYS.refresh, refresh);
}

export async function setup(options: SetupOptions = {}): Promise<Harness> {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(TODAY);
  const api = options.api ?? new MockApi();
  const storage = options.storage ?? new MemoryStorage();
  if (options.signedIn ?? true) keepSignIn(storage);
  const path = options.path ?? '/console/';
  const url = new URL(path, ORIGIN);
  const location = { origin: ORIGIN, pathname: url.pathname, search: url.search, hash: url.hash, href: url.href };
  const assigned: string[] = [];
  const environment: SessionEnvironment = {
    location,
    assign: (target) => void assigned.push(target),
    replaceUrl: (target) => {
      const next = new URL(target, ORIGIN);
      Object.assign(location, { pathname: next.pathname, search: next.search, hash: next.hash, href: next.href });
    },
    storage,
    isSecureContext: true,
    fetch: api.fetch,
    claim: options.claim ?? (async () => () => undefined),
  };
  const app = createConsole({
    environment,
    history: () => createMemoryHistory({ initialEntries: [`${location.pathname}${location.search}${location.hash}`] }),
    locale: 'en-US',
    ...(options.extensions ? { extensions: options.extensions } : {}),
  });
  const view = render(<app.App />);
  if (!options.manualStart) {
    await act(async () => {
      await app.session.start();
    });
  }
  return { api, app, storage, assigned, location, view };
}
