/**
 * Appearance (designs 23 to 25): which theme this phone draws Salli in, and
 * whether a theme with a night side follows the phone. Kept on the phone.
 */

export const THEMES = ['ledger', 'bold', 'aurora'] as const;
export type ThemeId = (typeof THEMES)[number];

export const MODES = ['auto', 'light', 'dark'] as const;
export type Mode = (typeof MODES)[number];

export interface Appearance {
  theme: ThemeId;
  mode: Mode;
}

/** Where the phone keeps it. */
export const APPEARANCE_KEY = 'salli.appearance';

export const DEFAULT_APPEARANCE: Appearance = { theme: 'ledger', mode: 'auto' };

/** The themes with both a day and a night side; the others are always one. */
export const HAS_NIGHT: readonly ThemeId[] = ['ledger'];

/** Themes that were retired: Ledger Rounded became Ledger, and Sticker's outlines gave way to it. */
const RETIRED: Record<string, ThemeId> = { ledgerRounded: 'ledger', sticker: 'ledger' };

/** What was stored, or the defaults where it is missing or unreadable; a retired theme becomes Ledger. */
export function appearanceOf(text: string | null): Appearance {
  if (!text) return DEFAULT_APPEARANCE;
  try {
    const found = JSON.parse(text) as Partial<Appearance>;
    const stored = typeof found.theme === 'string' ? (RETIRED[found.theme] ?? found.theme) : undefined;
    return {
      theme: THEMES.includes(stored as ThemeId) ? (stored as ThemeId) : DEFAULT_APPEARANCE.theme,
      mode: MODES.includes(found.mode as Mode) ? (found.mode as Mode) : DEFAULT_APPEARANCE.mode,
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

/** Whether the theme is drawn on its night side. */
export function isNight(appearance: Appearance, phoneDark: boolean): boolean {
  if (appearance.theme === 'bold' || appearance.theme === 'aurora') return true;
  return appearance.mode === 'auto' ? phoneDark : appearance.mode === 'dark';
}

export type TypeId = 'geist' | 'bold' | 'aurora';

export function typeOf(theme: ThemeId): TypeId {
  return theme === 'ledger' ? 'geist' : theme;
}

/** The app icon each theme sets: null is the app's own, Ledger's. */
export function iconOf(theme: ThemeId): string | null {
  return theme === 'ledger' ? null : theme === 'bold' ? 'Bold' : 'Aurora';
}
