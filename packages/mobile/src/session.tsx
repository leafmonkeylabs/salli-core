/**
 * The app's sign-ins (docs/design/mobile.md, "Signing in"): the
 * authorization code with PKCE on each server's own page, in the phone's
 * secure browser sheet, back to `money.salli.app:/oauth/callback`. Tokens
 * live in the keychain (iOS) or the keystore (Android), one item a server,
 * never anywhere else; the index of servers beside them holds no secret.
 */
import { authMe, createClient, oauth, profileGet, SalliApiError, type SalliClient } from '@leafmonkeylabs/salli-sdk';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { authorizationUrlOf, base64UrlOf, callbackOf, tokenOf } from './lib/pkce';
import { checkServer, type AppSignIn, type ServerCheck } from './lib/server';
import { forgotten, listOf, remembered, storeKeyOf, withoutServer, withServer, type ServerIndex } from './lib/servers';

const INDEX_KEY = 'salli.servers';
/** The one sign-in an earlier version kept: moved into the index on launch. */
const LEGACY_KEY = 'salli.sign-in';
const KEYCHAIN = { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY };
const USER_AGENT = 'Salli app';
const READ_TIMEOUT_MS = 12_000;

interface Stored {
  server: string;
  signIn: AppSignIn;
  tokens: oauth.StoredTokens;
  consoleUrl: string | null;
}

export type SignInResult = { ok: true } | { ok: false; reason: 'denied' } | { ok: false; reason: 'failed'; detail: string };

/** A server this phone remembers: signed in to or not, and who you are on it. */
export interface Known {
  server: string;
  signedIn: boolean;
  email?: string;
  currency?: string;
}

export type Session =
  | { status: 'loading' }
  | { status: 'signed-out'; ended: boolean; endedOn?: string; known: readonly Known[] }
  | {
      status: 'signed-in';
      server: string;
      client: SalliClient;
      consoleUrl: string | null;
      /** Every server this phone is signed in to, the one on screen among them. */
      servers: readonly string[];
      /** A server whose sign-in ended, if one did since the last change: said once on Home. */
      endedOn?: string;
      /** Every server remembered, signed in to or not. */
      known: readonly Known[];
    };

interface SessionApi {
  session: Session;
  /** Signs in to a server and puts it on screen; the others stay signed in. */
  signIn(server: string, signIn: AppSignIn, consoleUrl: string | null): Promise<SignInResult>;
  /** Puts another signed-in server on screen. */
  switchTo(server: string): Promise<void>;
  /** Signs out of the server on screen, on the server too; the next one left comes on screen. */
  signOut(): Promise<void>;
  /** `server` ended its sign-in (a 401 the token provider couldn't refresh past). */
  ended(server: string): void;
  /** Forgets a server signed out of: nothing of it stays on the phone. */
  forgetServer(server: string): Promise<void>;
}

const SessionContext = createContext<SessionApi | null>(null);

export function useSession(): SessionApi {
  const api = useContext(SessionContext);
  if (!api) throw new Error('useSession outside SessionProvider');
  return api;
}

/** What `/v1/meta` says about signing in to `server` from the app. */
export async function findServer(server: string): Promise<ServerCheck | { ok: false; problem: 'unreachable' }> {
  let answer: unknown;
  try {
    const response = await fetch(`${server}/v1/meta`, {
      headers: { Accept: 'application/json', 'User-Agent': USER_AGENT },
      signal: AbortSignal.timeout(15_000),
    });
    answer = response.ok ? await response.json().catch(() => undefined) : undefined;
  } catch {
    return { ok: false, problem: 'unreachable' };
  }
  return checkServer(server, answer);
}

async function read<T>(key: string): Promise<T | undefined> {
  const text = await SecureStore.getItemAsync(key);
  if (!text) return undefined;
  try {
    return JSON.parse(text) as T;
  } catch {
    await SecureStore.deleteItemAsync(key);
    return undefined;
  }
}

async function write(key: string, value: unknown): Promise<void> {
  await SecureStore.setItemAsync(key, JSON.stringify(value), KEYCHAIN);
}

