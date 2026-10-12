/**
 * The decision lab's own places, under the page's title: a second row of
 * links (the lab is one place in the console's navigation, "Decide").
 */
import { Link } from '@tanstack/react-router';
import { labStrings } from '../../lab-strings';

const n = labStrings.nav;

export const LAB_PLACES = [
  { to: '/decide', label: n.overview, exact: true },
  { to: '/decide/templates', label: n.templates, exact: false },
  { to: '/decide/scenarios', label: n.scenarios, exact: false },
  { to: '/decide/principles', label: n.principles, exact: false },
  { to: '/decide/journal', label: n.journal, exact: false },
  { to: '/decide/baseline', label: n.baseline, exact: false },
] as const;

/** Where a journal entry is. */
export function journalPath(id: string): string {
  return `/decide/journal/${encodeURIComponent(id)}`;
}

/** Where a template's questions are. */
export function templatePath(id: string): string {
  return `/decide/templates/${encodeURIComponent(id)}`;
}

export function LabNav() {
  return (
    <nav aria-label={n.label} className="subnav">
      <ul>
        {LAB_PLACES.map((place) => (
          <li key={place.to}>
            <Link to={place.to} activeOptions={{ exact: place.exact }} activeProps={{ 'aria-current': 'page' }}>
              {place.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
