import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon, Title } from '../kit';
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
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.chrome }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={[styles.page, { paddingTop: insets.top + 4, paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
        <Pressable accessibilityRole="link" onPress={() => router.back()} style={styles.back}>
          <Icon name="back" colour={theme.text} />
          <Body>{t.back}</Body>
        </Pressable>
        <View style={{ gap: 8 }}>
          <Title>{t.title}</Title>
          <Body muted>{t.body}</Body>
        </View>

        <View style={{ gap: 8 }}>
          <Text nativeID="invitation-label" style={[styles.fieldLabel, { color: theme.text }]}>
            {t.label}
          </Text>
          <TextInput
            accessibilityLabelledBy="invitation-label"
            accessibilityHint={t.help}
            value={typed}
            onChangeText={setTyped}
            onSubmitEditing={() => void go()}
            placeholder={t.placeholder}
            placeholderTextColor={theme.muted}
            keyboardType="url"
            textContentType="URL"
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            returnKeyType="go"
            style={[styles.input, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
          />
          {wrong ? <Body alert>{t.notALink}</Body> : null}
          <View style={{ marginTop: 8 }}>
            <Button label={t.continue} busy={open} disabled={open} onPress={() => void go()} />
          </View>
        </View>
        <Body small muted>
          {t.note}
        </Body>

        <View style={{ flex: 1 }} />
        <View style={[styles.foot, { borderTopColor: theme.rule }]}>
          <Body style={{ fontFamily: font.medium }}>{t.noInvitation}</Body>
          <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(t.pilotUrl)} style={styles.link}>
            <Body style={{ flex: 1 }}>{t.pilot}</Body>
            <Icon name="chevron" size={18} colour={theme.muted} />
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: 22 },
  back: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingRight: 12 },
  fieldLabel: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.mono, fontSize: size.body },
  foot: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: 12, gap: 6 },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8 },
});
