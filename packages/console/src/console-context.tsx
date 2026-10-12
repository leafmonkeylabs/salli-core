/**
 * What the running console holds: the extensions this server runs (their
 * navigation and settings panels) beside the console's own.
 */
import { createContext, useContext, type ReactNode } from 'react';
import type { ConsoleExtension, NavigationItem, SettingsPanel } from './extensions';

export interface ConsoleExtensions {
  /** Every extension the console was built with. */
  all: readonly ConsoleExtension[];
  /** Those whose server half /v1/meta lists. */
  enabled: readonly ConsoleExtension[];
  navigation: NavigationItem[];
  settingsPanels: SettingsPanel[];
}

const empty: ConsoleExtensions = { all: [], enabled: [], navigation: [], settingsPanels: [] };

const ExtensionsContext = createContext<ConsoleExtensions>(empty);

export function ExtensionsProvider({ value, children }: { value: ConsoleExtensions; children: ReactNode }) {
  return <ExtensionsContext.Provider value={value}>{children}</ExtensionsContext.Provider>;
}

export function useConsoleExtensions(): ConsoleExtensions {
  return useContext(ExtensionsContext);
}

export function extensionsFor(all: readonly ConsoleExtension[], enabled: readonly ConsoleExtension[]): ConsoleExtensions {
  return {
    all,
    enabled,
    navigation: enabled.flatMap((extension) => extension.navigation ?? []),
    settingsPanels: enabled.flatMap((extension) => extension.settingsPanels ?? []),
  };
}
