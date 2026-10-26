/**
 * The frame around a place: the bar at the top (which server, and adding an
 * entry), and a place still to come, which says where it is meanwhile.
 */
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, RadialGradient, Rect, Stop } from 'react-native-svg';
import { useYourAI } from './ai/store';
import { Body, Button, Card, Icon, Title, useLargeText } from './kit';
import { useSession, labelIn } from './session';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

/** The top bar: a way back, or on Home the server you are on; one action; a place's title. */
export function Header({ title, server, unreachable, back, action }: { title?: string; server?: boolean; unreachable?: boolean; back?: { label: string; onPress: () => void }; action?: ReactNode }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session } = useSession();
  const host = session.status === 'signed-in' ? labelIn(session, session.server) : '';
  const named = session.status === 'signed-in' && session.known.some((k) => k.server === session.server && k.name);
  const large = useLargeText();
  const lead = back ? (
    <BackLink label={back.label} onPress={back.onPress} />
  ) : server ? (
    <Pressable accessibilityRole="button" accessibilityLabel={unreachable ? strings.reach.switchServer(host) : strings.home.switchServer(host)} onPress={() => router.push('/servers')} style={styles.server}>
      {/* An address never breaks inside: it grows to twice its size at most, and a long one ends in an ellipsis. */}
      <Text maxFontSizeMultiplier={named ? undefined : 2} style={[styles.host, named ? styles.name : null, { color: theme.text, flexShrink: 1 }]} numberOfLines={large && named ? undefined : 1}>
        {host}
      </Text>
      <Icon name="down" size={14} colour={theme.muted} />
    </Pressable>
  ) : null;
  return (
    <View style={[styles.header, { paddingTop: insets.top, backgroundColor: theme.chrome, borderBottomColor: theme.rule }]}>
      {/* At large text the actions keep their own line, above the server's name (design LargeHome). */}
      {lead && action && large ? (
        <>
          <View style={[styles.bar, { justifyContent: 'flex-end' }]}>{action}</View>
          <View style={styles.bar}>{lead}</View>
        </>
      ) : lead || action ? (
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

export type AITab = 'home' | 'cash' | 'decide' | 'books';

/**
 * Your AI, a tap away (design AIButtonPlacement): in the header beside + on
 * Home, Cash, Decide and Books, opening with starters for the tab it is on.
 * Before an AI is set up it opens More → Your AI instead.
 */
export function AIButton({ from }: { from: AITab }) {
  const theme = useTheme();
  const ai = useYourAI();
  if (!ai.loaded || !ai.enabled) return null;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={ai.ready ? strings.ai.open : strings.ai.openSetUp}
      onPress={() => (ai.ready ? router.push({ pathname: '/agent', params: { from } }) : router.push('/ai'))}
      style={styles.icon}
    >
      <Icon name="message" colour={theme.text} />
    </Pressable>
  );
}

/** Aurora's two lights behind a page; nothing in other themes. */
export function Glow() {
  const theme = useTheme();
  if (!theme.glow) return null;
  const [one, two] = theme.glow;
  return (
    <Svg style={StyleSheet.absoluteFill} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Defs>
        <RadialGradient id="one" cx="10%" cy="8%" r="60%">
          <Stop offset="0" stopColor={one} stopOpacity={0.35} />
          <Stop offset="1" stopColor={one} stopOpacity={0} />
        </RadialGradient>
        <RadialGradient id="two" cx="100%" cy="40%" r="60%">
          <Stop offset="0" stopColor={two} stopOpacity={0.4} />
          <Stop offset="1" stopColor={two} stopOpacity={0} />
        </RadialGradient>
      </Defs>
      <Rect width="100%" height="100%" fill="url(#one)" />
      <Rect width="100%" height="100%" fill="url(#two)" />
    </Svg>
  );
}

/** A place: its header, then its cards, pulled down to read again. */
export function Page({
  title,
  back,
  action,
  children,
  onRefresh,
  ai,
}: {
  title?: string;
  /** A tab with the AI button in its header. */
  ai?: AITab;
  back?: { label: string; onPress: () => void };
  action?: ReactNode;
  children: ReactNode;
  onRefresh?: () => Promise<unknown>;
}) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Glow />
      <Header {...(title ? { title } : {})} {...(back ? { back } : {})} action={ai ? <AIButton from={ai} /> : action} />
      <ScrollView
        contentContainerStyle={styles.page}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
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
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.back}>
      <Icon name="back" colour={theme.text} />
      <Body max={1.5}>{label}</Body>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: { borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8 },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: size.target },
  server: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 8, flexShrink: 1 },
  host: { fontFamily: font.mono, fontSize: size.small },
  name: { fontFamily: font.medium, fontSize: size.body },
  titleBox: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 8, paddingBottom: 8 },
  page: { padding: size.gutter, gap: size.gap },
  icon: { width: size.target, height: size.target, alignItems: 'center', justifyContent: 'center' },
  back: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingRight: 12 },
});
