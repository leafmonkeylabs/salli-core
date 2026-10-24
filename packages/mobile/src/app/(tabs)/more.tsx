import { router } from 'expo-router';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { cardOf, Icon, type IconName } from '../../kit';
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
  { key: 'settings', icon: 'settings', path: '/settings' },
];

/** More (designs 14 and 31): this phone's places, then the console's, as tiles. */
export default function More() {
  const { session } = useSession();
  const ai = useYourAI();
  const { appearance } = useAppearance();
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  const host = session.status === 'signed-in' ? session.server.replace(/^https?:\/\//, '') : '';

  const status = !ai.enabled ? strings.ai.off : (ai.model ?? strings.ai.notSet);
  return (
    <Page title={t.title}>
      <View style={styles.grid}>
        <Tile icon="ai" title={strings.ai.title} status={status} hint={ai.model ? `${ai.model} · ${providerOf(ai.provider)?.name ?? ''}` : undefined} onPress={() => router.push('/ai')} />
        <Tile icon="message" title={t.automationsPlace} hint={t.automationsBody} onPress={() => router.push('/automations')} />
        <Tile icon="appearance" title={strings.appearance.title} status={strings.appearance.names[appearance.theme]} onPress={() => router.push('/appearance')} />
        <Tile icon="server" title={t.serversShort} status={host} hint={t.serversBody(host)} onPress={() => router.push('/sign-ins')} />
        <Tile icon="independence" title={strings.fi.title} onPress={() => router.push('/fi')} />
        {consoleUrl
          ? PLACES.map((place) => (
              <Tile
                key={place.key}
                icon={place.icon}
                title={t.places[place.key].title}
                label={t.inConsole(t.places[place.key].title)}
                hint={t.places[place.key].body}
                external
                onPress={() => void Linking.openURL(`${consoleUrl}${place.path}`)}
              />
            ))
          : null}
      </View>
    </Page>
  );
}

/** A place as a tile: its icon, its title, and a word on how it stands; one in the console says so with ↗. */
function Tile({ icon, title, status, label, hint, external, onPress }: { icon: IconName; title: string; status?: string; label?: string; hint?: string; external?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={[label ?? title, status].filter(Boolean).join(', ')}
      {...(hint ? { accessibilityHint: hint } : {})}
      onPress={onPress}
      style={({ pressed }) => [styles.tile, cardOf(theme), { opacity: pressed ? 0.8 : 1 }]}
    >
      <View style={styles.tileTop}>
        <Icon name={icon} size={24} colour={theme.text} />
        {external ? <Icon name="external" size={14} colour={theme.muted} /> : null}
      </View>
      <View style={{ gap: 2 }}>
        <Text style={[styles.tileTitle, { color: theme.text }]} numberOfLines={1}>
          {title}
        </Text>
        {status ? (
          <Text style={[styles.tileStatus, { color: theme.muted }]} numberOfLines={1}>
            {status}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tile: { flexBasis: '48%', flexGrow: 1, minHeight: 104, padding: 14, justifyContent: 'space-between', gap: 14 },
  tileTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  tileTitle: { fontFamily: font.medium, fontSize: size.body },
  tileStatus: { fontFamily: font.regular, fontSize: 13 },
});
