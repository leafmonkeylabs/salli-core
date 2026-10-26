import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon } from '../kit';
import { useSession, labelIn } from '../session';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.servers;

/** The servers this phone is signed in to: one on screen, the others a tap away. */
export default function Servers() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session, switchTo } = useSession();
  if (session.status !== 'signed-in') return null;

  return (
    <View style={{ flex: 1, backgroundColor: theme.chrome }}>
      <View style={[styles.header, { borderBottomColor: theme.rule }]}>
        <View style={styles.headerButton} />
        <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
          {t.title}
        </Text>
        <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.headerButton}>
          <Body style={{ textAlign: 'right' }}>{t.close}</Body>
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={{ padding: size.gutter, gap: 20, paddingBottom: insets.bottom + 24 }} accessibilityRole="radiogroup">
        <View>
          {session.servers.map((server) => {
            const on = server === session.server;
            const host = labelIn(session, server);
            const named = session.known.some((k) => k.server === server && k.name);
            return (
              <Pressable
                key={server}
                accessibilityRole="radio"
                accessibilityState={{ checked: on }}
                accessibilityLabel={on ? `${host}, ${t.onScreen}` : t.switchTo(host)}
                onPress={() => {
                  void switchTo(server);
                  router.back();
                }}
                style={[styles.option, { borderBottomColor: theme.rule }]}
              >
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={[styles.host, named ? styles.name : null, { color: theme.text }]} numberOfLines={1}>
                    {host}
                  </Text>
                  <Body small muted>
                    {on ? t.onScreen : t.signedIn}
                  </Body>
                </View>
                {on ? <Icon name="check" size={20} colour={theme.text} /> : null}
              </Pressable>
            );
          })}
        </View>
        <View style={{ gap: 6 }}>
          <Button
            kind="secondary"
            label={t.add}
            accessibilityHint={t.addHelp}
            onPress={() => {
              router.back();
              router.push('/welcome');
            }}
          />
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  name: { fontFamily: font.medium },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8, paddingTop: 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { fontFamily: font.medium, fontSize: 17 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  host: { fontFamily: font.mono, fontSize: size.body },
});
