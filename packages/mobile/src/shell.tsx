/**
 * The frame around a place: the bar at the top (which server, and adding an
 * entry), and a place still to come, which says where it is meanwhile.
 */
import { router } from 'expo-router';
import { createContext, useContext, useState, type ReactNode } from 'react';
import { Linking, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Defs, RadialGradient, Rect, Stop } from 'react-native-svg';
import { useYourAI } from './ai/store';
import { Body, Button, Card, Icon, Press, RoundButton, Title, radii, shape, useLargeText } from './kit';
import { useSession, labelIn } from './session';
import { strings } from './strings';
import { elevation, font, size, useTheme } from './theme';

/** What the floating tab bar covers at the foot of a tab's page (0 elsewhere): its height, its inset and the safe area. */
export const TabInset = createContext(0);

/** The server as a pill: the name or address, and a chevron to switch. */
export function ServerPill({ unreachable }: { unreachable?: boolean }) {
  const theme = useTheme();
  const { session } = useSession();
  const host = session.status === 'signed-in' ? labelIn(session, session.server) : '';
  const named = session.status === 'signed-in' && session.known.some((k) => k.server === session.server && k.name);
  const large = useLargeText();
  return (
    <Press
      accessibilityRole="button"
      accessibilityLabel={unreachable ? strings.reach.switchServer(host) : strings.home.switchServer(host)}
      hitSlop={4}
      onPress={() => router.push('/servers')}
      style={[styles.server, shape(radii.pill), { backgroundColor: theme.surface }, elevation(theme, 'card')]}
    >
      <View style={[styles.dot, shape(radii.pill), { backgroundColor: unreachable ? theme.red : theme.green }]} />
      {/* An address never breaks inside: it grows to twice its size at most, and a long one ends in an ellipsis. */}
      <Text maxFontSizeMultiplier={named ? undefined : 2} style={[styles.host, named ? styles.name : null, { color: theme.text, flexShrink: 1 }]} numberOfLines={large && named ? undefined : 1}>
        {host}
      </Text>
      <Icon name="down" size={14} colour={theme.muted} />
    </Press>
  );
}

/**
 * The top bar: a way back, or on Home the server as a pill; the actions as
 * 40 circles at its end. It has no rule under it: the page's own title is
 * large, below it, and scrolls away.
 */
export function Header({ server, unreachable, back, action }: { title?: string; server?: boolean; unreachable?: boolean; back?: { label: string; onPress: () => void }; action?: ReactNode }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const large = useLargeText();
  const lead = back ? <BackLink label={back.label} onPress={back.onPress} /> : server ? <ServerPill {...(unreachable ? { unreachable } : {})} /> : null;
  return (
    <View style={[styles.header, { paddingTop: insets.top, backgroundColor: theme.ground }]}>
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
      ) : (
        <View style={{ height: 8 }} />
      )}
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
  const ai = useYourAI();
  if (!ai.loaded || !ai.enabled) return null;
  return <RoundButton icon="ai" label={ai.ready ? strings.ai.open : strings.ai.openSetUp} onPress={() => (ai.ready ? router.push({ pathname: '/agent', params: { from } }) : router.push('/ai'))} />;
}

/** The AI button beside + (design Home): 40 circles, the AI on the left. */
export function HeaderActions({ from, add }: { from?: AITab; add?: { label: string; onPress: () => void; disabled?: boolean } }) {
  return (
    <View style={styles.actions}>
      {from ? <AIButton from={from} /> : null}
      {add ? <RoundButton icon="plus" tone="ink" label={add.label} onPress={add.disabled ? () => undefined : add.onPress} /> : null}
    </View>
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

/** A place: its header, its large title, then its cards, pulled down to read again. On a tab the floating bar's room is kept at the foot. */
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
  const inset = useContext(TabInset);
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, backgroundColor: theme.ground }}>
      <Glow />
      <Header {...(back ? { back } : {})} action={ai ? <HeaderActions from={ai} /> : action} />
      <ScrollView
        contentContainerStyle={[styles.page, { paddingBottom: inset || insets.bottom + size.gutter }]}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
        refreshControl={onRefresh ? <Pull read={onRefresh} /> : undefined}
      >
        {title ? <Title>{title}</Title> : null}
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
    <View style={{ flex: 1, backgroundColor: theme.ground }}>
      <Header />
      <ScrollView contentContainerStyle={styles.page}>
        <Title>{title}</Title>
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
    <Press accessibilityRole="button" hitSlop={4} onPress={onPress} style={[styles.back, shape(radii.pill), { backgroundColor: theme.surface }, elevation(theme, 'card')]}>
      <Icon name="back" size={20} colour={theme.text} />
      <Body max={1.5} small>{label}</Body>
    </Press>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: size.gutter },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: size.target, columnGap: 12 },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  server: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, flexShrink: 1 },
  dot: { width: 8, height: 8 },
  host: { fontFamily: font.mono, fontSize: size.label },
  name: { fontFamily: font.medium, fontSize: size.small },
  page: { paddingHorizontal: size.gutter, paddingTop: size.gap, gap: size.gap },
  back: { minHeight: 40, flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', paddingLeft: 10, paddingRight: 16 },
});
