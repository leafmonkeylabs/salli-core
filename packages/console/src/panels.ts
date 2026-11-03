/**
 * The panels a server describes (`salli.panel/1`, `/v1/panels`): which it
 * lists for the navigation, and one document. A server that says
 * `panels: true` in /v1/meta has some; the console draws what each says
 * (kit/PanelView.tsx) and adds no word of its own.
 */
import { panelsList, panelsShow, parsePanel, type PanelDocument, type PanelEntry } from '@leafmonkeylabs/salli-sdk';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useApi, useRead, useSession } from './api';
import type { NavigationItem } from './extensions';

/** The panels the server lists; none while it says it has none. */
export function usePanelEntries(): PanelEntry[] {
  const session = useSession();
  const on = session.meta?.panels === true;
  const list = useRead('panels.list', panelsList, undefined, { enabled: on });
  return on ? (list.data?.panels ?? []) : [];
}

/** The panels as places in the navigation, titled by the server. */
export function usePanelNavigation(): NavigationItem[] {
  return usePanelEntries().map((panel) => ({ to: `/panel/${panel.id}`, label: panel.title }));
}

/** One panel's document: null when the server's is not one the console can draw. */
export function usePanel(id: string): UseQueryResult<PanelDocument | null, Error> {
  const api = useApi();
  return useQuery({
    queryKey: ['panels.show', id],
    queryFn: async ({ signal }) => parsePanel(await api.call(panelsShow, { path: { panel_id: id }, signal })) ?? null,
  });
}

/** The reads a panel action changes. */
export const PANEL_READS = ['panels.show', 'panels.list'];
