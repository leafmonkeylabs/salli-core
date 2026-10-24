import { router } from 'expo-router';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Body, Card, Icon, type IconName } from '../../kit';
import { useYourAI } from '../../ai/store';
import { useAppearance } from '../../appearance';
import { providerOf } from '../../lib/ai';
import { useSession } from '../../session';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.more;

/** The console's places the app doesn't have yet: each opens the console's own page. */
const PLACES: readonly { key: keyof typeof t.places; icon: IconName; path: string }[] = [
  { key: 'tax', icon: 'tax', path: '/tax' },
  { key: 'attention', icon: 'attention', path: '/attention' },
  { key: 'fi', icon: 'independence', path: '/fi' },
  { key: 'settings', icon: 'settings', path: '/settings' },
];

/** More (design 14): the places beyond the bar, then Servers and sign-in. */
export default function More() {
  const { session } = useSession();
  const ai = useYourAI();
  const { appearance } = useAppearance();
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  const host = session.status === 'signed-in' ? session.server.replace(/^https?:\/\//, '') : '';

  return (
    <Page title={t.title}>
      {consoleUrl ? (
        <Card style={{ paddingVertical: 4 }}>
          {PLACES.map((place, i) => (
            <Place
              key={place.key}
              icon={place.icon}
              title={t.places[place.key].title}
              body={t.places[place.key].body}
              label={t.inConsole(t.places[place.key].title)}
              external
              onPress={() => void Linking.openURL(`${consoleUrl}${place.path}`)}
              last={i === PLACES.length - 1}
            />
          ))}
        </Card>
      ) : null}
      <Card style={{ paddingVertical: 4 }}>
        <Place icon="ai" title={strings.ai.title} body={!ai.enabled ? strings.ai.off : ai.model ? `${ai.model} · ${providerOf(ai.provider)?.name ?? ''}` : strings.ai.notSet} onPress={() => router.push('/ai')} />
        <Place icon="message" title={t.automationsPlace} body={t.automationsBody} onPress={() => router.push('/automations')} />
        <Place icon="appearance" title={strings.appearance.title} body={strings.appearance.names[appearance.theme]} onPress={() => router.push('/appearance')} />
        <Place icon="server" title={t.serversPlace} body={t.serversBody(host)} onPress={() => router.push('/sign-ins')} last />
      </Card>
      <Body small muted>
        {t.footer}
      </Body>
    </Page>
  );
}

function Place({ icon, title, body, label, external, onPress, last }: { icon: IconName; title: string; body: string; label?: string; external?: boolean; onPress: () => void; last?: boolean }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={label ?? title}
      accessibilityHint={body}
      onPress={onPress}
      style={[styles.place, last ? null : { borderBottomColor: theme.rule, borderBottomWidth: StyleSheet.hairlineWidth }]}
    >
      <Icon name={icon} size={22} colour={theme.text} />
      <View style={{ flex: 1, gap: 2 }}>
        <Body style={styles.title}>{title}</Body>
        <Body small muted>
          {body}
        </Body>
      </View>
      <Icon name={external ? 'external' : 'chevron'} size={16} colour={theme.muted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  place: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 64, paddingVertical: 12 },
  title: { fontFamily: font.medium, fontSize: size.body },
});
