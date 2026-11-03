import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon, Logo, Problem, Title } from '../kit';
import { hostedServerOf } from '../lib/server';
import { findServer, useSession, labelIn } from '../session';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.host;
const p = strings.problem;

/** Salli's own server, when this build of the app names it: its sign-up opens from the first screen. */
const HOSTED = hostedServerOf(process.env.EXPO_PUBLIC_HOSTED_SERVER);

/** Where the books live: Salli's server, by invitation, or the person's own. */
export default function Welcome() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session, signIn } = useSession();
  const [opening, setOpening] = useState(false);
  const [problem, setProblem] = useState<string | undefined>();
  const ended = session.status === 'signed-out' && session.ended;
  // Signed in, this is adding another server.
  const adding = session.status === 'signed-in';

  /** Salli's server: its sign-up page in the secure browser sheet, which returns through the app's callback; then on as to any server. */
  const signUp = async (server: string) => {
    setOpening(true);
    setProblem(undefined);
    const found = await findServer(server);
    if (!found.ok) {
      setOpening(false);
      return setProblem(found.problem === 'unreachable' ? p.unreachable(server) : p[found.problem].body(server));
    }
    const outcome = await signIn(server, found.signIn, found.meta.console_url ?? null, 'signup');
    setOpening(false);
    if (!outcome.ok) return outcome.reason === 'denied' ? undefined : setProblem(p.failed(outcome.detail));
    if (router.canDismiss()) router.dismissAll();
    router.replace('/home');
  };

  return (
    <ScrollView style={{ backgroundColor: theme.chrome }} contentContainerStyle={[styles.page, { paddingTop: insets.top + (adding ? 4 : 32), paddingBottom: insets.bottom + 24 }]}>
      {adding ? (
        <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.cancel}>
          <Body>{t.cancel}</Body>
        </Pressable>
      ) : null}
      <View style={{ marginLeft: -8 }}>
        <Logo height={36} />
      </View>
      {ended ? (
        <View style={[styles.notice, { borderColor: theme.rule, backgroundColor: theme.card, borderRadius: theme.radius }]} accessibilityRole="alert">
          <Body style={{ fontFamily: font.medium }}>{strings.problem.signedOutTitle}</Body>
          <Body small muted>
            {strings.problem.signedOut}
          </Body>
        </View>
      ) : null}
      {/* Signed out of every server: the ones remembered are a tap from signing in again. */}
      {session.status === 'signed-out' && session.known.length ? (
        <View style={{ gap: 8 }}>
          {session.known.map((known) => (
            <Button
              key={known.server}
              kind="secondary"
              label={strings.servers.signInTo(labelIn(session, known.server))}
              onPress={() => router.push({ pathname: '/connect', params: { server: known.server } })}
            />
          ))}
        </View>
      ) : null}
      <View style={{ gap: 10 }}>
        <Title>{t.title}</Title>
        <Body muted>{t.body}</Body>
      </View>

      <View accessibilityLabel={t.group} style={{ gap: 10 }}>
        <Choice
          first
          title={t.salli}
          body={t.salliBody}
          note={HOSTED ? (opening ? t.signingUp : t.salliNoteOpen) : t.salliNote}
          onPress={() => (HOSTED ? void signUp(HOSTED) : router.push('/join'))}
        />
        <Choice title={t.own} body={t.ownBody} onPress={() => router.push('/address')} />
      </View>

      {problem ? <Problem title={p.failedTitle} body={problem} /> : null}
      {HOSTED ? (
        <View>
          <Pressable accessibilityRole="link" onPress={() => router.push('/join')} style={styles.secondary}>
            <Body>{t.haveInvitation}</Body>
          </Pressable>
          <Pressable accessibilityRole="link" onPress={() => router.push({ pathname: '/connect', params: { server: HOSTED } })} style={styles.secondary}>
            <Body>{t.haveAccount}</Body>
          </Pressable>
        </View>
      ) : null}

      <View style={{ flex: 1 }} />
      <View style={{ gap: 6 }}>
        <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(t.hostingUrl)} style={[styles.link, { borderColor: theme.rule }]}>
          <Body style={{ flex: 1 }}>{t.hosting}</Body>
          <Icon name="chevron" size={18} colour={theme.muted} />
        </Pressable>
        <Body small muted>
          {t.yours}
        </Body>
      </View>
    </ScrollView>
  );
}

/** One place the books may live; Salli's server drawn first and marked, as the design has it. */
function Choice({ title, body, note, first, onPress }: { title: string; body: string; note?: string; first?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={[title, body, note].filter(Boolean).join('. ')}
      onPress={onPress}
      style={[styles.choice, first ? { backgroundColor: theme.work, borderColor: theme.button, borderWidth: 2 } : { backgroundColor: theme.chrome, borderColor: theme.rule, borderWidth: 1 }, { borderRadius: theme.radius }]}
    >
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={[styles.choiceTitle, { color: theme.text }]}>{title}</Text>
        <Body small muted>
          {body}
        </Body>
        {note ? <Text style={[styles.note, { color: theme.muted }]}>{note}</Text> : null}
      </View>
      <Icon name="chevron" size={18} colour={theme.muted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: 28 },
  cancel: { minHeight: size.target, justifyContent: 'center', alignSelf: 'flex-start', paddingRight: 12 },
  notice: { borderWidth: StyleSheet.hairlineWidth, padding: 14, gap: 4 },
  choice: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 88, padding: 14 },
  choiceTitle: { fontFamily: font.medium, fontSize: 17 },
  note: { fontFamily: font.regular, fontSize: 13 },
  secondary: { minHeight: size.target, justifyContent: 'center' },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth },
});
