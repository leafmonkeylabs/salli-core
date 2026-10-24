/**
 * Appearance (designs 23 to 25): the theme this phone draws Salli in, kept
 * on the phone. Its colours, corners and icons change at once; its type is
 * the one the app opened with (theme.ts, `openedWith`). The app icon follows
 * where the phone allows it.
 */
import { BricolageGrotesque_400Regular, BricolageGrotesque_600SemiBold, BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque';
import { Geist_400Regular, Geist_500Medium, Geist_600SemiBold } from '@expo-google-fonts/geist';
import { GeistMono_400Regular } from '@expo-google-fonts/geist-mono';
import { PlusJakartaSans_400Regular, PlusJakartaSans_500Medium, PlusJakartaSans_700Bold } from '@expo-google-fonts/plus-jakarta-sans';
import { SpaceGrotesk_400Regular, SpaceGrotesk_500Medium, SpaceGrotesk_700Bold } from '@expo-google-fonts/space-grotesk';
import { getAppIconName, setAlternateAppIcon, supportsAlternateIcons } from 'expo-alternate-app-icons';
import * as Font from 'expo-font';
import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { APPEARANCE_KEY, appearanceOf, iconOf, typeOf, type Appearance } from './lib/appearance';
import { AppearanceContext, font, openedWith } from './theme';

/** Each type's files, by the names theme.ts gives them. */
const FILES = {
  geist: [Geist_400Regular, Geist_500Medium, Geist_600SemiBold],
  bold: [SpaceGrotesk_400Regular, SpaceGrotesk_500Medium, SpaceGrotesk_700Bold],
  sticker: [BricolageGrotesque_400Regular, BricolageGrotesque_600SemiBold, BricolageGrotesque_800ExtraBold],
  aurora: [PlusJakartaSans_400Regular, PlusJakartaSans_500Medium, PlusJakartaSans_700Bold],
} as const;

interface AppearanceApi {
  appearance: Appearance;
  set(next: Appearance): void;
}

const Api = createContext<AppearanceApi | null>(null);

export function useAppearance(): AppearanceApi {
  const api = useContext(Api);
  if (!api) throw new Error('useAppearance outside AppearanceProvider');
  return api;
}

/** Draws nothing until the type the app opened with is loaded. */
export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearance] = useState<Appearance>(() => appearanceOf(SecureStore.getItem(APPEARANCE_KEY)));
  const [typeLoaded, setTypeLoaded] = useState(false);

  useEffect(() => {
    const [regular, medium, semibold] = FILES[typeOf(openedWith)];
    void Font.loadAsync({ [font.regular]: regular, [font.medium]: medium, [font.semibold]: semibold, [font.mono]: GeistMono_400Regular }).finally(() => setTypeLoaded(true));
  }, []);

  const set = useCallback((next: Appearance) => {
    setAppearance(next);
    void SecureStore.setItemAsync(APPEARANCE_KEY, JSON.stringify(next));
    const icon = iconOf(next.theme);
    if (supportsAlternateIcons && getAppIconName() !== icon) void setAlternateAppIcon(icon).catch(() => undefined);
  }, []);

  const api = useMemo(() => ({ appearance, set }), [appearance, set]);
  if (!typeLoaded) return null;
  return (
    <Api.Provider value={api}>
      <AppearanceContext.Provider value={appearance}>{children}</AppearanceContext.Provider>
    </Api.Provider>
  );
}
