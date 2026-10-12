/**
 * How an edition adds to the console (decision 19): build-time composition.
 * An edition is a small app that imports this package and passes its
 * extensions to `createConsole({ extensions })`, building one bundle. The
 * open console is built through the same call, with none.
 *
 * Each extension names the server extension it belongs to (`requires`): its
 * pages, navigation and settings panels appear only when `/v1/meta` lists
 * that extension, so a console built with it, on a server without it, is the
 * open console. Nothing here decides what a person may see: pages show what
 * the API returns.
 */
import type { ComponentType } from 'react';
import type { TokenName } from './theme';

/** A page under /console/<path>. */
export interface ConsoleRoute {
  /** The path under /console, starting with a slash: `/example`. */
  path: string;
  /** The page. */
  component?: ComponentType;
  /** Or a loader of it, so the page is its own chunk: `() => import('./Page')`. */
  load?: () => Promise<{ default: ComponentType }>;
}

/** A place in the navigation. */
export interface NavigationItem {
  /** The path under /console it opens. */
  to: string;
  label: string;
}

/** A panel in Settings, after the console's own. */
export interface SettingsPanel {
  id: string;
  title: string;
  component: ComponentType;
}

/** The brand tokens, replaced whole: each role's light and dark value. */
export type ThemeTokens = Record<TokenName, { light: string; dark: string }>;

export interface ConsoleExtension {
  /** The server extension it belongs to: shown only when /v1/meta lists it. */
  requires: string;
  routes?: ConsoleRoute[];
  navigation?: NavigationItem[];
  settingsPanels?: SettingsPanel[];
  theme?: ThemeTokens;
}

/** The extensions whose server half this server runs. */
export function enabledExtensions(extensions: readonly ConsoleExtension[], serverExtensions: readonly string[]): ConsoleExtension[] {
  const running = new Set(serverExtensions);
  return extensions.filter((extension) => running.has(extension.requires));
}
