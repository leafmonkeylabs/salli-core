import { authSignInsList } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../api';
import { Body, Button, Card, CardHead, Icon, Toggle } from '../kit';
import { displayDateTime } from '../lib/display';
import { usePhone } from '../phone';
import { useSession, type Known } from '../session';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.servers;
const p = strings.phone;
const hostOf = (server: string): string => server.replace(/^https?:\/\//, '');

/**
 * Servers and sign-in (design 4): every server this phone remembers, this
 * phone's lock and discretion, and this sign-in, from the server's own list
 * of sign-ins, where it can be ended from anywhere.
 */
export default function SignIns() {
  const theme = useTheme();
  const { session, switchTo, signOut, forgetServer } = useSession();
  const phone = usePhone();
  const signIns = useRead('auth.signIns.list', authSignInsList);
  const [leaving, setLeaving] = useState<string | undefined>(undefined);
  if (session.status !== 'signed-in') return null;
  const host = hostOf(session.server);
  const mine = signIns.data?.find((s) => s.current);
  const how = p.how[phone.unlockWith ?? 'passcode'];

  return (
    <Page title={t.page} back={{ label: t.back, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      <Card style={{ paddingVertical: 12 }}>
        <CardHead label={t.yours} />
        <View accessibilityRole="radiogroup">
          {session.known.map((known) => (
            <ServerRow
              key={known.server}
              known={known}
              onScreen={known.server === session.server}
              onSwitch={() => void switchTo(known.server)}
              onSignIn={() => router.push({ pathname: '/connect', params: { server: known.server } })}
              onForget={() => void forgetServer(known.server)}
            />
          ))}
        </View>
        <Pressable accessibilityRole="button" onPress={() => router.push('/welcome')} style={styles.add}>
          <Icon name="plus" size={20} colour={theme.chart} />
          <Text style={[styles.addText, { color: theme.chart }]}>{t.add}</Text>
        </Pressable>
      </Card>

      <Card style={{ paddingVertical: 4 }}>
        <View style={{ paddingTop: 8 }}>
          <CardHead label={p.title} />
        </View>
        <Toggle label={p.lock(how)} help={phone.unlockWith ? p.lockHelpShort : p.noLock} value={phone.settings.lock} disabled={!phone.unlockWith} onChange={(on) => void phone.setLock(on)} />
      </Card>

      <Card style={{ gap: 12 }}>
        <CardHead label={t.signedInCard} />
        {mine ? (
          <Text accessibilityLabel={t.since(displayDateTime(new Date(mine.started_at)), mine.client_name ?? 'Salli app')} style={[styles.since, { color: theme.muted }]}>
            {t.sinceShort(displayDateTime(new Date(mine.started_at)))}
          </Text>
        ) : null}
        <Button
          kind="secondary"
          label={strings.more.signOut(host)}
          busy={leaving === session.server}
          disabled={leaving === session.server}
          onPress={() => {
            setLeaving(session.server);
            void signOut();
          }}
        />
        <Body small muted>
          {session.servers.length > 1 ? strings.more.signOutNoteOthers : strings.more.signOutNote}
        </Body>
      </Card>
    </Page>
  );
}

function ServerRow({ known, onScreen, onSwitch, onSignIn, onForget }: { known: Known; onScreen: boolean; onSwitch: () => void; onSignIn: () => void; onForget: () => void }) {
  const theme = useTheme();
  const host = hostOf(known.server);
  const who = t.who([known.email ?? '', known.currency ?? '', known.signedIn ? t.signedInNow : t.signedOut]);
  return (
    <View style={[styles.server, { borderBottomColor: theme.rule }]}>
      <Pressable
        accessibilityRole="radio"
        accessibilityState={{ checked: onScreen, disabled: !known.signedIn }}
        accessibilityLabel={`${host}, ${who}`}
        disabled={!known.signedIn || onScreen}
        onPress={onSwitch}
        style={styles.serverMain}
      >
        <View style={[styles.radio, { borderColor: onScreen ? theme.text : theme.muted }]}>{onScreen ? <View style={[styles.dot, { backgroundColor: theme.text }]} /> : null}</View>
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <Text style={[styles.host, { color: theme.text }]} numberOfLines={1}>
            {host}
          </Text>
          <Body small muted>
            {who}
          </Body>
        </View>
      </Pressable>
      {onScreen ? (
        <Text style={[styles.thisOne, { color: theme.text }]}>{t.thisOne}</Text>
      ) : !known.signedIn ? (
        <View style={{ alignItems: 'flex-end' }}>
          <Button kind="secondary" label={t.signIn} accessibilityLabel={t.signInTo(host)} onPress={onSignIn} />
          <Pressable accessibilityRole="button" accessibilityLabel={t.forget(host)} accessibilityHint={t.forgetHelp} onPress={onForget} style={styles.forget}>
            <Body small muted style={styles.underline}>
              {t.forgetShort}
            </Body>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  since: { fontFamily: font.regular, fontSize: size.small },
  server: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  serverMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48 },
  host: { fontFamily: font.mono, fontSize: size.small },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  thisOne: { fontFamily: font.medium, fontSize: size.small },
  forget: { minHeight: 32, justifyContent: 'center' },
  underline: { textDecorationLine: 'underline' },
  add: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52 },
  addText: { fontFamily: font.medium, fontSize: size.body },
});
