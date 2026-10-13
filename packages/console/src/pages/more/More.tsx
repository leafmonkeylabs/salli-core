/**
 * More: the places a phone's bar of five has no room for (Attention,
 * financial independence, any an edition adds, Settings), each with what
 * it holds. On a wide screen every place is in the top bar as well.
 */
import { Link } from '@tanstack/react-router';
import { useConsoleExtensions } from '../../console-context';
import { Page } from '../../kit/layout';
import { strings } from '../../strings';

export function More() {
  const { navigation } = useConsoleExtensions();
  const places = [
    { to: '/attention', label: strings.nav.attention },
    { to: '/fi', label: strings.nav.fi },
    ...navigation.map((item) => ({ to: item.to, label: item.label })),
    { to: '/settings', label: strings.nav.settings },
  ];
  return (
    <Page title={strings.more.title} description={strings.more.description}>
      <ul className="list places">
        {places.map((place) => (
          <li key={place.to}>
            <Link to={place.to} className="strong-link">
              {place.label}
            </Link>
            {strings.more.places[place.to] ? <p className="muted">{strings.more.places[place.to]}</p> : null}
          </li>
        ))}
      </ul>
    </Page>
  );
}

export default More;
