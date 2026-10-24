/**
 * Data, only through the SDK, as the console reads it (packages/console/src/
 * api.tsx): every call a generated function through the session's client,
 * keyed by its operation name, so the app calls no URL by hand.
 */
import type { CallOptions, DataOf, SalliClient } from '@leafmonkeylabs/salli-sdk';
import { SalliNetworkError } from '@leafmonkeylabs/salli-sdk';
import { focusManager, QueryCache, QueryClient, QueryClientProvider, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { AppState } from 'react-native';
import { useCallback, useMemo, useSyncExternalStore, type ReactNode } from 'react';
import { isSignedOutError, useSession } from './session';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Operation = (options: any) => Promise<any>;

export function useApi(): SalliClient {
  const { session } = useSession();
  if (session.status !== 'signed-in') throw new Error('useApi while signed out');
  return session.client;
}

// The app coming back to the screen is a phone's window focus: a stale read runs again.
focusManager.setEventListener((focused) => {
  const subscription = AppState.addEventListener('change', (state) => focused(state === 'active'));
  return () => subscription.remove();
});

/** The query client: no retries of an answer, one of a dropped connection; a 401 ends its server's sign-in. */
export function ApiProvider({ children }: { children: ReactNode }) {
  const { ended } = useSession();
  const queryClient = useMemo(
    () =>
      new QueryClient({
        // Every key starts with its server: a 401 ends that server's sign-in, not the one on screen.
        queryCache: new QueryCache({ onError: (error, query) => (isSignedOutError(error) ? ended(String(query.queryKey[0])) : undefined) }),
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: (count, error) => count < 1 && error instanceof SalliNetworkError,
          },
          mutations: { retry: false },
        },
      }),
    [ended],
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

/** Reads an operation: `useRead('reports.balanceSheet', reportsBalanceSheet)`. */
export function useRead<F extends Operation>(name: string, fn: F, options?: CallOptions<F>, read?: { enabled?: boolean }): UseQueryResult<DataOf<F>, Error> {
  const api = useApi();
  return useQuery({
    enabled: read?.enabled ?? true,
    queryKey: [api.server, name, options ?? null],
    queryFn: ({ signal }) => (api.call as (f: F, o: unknown) => Promise<DataOf<F>>)(fn, { ...(options ?? {}), signal }),
  });
}

/** Whether the server on screen is answering, and when it last did. */
export interface Reach {
  /** Its latest read failed for want of an answer (not a refusal: an answer is an answer). */
  unreachable: boolean;
  /** When a read last came back from it, in this run of the app. */
  lastAnswer: Date | undefined;
}

/** The reach as a value, `"<unreachable>|<last answer ms>"`: equal when nothing changed. */
function reachKey(queries: readonly { queryKey: readonly unknown[]; state: { dataUpdatedAt: number; errorUpdatedAt: number; error: unknown } }[], server: string): string {
  let answered = 0;
  let failed = 0;
  for (const query of queries) {
    if (query.queryKey[0] !== server) continue;
    answered = Math.max(answered, query.state.dataUpdatedAt);
    if (query.state.error instanceof SalliNetworkError) failed = Math.max(failed, query.state.errorUpdatedAt);
  }
  return `${failed > answered ? 1 : 0}|${answered}`;
}

/** The reach of the server on screen, from the reads already made: it asks nothing itself. */
export function useReach(): Reach {
  const api = useApi();
  const cache = useQueryClient().getQueryCache();
  // The cache tells of new reads while others render: React's store hook takes that in turn.
  const subscribe = useCallback((changed: () => void) => cache.subscribe(changed), [cache]);
  const key = useSyncExternalStore(subscribe, () => reachKey(cache.getAll(), api.server));
  return useMemo(() => {
    const [unreachable, answered = '0'] = key.split('|');
    // eslint-disable-next-line no-restricted-syntax -- not money: a time in milliseconds
    const at = Number(answered);
    return { unreachable: unreachable === '1', lastAnswer: at ? new Date(at) : undefined };
  }, [key]);
}
