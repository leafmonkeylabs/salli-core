/**
 * The pages a server describes as panels, as the app places them: which
 * ones More and Settings list, and the sheet a refusal's offer opens.
 */
import { isPanelId, type Offer, type PanelEntry } from '@leafmonkeylabs/salli-sdk';

/** The panels the server places at `entry` (`more`, `settings`), in the order it listed them. */
export function placesOf(list: readonly PanelEntry[], entry: 'more' | 'settings'): PanelEntry[] {
  return list.filter((panel) => panel.entry === entry);
}

/** The screen a panel opens, or undefined for an id that cannot sit in a path. */
export function panelPathOf(id: string): string | undefined {
  return isPanelId(id) ? `/panel/${id}` : undefined;
}

/** Whether an offer on one server is for the server on screen (a sheet never opens another server's panel). */
export function offerIsFor(offered: { server: string; offer: Offer }, onScreen: string | undefined): boolean {
  return offered.server === onScreen;
}
