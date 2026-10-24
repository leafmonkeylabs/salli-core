/**
 * Your AI's settings and what it keeps, all on this phone
 * (docs/design/mobile.md, "Your AI"): the provider and model, each
 * provider's key in the keychain, the AI's own sign-in to the server's MCP
 * (a second sign-in, an AI connection on the server), and the last 20
 * conversations in a file of the app's own. Nothing here reaches a server.
 */
import { oauth } from '@leafmonkeylabs/salli-sdk';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';
import type { ModelMessage } from 'ai';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { keepNewest, providerOf, type ProviderId } from '../lib/ai';
import { conversationsFile } from './files';
import { authorizationUrlOf, base64UrlOf, callbackOf, tokenOf } from '../lib/pkce';
import { storeKeyOf } from '../lib/servers';
import { useSession } from '../session';

const SETTINGS = 'salli.ai';
const keyOf = (provider: ProviderId) => `salli.ai.key.${provider}`;

interface Settings {
  provider?: ProviderId;
  models: Partial<Record<ProviderId, string>>;
}

export interface Conversation {
  id: string;
  title: string;
  /** When it last changed, as an ISO time. */
  at: string;
  messages: ModelMessage[];
}

interface Stored {
  tokens: oauth.StoredTokens;
  since: string;
}

export interface YourAI {
  loaded: boolean;
  provider: ProviderId | undefined;
  model: string | undefined;
  /** The key's last four characters, when one is saved for the provider. */
  keyEnd: string | undefined;
  /** When the AI's sign-in to the server's MCP was made; undefined when not connected. */
  connectedSince: string | undefined;
  /** Provider, key, model and the tools: everything a conversation needs. */
  ready: boolean;
  conversations: readonly Conversation[];
  setProvider(provider: ProviderId): Promise<void>;
  setModel(model: string): Promise<void>;
  setKey(key: string): Promise<void>;
  removeKey(): Promise<void>;
  /** The key itself, for a call to the provider; never shown. */
  key(): Promise<string | undefined>;
  connect(): Promise<'connected' | 'denied' | string>;
  disconnect(): Promise<void>;
  /** A fresh access token for the server's MCP, refreshed when it needs to be. */
  mcpToken(): Promise<string | undefined>;
  mcpUrl: string;
  save(conversation: Conversation): Promise<void>;
  deleteConversations(): Promise<void>;
}

const AIContext = createContext<YourAI | undefined>(undefined);

export function useYourAI(): YourAI {
  const ai = useContext(AIContext);
  if (!ai) throw new Error('useYourAI outside YourAIProvider');
  return ai;
}

async function readJson<T>(key: string): Promise<T | undefined> {
  const text = await SecureStore.getItemAsync(key);
  if (!text) return undefined;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}

