import { router } from 'expo-router';
import { Linking } from 'react-native';
import type { ReactNode } from 'react';
import { Icon, Row, Section, Surface, type IconName } from '../../kit';
import { usePanelPlaces } from '../../panel';
import { useYourAI } from '../../ai/store';
import { useAppearance } from '../../appearance';
import { providerOf } from '../../lib/ai';
import { useSession, labelIn } from '../../session';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { size, useTheme } from '../../theme';

const t = strings.more;

/** The console's places the app doesn't have yet: each opens the console's own page. */
const PLACES: readonly { key: keyof typeof t.places; icon: IconName; path: string }[] = [
  { key: 'tax', icon: 'tax', path: '/tax' },
  { key: 'settings', icon: 'settings', path: '/settings' },
];

/** More (designs 14 and 31): this phone's places, then the console's, as tiles. */
export default function More() {
  const { session } = useSession();
  const ai = useYourAI();
  const { appearance } = useAppearance();
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  const host = session.status === 'signed-in' ? labelIn(session, session.server) : '';

  const places = [...usePanelPlaces('more'), ...usePanelPlaces('settings')];
  const status = !ai.enabled ? strings.ai.off : (ai.model ?? strings.ai.notSet);
  return (
    <Page title={t.title}>
      <Group>
        <Item icon="spark" title={strings.ai.title} detail={status} hint={ai.model ? `${ai.model} · ${providerOf(ai.provider)?.name ?? ''}` : undefined} onPress={() => router.push('/ai')} />
        <Item icon="message" title={t.automationsPlace} detail={t.automationsBody} onPress={() => router.push('/automations')} />
        <Item icon="appearance" title={strings.appearance.title} detail={strings.appearance.names[appearance.theme]} onPress={() => router.push('/appearance')} />
        <Item icon="attention" title={strings.notifications.title} onPress={() => router.push('/notifications')} last />
      </Group>

      <Section title={t.groups.books}>
        <Group>
          <Item icon="independence" title={strings.fi.title} onPress={() => router.push('/fi')} />
          <Item icon="attention" title={strings.attention.title} onPress={() => router.push('/attention')} last={!places.length} />
          {/* Pages the server describes, titled by it. */}
          {places.map((panel, i) => (
            <Item key={panel.id} icon="settings" title={panel.title} onPress={() => router.push({ pathname: '/panel/[id]', params: { id: panel.id } })} last={i === places.length - 1} />
          ))}
        </Group>
      </Section>

      <Section title={t.groups.server}>
        <Group>
          <Item icon="server" title={t.serversPlace} detail={host} hint={t.serversBody(host)} onPress={() => router.push('/sign-ins')} last />
        </Group>
      </Section>

      {consoleUrl ? (
        <Section title={t.groups.console}>
          <Group>
            {PLACES.map((place, i) => (
              <Item
                key={place.key}
                icon={place.icon}
                title={t.places[place.key].title}
                detail={t.places[place.key].body}
                hint={t.inConsole(t.places[place.key].title)}
                external
                onPress={() => void Linking.openURL(`${consoleUrl}${place.path}`)}
                last={i === PLACES.length - 1}
              />
            ))}
          </Group>
        </Section>
      ) : null}
    </Page>
  );
}

/** A grouped list: one surface, its rows set in from the edges, a line between them. */
function Group({ children }: { children: ReactNode }) {
  return (
    <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
      {children}
    </Surface>
  );
}

/** A place as a row: an icon on a tile, its title, a word on how it stands; one in the console says so with an arrow. */
function Item({ icon, title, detail, hint, external, last, onPress }: { icon: IconName; title: string; detail?: string; hint?: string; external?: boolean; last?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Row
      icon={icon}
      title={title}
      {...(detail ? { detail } : {})}
      {...(hint ? { hint } : {})}
      {...(external ? { action: <Icon name="external" size={16} colour={theme.muted} /> } : {})}
      {...(last ? { last } : {})}
      onPress={onPress}
    />
  );
}

