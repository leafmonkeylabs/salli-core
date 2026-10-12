/**
 * One refresh at a time, across processes.
 *
 * Salli revokes a whole sign-in when a refresh token is used twice
 * (docs/design/console.md, decision 5). Two `salli` commands that find their
 * access token expiring together (an agent running several at once, say)
 * would each refresh with the same refresh token, and the second would sign
 * both out. So a refresh holds a lock file beside the config while it reloads
 * the stored tokens, refreshes and saves: the second process then reloads the
 * first one's new tokens instead of refreshing again.
 *
 * The lock is a directory (`mkdir` is atomic everywhere). One left behind by
 * a process that died is taken over once it is older than any refresh takes.
 */
import { mkdir, rmdir, stat } from 'node:fs/promises';
import { join } from 'node:path';

/** Longer than any refresh: a lock this old was left by a process that died. */
const STALE_MS = 30_000;
/** How long to wait for another process's refresh before going ahead. */
const WAIT_MS = 15_000;
const POLL_MS = 50;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** The lock for a context's tokens, in `dir`. */
export function refreshLockPath(dir: string, context: string): string {
  return join(dir, `refresh-${encodeURIComponent(context)}.lock`);
}

async function acquire(path: string, now: () => number): Promise<boolean> {
  const deadline = now() + WAIT_MS;
  for (;;) {
    try {
      await mkdir(path);
      return true;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'EEXIST') return false;
    }
    try {
      const held = await stat(path);
      if (now() - held.mtimeMs > STALE_MS) {
        await rmdir(path).catch(() => undefined);
        continue;
      }
    } catch {
      continue; // released between our mkdir and stat
    }
    if (now() > deadline) return false;
    await sleep(POLL_MS);
  }
}

/**
 * Runs `refresh` holding the lock at `path`. If the lock can't be had (the
 * directory can't be written, or another refresh outlasts the wait), it runs
 * anyway: a sign-in that may need signing in again beats one that hangs.
 */
export async function withRefreshLock<T>(path: string, refresh: () => Promise<T>, now: () => number = Date.now): Promise<T> {
  const held = await acquire(path, now);
  try {
    return await refresh();
  } finally {
    if (held) await rmdir(path).catch(() => undefined);
  }
}
