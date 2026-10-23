/**
 * The app's sign-in to one server (docs/design/mobile.md, "Signing in"):
 * the authorization code with PKCE on the server's own page, in the phone's
 * secure browser sheet, back to `money.salli.app:/oauth/callback`. Tokens
 * live in the keychain (iOS) or the keystore (Android), never anywhere else.
 */
import { createClient, oauth, SalliApiError, type SalliClient } from '@leafmonkeylabs/salli-sdk';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { authorizationUrlOf, base64UrlOf, callbackOf, tokenOf } from './lib/pkce';
import { checkServer, type AppSignIn, type ServerCheck } from './lib/server';

const STORE_KEY = 'salli.sign-in';
const USER_AGENT = 'Salli app';

interface Stored {
  server: string;
  signIn: AppSignIn;
  tokens: oauth.StoredTokens;
  consoleUrl: string | null;
}

export type SignInResult = { ok: true } | { ok: false; reason: 'denied' } | { ok: false; reason: 'failed'; detail: string };

export type Session =
  | { status: 'loading' }
  | { status: 'signed-out'; ended: boolean }
  | { status: 'signed-in'; server: string; client: SalliClient; consoleUrl: string | null };

interface SessionApi {
  session: Session;
  signIn(server: string, signIn: AppSignIn, consoleUrl: string | null): Promise<SignInResult>;
  signOut(): Promise<void>;
  /** The server ended the sign-in (a 401 the token provider couldn't refresh past). */
  ended(): void;
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

async function load(): Promise<Stored | undefined> {
  const text = await SecureStore.getItemAsync(STORE_KEY);
  if (!text) return undefined;
  try {
    return JSON.parse(text) as Stored;
  } catch {
    await SecureStore.deleteItemAsync(STORE_KEY);
    return undefined;
  }
}

async function save(stored: Stored): Promise<void> {
  await SecureStore.setItemAsync(STORE_KEY, JSON.stringify(stored), {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

function clientFor(stored: Stored, onTokens: (tokens: oauth.StoredTokens) => void): SalliClient {
  const tokens = oauth.createOAuthTokenProvider({
    tokens: stored.tokens,
    tokenEndpoint: stored.signIn.tokenEndpoint,
    clientId: stored.signIn.clientId,
    resource: stored.signIn.resource,
    save: onTokens,
  });
  return createClient({ server: stored.server, auth: tokens, userAgent: USER_AGENT });
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>({ status: 'loading' });
  const stored = useRef<Stored | undefined>(undefined);

  const open = useCallback((next: Stored) => {
    stored.current = next;
    const client = clientFor(next, (tokens) => {
      // A refresh rotates the refresh token: keep the new one, or the next
      // launch presents a used one and the server ends the whole sign-in.
      if (!stored.current) return;
      stored.current = { ...stored.current, tokens };
      void save(stored.current);
    });
    setSession({ status: 'signed-in', server: next.server, client, consoleUrl: next.consoleUrl });
  }, []);

  useEffect(() => {
    void load().then((found) => (found ? open(found) : setSession({ status: 'signed-out', ended: false })));
  }, [open]);

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
        const next: Stored = { server, signIn, tokens: oauth.tokensFromResponse(response), consoleUrl };
        await save(next);
        open(next);
        return { ok: true };
      } catch (error) {
        return { ok: false, reason: 'failed', detail: error instanceof Error ? error.message : String(error) };
      }
    },
    [open],
  );

  const forget = useCallback(async (ended: boolean) => {
    stored.current = undefined;
    await SecureStore.deleteItemAsync(STORE_KEY);
    setSession({ status: 'signed-out', ended });
  }, []);

  const signOut = useCallback(async () => {
    const current = stored.current;
    if (current?.tokens.refresh_token) {
      // Revoking the refresh token revokes the whole grant, on the server.
      await oauth
        .revokeToken({
          revocationEndpoint: current.signIn.revocationEndpoint,
          token: current.tokens.refresh_token,
          tokenTypeHint: 'refresh_token',
          clientId: current.signIn.clientId,
        })
        .catch(() => undefined);
    }
    await forget(false);
  }, [forget]);

  const ended = useCallback(() => void forget(true), [forget]);

  const value = useMemo(() => ({ session, signIn, signOut, ended }), [session, signIn, signOut, ended]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** Whether an error means the sign-in is over: a 401 after the one refresh. */
export function isSignedOutError(error: unknown): boolean {
  return error instanceof SalliApiError && error.status === 401;
}
