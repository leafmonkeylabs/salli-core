/**
 * `createConsole({ extensions })`: the console, assembled (decision 19).
 *
 * The open console is `createConsole()` with no extensions (main.tsx); an
 * edition passes its own, which add pages under /console, places in the
 * navigation and panels in Settings, each shown only when `/v1/meta` lists
 * the server extension it `requires`. Everything else is the same build:
 * the sign-in, the kit, the pages.
 */
import {
  createRootRoute,
  createRoute,
  createRouter,
  createBrowserHistory,
  RouterProvider,
  type AnyRoute,
  type RouterHistory,
} from '@tanstack/react-router';
import type { QueryClient } from '@tanstack/react-query';
import { lazy, StrictMode, Suspense, useEffect, useMemo, useSyncExternalStore, type ComponentType, type ReactElement } from 'react';
import { createRoot } from 'react-dom/client';
import { ApiProvider, createQueryClient } from './api';
import { BASE_PATH, browserEnvironment, ConsoleSession, type SessionEnvironment } from './auth/session';
import { ExtensionsProvider, extensionsFor, useConsoleExtensions } from './console-context';
import { enabledExtensions, type ConsoleExtension, type ConsoleRoute } from './extensions';
import { Loading, Page } from './kit/layout';
import { ProblemView } from './kit/Problem';
import { Home } from './pages/home/Home';
import { PreferencesProvider } from './preferences';
import { Screen } from './shell/Screens';
import { Shell } from './shell/Shell';
import { isChunkLoadError, markUpdated } from './shell/update';
import { strings } from './strings';
import { applyThemeTokens } from './theme';

export interface CreateConsoleOptions {
  /** What this edition adds. The open console passes none. */
  extensions?: ConsoleExtension[];
  /** The page the console runs in (tests pass their own). */
  environment?: SessionEnvironment;
  /** Makes the router's history once signed in (tests make a memory history). */
  history?: () => RouterHistory;
  /** A fixed locale for numbers and dates (tests); otherwise the device's choice or the browser's. */
  locale?: string;
}

export interface SalliConsole {
  session: ConsoleSession;
  queryClient: QueryClient;
  /** The whole console as a component, for rendering it yourself. */
  App: ComponentType;
  /** Renders the console into `element` and starts it. Returns an unmount. */
  mount(element: HTMLElement): () => void;
}

function NotFound() {
  return (
    <Page title={strings.notFound.title} description={strings.notFound.body}>
      <p>
        <a href={`${BASE_PATH}/`}>{strings.notFound.home}</a>
      </p>
    </Page>
  );
}

function RouteError({ error }: { error: unknown }) {
  useEffect(() => {
    if (isChunkLoadError(error)) markUpdated();
  }, [error]);
  if (isChunkLoadError(error)) {
    return (
      <Page title={strings.update.message}>
        <button type="button" className="button button-primary" onClick={() => window.location.reload()}>
          {strings.update.reload}
        </button>
      </Page>
    );
  }
  return (
    <Page title={strings.problem.title}>
      <ProblemView error={error} />
    </Page>
  );
}

/** A route's page: its component, or its loader's in a chunk of its own. */
function pageOf(route: ConsoleRoute): () => ReactElement {
  if (route.load) {
    const Lazy = lazy(route.load);
    return function LazyPage() {
      return (
        <Suspense fallback={<Loading lines={4} />}>
          <Lazy />
        </Suspense>
      );
    };
  }
  const Component = route.component ?? NotFound;
  return function RoutePage() {
    return <Component />;
  };
}

/** A page of an extension: only when this server runs its server half. */
function guarded(requires: string, Page: ComponentType): () => ReactElement {
  return function ExtensionPage() {
    const { enabled } = useConsoleExtensions();
    return enabled.some((extension) => extension.requires === requires) ? <Page /> : <NotFound />;
  };
}

const SettingsPage = lazy(() => import('./pages/settings/Settings'));

/**
 * The decision lab (C3): each view a chunk of its own, loaded when it is
 * opened, so the shell and Home stay within their budget.
 */
const LAB: ConsoleRoute[] = [
  { path: '/decide', load: () => import('./pages/decide/Lab') },
  { path: '/decide/templates', load: () => import('./pages/decide/Templates').then((m) => ({ default: m.TemplateList })) },
  { path: '/decide/templates/$template', load: () => import('./pages/decide/Templates') },
  { path: '/decide/scenarios', load: () => import('./pages/decide/Scenarios') },
  { path: '/decide/principles', load: () => import('./pages/decide/Principles') },
  { path: '/decide/journal', load: () => import('./pages/decide/Journal') },
  { path: '/decide/journal/$decision', load: () => import('./pages/decide/Entry') },
  { path: '/decide/baseline', load: () => import('./pages/decide/Baseline') },
];

