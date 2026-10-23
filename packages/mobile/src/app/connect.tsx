import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon, Problem, SectionLabel } from '../kit';
import { isThisMachine, type ServerCheck } from '../lib/server';
import { findServer, useSession, type SignInResult } from '../session';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.connect;
const p = strings.problem;

type Found = ServerCheck | { ok: false; problem: 'unreachable' } | undefined;

export default function Connect() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { server = '' } = useLocalSearchParams<{ server: string }>();
  const { signIn } = useSession();
  const [found, setFound] = useState<Found>(undefined);
  const [signingIn, setSigningIn] = useState(false);
  const [result, setResult] = useState<SignInResult | undefined>(undefined);
  const host = server.replace(/^https?:\/\//, '');

  const check = useCallback(() => {
    // Opened with no address (a link from elsewhere): start from the beginning.
    if (!server) return void router.replace('/welcome');
    setFound(undefined);
    void findServer(server).then(setFound);
  }, [server]);
  useEffect(check, [check]);

  const start = async () => {
    if (!found?.ok) return;
    setSigningIn(true);
    setResult(undefined);
    const outcome = await signIn(server, found.signIn, found.meta.console_url ?? null);
    setSigningIn(false);
    // Signed in: the navigator leaves for Home on its own.
    if (!outcome.ok) setResult(outcome);
  };

  return (
    <ScrollView style={{ backgroundColor: theme.chrome }} contentContainerStyle={[styles.page, { paddingTop: insets.top + 4, paddingBottom: insets.bottom + 24 }]}>
      <Pressable accessibilityRole="link" onPress={() => router.back()} style={styles.back}>
        <Icon name="back" colour={theme.text} />
        <Body>{t.back}</Body>
      </Pressable>

      {found === undefined ? (
        <Text accessibilityLiveRegion="polite" style={[styles.value, { color: theme.muted }]}>
          {t.checking(host)}
        </Text>
      ) : found.ok ? (
        <>
          <View style={{ gap: 8 }}>
            <SectionLabel>{t.found}</SectionLabel>
            <Text accessibilityRole="header" style={[styles.host, { color: theme.text }]}>
              {server}
            </Text>
          </View>
          <View style={{ borderTopColor: theme.rule, borderTopWidth: StyleSheet.hairlineWidth }}>
            <Fact name={t.version} value={found.meta.server_version} mono />
            <Fact name={t.api} value={`✓ ${t.apiOk}`} />
            <Fact name={t.connection} value={`✓ ${isThisMachine(server) && !server.startsWith('https:') ? t.local : t.https}`} />
          </View>
          <Body muted>{t.signInNote(host)}</Body>
          {result && !result.ok ? (
            <Problem
              title={result.reason === 'denied' ? p.deniedTitle : p.failedTitle}
              body={result.reason === 'denied' ? p.denied : p.failed(result.detail)}
            />
          ) : null}
          <View style={{ flex: 1 }} />
          <View style={{ gap: 10 }}>
            <Button label={signingIn ? t.signingIn : t.signIn(host)} busy={signingIn} disabled={signingIn} onPress={() => void start()} />
            <Body small muted style={{ textAlign: 'center' }}>
              {t.sheetNote}
            </Body>
          </View>
        </>
      ) : found.problem === 'unreachable' ? (
        <Problem title={p.unreachableTitle} body={p.unreachable(server)}>
          <Retry onRetry={check} />
        </Problem>
      ) : (
        <Problem title={p[found.problem].title} body={p[found.problem].body(server)}>
          <Retry onRetry={check} />
        </Problem>
      )}
    </ScrollView>
  );
}

function Fact({ name, value, mono }: { name: string; value: string; mono?: boolean }) {
  const theme = useTheme();
  return (
    <View style={[styles.fact, { borderBottomColor: theme.rule }]}>
      <Body muted>{name}</Body>
      <Text style={[mono ? styles.mono : styles.value, { color: theme.text }]}>{value}</Text>
    </View>
  );
}

function Retry({ onRetry }: { onRetry: () => void }) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      <Button label={t.tryAgain} onPress={onRetry} />
      <Button label={t.back} kind="tertiary" onPress={() => router.back()} />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: 24 },
  back: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingRight: 12 },
  host: { fontFamily: font.mono, fontSize: 20 },
  fact: { flexDirection: 'row', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  value: { fontFamily: font.regular, fontSize: size.body },
  mono: { fontFamily: font.mono, fontSize: size.small },
});
