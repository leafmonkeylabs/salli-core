/**
 * The frame every page sits in (C5): a skip link; a 56 px top bar with the
 * logo, the server and its version, the theme and who is signed in; a
 * side menu of the places (the current place's own places under it, a
 * count beside Attention), which folds to a rail of icons; a bar under the
 * top one with the side menu's switch, the way back and where you are;
 * then the page. On a phone the side menu gives way to the bottom bar of
 * five places (Home, Cash, Decide, Books and More, where the rest are), as
 * the design decided. It also keeps the tab's two watches: the idle
 * sign-out, and whether Salli was updated under an open tab.
 */
import { insightsSignals, profileGet } from '@leafmonkeylabs/salli-sdk';
import { Link, Outlet, useRouter, useRouterState } from '@tanstack/react-router';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useRead, useSession } from '../api';
import { idleLimitMs, startIdleTimer } from '../auth/idle';
import { useConsoleExtensions } from '../console-context';
import { Count } from '../kit/chips';
import { Icon, type IconName } from '../kit/Icon';
import { Logo } from '../kit/Logo';
import { Popover } from '../kit/Popover';
import { usePreferences } from '../preferences';
import { strings } from '../strings';
import { ShellContext, type ShellPage } from './context';
import { appPath, crumbsOf, isCurrent, placesOf, within, type Crumb, type Place } from './places';
import { useServerVersion } from './update';

/** The places a phone's bar holds; every other place is under More. */
const BAR = ['/', '/cash', '/decide', '/books'];
/** TanStack marks a link current below its path too; the console says which itself. */
const EXACT = { exact: true } as const;

/** Whether a media query matches, following it as it changes. */
function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (listener) => {
      const list = globalThis.matchMedia?.(query);
      list?.addEventListener('change', listener);
      return () => list?.removeEventListener('change', listener);
    },
    () => globalThis.matchMedia?.(query).matches ?? false,
  );
}

function Notice() {
  const session = useSession();
  const [notice, setNotice] = useState(session.notice);
  if (!notice || session.state.status !== 'signed-in') return null;
  const text = notice.kind === 'different-person' ? strings.signIn.differentPerson(session.state.user.email) : strings.signIn.stepUpCancelled;
  return (
    <div className="banner" role="status">
      <p>{text}</p>
      <button
        type="button"
        className="button-link"
        onClick={() => {
          session.notice = undefined;
          setNotice(undefined);
        }}
      >
        {strings.dismiss}
      </button>
    </div>
  );
}

function UpdateBanner() {
  const updated = useServerVersion();
  if (!updated) return null;
  return (
    <div className="banner" role="alert">
      <p>{strings.update.message}</p>
      <button type="button" className="button button-primary" onClick={() => window.location.reload()}>
        {strings.update.reload}
      </button>
    </div>
  );
}

/** Light or dark, the other way from how the page looks now. */
function ThemeSwitch() {
  const { theme, setTheme } = usePreferences();
  const systemDark = useMedia('(prefers-color-scheme: dark)');
  const dark = theme === 'dark' || (theme === 'system' && systemDark);
  return (
    <button type="button" className="icon-button" aria-label={dark ? strings.shell.useLight : strings.shell.useDark} onClick={() => setTheme(dark ? 'light' : 'dark')}>
      <Icon name={dark ? 'sun' : 'moon'} />
    </button>
  );
}

/** Who is signed in: their initial and name, and a panel with Settings and Sign out. */
function You() {
  const session = useSession();
  const profile = useRead('profile.get', profileGet);
  const email = session.state.status === 'signed-in' ? session.state.user.email : '';
  const name = profile.data?.display_name?.trim() || email;
  const initial = (name || strings.shell.you).charAt(0).toUpperCase();
  return (
    <Popover
      label={strings.shell.you}
      align="end"
      role="group"
      className="you"
      trigger={(props) => (
        <button {...props} className="you-button">
          <span className="avatar" aria-hidden="true">
            {initial}
          </span>
          <span className="you-name" aria-hidden="true">
            {name}
          </span>
          <span className="sr-only">{strings.shell.youAre(name, email)}</span>
          <Icon name="down" small />
        </button>
      )}
    >
      {(close) => (
        <>
          <p className="you-email">{strings.nav.signedInAs(email)}</p>
          <Link to="/settings" className="menu-item" activeOptions={EXACT} onClick={close}>
            <Icon name="settings" small />
            {strings.nav.settings}
          </Link>
          <button type="button" className="menu-item" onClick={() => void session.signOut('signed-out')}>
            <Icon name="back" small />
            {strings.nav.signOut}
          </button>
        </>
      )}
    </Popover>
  );
}

function PlaceLink({ place, path, count }: { place: Place; path: string; count?: number }) {
  const current = within(path, place.to);
  return (
    <Link to={place.to} className="side-link" activeOptions={EXACT} title={place.label} {...(current ? { 'aria-current': 'page' as const } : {})}>
      <Icon name={place.icon} />
      <span className="side-label">{place.label}</span>
      {count ? <Count n={count} words={strings.shell.signals(count)} /> : null}
    </Link>
  );
}

