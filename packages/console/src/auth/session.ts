/**
 * Signing in to the console (docs/design/console.md, section 2; decisions
 * 3 to 6).
 *
 * - **The flow.** OAuth's authorisation code with PKCE (S256), as the
 *   first-party public client `salli-console`, for the API's resource. The
 *   person types their password only on Salli's own sign-in page; the
 *   console has no sign-in form. The state and the verifier wait in the
 *   tab's sessionStorage across the redirect, and come back to
 *   `/console/callback`.
 * - **Where the tokens live.** The access token in memory only; the refresh
 *   token in memory and in the tab's sessionStorage, so a reload keeps the
 *   sign-in and closing the tab ends it. Refreshes run under a Web Lock
 *   (`oauth.createBrowserTokenProvider`).
 * - **One sign-in per tab.** A tab claims its sign-in with a Web Lock held
 *   while it lives (claim.ts); a duplicated tab finds it held, drops its
 *   copy and signs in afresh.
 * - **Step-up.** When Salli answers `/problems/step-up-required`, the
 *   console sends the person through the sign-in page again with
 *   `prompt=login`, keeping their place and the write they asked for. On
 *   return it checks that the same person signed in, swaps to the new grant
 *   (revoking the old one) and retries the write once.
 * - **Signing out** revokes the tab's grant (`/mcp/oauth/revoke` revokes the
 *   whole grant) and clears the tab. Idle sign-out is idle.ts's.
 * - **One origin.** The console moves to SALLI_PUBLIC_URL's origin before
 *   signing in, since the tokens are bound to it, and refuses to start
 *   outside a secure context (HTTPS or localhost), saying why.
 */
import {
  authMe,
  createClient,
  oauth,
  SalliApiError,
  type Meta,
  type OAuthTokenProvider,
  type SalliClient,
  type StoredTokens,
  type TokenProvider,
} from '@leafmonkeylabs/salli-sdk';
import { claimSignIn, type Release } from './claim';

/** sessionStorage keys, all this tab's own. */
export const KEYS = {
  /** `{ id, user_id, email }` of the tab's sign-in. */
  signIn: 'salli-console:sign-in',
  /** The refresh token (the SDK's browser provider writes it). */
  refresh: 'salli-console:refresh',
  /** `{ state, verifier, return_to, step_up, write }` across the redirect. */
  pending: 'salli-console:pending',
  /** The write to retry once after a step-up: `{ name, input }`. */
  retry: 'salli-console:retry',
  /** What to say after a redirect: a step-up that didn't happen. */
  notice: 'salli-console:notice',
} as const;

export type SignOutReason = 'signed-out' | 'idle' | 'ended';

export type Notice = { kind: 'different-person' } | { kind: 'step-up-cancelled' };

export interface SignedInUser {
  user_id: string;
  email: string;
}

export type SessionState =
  | { status: 'starting' }
  | { status: 'redirecting' }
  | { status: 'insecure'; origin: string }
  | { status: 'unreachable'; error: unknown }
  | { status: 'signed-in'; user: SignedInUser }
  | { status: 'signed-out'; reason: SignOutReason }
  | { status: 'callback-error'; kind: 'stale' | 'denied' | 'failed'; error?: unknown };

/** A write waiting on a step-up: its name and its (JSON) input. */
export interface PendingWrite {
  name: string;
  input: unknown;
}

interface Pending {
  state: string;
  verifier: string;
  return_to: string;
  step_up: boolean;
  write?: PendingWrite;
}

interface StoredSignIn {
  id: string;
  user_id: string;
  email: string;
}

/** What the session needs of the page it runs in; tests pass their own. */
export interface SessionEnvironment {
  location: Pick<Location, 'origin' | 'pathname' | 'search' | 'hash' | 'href'>;
  /** Leaves the page for `url` (the sign-in page, or the public origin). */
  assign(url: string): void;
  /** Changes the address without leaving the page (after the callback). */
  replaceUrl(url: string): void;
  storage: Storage;
  isSecureContext: boolean;
  fetch?: typeof globalThis.fetch;
  claim?: (id: string) => Promise<Release | null>;
}

