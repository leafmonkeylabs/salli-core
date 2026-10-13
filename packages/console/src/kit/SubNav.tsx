/**
 * A place's own places, under the page's header (the decision lab's, the
 * books', Settings'): a segmented row of links on a bone track, the
 * current one raised on paper. The console's side menu names the place;
 * this names what is inside it. No single-key shortcuts: the console has
 * none (WCAG 2.1.4), so it shows none.
 */
import { Link, useRouterState } from '@tanstack/react-router';
import { appPath, isCurrent, type SubPlace } from '../shell/places';

export type { SubPlace };

/** TanStack marks a link current below its path too; the console says which itself. */
const EXACT = { exact: true } as const;

export function SubNav({ label, places }: { label: string; places: readonly SubPlace[] }) {
  const path = appPath(useRouterState({ select: (state) => state.location.pathname }));
  return (
    <nav aria-label={label} className="subnav">
      <ul>
        {places.map((place) => (
          <li key={place.to}>
            <Link to={place.to} activeOptions={EXACT} {...(isCurrent(place, path) ? { 'aria-current': 'page' as const } : {})}>
              {place.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
