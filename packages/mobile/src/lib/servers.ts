/**
 * The servers on this phone, and when it asks to be unlocked: what the
 * session keeps, as pure functions of it.
 */

/** Which servers this phone is signed in to, and the one on screen. */
export interface ServerIndex {
  current: string;
  servers: readonly string[];
}

/**
 * The keychain key for a server's sign-in. A key takes letters, digits and
 * `.-_` only, so every other character (and `-` itself) is written as `-`
 * and its code in hex: two servers never share a key.
 */
export function storeKeyOf(server: string): string {
  const escaped = Array.from(server, (c) => (/[A-Za-z0-9._]/.test(c) ? c : `-${c.codePointAt(0)?.toString(16) ?? ''}`)).join('');
  return `salli.sign-in.${escaped}`;
}

/** The index with `server` signed in to and on screen; signing in again keeps its place. */
export function withServer(index: ServerIndex | undefined, server: string): ServerIndex {
  const servers = index?.servers ?? [];
  return { current: server, servers: servers.includes(server) ? servers : [...servers, server] };
}

/** The index without `server`: the one on screen moves to the first left, or there is none. */
export function withoutServer(index: ServerIndex, server: string): ServerIndex | undefined {
  const servers = index.servers.filter((s) => s !== server);
  const first = servers[0];
  if (first === undefined) return undefined;
  return { current: index.current === server ? first : index.current, servers };
}

/** How long the app may be away before it asks to be unlocked again. */
export const LOCK_AFTER_MS = 60_000;

/** Whether coming back after `awayMs` in the background asks to be unlocked. */
export function lockDue(lock: boolean, awayMs: number): boolean {
  return lock && awayMs >= LOCK_AFTER_MS;
}
