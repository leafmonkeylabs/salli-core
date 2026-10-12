/**
 * Signing out after 30 minutes without a key or a click (decision 5).
 */
import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IDLE_LIMIT_MS, IDLE_OVERRIDE_KEY, idleLimitMs, startIdleTimer } from '../src/auth/idle';
import { MemoryStorage, setup, TODAY } from './harness';

afterEach(() => {
  vi.useRealTimers();
});

describe('the idle limit', () => {
  it('is 30 minutes, and a test may only shorten it', () => {
    const storage = new MemoryStorage();
    expect(idleLimitMs(storage)).toBe(30 * 60 * 1000);
    storage.setItem(IDLE_OVERRIDE_KEY, '3');
    expect(idleLimitMs(storage)).toBe(3000);
    storage.setItem(IDLE_OVERRIDE_KEY, '7200');
    expect(idleLimitMs(storage)).toBe(IDLE_LIMIT_MS);
    storage.setItem(IDLE_OVERRIDE_KEY, '1e9');
    expect(idleLimitMs(storage)).toBe(IDLE_LIMIT_MS);
  });

  it('counts from the last key or click', () => {
    vi.useFakeTimers();
    const onIdle = vi.fn();
    const timer = startIdleTimer(onIdle, 60_000, document);
    vi.advanceTimersByTime(50_000);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    vi.advanceTimersByTime(50_000);
    expect(onIdle).not.toHaveBeenCalled();
    document.dispatchEvent(new Event('pointerdown'));
    vi.advanceTimersByTime(59_000);
    expect(onIdle).not.toHaveBeenCalled();
    vi.advanceTimersByTime(2_000);
    expect(onIdle).toHaveBeenCalledTimes(1);
    timer.stop();
  });
});

describe('the console', () => {
  it('signs out after the limit, revokes the grant and says why', async () => {
    const storage = new MemoryStorage();
    storage.setItem(IDLE_OVERRIDE_KEY, '1');
    const { api } = await setup({ storage });
    await screen.findByRole('heading', { level: 1, name: 'Home' });
    vi.setSystemTime(new Date(TODAY.getTime() + 5_000));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
    });
    expect(await screen.findByText(/signed out after 30 minutes without a key or a click/)).toBeTruthy();
    expect(api.to('/mcp/oauth/revoke')).toHaveLength(1);
  });
});
