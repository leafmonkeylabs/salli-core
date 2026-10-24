import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button } from '../kit';
import { useSession } from '../session';
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
            const host = server.replace(/^https?:\/\//, '');
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
                <View style={[styles.radio, { borderColor: on ? theme.text : theme.muted }]}>{on ? <View style={[styles.dot, { backgroundColor: theme.text }]} /> : null}</View>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={[styles.host, { color: theme.text }]} numberOfLines={1}>
                    {host}
                  </Text>
                  <Body small muted>
                    {on ? t.onScreen : t.signedIn}
                  </Body>
                </View>
              </Pressable>
            );
          })}
        </View>
        <View style={{ gap: 6 }}>
          <Button
            kind="secondary"
            label={t.add}
            onPress={() => {
              router.back();
              router.push('/welcome');
            }}
          />
          <Body small muted>
            {t.addHelp}
          </Body>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8, paddingTop: 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { fontFamily: font.medium, fontSize: 17 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  host: { fontFamily: font.mono, fontSize: size.body },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
