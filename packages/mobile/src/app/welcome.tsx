import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon, IconTile, Logo, Notice, Press, Problem, Title, radii, shape } from '../kit';
import { hostedServerOf } from '../lib/server';
import { findServer, useSession, labelIn } from '../session';
import { strings } from '../strings';
import { elevation, font, size, useTheme } from '../theme';

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
    <ScrollView style={{ backgroundColor: theme.ground }} contentContainerStyle={[styles.page, { paddingTop: insets.top + (adding ? 4 : 32), paddingBottom: insets.bottom + 24 }]}>
      {adding ? (
        <Button kind="tertiary" label={t.cancel} onPress={() => router.back()} />
      ) : null}
      <View>
        <Logo height={36} />
      </View>
      {ended ? (
        <Notice tone="warn">
          <Body small style={{ fontFamily: font.medium }}>{strings.problem.signedOutTitle}</Body>
          <Body small muted>
            {strings.problem.signedOut}
          </Body>
        </Notice>
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
      <View style={{ gap: 12 }}>
        <Title>{t.title}</Title>
        <Body muted>{t.body}</Body>
      </View>

      <View accessibilityLabel={t.group} style={{ gap: 12 }}>
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
          <Button kind="tertiary" label={t.haveInvitation} onPress={() => router.push('/join')} />
          <Button kind="tertiary" label={t.haveAccount} onPress={() => router.push({ pathname: '/connect', params: { server: HOSTED } })} />
        </View>
      ) : null}

      <View style={{ flex: 1 }} />
      <View style={{ gap: 6 }}>
        <Press highlight accessibilityRole="link" onPress={() => void Linking.openURL(t.hostingUrl)} style={styles.link}>
          <Body small style={{ flex: 1, color: theme.green }}>{t.hosting}</Body>
          <Icon name="external" size={16} colour={theme.green} />
        </Press>
        <Body small muted>
          {t.yours}
        </Body>
      </View>
    </ScrollView>
  );
}

/** One place the books may live; Salli's server drawn first, in the green tint, as the design has it. */
function Choice({ title, body, note, first, onPress }: { title: string; body: string; note?: string; first?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Press
      accessibilityRole="button"
      accessibilityLabel={[title, body, note].filter(Boolean).join('. ')}
      onPress={onPress}
      style={[styles.choice, shape(radii.card), { backgroundColor: first ? theme.greenTint : theme.surface }, elevation(theme, 'card')]}
    >
      <IconTile name={first ? 'spark' : 'server'} tone={first ? 'green' : 'fill'} />
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={[styles.choiceTitle, { color: theme.text }]}>{title}</Text>
        <Body small muted>
          {body}
        </Body>
        {note ? <Text style={[styles.note, { color: theme.muted }]}>{note}</Text> : null}
      </View>
      <Icon name="chevron" size={18} colour={theme.muted} />
    </Press>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: size.section },
  choice: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 88, padding: size.pad },
  choiceTitle: { fontFamily: font.semibold, fontSize: size.headline },
  note: { fontFamily: font.regular, fontSize: size.label },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8 },
});
