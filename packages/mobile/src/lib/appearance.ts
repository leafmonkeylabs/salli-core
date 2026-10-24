/**
 * Appearance (designs 23 to 25): which theme this phone draws Salli in, and
 * whether a theme with a night side follows the phone. Kept on the phone.
 */

export const THEMES = ['ledger', 'ledgerRounded', 'bold', 'sticker', 'aurora'] as const;
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
export const HAS_NIGHT: readonly ThemeId[] = ['ledger', 'ledgerRounded'];

/** What was stored, or the defaults where it is missing or unreadable. */
export function appearanceOf(text: string | null): Appearance {
  if (!text) return DEFAULT_APPEARANCE;
  try {
    const found = JSON.parse(text) as Partial<Appearance>;
    return {
      theme: THEMES.includes(found.theme as ThemeId) ? (found.theme as ThemeId) : DEFAULT_APPEARANCE.theme,
      mode: MODES.includes(found.mode as Mode) ? (found.mode as Mode) : DEFAULT_APPEARANCE.mode,
    };
  } catch {
    return DEFAULT_APPEARANCE;
  }
}

/** Whether the theme is drawn on its night side. */
export function isNight(appearance: Appearance, phoneDark: boolean): boolean {
  if (appearance.theme === 'bold' || appearance.theme === 'aurora') return true;
  if (appearance.theme === 'sticker') return false;
  return appearance.mode === 'auto' ? phoneDark : appearance.mode === 'dark';
}

/** The themes that share a typeface: Ledger's two. */
export type TypeId = 'geist' | 'bold' | 'sticker' | 'aurora';

export function typeOf(theme: ThemeId): TypeId {
  return theme === 'ledger' || theme === 'ledgerRounded' ? 'geist' : theme;
}

/** The app icon each theme sets: null is the app's own, Ledger's. */
export function iconOf(theme: ThemeId): string | null {
  return theme === 'ledger' ? null : theme === 'ledgerRounded' ? 'LedgerRounded' : theme === 'bold' ? 'Bold' : theme === 'sticker' ? 'Sticker' : 'Aurora';
}
