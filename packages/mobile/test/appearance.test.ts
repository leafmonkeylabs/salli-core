import { describe, expect, it } from 'vitest';
import { appearanceOf, DEFAULT_APPEARANCE, iconOf, isNight, THEMES, typeOf } from '../src/lib/appearance';

describe('appearance', () => {
  it('reads what was stored, and the defaults for anything else', () => {
    expect(appearanceOf(null)).toEqual(DEFAULT_APPEARANCE);
    expect(appearanceOf('not json')).toEqual(DEFAULT_APPEARANCE);
    expect(appearanceOf('{"theme":"aurora","mode":"dark"}')).toEqual({ theme: 'aurora', mode: 'dark' });
    expect(appearanceOf('{"theme":"pocket","mode":"dim"}')).toEqual(DEFAULT_APPEARANCE);
  });

  it('follows the phone only where a theme has a night side', () => {
    expect(isNight({ theme: 'ledger', mode: 'auto' }, true)).toBe(true);
    expect(isNight({ theme: 'ledgerRounded', mode: 'light' }, true)).toBe(false);
    expect(isNight({ theme: 'ledger', mode: 'dark' }, false)).toBe(true);
    expect(isNight({ theme: 'bold', mode: 'light' }, false)).toBe(true);
    expect(isNight({ theme: 'aurora', mode: 'auto' }, false)).toBe(true);
    expect(isNight({ theme: 'sticker', mode: 'dark' }, true)).toBe(false);
  });

  it("gives every theme but Ledger an icon of its own", () => {
    expect(iconOf('ledger')).toBeNull();
    const icons = THEMES.filter((t) => t !== 'ledger').map(iconOf);
    expect(new Set(icons).size).toBe(icons.length);
    expect(icons.every((i) => typeof i === 'string')).toBe(true);
  });

  it("shares Ledger's type between its two themes only", () => {
    expect(typeOf('ledger')).toBe(typeOf('ledgerRounded'));
    expect(new Set(THEMES.map(typeOf)).size).toBe(4);
  });
});
