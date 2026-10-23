/**
 * The frame around a place: the bar at the top (which server, and adding an
 * entry), and a place still to come, which says where it is meanwhile.
 */
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Card, Icon, Title } from './kit';
import { useSession } from './session';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

/** The top bar: a place's title, or on Home the server you are on. */
export function Header({ title, server }: { title?: string; server?: boolean }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session } = useSession();
  const host = session.status === 'signed-in' ? session.server.replace(/^https?:\/\//, '') : '';
  return (
    <View style={[styles.header, { paddingTop: insets.top, backgroundColor: theme.chrome, borderBottomColor: theme.rule }]}>
      {server ? (
        <View accessible accessibilityLabel={strings.home.switchServer(host)} style={styles.server}>
          <Text style={[styles.host, { color: theme.text }]} numberOfLines={1}>
            {host}
          </Text>
        </View>
      ) : (
        <View style={styles.titleBox}>
          <Title>{title ?? ''}</Title>
        </View>
      )}
    </View>
  );
}

/** A place the app doesn't have yet: the console has it, on this server. */
export function Later({ title }: { title: string }) {
  const theme = useTheme();
  const { session } = useSession();
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Header title={title} />
      <ScrollView contentContainerStyle={styles.page}>
        <Card style={{ gap: 12 }}>
          <Body>{strings.later.body}</Body>
          {consoleUrl ? <Button kind="secondary" label={strings.later.open} onPress={() => void Linking.openURL(consoleUrl)} /> : null}
        </Card>
      </ScrollView>
    </View>
  );
}

export function BackLink({ label, onPress }: { label: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable accessibilityRole="link" onPress={onPress} style={styles.back}>
      <Icon name="back" colour={theme.text} />
      <Body>{label}</Body>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: { borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8 },
  server: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 8 },
  host: { fontFamily: font.mono, fontSize: size.small },
  titleBox: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 8, paddingBottom: 8 },
  page: { padding: size.gutter, gap: size.gap },
  back: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingRight: 12 },
});
