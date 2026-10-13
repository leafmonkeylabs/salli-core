/**
 * Settings' own places, under each Settings page's title: the profile and
 * sign-ins (C1), then tokens, AI connections, digests and your data (C4).
 */
import { SubNav } from '../../kit/SubNav';
import { strings } from '../../strings';

const p = strings.settings.places;

export const SETTINGS_PLACES = [
  { to: '/settings', label: p.profile, exact: true },
  { to: '/settings/tokens', label: p.tokens, exact: true },
  { to: '/settings/ai', label: p.ai, exact: true },
  { to: '/settings/digests', label: p.digests, exact: true },
  { to: '/settings/data', label: p.data, exact: true },
] as const;

export function SettingsNav() {
  return <SubNav label={p.label} places={SETTINGS_PLACES} />;
}
