/**
 * A server, as the app finds it: the address a person types, and what the
 * server's `/v1/meta` says about signing in to it from a phone.
 */
import { normalizeServerUrl, SUPPORTED_API_VERSIONS, type Meta } from '@leafmonkeylabs/salli-sdk';

/**
 * The server URL for a typed address: `https://` added to a bare host
 * (`http://` for this machine, where a local server has no certificate),
 * and `/console` dropped (people copy the console's address). Undefined when
 * it isn't an address at all.
 */
export function serverUrlOf(typed: string): string | undefined {
  let text = typed.trim();
  if (!text) return undefined;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) {
    text = `https://${text}`;
    try {
      if (isThisMachine(text)) text = text.replace(/^https:/, 'http:');
    } catch {
      return undefined;
    }
  }
  try {
    return normalizeServerUrl(text).replace(/\/console$/, '');
  } catch {
    return undefined;
  }
}

/**
 * An invitation link, as `salli-server members invite` makes it
 * (`https://<host>/join?t=<token>`): the link to open and the server it is
 * on, which the app then signs in to like any other. Undefined when it isn't
 * one.
 */
export function invitationOf(typed: string): { link: string; server: string } | undefined {
  const text = typed.trim();
  const schemed = /^[a-z][a-z0-9+.-]*:\/\//i.test(text);
  let url: URL;
  try {
    url = new URL(schemed ? text : `https://${text}`);
  } catch {
    return undefined;
  }
  const at = url.pathname.replace(/\/+$/, '');
  if (!at.endsWith('/join') || !url.searchParams.get('t')) return undefined;
  // Without a scheme, as typed: serverUrlOf picks https, or http for this machine.
  const server = serverUrlOf(`${schemed ? `${url.protocol}//` : ''}${url.host}${at.slice(0, -'/join'.length)}`);
  if (server && !schemed) url.protocol = new URL(server).protocol;
  return server ? { link: url.toString(), server } : undefined;
}

/** Whether a URL is this machine, where plain HTTP is allowed (a simulator). */
export function isThisMachine(url: string): boolean {
  const host = new URL(url).hostname.toLowerCase().replace(/^\[|\]$/g, '');
  return host === 'localhost' || host.endsWith('.localhost') || host === '::1' || /^127\./.test(host);
}

/** What stops the app signing in to a server, if anything. */
export type ServerProblem =
  /** It answered, but not as a Salli server does. */
  | 'not-salli'
  /** Its API is a version the app doesn't speak. */
  | 'version'
  /** It is older than the app's sign-in (no `mobile_client_id`). */
  | 'no-app-sign-in'
  /** Plain HTTP on another machine: a password would cross unencrypted. */
  | 'insecure';

/** The app's sign-in, as a server advertises it. */
export interface AppSignIn {
  authorizationEndpoint: string;
  tokenEndpoint: string;
  revocationEndpoint: string;
  clientId: string;
  redirectUri: string;
  resource: string;
}

export type ServerCheck = { ok: true; meta: Meta; signIn: AppSignIn } | { ok: false; problem: ServerProblem };

/** Reads a server's `/v1/meta` answer: whether, and how, the app signs in. */
export function checkServer(url: string, meta: unknown): ServerCheck {
  if (!isMeta(meta)) return { ok: false, problem: 'not-salli' };
  if (!SUPPORTED_API_VERSIONS.includes(meta.api_version)) return { ok: false, problem: 'version' };
  const oauth = meta.oauth as Meta['oauth'] & Partial<Record<'mobile_client_id' | 'mobile_redirect_uri', string>>;
  if (!oauth.mobile_client_id || !oauth.mobile_redirect_uri) return { ok: false, problem: 'no-app-sign-in' };
  if (new URL(url).protocol !== 'https:' && !isThisMachine(url)) return { ok: false, problem: 'insecure' };
  return {
    ok: true,
    meta,
    signIn: {
      authorizationEndpoint: oauth.authorization_endpoint,
      tokenEndpoint: oauth.token_endpoint,
      revocationEndpoint: oauth.revocation_endpoint,
      clientId: oauth.mobile_client_id,
      redirectUri: oauth.mobile_redirect_uri,
      resource: oauth.api_resource,
    },
  };
}

function isMeta(value: unknown): value is Meta {
  if (typeof value !== 'object' || value === null) return false;
  const meta = value as Partial<Meta>;
  return typeof meta.api_version === 'string' && typeof meta.oauth === 'object' && meta.oauth !== null;
}
