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
  const { session } = useSession();
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
  const ended = session.status === 'signed-out' && session.ended;

  const check = () => {
    const server = serverUrlOf(typed);
    if (!server) return setWrong(true);
    setWrong(false);
    router.push({ pathname: '/connect', params: { server } });
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.chrome }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={[styles.page, { paddingTop: insets.top + 32, paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
        <View style={{ marginLeft: -8 }}>
          <Logo height={40} />
        </View>
        {ended ? (
          <View style={[styles.notice, { borderColor: theme.rule, backgroundColor: theme.card }]} accessibilityRole="alert">
            <Body style={{ fontFamily: font.medium }}>{strings.problem.signedOutTitle}</Body>
            <Body small muted>
              {strings.problem.signedOut}
            </Body>
          </View>
        ) : null}
        <View style={{ gap: 10 }}>
          <Title>{t.title}</Title>
          <Body muted>{t.body}</Body>
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

        <View style={{ flex: 1 }} />
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
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, paddingHorizontal: size.gutter, gap: 28 },
  notice: { borderWidth: StyleSheet.hairlineWidth, padding: 14, gap: 4 },
  fieldLabel: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.mono, fontSize: size.body },
  link: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 8, borderTopWidth: StyleSheet.hairlineWidth, borderBottomWidth: StyleSheet.hairlineWidth },
});
