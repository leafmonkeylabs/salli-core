/**
 * The frame every page sits in: a skip link, the logo, the places (the
 * console's own and those extensions add), who is signed in and Sign out; a
 * bottom bar of five places on phones (Home, Cash, Decide, Books and More,
 * where the rest are). It also keeps the tab's two watches: the idle
 * sign-out, and whether Salli was updated under an open tab.
 */
import { Link, Outlet, useRouter, useRouterState } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { useSession } from '../api';
import { idleLimitMs, startIdleTimer } from '../auth/idle';
import { useConsoleExtensions } from '../console-context';
import { Logo } from '../kit/Logo';
import { strings } from '../strings';
import { useServerVersion } from './update';

interface Place {
  to: string;
  label: string;
  icon: 'home' | 'cash' | 'decide' | 'books' | 'more' | 'settings' | 'page';
}

/** The places a phone's bar holds; every other place is under More. */
const BAR = ['/', '/cash', '/decide', '/books'];

/** Whether `pathname` (under /console) is at `to` or below it. */
function within(pathname: string, to: string): boolean {
  const path = pathname.replace(/^\/console/, '') || '/';
  return to === '/' ? path === '/' : path === to || path.startsWith(`${to}/`);
}

function Icon({ name }: { name: Place['icon'] }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
      {name === 'home' ? <path d="M4 11 12 4l8 7v9h-5v-6H9v6H4z" /> : null}
      {name === 'decide' ? (
        <>
          <path d="M12 3v18M7 21h10" />
          <path d="M4 7h16" />
          <path d="M4 7l-2 6h4zM20 7l-2 6h4z" />
        </>
      ) : null}
      {name === 'cash' ? (
        <>
          <rect x="3" y="6" width="18" height="12" />
          <path d="M3 10h18M7 14h3" />
        </>
      ) : null}
      {name === 'books' ? (
        <>
          <path d="M5 4h11l3 3v13H5z" />
          <path d="M8 10h8M8 14h8M8 18h5" />
        </>
      ) : null}
      {name === 'more' ? <path d="M4 7h16M4 12h16M4 17h16" /> : null}
      {name === 'settings' ? (
        <>
          <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
          <rect x="14" y="5" width="4" height="4" />
          <rect x="6" y="15" width="4" height="4" />
        </>
      ) : null}
      {name === 'page' ? <rect x="5" y="4" width="14" height="16" /> : null}
    </svg>
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

export function Shell() {
  const session = useSession();
  const router = useRouter();
  const { navigation } = useConsoleExtensions();
  const main = useRef<HTMLElement>(null);

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

  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const places: Place[] = [
    { to: '/', label: strings.nav.home, icon: 'home' },
    { to: '/cash', label: strings.nav.cash, icon: 'cash' },
    { to: '/decide', label: strings.nav.decide, icon: 'decide' },
    { to: '/books', label: strings.nav.books, icon: 'books' },
    { to: '/attention', label: strings.nav.attention, icon: 'page' },
    { to: '/fi', label: strings.nav.fi, icon: 'page' },
    ...navigation.map((item) => ({ to: item.to, label: item.label, icon: 'page' as const })),
    { to: '/settings', label: strings.nav.settings, icon: 'settings' },
  ];
  const bar: Place[] = [...places.filter((place) => BAR.includes(place.to)), { to: '/more', label: strings.nav.more, icon: 'more' }];
  // More is the current place for any page the bar doesn't name.
  const inMore = !BAR.some((to) => within(pathname, to));
  const email = session.state.status === 'signed-in' ? session.state.user.email : '';

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        {strings.skipToContent}
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand-link" aria-label={`${strings.product}, ${strings.nav.home}`}>
            <Logo />
          </Link>
          <nav aria-label={strings.nav.label} className="topnav">
            <ul>
              {places.map((place) => (
                <li key={place.to}>
                  <Link to={place.to} activeOptions={{ exact: place.to === '/' }} activeProps={{ 'aria-current': 'page' }}>
                    {place.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="topbar-user">
            {email ? <span className="muted user-email">{strings.nav.signedInAs(email)}</span> : null}
            <button type="button" className="button button-secondary" onClick={() => void session.signOut('signed-out')}>
              {strings.nav.signOut}
            </button>
          </div>
        </div>
      </header>
      <UpdateBanner />
      <Notice />
      <main id="main" ref={main} tabIndex={-1}>
        <Outlet />
      </main>
      <nav aria-label={strings.nav.label} className="bottombar">
        <ul>
          {bar.map((place) => (
            <li key={place.to}>
              <Link
                to={place.to}
                activeOptions={{ exact: place.to === '/' }}
                activeProps={{ 'aria-current': 'page' }}
                {...(place.to === '/more' && inMore ? { 'aria-current': 'page' as const } : {})}
              >
                <Icon name={place.icon} />
                <span>{place.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
