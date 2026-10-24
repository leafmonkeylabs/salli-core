import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon, Logo, Title } from '../kit';
import { serverUrlOf } from '../lib/server';
import { useSession } from '../session';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.welcome;

export default function Welcome() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session, switchTo } = useSession();
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
  const ended = session.status === 'signed-out' && session.ended;
  // Signed in, this is adding another server.
  const adding = session.status === 'signed-in';

  const check = () => {
    const server = serverUrlOf(typed);
    if (!server) return setWrong(true);
    setWrong(false);
    // Already signed in to it: show it, rather than start a second sign-in.
    if (adding && session.servers.includes(server)) {
      void switchTo(server).then(() => {
        if (router.canDismiss()) router.dismissAll();
        router.replace('/home');
      });
      return;
    }
    router.push({ pathname: '/connect', params: { server } });
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.chrome }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={[styles.page, { paddingTop: insets.top + (adding ? 4 : 32), paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
        {adding ? (
          <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.cancel}>
            <Body>{t.cancel}</Body>
          </Pressable>
        ) : null}
        {/* The logo heads the page either way, as the design has it. */}
        <View style={{ marginLeft: -8 }}>
          <Logo height={40} />
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
                label={strings.servers.signInTo(known.server.replace(/^https?:\/\//, ''))}
                onPress={() => router.push({ pathname: '/connect', params: { server: known.server } })}
              />
            ))}
          </View>
        ) : null}
        <View style={{ gap: 10 }}>
          <Title>{adding ? t.addTitle : t.title}</Title>
          <Body muted>{adding ? t.addBody : t.body}</Body>
        </View>

        <View style={{ gap: 8 }}>
          <Text nativeID="server-label" style={[styles.fieldLabel, { color: theme.text }]}>
            {t.label}
          </Text>
          <TextInput
            accessibilityLabelledBy="server-label"
            accessibilityHint={t.help}
            value={typed}
            onChangeText={setTyped}
            onSubmitEditing={check}
            placeholder={t.placeholder}
            placeholderTextColor={theme.muted}
            keyboardType="url"
            textContentType="URL"
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            returnKeyType="go"
            style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text }]}
          />
          <Body small muted>
            {wrong ? t.notAnAddress : t.help}
          </Body>
          <View style={{ marginTop: 8 }}>
            <Button label={t.check} onPress={check} />
          </View>
        </View>

        {/* Planned: a pairing code needs the server's side (salli ui --qr) first. */}
        <View accessible accessibilityState={{ disabled: true }} accessibilityLabel={`${t.scan}. ${t.planned}. ${t.scanHelp}`} style={[styles.scan, { borderColor: theme.rule }]}>
          <Icon name="scan" colour={theme.muted} />
          <View style={{ flex: 1, gap: 2 }}>
            <Body style={{ fontFamily: font.medium }}>{t.scan}</Body>
            <Body small muted>
              {t.scanHelp}
            </Body>
          </View>
          <Text style={[styles.chip, { color: theme.muted, borderColor: theme.rule }]}>{t.planned}</Text>
        </View>

        <View style={{ flex: 1 }} />
        {/* Adding a server, the person has one: no need to say how to run one. */}
        {adding ? null : (
          <>
            <Pressable
              accessibilityRole="link"
              onPress={() => void Linking.openURL(t.noServerUrl)}
              style={[styles.link, { borderColor: theme.rule }]}
            >
              <Body style={{ flex: 1 }}>{t.noServer}</Body>
              <Icon name="external" size={16} colour={theme.muted} />
            </Pressable>
            <Body small muted>
              {t.footer}
            </Body>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: 28 },
  scan: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 72, paddingVertical: 12, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth },
  chip: { fontFamily: font.medium, fontSize: 12.5, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 2 },
  cancel: { minHeight: size.target, justifyContent: 'center', alignSelf: 'flex-start', paddingRight: 12 },
  notice: { borderWidth: StyleSheet.hairlineWidth, padding: 14, gap: 4 },
  fieldLabel: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.mono, fontSize: size.body },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth },
});
