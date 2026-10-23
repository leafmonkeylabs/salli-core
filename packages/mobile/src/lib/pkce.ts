/**
 * PKCE (RFC 7636) and the sign-in's redirect, in plain TypeScript. The SDK's
 * own PKCE needs `crypto.subtle`, which React Native doesn't have, so the app
 * hashes with expo-crypto and hands this module the bytes.
 */

/** Base64 (as expo-crypto writes a digest) to base64url without padding. */
export function base64UrlOf(base64: string): string {
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Random bytes as a base64url string: a verifier or a state. */
export function tokenOf(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return base64UrlOf(btoa(binary));
}

/** What the sign-in page sent back to the app's redirect. */
export type Callback = { code: string } | { error: 'access_denied' | 'state' | 'invalid'; description?: string };

/**
 * Reads `money.salli.app:/oauth/callback?code=…&state=…`. A state that isn't
 * the one sent means the answer is for another sign-in: it is refused.
 */
export function callbackOf(url: string, redirectUri: string, state: string): Callback {
  if (!url.startsWith(`${redirectUri}?`)) return { error: 'invalid' };
  const query = new URLSearchParams(url.slice(redirectUri.length + 1));
  if (query.get('state') !== state) return { error: 'state' };
  const error = query.get('error');
  if (error === 'access_denied') return { error: 'access_denied' };
  if (error) {
    const description = query.get('error_description');
    return description ? { error: 'invalid', description } : { error: 'invalid' };
  }
  const code = query.get('code');
  return code ? { code } : { error: 'invalid' };
}

/** The authorization URL, built without `URL` setters (React Native's are partial). */
export function authorizationUrlOf(params: {
  authorizationEndpoint: string;
  clientId: string;
  redirectUri: string;
  challenge: string;
  state: string;
  resource: string;
  prompt?: 'login';
}): string {
  const query = new URLSearchParams({
    response_type: 'code',
    client_id: params.clientId,
    redirect_uri: params.redirectUri,
    code_challenge: params.challenge,
    code_challenge_method: 'S256',
    state: params.state,
    resource: params.resource,
    ...(params.prompt ? { prompt: params.prompt } : {}),
  });
  const joiner = params.authorizationEndpoint.includes('?') ? '&' : '?';
  return `${params.authorizationEndpoint}${joiner}${query.toString()}`;
}
