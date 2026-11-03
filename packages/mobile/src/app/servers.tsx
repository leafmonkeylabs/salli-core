import { router } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Button, Option, Surface } from '../kit';
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
    <View style={{ flex: 1, backgroundColor: theme.ground }}>
      <View style={[styles.header, { paddingTop: 16 }]}>
        <View style={styles.headerButton} />
        <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
          {t.title}
        </Text>
        <View style={styles.headerButton}>
          <Button kind="tertiary" small label={t.close} onPress={() => router.back()} />
        </View>
      </View>
      <ScrollView contentContainerStyle={{ padding: size.gutter, gap: 20, paddingBottom: insets.bottom + 24 }} accessibilityRole="radiogroup">
        <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
          {session.servers.map((server, i) => {
            const on = server === session.server;
            const host = labelIn(session, server);
            return (
              <Option
                key={server}
                last={i === session.servers.length - 1}
                label={host}
                detail={on ? t.onScreen : t.signedIn}
                chosen={on}
                accessibilityLabel={on ? `${host}, ${t.onScreen}` : t.switchTo(host)}
                onPress={() => {
                  void switchTo(server);
                  router.back();
                }}
              />
            );
          })}
        </Surface>
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
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: size.gutter },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', alignItems: 'flex-end' },
  headerTitle: { fontFamily: font.semibold, fontSize: size.title },
});
