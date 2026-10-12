/**
 * Whether Salli was updated under an open tab (decision 24): the tab reads
 * `/v1/meta.server_version` when it regains focus and on each navigation,
 * and when it differs from the version the tab started with, says "Salli
 * was updated. Reload to continue." A page chunk that fails to load after an
 * upgrade says the same (the router's error view), never a blank page.
 */
import { useRouter } from '@tanstack/react-router';
import { useEffect, useState } from 'react';
import { useSession } from '../api';

/** At most one check this often. */
const EVERY_MS = 30_000;

let updated = false;
const listeners = new Set<() => void>();

/** Says the console is out of date (a chunk failed to load, or the version moved). */
export function markUpdated(): void {
  if (updated) return;
  updated = true;
  for (const listener of listeners) listener();
}

/** Whether a failed dynamic import is a chunk the server no longer has. */
export function isChunkLoadError(error: unknown): boolean {
  return error instanceof TypeError && /dynamically imported module|Importing a module script failed|error loading dynamically imported module/i.test(error.message);
}

export function useServerVersion(): boolean {
  const session = useSession();
  const router = useRouter();
  const [isUpdated, setUpdated] = useState(updated);

  useEffect(() => {
    const listener = (): void => setUpdated(true);
    listeners.add(listener);
    const started = session.meta?.server_version;
    let last = Date.now();
    const check = async (): Promise<void> => {
      if (updated || !started || Date.now() - last < EVERY_MS) return;
      last = Date.now();
      try {
        const meta = await session.client.meta({ timeoutMs: 10_000 });
        if (meta.server_version !== started) markUpdated();
      } catch {
        // Unreachable for now: the pages will say so.
      }
    };
    const onFocus = (): void => void check();
    window.addEventListener('focus', onFocus);
    const unsubscribe = router.subscribe('onResolved', () => void check());
    return () => {
      listeners.delete(listener);
      window.removeEventListener('focus', onFocus);
      unsubscribe();
    };
  }, [session, router]);

  return isUpdated;
}
