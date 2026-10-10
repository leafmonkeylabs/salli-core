/**
 * What is stored per context: OAuth tokens (and how to refresh and revoke
 * them), or a personal access token. Always bound to the server it was
 * issued by, so a token is never sent anywhere else.
 */
import type { AuthIdentity, StoredTokens } from '@leafmonkeylabs/salli-sdk';

export interface OAuthCredentials {
  kind: 'oauth';
  /** The server the tokens were issued for (normalised base URL). */
  server: string;
  client_id: string;
  token_endpoint: string;
  revocation_endpoint?: string;
  /** RFC 8707 resource the tokens are for: the server's `api_resource`. */
  resource?: string;
  /** How the user signed in. */
  method: 'browser' | 'device';
  tokens: StoredTokens;
  signed_in_at: string;
}

export interface TokenCredentials {
  kind: 'token';
  server: string;
  token: string;
  signed_in_at: string;
}

export type StoredCredentials = OAuthCredentials | TokenCredentials;

export function parseCredentials(secret: string | undefined): StoredCredentials | undefined {
  if (!secret) return undefined;
  let value: unknown;
  try {
    value = JSON.parse(secret);
  } catch {
    return undefined;
  }
  if (typeof value !== 'object' || value === null) return undefined;
  const v = value as Partial<StoredCredentials>;
  if (v.kind === 'token' && typeof v.server === 'string' && typeof (v as TokenCredentials).token === 'string') {
    return v as TokenCredentials;
  }
  if (
    v.kind === 'oauth' &&
    typeof v.server === 'string' &&
    typeof (v as OAuthCredentials).client_id === 'string' &&
    typeof (v as OAuthCredentials).token_endpoint === 'string' &&
    typeof (v as OAuthCredentials).tokens?.access_token === 'string'
  ) {
    return v as OAuthCredentials;
  }
  return undefined;
}

export function serializeCredentials(credentials: StoredCredentials): string {
  return JSON.stringify(credentials);
}

/** Who `/v1/auth/me` says you are: your email (when the server knows it) and your user id. */
export function identityOf(me: AuthIdentity): { email: string | undefined; userId: string } {
  return { email: me.email || undefined, userId: me.user_id };
}
