/**
 * Data, only through the SDK, as the console reads it (packages/console/src/
 * api.tsx): every call a generated function through the session's client,
 * keyed by its operation name, so the app calls no URL by hand.
 */
import type { CallOptions, DataOf, SalliClient } from '@leafmonkeylabs/salli-sdk';
import { SalliNetworkError } from '@leafmonkeylabs/salli-sdk';
import { QueryCache, QueryClient, QueryClientProvider, useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useMemo, type ReactNode } from 'react';
import { isSignedOutError, useSession } from './session';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Operation = (options: any) => Promise<any>;

export function useApi(): SalliClient {
  const { session } = useSession();
  if (session.status !== 'signed-in') throw new Error('useApi while signed out');
  return session.client;
}

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
export function useRead<F extends Operation>(name: string, fn: F, options?: CallOptions<F>): UseQueryResult<DataOf<F>, Error> {
  const api = useApi();
  return useQuery({
    queryKey: [api.server, name, options ?? null],
    queryFn: ({ signal }) => (api.call as (f: F, o: unknown) => Promise<DataOf<F>>)(fn, { ...(options ?? {}), signal }),
  });
}