/**
 * Where you stand (C2): the books, cash, attention and financial
 * independence, each page a chunk of its own; and More, a phone's list of
 * the places its bar has no room for.
 */
const WHERE: ConsoleRoute[] = [
  { path: '/books', load: () => import('./pages/books/Accounts') },
  { path: '/books/accounts/$account', load: () => import('./pages/books/Account') },
  { path: '/books/entries', load: () => import('./pages/books/Entries') },
  { path: '/books/entries/new', load: () => import('./pages/books/AddEntry') },
  { path: '/books/entries/$entry', load: () => import('./pages/books/Entry') },
  { path: '/cash', load: () => import('./pages/cash/Cash') },
  { path: '/attention', load: () => import('./pages/attention/Attention') },
  { path: '/fi', load: () => import('./pages/fi/Fi') },
  { path: '/more', load: () => import('./pages/more/More') },
];

/**
 * Books, tax and settings (C4): imports and review, rules, tax with its
 * rule sets, and the rest of Settings, each page a chunk of its own.
 */
const BOOKS_TAX_SETTINGS: ConsoleRoute[] = [
  { path: '/books/imports', load: () => import('./pages/books/Imports') },
  { path: '/books/imports/$statement', load: () => import('./pages/books/Review') },
  { path: '/books/rules', load: () => import('./pages/books/Rules') },
];

function Settings() {
  return (
    <Suspense fallback={<Loading lines={6} />}>
      <SettingsPage />
    </Suspense>
  );
}

function buildRouter(extensions: readonly ConsoleExtension[], history: (() => RouterHistory) | undefined) {
  const root = createRootRoute({ component: Shell, notFoundComponent: NotFound, errorComponent: RouteError });
  const pages: AnyRoute[] = [
    createRoute({ getParentRoute: () => root, path: '/', component: Home }),
    createRoute({ getParentRoute: () => root, path: '/settings', component: Settings }),
    ...[...WHERE, ...LAB, ...BOOKS_TAX_SETTINGS].map((route) => createRoute({ getParentRoute: () => root, path: route.path, component: pageOf(route) })),
  ];
  for (const extension of extensions) {
    for (const route of extension.routes ?? []) {
      pages.push(createRoute({ getParentRoute: () => root, path: route.path, component: guarded(extension.requires, pageOf(route)) }));
    }
  }
  return createRouter({
    routeTree: root.addChildren(pages),
    basepath: BASE_PATH,
    history: history ? history() : createBrowserHistory(),
    defaultPreload: false,
    scrollRestoration: true,
  });
}

/**
 * React Aria adds a <style> for its pressable elements unless one with its
 * id is already there; the CSP would refuse it. The console's stylesheet
 * has that rule (kit.css), so mark it present.
 */
export function preemptInlineStyles(doc: Document = document): void {
  const id = 'react-aria-pressable-style';
  if (doc.getElementById(id)) return;
  const marker = doc.createElement('meta');
  marker.id = id;
  marker.name = 'salli-console-styles';
  marker.content = 'React Aria\'s pressable rule is in the console\'s stylesheet.';
  doc.head.append(marker);
}

export function createConsole(options: CreateConsoleOptions = {}): SalliConsole {
  const extensions = options.extensions ?? [];
  const session = new ConsoleSession(options.environment ?? browserEnvironment());
  const queryClient = createQueryClient(session);
  let router: ReturnType<typeof buildRouter> | undefined;

  // Whatever a sign-in read stays with it.
  session.subscribe((state) => {
    if (state.status !== 'signed-in') queryClient.clear();
  });

  function Signed() {
    const value = useMemo(() => {
      const enabled = enabledExtensions(extensions, session.meta?.extensions ?? []);
      return extensionsFor(extensions, enabled);
    }, []);
    useEffect(() => {
      const theme = value.enabled.find((extension) => extension.theme)?.theme;
      if (theme) applyThemeTokens(theme);
    }, [value]);
    router ??= buildRouter(extensions, options.history);
    return (
      <ExtensionsProvider value={value}>
        <RouterProvider router={router} />
      </ExtensionsProvider>
    );
  }

  function App() {
    const state = useSyncExternalStore(
      (listener) => session.subscribe(listener),
      () => session.state,
    );
    return (
      <PreferencesProvider {...(options.locale ? { locale: options.locale } : {})}>
        <ApiProvider session={session} queryClient={queryClient}>
          {state.status === 'signed-in' ? <Signed /> : <Screen state={state} session={session} />}
        </ApiProvider>
      </PreferencesProvider>
    );
  }

  return {
    session,
    queryClient,
    App,
    mount(element) {
      preemptInlineStyles(element.ownerDocument);
      const root = createRoot(element);
      root.render(
        <StrictMode>
          <App />
        </StrictMode>,
      );
      void session.start();
      return () => root.unmount();
    },
  };
}
