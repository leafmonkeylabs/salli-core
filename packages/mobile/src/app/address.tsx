import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Field, Icon, IconTile, Logo, Press, Surface, Tag, Title } from '../kit';
import { BackLink } from '../shell';
import { serverUrlOf } from '../lib/server';
import { useSession } from '../session';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.welcome;

/** Your own server: its address, checked before signing in. */
export default function Address() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { session, switchTo } = useSession();
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
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
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.ground }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={[styles.page, { paddingTop: insets.top + 4, paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
        {/* Reached from where the books live, Salli's server or your own. */}
        <BackLink label={t.back} onPress={() => router.back()} />
        <View>
          <Logo height={40} />
        </View>
        <View style={{ gap: 10 }}>
          <Title>{adding ? t.addTitle : t.title}</Title>
          <Body muted>{adding ? t.addBody : t.body}</Body>
        </View>

        <View style={{ gap: 12 }}>
          <Field
            label={t.label}
            accessibilityHint={t.help}
            value={typed}
            onChangeText={setTyped}
            onSubmitEditing={check}
            placeholder={t.placeholder}
            keyboardType="url"
            textContentType="URL"
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            returnKeyType="go"
            mono
            {...(wrong ? { error: t.notAnAddress } : {})}
          />
          <Button label={t.check} onPress={check} />
        </View>

        {/* Planned: a pairing code needs the server's side (salli ui --qr) first. */}
        <Surface kind="inset">
          <View accessible accessibilityState={{ disabled: true }} accessibilityLabel={`${t.scan}. ${t.planned}. ${t.scanHelp}`} style={styles.scan}>
            <IconTile name="scan" tone="fill" />
            <View style={{ flex: 1, gap: 2 }}>
              <Body style={{ fontFamily: font.medium }}>{t.scan}</Body>
              <Body small muted>
                {t.scanHelp}
              </Body>
            </View>
            <Tag>{t.planned}</Tag>
          </View>
        </Surface>

        <View style={{ flex: 1 }} />
        {/* Adding a server, the person has one: no need to say how to run one. */}
        {adding ? null : (
          <>
            <Press highlight accessibilityRole="link" onPress={() => void Linking.openURL(t.noServerUrl)} style={styles.link}>
              <Body small style={{ flex: 1, color: theme.green }}>{t.noServer}</Body>
              <Icon name="external" size={16} colour={theme.green} />
            </Press>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: size.section },
  scan: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 56 },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8 },
});
