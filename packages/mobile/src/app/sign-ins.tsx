import { authSignInsList } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRead } from '../api';
import { Body, Button, Card, CardHead, Icon, Toggle } from '../kit';
import { displayDateTime } from '../lib/display';
import { labelOf } from '../lib/servers';
import { usePhone } from '../phone';
import { labelIn, useSession, type Known } from '../session';
import { Sheet, SheetTitle } from '../sheet';
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
  const { session, switchTo, signOut, forgetServer, rename } = useSession();
  const [naming, setNaming] = useState(false);
  const phone = usePhone();
  const signIns = useRead('auth.signIns.list', authSignInsList);
  const [leaving, setLeaving] = useState<string | undefined>(undefined);
  if (session.status !== 'signed-in') return null;
  const host = labelIn(session, session.server);
  const name = session.known.find((k) => k.server === session.server)?.name;
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
        <Pressable accessibilityRole="button" accessibilityLabel={`${t.name}: ${name ?? t.noName}`} onPress={() => setNaming(true)} style={styles.nameRow}>
          <Text style={[styles.nameLabel, { color: theme.muted }]}>{t.name}</Text>
          <Text style={[styles.nameValue, { color: name ? theme.text : theme.muted }]} numberOfLines={1}>
            {name ?? t.noName}
          </Text>
          <Icon name="chevron" size={16} colour={theme.muted} />
        </Pressable>
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
      <NameSheet
        // Opened afresh each time, with the name as it is now.
        key={naming ? 'open' : 'closed'}
        visible={naming}
        address={hostOf(session.server)}
        name={name ?? ''}
        onClose={() => setNaming(false)}
        onSave={(next) => void rename(session.server, next).then(() => setNaming(false))}
      />
    </Page>
  );
}

/** Naming the server on screen: what this phone calls it, in place of its address. */
function NameSheet({ visible, address, name, onClose, onSave }: { visible: boolean; address: string; name: string; onClose: () => void; onSave: (name: string) => void }) {
  const theme = useTheme();
  const [typed, setTyped] = useState(name);
  return (
    <Sheet visible={visible} onClose={onClose} label={t.name}>
      <SheetTitle style={[styles.sheetTitle, { color: theme.text }]}>
        {t.nameTitle}
      </SheetTitle>
      <Text style={[styles.address, { color: theme.muted }]}>{address}</Text>
      <TextInput
        value={typed}
        onChangeText={setTyped}
        onSubmitEditing={() => onSave(typed)}
        placeholder={t.namePlaceholder}
        placeholderTextColor={theme.muted}
        accessibilityLabel={t.name}
        accessibilityHint={t.nameHelp}
        autoFocus
        returnKeyType="done"
        style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
      />
      <Button label={t.save} onPress={() => onSave(typed)} />
      {name ? <Button kind="tertiary" label={t.useAddress} onPress={() => onSave('')} /> : null}
    </Sheet>
  );
}

function ServerRow({ known, onScreen, onSwitch, onSignIn, onForget }: { known: Known; onScreen: boolean; onSwitch: () => void; onSignIn: () => void; onForget: () => void }) {
  const theme = useTheme();
  const host = labelOf(known.server, known.name);
  // Named, its address shows under the name: the one place it still does.
  const who = t.who([known.name ? hostOf(known.server) : '', known.email ?? '', known.currency ?? '', known.signedIn ? t.signedInNow : t.signedOut]);
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
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <Text style={[styles.host, known.name ? styles.named : null, { color: theme.text }]} numberOfLines={1}>
            {host}
          </Text>
          <Body small muted>
            {who}
          </Body>
        </View>
      </Pressable>
      {onScreen ? (
        <View style={styles.thisOneRow}>
          <Icon name="check" size={20} colour={theme.text} />
          <Text style={[styles.thisOne, { color: theme.text }]}>{t.thisOne}</Text>
        </View>
      ) : !known.signedIn ? (
        <View style={{ alignItems: 'flex-end' }}>
          <Button kind="secondary" label={t.signIn} accessibilityLabel={t.signInTo(host)} onPress={onSignIn} />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t.forget(host)}
            accessibilityHint={t.forgetHelp}
            onPress={onForget}
            style={[styles.forget, { borderColor: theme.fieldBorder, backgroundColor: theme.chrome, borderRadius: theme.control }]}
          >
            <Text style={[styles.forgetText, { color: theme.negative }]}>{t.forgetShort}</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  named: { fontFamily: font.medium },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: size.target },
  nameLabel: { fontFamily: font.regular, fontSize: size.body },
  nameValue: { flex: 1, textAlign: 'right', fontFamily: font.regular, fontSize: size.body },
  sheetTitle: { fontFamily: font.medium, fontSize: size.heading },
  address: { fontFamily: font.mono, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  since: { fontFamily: font.regular, fontSize: size.small },
  server: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  serverMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48 },
  host: { fontFamily: font.mono, fontSize: size.small },
  thisOne: { fontFamily: font.medium, fontSize: size.small },
  forget: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 14, borderWidth: 1, marginTop: 6 },
  forgetText: { fontFamily: font.medium, fontSize: size.small },
  thisOneRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  underline: { textDecorationLine: 'underline' },
  add: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52 },
  addText: { fontFamily: font.medium, fontSize: size.body },
});
