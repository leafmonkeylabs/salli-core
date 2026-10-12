/**
 * A place's own places, under the page's title: a second row of links, the
 * current one marked (the decision lab's, the books'). The console's own
 * navigation names the place; this names what is inside it.
 */
import { Link } from '@tanstack/react-router';

export interface SubPlace {
  to: string;
  label: string;
  /** Current only on exactly this path (an overview), not below it. */
  exact?: boolean;
}

export function SubNav({ label, places }: { label: string; places: readonly SubPlace[] }) {
  return (
    <nav aria-label={label} className="subnav">
      <ul>
        {places.map((place) => (
          <li key={place.to}>
            <Link to={place.to} activeOptions={{ exact: place.exact ?? false }} activeProps={{ 'aria-current': 'page' }}>
              {place.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
