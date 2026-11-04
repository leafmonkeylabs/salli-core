import { accountDelete, describeDetail, SalliApiError } from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';
import { Body, Button, Field, IconTile, Press, Section, Surface, Icon } from '../kit';
import { labelIn, useSession } from '../session';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, size, space, useTheme } from '../theme';

const t = strings.deleteAccount;

/**
 * Delete account (design DeleteAccount): what goes, a way to keep a copy,
 * DELETE to type, then the server's own erasure. It asks for a recent
 * password, so a refusal for that sends the person through the server's
 * sign-in page again and the call is made once more. Nothing of the server
 * stays on the phone afterwards.
 */
export default function DeleteAccount() {
  const theme = useTheme();
  const { session, signIn, signOut, forgetServer } = useSession();
  const queryClient = useQueryClient();
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  // Two-step sign-in asks for its code with the erasure.
  const [code, setCode] = useState<string | undefined>(undefined);
  // Raised after signing in again, so the call is made with the new session's client.
  const [again, setAgain] = useState(0);
  const signedIn = session.status === 'signed-in';
  const server = signedIn ? session.server : '';
  const email = signedIn ? session.known.find((k) => k.server === server)?.email : undefined;
  const host = signedIn ? labelIn(session, server) : '';

  const erase = async () => {
    if (!signedIn || !email) return;
    setBusy(true);
    setProblem(undefined);
    try {
      await session.client.call(accountDelete, { body: { confirm_email: email }, ...(code?.trim() ? { headers: { 'Salli-Two-Step': code.trim() } } : {}) });
    } catch (error) {
      if (error instanceof SalliApiError && error.status === 403 && error.type.endsWith('/step-up-required')) {
        const outcome = await signIn(server, session.signIn, session.consoleUrl, 'again');
        if (outcome.ok) return setAgain((n) => n + 1);
        setBusy(false);
        return setProblem(outcome.reason === 'denied' ? t.denied : t.failed(outcome.detail));
      }
      setBusy(false);
      if (error instanceof SalliApiError && error.status === 403) {
        const said = describeDetail(error.detail);
        // The server's own sentence says whether a code is wanted.
        if (/authenticator code|code/i.test(said)) setCode((c) => c ?? '');
        return setProblem(said || t.twoStep);
      }
      return setProblem(t.failed(error instanceof Error ? error.message : String(error)));
    }
    // Gone on the server: leave this screen for one that outlives the sign-in, then forget the server here.
    router.replace({ pathname: '/account-deleted', params: { host } });
    queryClient.clear();
    await signOut();
    await forgetServer(server);
  };

  const run = erase;
  useEffect(() => {
    if (again > 0) void run();
    // Only when a new sign-in has come back; `run` is that render's own.
  }, [again]);

  if (!signedIn) return null;
  const ready = typed.trim() === t.word && !!email && !busy;

  return (
    <Page title={t.title} back={{ label: t.back, onPress: () => router.back() }}>
      <Body muted>{t.intro(host)}</Body>
      <Section title={t.goes}>
        <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
          <Goes icon="books" title={t.books} detail={t.booksHelp} />
          <Goes icon="upload" title={t.files} detail={t.filesHelp} line />
          <Goes icon="settings" title={t.signIns} detail={t.signInsHelp} line />
        </Surface>
        {session.consoleUrl ? (
          <Surface pad={false} style={{ paddingHorizontal: size.pad, marginTop: space.s12 }}>
            <Press highlight accessibilityRole="button" onPress={() => void Linking.openURL(`${session.consoleUrl}/settings`)} style={styles.goes}>
              <IconTile name="download" tone="fill" />
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={[styles.title, { color: theme.text }]}>{t.copy}</Text>
                <Body small muted>{t.copyHelp}</Body>
              </View>
              <Icon name="external" size={16} colour={theme.muted} />
            </Press>
          </Surface>
        ) : null}
      </Section>
      <Section title={t.typeIt}>
        <Field value={typed} onChangeText={setTyped} accessibilityLabel={t.fieldLabel} autoCapitalize="characters" autoCorrect={false} returnKeyType="done" />
      </Section>
      {code !== undefined ? (
        <Section title={t.codeTitle}>
          <Field value={code} onChangeText={setCode} accessibilityLabel={t.codeTitle} keyboardType="number-pad" autoCorrect={false} returnKeyType="done" />
          <Body small muted>{t.codeHelp}</Body>
        </Section>
      ) : null}
      {!email ? <Body small alert>{t.noEmail}</Body> : null}
      {problem ? <Body small alert>{problem}</Body> : null}
      <Body small muted style={{ textAlign: 'center' }}>{t.passwordNext}</Body>
      <Button kind="danger" label={t.go} busy={busy} disabled={!ready} onPress={() => void erase()} />
      <Button kind="secondary" label={t.keep} onPress={() => router.back()} />
    </Page>
  );
}

function Goes({ icon, title, detail, line }: { icon: 'books' | 'upload' | 'settings'; title: string; detail: string; line?: boolean }) {
  const theme = useTheme();
  return (
    <View style={[styles.goes, line ? { borderTopColor: theme.line, borderTopWidth: StyleSheet.hairlineWidth } : null]}>
      <IconTile name={icon} tone="fill" />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={[styles.title, { color: theme.text }]}>{title}</Text>
        <Body small muted>{detail}</Body>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  goes: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 64, paddingVertical: 9 },
  title: { fontFamily: font.regular, fontSize: size.body },
});