export function browserEnvironment(): SessionEnvironment {
  return {
    location: window.location,
    assign: (url) => window.location.assign(url),
    replaceUrl: (url) => window.history.replaceState(null, '', url),
    storage: window.sessionStorage,
    isSecureContext: window.isSecureContext && typeof crypto?.subtle?.digest === 'function',
  };
}

/** The console's base path, as the server serves it and Vite builds it. */
export const BASE_PATH = '/console';

/** Whether an error is Salli asking for the password again (RFC 9470). */
export function isStepUpRequired(error: unknown): boolean {
  return error instanceof SalliApiError && error.status === 403 && /\/problems\/step-up-required$/.test(error.type);
}

/** Whether an error means the sign-in is no longer accepted. */
export function isSignedOutError(error: unknown): boolean {
  return error instanceof SalliApiError && error.status === 401;
}

function readJson<T>(storage: Storage, key: string): T | undefined {
  try {
    const text = storage.getItem(key);
    return text ? (JSON.parse(text) as T) : undefined;
  } catch {
    return undefined;
  }
}

function writeJson(storage: Storage, key: string, value: unknown): void {
  storage.setItem(key, JSON.stringify(value));
}

function forget(storage: Storage, ...keys: string[]): void {
  for (const key of keys) {
    try {
      storage.removeItem(key);
    } catch {
      // nothing to forget
    }
  }
}

type Listener = (state: SessionState) => void;

export class ConsoleSession {
  readonly env: SessionEnvironment;
  /** The API client every page uses; its token follows the tab's sign-in. */
  readonly client: SalliClient;
  /** What /v1/meta said when the console started. */
  meta: Meta | undefined;
  state: SessionState = { status: 'starting' };
  notice: Notice | undefined;

  private provider: OAuthTokenProvider | undefined;
  private release: Release | undefined;
  private listeners = new Set<Listener>();
  private signInId: string | undefined;

