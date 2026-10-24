/**
 * The servers on this phone, and when it asks to be unlocked: what the
 * session keeps, as pure functions of it.
 */

/** Who you are on a server, kept beside its sign-in: no token and no figure. */
export interface KnownServer {
  email?: string;
  currency?: string;
}

/**
 * The servers on this phone: those signed in to, the one on screen ('' with
 * none), and every server it remembers, signed in or not, so one whose
 * sign-in ended stays listed to sign in again.
 */
export interface ServerIndex {
  current: string;
  servers: readonly string[];
  known?: Readonly<Record<string, KnownServer>>;
}

/**
 * The keychain key for a server's sign-in, its automation rules, the
 * messages they couldn't read, or its AI's sign-in to MCP. A key takes letters, digits and
 * `.-_` only, so every other character (and `-` itself) is written as `-`
 * and its code in hex: two servers never share a key.
 */
export function storeKeyOf(server: string, what: 'sign-in' | 'automations' | 'unread' | 'mcp' = 'sign-in'): string {
  const escaped = Array.from(server, (c) => (/[A-Za-z0-9._]/.test(c) ? c : `-${c.codePointAt(0)?.toString(16) ?? ''}`)).join('');
  return `salli.${what}.${escaped}`;
}

/** The index with `server` signed in to and on screen; signing in again keeps its place. */
export function withServer(index: ServerIndex | undefined, server: string): ServerIndex {
  const servers = index?.servers ?? [];
  return {
    current: server,
    servers: servers.includes(server) ? servers : [...servers, server],
    known: { ...(index?.known ?? {}), [server]: index?.known?.[server] ?? {} },
  };
}

/** The index with `server` signed out of: still remembered, the one on screen moved to the first left ('' with none). */
export function withoutServer(index: ServerIndex, server: string): ServerIndex {
  const servers = index.servers.filter((s) => s !== server);
  return { current: index.current === server ? (servers[0] ?? '') : index.current, servers, known: { ...(index.known ?? {}), [server]: index.known?.[server] ?? {} } };
}

/** The index with `server` forgotten: neither signed in to nor remembered. */
export function forgotten(index: ServerIndex, server: string): ServerIndex {
  const known = { ...(index.known ?? {}) };
  delete known[server];
  const servers = index.servers.filter((s) => s !== server);
  return { current: index.current === server ? (servers[0] ?? '') : index.current, servers, known };
}

/** The index with who you are on `server`, as it said. */
export function remembered(index: ServerIndex, server: string, who: KnownServer): ServerIndex {
  return { ...index, known: { ...(index.known ?? {}), [server]: { ...(index.known?.[server] ?? {}), ...who } } };
}

/** Every remembered server, those signed in to first in their order, then the rest. */
export function listOf(index: ServerIndex | undefined): { server: string; signedIn: boolean; email?: string; currency?: string }[] {
  if (!index) return [];
  const known = index.known ?? {};
  const signedOut = Object.keys(known).filter((s) => !index.servers.includes(s));
  return [...index.servers.map((server) => ({ server, signedIn: true })), ...signedOut.map((server) => ({ server, signedIn: false }))].map((row) => ({
    ...row,
    ...(known[row.server] ?? {}),
  }));
}

/** How long the app may be away before it asks to be unlocked again. */
export const LOCK_AFTER_MS = 60_000;

/** Whether coming back after `awayMs` in the background asks to be unlocked. */
export function lockDue(lock: boolean, awayMs: number): boolean {
  return lock && awayMs >= LOCK_AFTER_MS;
}