const loadSignIn = (server: string): Promise<Stored | undefined> => read<Stored>(storeKeyOf(server));
const saveSignIn = (stored: Stored): Promise<void> => write(storeKeyOf(stored.server), stored);

/** The index, after moving an earlier version's one sign-in into it. */
async function loadIndex(): Promise<ServerIndex | undefined> {
  const index = await read<ServerIndex>(INDEX_KEY);
  if (index) return index;
  const legacy = await read<Stored>(LEGACY_KEY);
  if (!legacy) return undefined;
  const moved = withServer(undefined, legacy.server);
  await saveSignIn(legacy);
  await write(INDEX_KEY, moved);
  await SecureStore.deleteItemAsync(LEGACY_KEY);
  return moved;
}

function clientFor(stored: Stored, onTokens: (tokens: oauth.StoredTokens) => void): SalliClient {
  const tokens = oauth.createOAuthTokenProvider({
    tokens: stored.tokens,
    tokenEndpoint: stored.signIn.tokenEndpoint,
    clientId: stored.signIn.clientId,
    resource: stored.signIn.resource,
    save: onTokens,
  });
  // A phone away from its server should say so in seconds, not half a minute:
  // a read gives up after READ_TIMEOUT_MS (an upload sets its own).
  return createClient({ server: stored.server, auth: tokens, userAgent: USER_AGENT, timeoutMs: READ_TIMEOUT_MS });
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ status: 'loading' });
  const index = useRef<ServerIndex | undefined>(undefined);
  const current = useRef<Stored | undefined>(undefined);

  const open = useCallback((next: Stored, endedOn?: string): SalliClient => {
    current.current = next;
    const client = clientFor(next, (tokens) => {
      // A refresh rotates the refresh token: keep the new one, or the next
      // launch presents a used one and the server ends the whole sign-in.
      // Kept for this server only, and only while the phone is signed in to it.
      if (!index.current?.servers.includes(next.server)) return;
      if (current.current?.server === next.server) current.current = { ...current.current, tokens };
      void saveSignIn({ ...next, tokens });
    });
    setSession({
      status: 'signed-in',
      server: next.server,
      client,
      consoleUrl: next.consoleUrl,
      servers: index.current?.servers ?? [next.server],
      ...(endedOn ? { endedOn } : {}),
      known: listOf(index.current),
    });
    return client;
  }, []);

  /**
   * Who you are on a server, kept beside its sign-in for the servers list:
   * your email and its currency, nothing else. Read once a sign-in opens;
   * a failed read leaves what was kept.
   */
  // Through the session's own client: a second one would drop a rotated refresh token.
  const identify = useCallback(async (server: string, client: SalliClient) => {
    const [me, profile] = await Promise.all([client.call(authMe).catch(() => undefined), client.call(profileGet).catch(() => undefined)]);
    const known = index.current;
    if (!known || !(me || profile)) return;
    const next = remembered(known, server, { ...(me?.email ? { email: me.email } : {}), ...(profile?.base_currency ? { currency: profile.base_currency } : {}) });
    index.current = next;
    await write(INDEX_KEY, next);
    setSession((now) => (now.status === 'signed-in' ? { ...now, known: listOf(next) } : now));
  }, []);

  /** Puts `next` (the index's current server) on screen, or signs out when there is none. */
  const show = useCallback(
    async (next: ServerIndex | undefined, endedOn?: string): Promise<void> => {
      index.current = next;
      if (!next || !next.servers.length) {
        current.current = undefined;
        // Servers signed out of stay listed, to sign in to again; with none, nothing is kept.
        if (next && listOf(next).length) await write(INDEX_KEY, next);
        else await SecureStore.deleteItemAsync(INDEX_KEY);
        setSession({ status: 'signed-out', ended: endedOn !== undefined, ...(endedOn ? { endedOn } : {}), known: listOf(next) });
        return;
      }
      await write(INDEX_KEY, next);
      const stored = await loadSignIn(next.current);
      // An index naming a sign-in the keychain no longer has: drop it and go on.
      if (!stored) return show(withoutServer(next, next.current), endedOn);
      void identify(stored.server, open(stored, endedOn));
    },
    [open, identify],
  );

  useEffect(() => {
    void loadIndex().then((found) => show(found));
  }, [show]);

  const signIn = useCallback(
    async (server: string, signIn: AppSignIn, consoleUrl: string | null): Promise<SignInResult> => {
      const verifier = tokenOf(Crypto.getRandomBytes(32));
      const digest = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, verifier, {
        encoding: Crypto.CryptoEncoding.BASE64,
      });
      const state = tokenOf(Crypto.getRandomBytes(16));
      const url = authorizationUrlOf({
        authorizationEndpoint: signIn.authorizationEndpoint,
        clientId: signIn.clientId,
        redirectUri: signIn.redirectUri,
        challenge: base64UrlOf(digest),
        state,
        resource: signIn.resource,
      });
      // Ephemeral: the sheet shares no cookies with the phone's browser, and
      // Salli's sign-in page uses none anyway.
      const result = await WebBrowser.openAuthSessionAsync(url, signIn.redirectUri, { preferEphemeralSession: true });
      if (result.type !== 'success') return { ok: false, reason: 'denied' };
      const callback = callbackOf(result.url, signIn.redirectUri, state);
      if ('error' in callback) {
        if (callback.error === 'access_denied') return { ok: false, reason: 'denied' };
        return { ok: false, reason: 'failed', detail: callback.description ?? 'The server sent back no code.' };
      }
      try {
        const response = await oauth.exchangeAuthorizationCode({
          tokenEndpoint: signIn.tokenEndpoint,
          clientId: signIn.clientId,
          code: callback.code,
          redirectUri: signIn.redirectUri,
          codeVerifier: verifier,
          resource: signIn.resource,
        });
        await saveSignIn({ server, signIn, tokens: oauth.tokensFromResponse(response), consoleUrl });
        await show(withServer(index.current, server));
        return { ok: true };
      } catch (error) {
        return { ok: false, reason: 'failed', detail: error instanceof Error ? error.message : String(error) };
      }
    },
    [show],
  );

  const switchTo = useCallback(
    async (server: string) => {
      if (!index.current?.servers.includes(server) || current.current?.server === server) return;
      await show({ ...index.current, current: server });
    },
    [show],
  );

  /** Signs this phone out of `server`: its tokens go, its address and who you are on it stay listed. */
  const forget = useCallback(
    async (server: string, endedOn?: string) => {
      if (!index.current?.servers.includes(server)) return;
      await SecureStore.deleteItemAsync(storeKeyOf(server));
      await show(withoutServer(index.current, server), endedOn);
    },
    [show],
  );

  const forgetServer = useCallback(
    async (server: string) => {
      if (!index.current || index.current.servers.includes(server)) return;
      const next = forgotten(index.current, server);
      index.current = next;
      // Its automation rules go with it: they name its accounts.
      await SecureStore.deleteItemAsync(storeKeyOf(server, 'automations'));
      await SecureStore.deleteItemAsync(storeKeyOf(server, 'unread'));
      if (listOf(next).length) await write(INDEX_KEY, next);
      else await SecureStore.deleteItemAsync(INDEX_KEY);
      setSession((now) => (now.status === 'loading' ? now : { ...now, known: listOf(next) }));
    },
    [],
  );

  const signOut = useCallback(async () => {
    const stored = current.current;
    if (!stored) return;
    if (stored.tokens.refresh_token) {
      // Revoking the refresh token revokes the whole grant, on the server.
      await oauth
        .revokeToken({
          revocationEndpoint: stored.signIn.revocationEndpoint,
          token: stored.tokens.refresh_token,
          tokenTypeHint: 'refresh_token',
          clientId: stored.signIn.clientId,
        })
        .catch(() => undefined);
    }
    await forget(stored.server);
  }, [forget]);

  const ended = useCallback((server: string) => void forget(server, server), [forget]);

  const value = useMemo(() => ({ session, signIn, switchTo, signOut, ended, forgetServer }), [session, signIn, switchTo, signOut, ended, forgetServer]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** Whether an error means the sign-in is over: a 401 after the one refresh. */
export function isSignedOutError(error: unknown): boolean {
  return error instanceof SalliApiError && error.status === 401;
}