  constructor(env: SessionEnvironment) {
    this.env = env;
    const auth: TokenProvider = {
      getToken: () => this.provider?.getToken(),
      refresh: (failed) => (this.provider ? this.provider.refresh(failed) : Promise.resolve(undefined)),
    };
    this.client = createClient({
      server: env.location.origin,
      auth,
      ...(env.fetch ? { fetch: env.fetch } : {}),
    });
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private set(state: SessionState): void {
    this.state = state;
    for (const listener of this.listeners) listener(state);
  }

  private get oauthInfo(): Meta['oauth'] {
    if (!this.meta) throw new Error('The console has not started');
    return this.meta.oauth;
  }

  /** `{public URL}/console/callback`: the console client's one redirect. */
  get callbackUrl(): string {
    const consoleUrl = this.meta?.console_url ?? `${this.oauthInfo.issuer.replace(/\/+$/, '')}${BASE_PATH}`;
    return `${consoleUrl.replace(/\/+$/, '')}/callback`;
  }

  /** Starts the console: the callback, a kept sign-in, or a new one. */
  async start(): Promise<SessionState> {
    const { env } = this;
    try {
      this.meta = await createClient({
        server: env.location.origin,
        ...(env.fetch ? { fetch: env.fetch } : {}),
      }).meta();
    } catch (error) {
      this.set({ status: 'unreachable', error });
      return this.state;
    }

    // Tokens are bound to SALLI_PUBLIC_URL: sign in only on its origin.
    const publicOrigin = new URL(this.meta.oauth.issuer).origin;
    if (publicOrigin !== env.location.origin) {
      this.set({ status: 'redirecting' });
      env.assign(`${publicOrigin}${env.location.pathname}${env.location.search}${env.location.hash}`);
      return this.state;
    }
    if (!env.isSecureContext) {
      this.set({ status: 'insecure', origin: env.location.origin });
      return this.state;
    }

    this.notice = readJson<Notice>(env.storage, KEYS.notice);
    forget(env.storage, KEYS.notice);

    if (env.location.pathname.replace(/\/+$/, '') === `${BASE_PATH}/callback`) {
      return this.finishSignIn(new URLSearchParams(env.location.search));
    }

    const kept = readJson<StoredSignIn>(env.storage, KEYS.signIn);
    const refreshToken = oauth.storedRefreshToken(env.storage, KEYS.refresh);
    if (kept && refreshToken) {
      if (await this.claim(kept.id)) {
        this.useTokens(kept, { access_token: '', refresh_token: refreshToken });
        this.set({ status: 'signed-in', user: { user_id: kept.user_id, email: kept.email } });
        return this.state;
      }
      // A duplicated tab: another tab holds this sign-in. Drop the copy.
      forget(env.storage, KEYS.signIn, KEYS.refresh, KEYS.retry);
    }
    await this.signIn(this.here());
    return this.state;
  }

  private here(): string {
    const { pathname, search, hash } = this.env.location;
    return `${pathname}${search}${hash}`;
  }

  private async claim(id: string): Promise<boolean> {
    const release = await (this.env.claim ?? claimSignIn)(id);
    if (!release) return false;
    this.release?.();
    this.release = release;
    return true;
  }

  private useTokens(signIn: StoredSignIn, tokens: StoredTokens): void {
    const info = this.oauthInfo;
    this.signInId = signIn.id;
    writeJson(this.env.storage, KEYS.signIn, signIn);
    this.provider = oauth.createBrowserTokenProvider({
      tokens,
      tokenEndpoint: info.token_endpoint,
      clientId: info.console_client_id,
      resource: info.api_resource,
      storage: this.env.storage,
      key: KEYS.refresh,
      lockName: `salli-console:refresh:${signIn.id}`,
      ...(this.env.fetch ? { fetch: this.env.fetch } : {}),
    });
  }

  /**
   * Sends the browser to Salli's sign-in page. With `stepUp`, the page asks
   * for the password again (`prompt=login`), and `write` is retried once on
   * return.
   */
  async signIn(returnTo: string = `${BASE_PATH}/`, options: { stepUp?: boolean; write?: PendingWrite } = {}): Promise<void> {
    const info = this.oauthInfo;
    const pkce = await oauth.createPkcePair();
    const state = oauth.randomToken();
    const pending: Pending = {
      state,
      verifier: pkce.verifier,
      return_to: returnTo.startsWith(`${BASE_PATH}/`) || returnTo === BASE_PATH ? returnTo : `${BASE_PATH}/`,
      step_up: options.stepUp ?? false,
      ...(options.write ? { write: options.write } : {}),
    };
    writeJson(this.env.storage, KEYS.pending, pending);
    this.set({ status: 'redirecting' });
    this.env.assign(
      oauth.buildAuthorizationUrl({
        authorizationEndpoint: info.authorization_endpoint,
        clientId: info.console_client_id,
        redirectUri: this.callbackUrl,
        codeChallenge: pkce.challenge,
        state,
        resource: info.api_resource,
        ...(options.stepUp ? { prompt: 'login' as const } : {}),
      }),
    );
  }

  /** Salli asked for the password again: sign in again, keeping this place and the write. */
  stepUp(write?: PendingWrite): Promise<void> {
    return this.signIn(this.here(), { stepUp: true, ...(write ? { write } : {}) });
  }

  /** The write waiting to be retried after a step-up, if it is `name`'s. Retried once: taking it forgets it. */
  takeRetry(name: string): PendingWrite | undefined {
    const retry = readJson<PendingWrite>(this.env.storage, KEYS.retry);
    if (!retry || retry.name !== name) return undefined;
    forget(this.env.storage, KEYS.retry);
    return retry;
  }

  private async finishSignIn(params: URLSearchParams): Promise<SessionState> {
    const { env } = this;
    const pending = readJson<Pending>(env.storage, KEYS.pending);
    const state = params.get('state');
    if (!pending || !state || state !== pending.state) {
      forget(env.storage, KEYS.pending);
      env.replaceUrl(`${BASE_PATH}/`);
      this.set({ status: 'callback-error', kind: 'stale' });
      return this.state;
    }
    forget(env.storage, KEYS.pending);
    const kept = readJson<StoredSignIn>(env.storage, KEYS.signIn);
    const keptRefresh = oauth.storedRefreshToken(env.storage, KEYS.refresh);
    const code = params.get('code');

    if (!code) {
      // access_denied, or the page was left: a step-up that didn't happen
      // keeps the sign-in it was asked for.
      if (pending.step_up && kept && keptRefresh) return this.resume(kept, keptRefresh, pending.return_to, { kind: 'step-up-cancelled' });
      env.replaceUrl(`${BASE_PATH}/`);
      this.set({ status: 'callback-error', kind: 'denied' });
      return this.state;
    }

    const info = this.oauthInfo;
    let tokens: StoredTokens;
    let me: { user_id: string; email?: string | null };
    try {
      tokens = oauth.tokensFromResponse(
        await oauth.exchangeAuthorizationCode({
          tokenEndpoint: info.token_endpoint,
          clientId: info.console_client_id,
          code,
          redirectUri: this.callbackUrl,
          codeVerifier: pending.verifier,
          resource: info.api_resource,
          ...(env.fetch ? { fetch: env.fetch } : {}),
        }),
      );
      me = await createClient({
        server: env.location.origin,
        auth: tokens.access_token,
        ...(env.fetch ? { fetch: env.fetch } : {}),
      }).call(authMe);
    } catch (error) {
      env.replaceUrl(`${BASE_PATH}/`);
      this.set({ status: 'callback-error', kind: 'failed', error });
      return this.state;
    }

    if (pending.step_up && kept && keptRefresh) {
      if (me.user_id !== kept.user_id) {
        // Someone else typed their password: end what they started, and
        // keep the sign-in that asked.
        await this.revoke(tokens.refresh_token);
        return this.resume(kept, keptRefresh, pending.return_to, { kind: 'different-person' });
      }
      // The same person, just now: swap to the new grant, end the old one.
      await this.revoke(keptRefresh);
      if (pending.write) writeJson(env.storage, KEYS.retry, pending.write);
      return this.begin({ ...kept }, tokens, pending.return_to);
    }

    if (kept && keptRefresh) await this.revoke(keptRefresh);
    const signIn: StoredSignIn = { id: oauth.randomToken(12), user_id: me.user_id, email: me.email ?? '' };
    return this.begin(signIn, tokens, pending.return_to);
  }

  private async begin(signIn: StoredSignIn, tokens: StoredTokens, returnTo: string): Promise<SessionState> {
    this.env.replaceUrl(returnTo);
    await this.claim(signIn.id);
    this.useTokens(signIn, tokens);
    this.set({ status: 'signed-in', user: { user_id: signIn.user_id, email: signIn.email } });
    return this.state;
  }

  private async resume(kept: StoredSignIn, refreshToken: string, returnTo: string, notice: Notice): Promise<SessionState> {
    this.notice = notice;
    return this.begin(kept, { access_token: '', refresh_token: refreshToken }, returnTo);
  }

  private async revoke(token: string | undefined): Promise<void> {
    if (!token || !this.meta) return;
    try {
      await oauth.revokeToken({
        revocationEndpoint: this.meta.oauth.revocation_endpoint,
        token,
        tokenTypeHint: 'refresh_token',
        clientId: this.meta.oauth.console_client_id,
        ...(this.env.fetch ? { fetch: this.env.fetch } : {}),
      });
    } catch {
      // Revoked or not, this tab forgets it.
    }
  }

  /** Ends the tab's sign-in: revokes its grant (unless Salli already ended it) and clears the tab. */
  async signOut(reason: SignOutReason = 'signed-out'): Promise<void> {
    if (this.state.status !== 'signed-in') return;
    const token = this.provider?.tokens.refresh_token ?? oauth.storedRefreshToken(this.env.storage, KEYS.refresh);
    this.provider = undefined;
    forget(this.env.storage, KEYS.signIn, KEYS.refresh, KEYS.retry, KEYS.pending);
    this.release?.();
    this.release = undefined;
    this.signInId = undefined;
    this.set({ status: 'signed-out', reason });
    if (reason !== 'ended') await this.revoke(token);
  }

  /** The sign-in id this tab holds (for its lock), if signed in. */
  get id(): string | undefined {
    return this.signInId;
  }
}
