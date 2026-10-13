/**
 * Signing out after 30 minutes without a key or a click (decision 5). It
 * doesn't stop a thief; it protects a shared screen.
 *
 * The time is measured from the last keydown or pointerdown, and checked
 * again whenever the tab becomes visible, since a hidden tab's timers are
 * slowed.
 */

export const IDLE_LIMIT_MS = 30 * 60 * 1000;

/** Where a test may shorten the limit (never lengthen it), in seconds. */
export const IDLE_OVERRIDE_KEY = 'salli-console:idle-seconds';

/**
 * The idle limit: 30 minutes, or less when this tab's sessionStorage names
 * a shorter one (the end-to-end tests set it to a few seconds).
 */
export function idleLimitMs(storage: Pick<Storage, 'getItem'> | undefined = globalThis.sessionStorage): number {
  let raw: string | null;
  try {
    raw = storage?.getItem(IDLE_OVERRIDE_KEY) ?? null;
  } catch {
    return IDLE_LIMIT_MS;
  }
  if (!raw || !/^\d{1,4}$/.test(raw)) return IDLE_LIMIT_MS;
  const seconds = JSON.parse(raw) as number;
  return seconds > 0 && seconds * 1000 < IDLE_LIMIT_MS ? seconds * 1000 : IDLE_LIMIT_MS;
}

export interface IdleTimer {
  stop(): void;
}

/** Calls `onIdle` once, after `limitMs` without a key or a click on `target`. */
export function startIdleTimer(
  onIdle: () => void,
  limitMs: number = idleLimitMs(),
  target: Document = document,
  now: () => number = Date.now,
): IdleTimer {
  let last = now();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;

  const check = (): void => {
    if (stopped) return;
    const left = last + limitMs - now();
    if (left <= 0) {
      stop();
      onIdle();
      return;
    }
    clearTimeout(timer);
    timer = setTimeout(check, Math.min(left, 60_000));
  };
  const active = (): void => {
    last = now();
  };
  const visible = (): void => {
    if (target.visibilityState === 'visible') check();
  };
  function stop(): void {
    stopped = true;
    clearTimeout(timer);
    target.removeEventListener('keydown', active, true);
    target.removeEventListener('pointerdown', active, true);
    target.removeEventListener('visibilitychange', visible);
  }

  target.addEventListener('keydown', active, true);
  target.addEventListener('pointerdown', active, true);
  target.addEventListener('visibilitychange', visible);
  check();
  return { stop };
}