function Side({ places, path, expanded, id }: { places: readonly Place[]; path: string; expanded: boolean; id: string }) {
  const signals = useRead('insights.signals', insightsSignals);
  const waiting = signals.data?.signals.length ?? 0;
  const groups = [0, 1, 2, 3].map((group) => places.filter((place) => place.group === group));
  return (
    <nav id={id} aria-label={strings.nav.label} className="side">
      <div className="side-inner">
        {groups.map((group, i) =>
          group.length ? (
            <ul key={i} className={i === 3 ? 'side-group side-foot-group' : 'side-group'}>
              {group.map((place) => (
                <li key={place.to}>
                  <PlaceLink place={place} path={path} {...(place.to === '/attention' ? { count: waiting } : {})} />
                  {expanded && place.children && within(path, place.to) ? (
                    <ul className="side-subs">
                      {place.children.map((sub) => (
                        <li key={sub.to}>
                          <Link to={sub.to} className="side-sub" activeOptions={EXACT} {...(isCurrent(sub, path) ? { 'aria-current': 'page' as const } : {})}>
                            {sub.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null,
        )}
        <p className="side-foot">{strings.shell.foot}</p>
      </div>
    </nav>
  );
}

function Crumbs({ crumbs }: { crumbs: readonly Crumb[] }) {
  return (
    <div className="crumbs">
      <ol>
        {crumbs.map((crumb, i) => (
          <li key={`${i}-${crumb.label}`}>
            {i > 0 ? (
              <span className="crumb-sep" aria-hidden="true">
                <Icon name="right" small />
              </span>
            ) : null}
            {crumb.to ? (
              <Link to={crumb.to} activeOptions={EXACT}>
                {crumb.label}
              </Link>
            ) : (
              <span aria-current="page" className="crumb-here">
                {crumb.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

const BAR_ICONS: Record<string, IconName> = { '/': 'home', '/cash': 'cash', '/decide': 'decide', '/books': 'books', '/more': 'more' };

export function Shell() {
  const session = useSession();
  const router = useRouter();
  const { navigation } = useConsoleExtensions();
  const { side, setSide } = usePreferences();
  const main = useRef<HTMLElement>(null);
  const wide = useMedia('(min-width: 1081px)');

  useEffect(() => {
    const timer = startIdleTimer(() => void session.signOut('idle'), idleLimitMs(session.env.storage));
    return () => timer.stop();
  }, [session]);

  // A new page (not the first): focus its region, so a screen reader and
  // the keyboard start there.
  useEffect(() => {
    const first = router.state.location.href;
    return router.subscribe('onResolved', ({ pathChanged, toLocation }) => {
      if (pathChanged && toLocation.href !== first) main.current?.focus({ preventScroll: true });
    });
  }, [router]);

  const path = appPath(useRouterState({ select: (state) => state.location.pathname }));
  const places = useMemo(() => placesOf(navigation), [navigation]);
  const [page, setPage] = useState<{ title: string; trail: readonly Crumb[] }>({ title: '', trail: [] });
  const report = useCallback<ShellPage['report']>((title, trail) => {
    setPage((was) => (was.title === title && JSON.stringify(was.trail) === JSON.stringify(trail) ? was : { title, trail }));
  }, []);
  const shell = useMemo(() => ({ places, report }), [places, report]);
  const crumbs = crumbsOf(path, places, page.title, page.trail);
  const parent = crumbs.length > 1 ? crumbs[crumbs.length - 2] : undefined;
  const expanded = side === 'auto' ? wide : side === 'open';

  const bar = [...BAR.flatMap((to) => places.filter((place) => place.to === to)), { to: '/more', label: strings.nav.more }];
  // More is the current place for any page the bar doesn't name.
  const inMore = !BAR.some((to) => within(path, to));
  const host = typeof window === 'undefined' ? '' : window.location.host;
  const version = session.meta?.server_version ?? '';

  return (
    <ShellContext.Provider value={shell}>
      <div className="shell" data-side={expanded ? 'open' : 'rail'}>
        <a className="skip-link" href="#main">
          {strings.skipToContent}
        </a>
        <header className="topbar">
          <Link to="/" activeOptions={EXACT} className="brand-link" aria-label={`${strings.product}, ${strings.nav.home}`}>
            <Logo />
          </Link>
          {host ? (
            <>
              <span className="topbar-slash" aria-hidden="true">
                /
              </span>
              <span className="server" title={strings.shell.server(host, version)}>
                <span className="mono">{host}</span>
                {version ? <span className="chip chip-id">{version}</span> : null}
              </span>
            </>
          ) : null}
          <span className="topbar-gap" />
          <ThemeSwitch />
          <You />
        </header>
        <div className="shell-body">
          <Side places={places} path={path} expanded={expanded} id="side" />
          <div className="shell-main">
            <nav className="crumbbar" aria-label={strings.shell.breadcrumb}>
              <button
                type="button"
                className="icon-button icon-button-bare side-switch"
                aria-expanded={expanded}
                aria-controls="side"
                aria-label={expanded ? strings.shell.hideSide : strings.shell.showSide}
                onClick={() => setSide(expanded ? 'closed' : 'open')}
              >
                <Icon name="sidebar" />
              </button>
              {parent?.to ? (
                <Link to={parent.to} activeOptions={EXACT} className="icon-button icon-button-bare" aria-label={strings.shell.backTo(parent.label)}>
                  <Icon name="back" />
                </Link>
              ) : null}
              <Crumbs crumbs={crumbs} />
            </nav>
            <UpdateBanner />
            <Notice />
            <main id="main" ref={main} tabIndex={-1}>
              <Outlet />
            </main>
          </div>
        </div>
        <nav aria-label={strings.nav.label} className="bottombar">
          <ul>
            {bar.map((place) => {
              const current = place.to === '/more' ? inMore : within(path, place.to);
              return (
                <li key={place.to}>
                  <Link to={place.to} activeOptions={EXACT} {...(current ? { 'aria-current': 'page' as const } : {})}>
                    <Icon name={BAR_ICONS[place.to] ?? 'page'} />
                    <span>{place.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </ShellContext.Provider>
  );
}