export function YourAIProvider({ children }: { children: ReactNode }) {
  const { session } = useSession();
  const server = session.status === 'signed-in' ? session.server : '';
  const signIn = session.status === 'signed-in' ? session.signIn : undefined;
  const mcpUrl = server ? `${server}/mcp` : '';

  const [settings, setSettings] = useState<Settings | undefined>(undefined);
  const [keyEnd, setKeyEnd] = useState<string | undefined>(undefined);
  const [stored, setStored] = useState<Stored | undefined>(undefined);
  const [conversations, setConversations] = useState<readonly Conversation[]>([]);
  const [loaded, setLoaded] = useState(false);

  // What the phone keeps: read on start and for each server put on screen.
  useEffect(() => {
    let live = true;
    void (async () => {
      const next = (await readJson<Settings>(SETTINGS)) ?? { models: {} };
      const key = next.provider ? await SecureStore.getItemAsync(keyOf(next.provider)) : null;
      const tools = server ? await readJson<Stored>(storeKeyOf(server, 'mcp')) : undefined;
      let kept: Conversation[] = [];
      if (server) {
        const file = conversationsFile(server);
        try {
          kept = file.exists ? (JSON.parse(await file.text()) as Conversation[]) : [];
        } catch {
          kept = [];
        }
      }
      if (!live) return;
      setSettings(next);
      setKeyEnd(key ? key.slice(-4) : undefined);
      setStored(tools);
      setConversations(kept);
      setLoaded(true);
    })();
    return () => {
      live = false;
    };
  }, [server]);

  const writeSettings = useCallback(async (next: Settings) => {
    setSettings(next);
    await SecureStore.setItemAsync(SETTINGS, JSON.stringify(next));
  }, []);

  const provider = settings?.provider;
  const model = provider ? (settings?.models[provider] ?? providerOf(provider)?.defaultModel) : undefined;

  const setProvider = useCallback(
    async (next: ProviderId) => {
      await writeSettings({ models: settings?.models ?? {}, provider: next });
      const key = await SecureStore.getItemAsync(keyOf(next));
      setKeyEnd(key ? key.slice(-4) : undefined);
    },
    [settings, writeSettings],
  );
  const setModel = useCallback(
    async (next: string) => {
      if (!provider) return;
      await writeSettings({ ...settings, models: { ...(settings?.models ?? {}), [provider]: next } });
    },
    [provider, settings, writeSettings],
  );
  const setKey = useCallback(
    async (key: string) => {
      if (!provider) return;
      await SecureStore.setItemAsync(keyOf(provider), key.trim());
      setKeyEnd(key.trim().slice(-4));
    },
    [provider],
  );
  const removeKey = useCallback(async () => {
    if (!provider) return;
    await SecureStore.deleteItemAsync(keyOf(provider));
    setKeyEnd(undefined);
  }, [provider]);
  const key = useCallback(async () => (provider ? ((await SecureStore.getItemAsync(keyOf(provider))) ?? undefined) : undefined), [provider]);

  // The AI's own sign-in: the app's client, for the MCP resource, on the server's own page.
  const connect = useCallback(async (): Promise<'connected' | 'denied' | string> => {
    if (!server || !signIn) return 'Not signed in.';
    const verifier = tokenOf(Crypto.getRandomBytes(32));
    const digest = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, verifier, { encoding: Crypto.CryptoEncoding.BASE64 });
    const state = tokenOf(Crypto.getRandomBytes(16));
    const url = authorizationUrlOf({
      authorizationEndpoint: signIn.authorizationEndpoint,
      clientId: signIn.clientId,
      redirectUri: signIn.redirectUri,
      challenge: base64UrlOf(digest),
      state,
      resource: mcpUrl,
    });
    const result = await WebBrowser.openAuthSessionAsync(url, signIn.redirectUri, { preferEphemeralSession: true });
    if (result.type !== 'success') return 'denied';
    const callback = callbackOf(result.url, signIn.redirectUri, state);
    if ('error' in callback) return callback.error === 'access_denied' ? 'denied' : (callback.description ?? 'The server sent back no code.');
    try {
      const response = await oauth.exchangeAuthorizationCode({
        tokenEndpoint: signIn.tokenEndpoint,
        clientId: signIn.clientId,
        code: callback.code,
        redirectUri: signIn.redirectUri,
        codeVerifier: verifier,
        resource: mcpUrl,
      });
      const next: Stored = { tokens: oauth.tokensFromResponse(response), since: new Date().toISOString() };
      await SecureStore.setItemAsync(storeKeyOf(server, 'mcp'), JSON.stringify(next));
      setStored(next);
      return 'connected';
    } catch (error) {
      return error instanceof Error ? error.message : String(error);
    }
  }, [server, signIn, mcpUrl]);

  const disconnect = useCallback(async () => {
    if (!server) return;
    const token = stored?.tokens.refresh_token ?? stored?.tokens.access_token;
    // Ended on the server as well, where it is an AI connection; gone here whatever it answers.
    if (token && signIn) await oauth.revokeToken({ revocationEndpoint: signIn.revocationEndpoint, clientId: signIn.clientId, token }).catch(() => undefined);
    await SecureStore.deleteItemAsync(storeKeyOf(server, 'mcp'));
    setStored(undefined);
  }, [server, signIn, stored]);

  // One token provider while the sign-in lasts: refresh tokens rotate, so one refresh at a time.
  const tokens = useMemo(() => {
    if (!stored || !signIn || !server) return undefined;
    return oauth.createOAuthTokenProvider({
      tokens: stored.tokens,
      tokenEndpoint: signIn.tokenEndpoint,
      clientId: signIn.clientId,
      resource: mcpUrl,
      save: (next) => SecureStore.setItemAsync(storeKeyOf(server, 'mcp'), JSON.stringify({ ...stored, tokens: next })),
    });
  }, [stored, signIn, server, mcpUrl]);
  const mcpToken = useCallback(async () => tokens?.getToken(), [tokens]);

  const save = useCallback(
    async (conversation: Conversation) => {
      if (!server) return;
      const next = keepNewest(conversations, conversation);
      setConversations(next);
      conversationsFile(server).write(JSON.stringify(next));
    },
    [server, conversations],
  );
  const deleteConversations = useCallback(async () => {
    if (!server) return;
    setConversations([]);
    const file = conversationsFile(server);
    if (file.exists) file.delete();
  }, [server]);

  const value = useMemo<YourAI>(
    () => ({
      loaded,
      provider,
      model,
      keyEnd,
      connectedSince: stored?.since,
      ready: Boolean(provider && model && keyEnd && stored),
      conversations,
      setProvider,
      setModel,
      setKey,
      removeKey,
      key,
      connect,
      disconnect,
      mcpToken,
      mcpUrl,
      save,
      deleteConversations,
    }),
    [loaded, provider, model, keyEnd, stored, conversations, setProvider, setModel, setKey, removeKey, key, connect, disconnect, mcpToken, mcpUrl, save, deleteConversations],
  );
  return <AIContext.Provider value={value}>{children}</AIContext.Provider>;
}

