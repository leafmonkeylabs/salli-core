import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Field, Icon, Press, Title } from '../kit';
import { BackLink } from '../shell';
import { invitationOf } from '../lib/server';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.join;

/**
 * Salli's server, by invitation: the link's page opens in the secure browser
 * sheet, where the person sets their password and two-step code; then the
 * app signs in to that server as to any other. The link is pasted: an
 * https link opens in the browser, not here.
 */
export default function Join() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
  const [open, setOpen] = useState(false);

  const go = async () => {
    const invitation = invitationOf(typed);
    if (!invitation) return setWrong(true);
    setWrong(false);
    setOpen(true);
    await WebBrowser.openBrowserAsync(invitation.link, { presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET });
    setOpen(false);
    router.push({ pathname: '/connect', params: { server: invitation.server } });
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.ground }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={[styles.page, { paddingTop: insets.top + 4, paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
        <BackLink label={t.back} onPress={() => router.back()} />
        <View style={{ gap: 8 }}>
          <Title>{t.title}</Title>
          <Body muted>{t.body}</Body>
        </View>

        <View style={{ gap: 12 }}>
          <Field
            label={t.label}
            accessibilityHint={t.help}
            value={typed}
            onChangeText={setTyped}
            onSubmitEditing={() => void go()}
            placeholder={t.placeholder}
            keyboardType="url"
            textContentType="URL"
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            returnKeyType="go"
            mono
            {...(wrong ? { error: t.notALink } : {})}
          />
          <Button label={t.continue} busy={open} disabled={open} onPress={() => void go()} />
        </View>
        <Body small muted>
          {t.note}
        </Body>

        <View style={{ flex: 1 }} />
        <View style={styles.foot}>
          <Body style={{ fontFamily: font.medium }}>{t.noInvitation}</Body>
          <Press highlight accessibilityRole="link" onPress={() => void Linking.openURL(t.pilotUrl)} style={styles.link}>
            <Body small style={{ flex: 1, color: theme.green }}>{t.pilot}</Body>
            <Icon name="external" size={16} colour={theme.green} />
          </Press>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: size.section },
  foot: { paddingTop: 12, gap: 6 },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8 },
});
