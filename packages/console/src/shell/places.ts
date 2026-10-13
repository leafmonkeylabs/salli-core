/**
 * The console's places (C5): each with its icon and its own places, in
 * the order the side menu shows them, and where a path is among them, for
 * the side menu, the breadcrumb, the page's tile and each place's row of
 * links. One list, so they never disagree.
 */
import type { NavigationItem } from '../extensions';
import type { IconName } from '../kit/Icon';
import { strings } from '../strings';

export interface SubPlace {
  to: string;
  label: string;
  /** Current only on exactly this path (an overview), not below it. */
  exact?: boolean;
  /** Paths below which it is current too (an account's page is among the accounts). */
  also?: readonly string[];
}

export interface Place {
  to: string;
  label: string;
  icon: IconName;
  /** The side menu's groups, top to bottom; 3 sits at the foot. */
  group: 0 | 1 | 2 | 3;
  children?: readonly SubPlace[];
}

const n = strings.nav;
const s = strings.settings.places;

export const BOOKS_PLACES: readonly SubPlace[] = [
  { to: '/books', label: n.accounts, exact: true, also: ['/books/accounts'] },
  { to: '/books/entries', label: n.entries },
  { to: '/books/imports', label: n.imports },
  { to: '/books/rules', label: n.rules },
];

export const DECIDE_PLACES: readonly SubPlace[] = [
  { to: '/decide', label: n.overview, exact: true },
  { to: '/decide/templates', label: n.templates },
  { to: '/decide/scenarios', label: n.scenarios },
  { to: '/decide/principles', label: n.principles },
  { to: '/decide/journal', label: n.journal },
  { to: '/decide/baseline', label: n.baseline },
];

export const SETTINGS_PLACES: readonly SubPlace[] = [
  { to: '/settings', label: s.profile, exact: true },
  { to: '/settings/tokens', label: s.tokens },
  { to: '/settings/ai', label: s.ai },
  { to: '/settings/digests', label: s.digests },
  { to: '/settings/data', label: s.data },
];

/** Every place: the console's own, and an edition's before Settings. */
export function placesOf(navigation: readonly NavigationItem[]): Place[] {
  return [
    { to: '/', label: n.home, icon: 'home', group: 0 },
    { to: '/cash', label: n.cash, icon: 'cash', group: 0 },
    { to: '/books', label: n.books, icon: 'books', group: 1, children: BOOKS_PLACES },
    { to: '/decide', label: n.decide, icon: 'decide', group: 1, children: DECIDE_PLACES },
    { to: '/tax', label: n.tax, icon: 'tax', group: 1 },
    { to: '/attention', label: n.attention, icon: 'attention', group: 2 },
    { to: '/fi', label: n.fi, icon: 'independence', group: 2 },
    ...navigation.map((item): Place => ({ to: item.to, label: item.label, icon: 'page', group: 2 })),
    { to: '/settings', label: n.settings, icon: 'settings', group: 3, children: SETTINGS_PLACES },
  ];
}

/** A router path without the console's base: `/console/books` → `/books`. */
export function appPath(pathname: string): string {
  return pathname.replace(/^\/console(?=\/|$)/, '') || '/';
}

/** Whether `path` is at `to` or below it. */
export function within(path: string, to: string): boolean {
  return to === '/' ? path === '/' : path === to || path.startsWith(`${to}/`);
}

/** Whether a place's own place is the current one. */
export function isCurrent(sub: SubPlace, path: string): boolean {
  if (sub.exact ? path === sub.to : within(path, sub.to)) return true;
  return (sub.also ?? []).some((to) => within(path, to));
}

/** The place `path` is in: the deepest whose path it is at or below. */
export function placeOf(path: string, places: readonly Place[]): Place | undefined {
  let found: Place | undefined;
  for (const place of places) if (within(path, place.to) && (!found || place.to.length > found.to.length)) found = place;
  return found;
}

export interface Crumb {
  label: string;
  /** Where it links; the last crumb, the page itself, has none. */
  to?: string;
}

/**
 * Where a page is: its place, the place's own place it is in, anything a
 * page names between (a rule set, above its version), then the page.
 */
export function crumbsOf(path: string, places: readonly Place[], title: string, trail: readonly Crumb[] = []): Crumb[] {
  const place = placeOf(path, places);
  if (!place) return title ? [{ label: title }] : [];
  const out: Crumb[] = [{ label: place.label, to: place.to }];
  const sub = place.children?.find((child) => isCurrent(child, path));
  let at = place.to;
  if (sub && !(sub.to === place.to && path === place.to)) {
    out.push({ label: sub.label, to: sub.to });
    at = sub.to;
  }
  out.push(...trail);
  if (path !== at && title && title !== out[out.length - 1]?.label) out.push({ label: title });
  // The last is where you are: not a link.
  const last = out[out.length - 1];
  if (last) out[out.length - 1] = { label: last.label };
  return out;
}
