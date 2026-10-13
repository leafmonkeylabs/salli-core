/**
 * Which tab holds a sign-in.
 *
 * Each tab is its own sign-in (decision 4). A tab opened with "duplicate"
 * inherits a copy of the original's sessionStorage, refresh token and all;
 * if both kept it, both would rotate one refresh token, and Salli revokes a
 * grant whose refresh token is used twice. So a tab claims its sign-in by
 * holding a Web Lock named for it for as long as the page lives: a copy
 * finds the lock held by the original and drops its copy.
 *
 * A reload releases the old page's lock as the page goes, so a reload waits
 * briefly for it rather than giving up at once.
 */

export type Release = () => void;

interface LockOptions {
  signal?: AbortSignal;
}

interface Locks {
  request(name: string, options: LockOptions, callback: () => Promise<void>): Promise<void>;
}

function browserLocks(): Locks | undefined {
  const locks = (globalThis.navigator as { locks?: Locks } | undefined)?.locks;
  return locks && typeof locks.request === 'function' ? locks : undefined;
}

/**
 * Claims sign-in `id` for this page, waiting up to `waitMs` for another
 * page (one being reloaded away) to let go. Resolves a release function, or
 * null when another open tab holds it. Without Web Locks every claim
 * succeeds: such a browser can't tell a copied tab from a reloaded one.
 */
export function claimSignIn(id: string, waitMs = 1500, locks: Locks | undefined = browserLocks()): Promise<Release | null> {
  if (!locks) return Promise.resolve(() => undefined);
  return new Promise((resolve) => {
    let release: Release = () => undefined;
    const held = new Promise<void>((done) => {
      release = done;
    });
    locks
      .request(`salli-console:sign-in:${id}`, { signal: AbortSignal.timeout(waitMs) }, () => {
        resolve(release);
        return held;
      })
      .catch(() => resolve(null));
  });
}
