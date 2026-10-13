/**
 * What this device shows: a light, dark or system theme, a locale for
 * numbers and dates (the browser's unless chosen), and whether the side
 * menu is open. Kept in localStorage,
 * the only thing the console keeps on disk besides the tab's sign-in
 * (docs/design/console.md, section 4); never sent to Salli.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

export type Theme = 'system' | 'light' | 'dark';
/** The side menu: as the screen's width has it, or as the person left it. */
export type Side = 'auto' | 'open' | 'closed';

const THEME_KEY = 'salli-console:theme';
const LOCALE_KEY = 'salli-console:locale';
const SIDE_KEY = 'salli-console:side';

function read(key: string): string | null {
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) globalThis.localStorage?.removeItem(key);
    else globalThis.localStorage?.setItem(key, value);
  } catch {
    // Storage refused (a private window): the choice lasts this page only.
  }
}

export function storedTheme(): Theme {
  const value = read(THEME_KEY);
  return value === 'light' || value === 'dark' ? value : 'system';
}

/** Sets `data-theme` on <html>: tokens.css picks the colour scheme from it. */
export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  if (theme === 'system') delete root.dataset.theme;
  else root.dataset.theme = theme;
}

/** Whether `tag` is a locale this browser's Intl knows. */
export function isLocale(tag: string): boolean {
  try {
    return Intl.NumberFormat.supportedLocalesOf([tag]).length > 0;
  } catch {
    return false;
  }
}

export function storedLocale(): string | undefined {
  const value = read(LOCALE_KEY);
  return value && isLocale(value) ? value : undefined;
}

export function storedSide(): Side {
  const value = read(SIDE_KEY);
  return value === 'open' || value === 'closed' ? value : 'auto';
}

export interface Preferences {
  theme: Theme;
  setTheme(theme: Theme): void;
  /** The chosen locale, or undefined for the browser's. */
  locale: string | undefined;
  setLocale(locale: string | undefined): void;
  side: Side;
  setSide(side: Side): void;
}

const PreferencesContext = createContext<Preferences | null>(null);

export function PreferencesProvider({ children, locale: fixed }: { children: ReactNode; locale?: string }) {
  const [theme, setThemeState] = useState<Theme>(storedTheme);
  const [locale, setLocaleState] = useState<string | undefined>(() => fixed ?? storedLocale());
  const setTheme = useCallback((next: Theme) => {
    write(THEME_KEY, next === 'system' ? null : next);
    applyTheme(next);
    setThemeState(next);
  }, []);
  const setLocale = useCallback((next: string | undefined) => {
    write(LOCALE_KEY, next ?? null);
    setLocaleState(next);
  }, []);
  const [side, setSideState] = useState<Side>(storedSide);
  const setSide = useCallback((next: Side) => {
    write(SIDE_KEY, next === 'auto' ? null : next);
    setSideState(next);
  }, []);
  const value = useMemo(() => ({ theme, setTheme, locale, setLocale, side, setSide }), [theme, setTheme, locale, setLocale, side, setSide]);
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): Preferences {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error('usePreferences outside PreferencesProvider');
  return value;
}

/** The locale to format numbers and dates in: the chosen one, or the browser's. */
export function useLocale(): string | undefined {
  return usePreferences().locale;
}
