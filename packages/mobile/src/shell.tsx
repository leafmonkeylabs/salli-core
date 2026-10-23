/**
 * The frame around a place: the bar at the top (which server, and adding an
 * entry), and a place still to come, which says where it is meanwhile.
 */
import { useState, type ReactNode } from 'react';
import { Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Card, Icon, Title } from './kit';
import { useSession } from './session';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

/** The top bar: a way back, or on Home the server you are on; one action; a place's title. */
export function Header({ title, server, back, action }: { title?: string; server?: boolean; back?: { label: string; onPress: () => void }; action?: ReactNode }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session } = useSession();
  const host = session.status === 'signed-in' ? session.server.replace(/^https?:\/\//, '') : '';
  const lead = back ? (
    <BackLink label={back.label} onPress={back.onPress} />
  ) : server ? (
    <View accessible accessibilityLabel={strings.home.switchServer(host)} style={styles.server}>
      <Text style={[styles.host, { color: theme.text }]} numberOfLines={1}>
        {host}
      </Text>
    </View>
  ) : null;
  return (
    <View style={[styles.header, { paddingTop: insets.top, backgroundColor: theme.chrome, borderBottomColor: theme.rule }]}>
      {lead || action ? (
        <View style={styles.bar}>
          {lead ?? <View />}
          {action}
        </View>
      ) : null}
      {title ? (
        <View style={styles.titleBox}>
          <Title>{title}</Title>
        </View>
      ) : null}
    </View>
  );
}

/**
 * Pulling down to read again. The spinner is the person's pull only: a read
 * that runs again after a change, in the background, doesn't show it.
 */
export function Pull({ read }: { read: () => Promise<unknown> }) {
  const [pulling, setPulling] = useState(false);
  return (
    <RefreshControl
      refreshing={pulling}
      onRefresh={() => {
        setPulling(true);
        void read().finally(() => setPulling(false));
      }}
    />
  );
}

/** A place: its header, then its cards, pulled down to read again. */
export function Page({
  title,
  back,
  action,
  children,
  onRefresh,
}: {
  title?: string;
  back?: { label: string; onPress: () => void };
  action?: ReactNode;
  children: ReactNode;
  onRefresh?: () => Promise<unknown>;
}) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Header {...(title ? { title } : {})} {...(back ? { back } : {})} action={action} />
      <ScrollView
        contentContainerStyle={styles.page}
        keyboardShouldPersistTaps="handled"
        refreshControl={onRefresh ? <Pull read={onRefresh} /> : undefined}
      >
        {children}
      </ScrollView>
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
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: size.target },
  server: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 8 },
  host: { fontFamily: font.mono, fontSize: size.small },
  titleBox: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 8, paddingBottom: 8 },
  page: { padding: size.gutter, gap: size.gap },
  back: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingRight: 12 },
});
