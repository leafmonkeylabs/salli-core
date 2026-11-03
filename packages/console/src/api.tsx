/**
 * Data, only through the SDK (docs/design/console.md, section 4): every call
 * is a generated function through the session's `SalliClient`, so the
 * console calls no URL by hand and defines no response type of its own.
 *
 * - `useRead` fetches with TanStack Query, keyed by the operation's name and
 *   its options, so a page refreshes what a write changed by name.
 * - `useWrite` runs a write. When Salli asks for the password again
 *   (`/problems/step-up-required`), it sends the person through the sign-in
 *   page with the write kept, and retries it once on return; a second
 *   step-up answer is shown, not followed.
 * - A 401 means the sign-in ended: the session says so and clears the tab.
 */
import {
  QueryCache,
  QueryClient,
  MutationCache,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { CallOptions, DataOf, SalliClient } from '@leafmonkeylabs/salli-sdk';
import { SalliApiError, SalliNetworkError } from '@leafmonkeylabs/salli-sdk';
import { createContext, useContext, useEffect, useRef, type ReactNode } from 'react';
import { isSignedOutError, isStepUpRequired, type ConsoleSession } from './auth/session';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Operation = (options: any) => Promise<any>;

const SessionContext = createContext<ConsoleSession | null>(null);

export function useSession(): ConsoleSession {
  const session = useContext(SessionContext);
  if (!session) throw new Error('useSession outside the console');
  return session;
}

export function useApi(): SalliClient {
  return useSession().client;
}

/** The query client: no retries of an answer, one of a dropped connection. */
export function createQueryClient(session: ConsoleSession): QueryClient {
  const ended = (error: unknown): void => {
    if (isSignedOutError(error)) void session.signOut('ended');
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError: ended }),
    mutationCache: new MutationCache({ onError: ended }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (count, error) => count < 1 && error instanceof SalliNetworkError,
      },
      mutations: { retry: false },
    },
  });
}

export function ApiProvider({ session, queryClient, children }: { session: ConsoleSession; queryClient: QueryClient; children: ReactNode }) {
  return (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
}

/**
 * Reads an operation: `useRead('reports.balanceSheet', reportsBalanceSheet)`.
 * The name is the operation id, so `invalidate` can name it.
 */
export function useRead<F extends Operation>(
  name: string,
  fn: F,
  options?: CallOptions<F>,
  config: { enabled?: boolean } = {},
): UseQueryResult<DataOf<F>, Error> {
  const api = useApi();
  return useQuery({
    queryKey: [name, options ?? null],
    queryFn: ({ signal }) => (api.call as (f: F, o: unknown) => Promise<DataOf<F>>)(fn, { ...(options ?? {}), signal }),
    ...(config.enabled === undefined ? {} : { enabled: config.enabled }),
  });
}

export interface WriteOptions<I, R> {
  /** Operation names whose reads this write changes. */
  invalidate?: string[];
  onSuccess?: (result: R, input: I) => void;
  /**
   * Where the write holds a secret, so nothing keeps it beyond the page
   * that shows it: no cached mutation outlives its page (TanStack's cache
   * forgets it once nothing observes it). `'input'`: what is sent is the
   * secret (a model key typed in), so it never waits in sessionStorage for
   * a step-up either: a step-up answer is shown, not followed. `'answer'`:
   * what comes back is (a token, shown once); the input is plain and may
   * wait for a step-up.
   */
  secret?: 'input' | 'answer';
}

/**
 * A write, retried once after a step-up. `name` identifies it across the
 * redirect, and `input` must be plain JSON (it waits in sessionStorage).
 */
export function useWrite<I, R>(name: string, run: (api: SalliClient, input: I) => Promise<R>, options: WriteOptions<I, R> = {}) {
  const session = useSession();
  const queryClient = useQueryClient();
  const retried = useRef(false);
  const followsStepUp = options.secret !== 'input';
  const mutation = useMutation<R, Error, I>({
    mutationKey: [name],
    mutationFn: (input) => run(session.client, input),
    ...(options.secret ? { gcTime: 0 } : {}),
    onSuccess: async (result, input) => {
      await Promise.all((options.invalidate ?? []).map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
      options.onSuccess?.(result, input);
    },
    onError: (error, input) => {
      if (followsStepUp && isStepUpRequired(error) && !retried.current) void session.stepUp({ name, input });
    },
  });

  // Back from a step-up with this write waiting: run it once more.
  const { mutate } = mutation;
  useEffect(() => {
    const retry = session.takeRetry(name);
    if (retry) {
      retried.current = true;
      mutate(retry.input as I);
    }
  }, [session, name, mutate]);

  const stepUpPending = followsStepUp && mutation.isError && isStepUpRequired(mutation.error) && !retried.current;
  return { ...mutation, stepUpPending, retried: retried.current };
}

/** An error as RFC 9457 problem details, or undefined for one that isn't Salli's. */
export function problemOf(error: unknown): SalliApiError | undefined {
  return error instanceof SalliApiError ? error : undefined;
}
