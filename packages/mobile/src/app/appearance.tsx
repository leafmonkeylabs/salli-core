import { supportsAlternateIcons } from 'expo-alternate-app-icons';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useColorScheme } from 'react-native';
import { useAppearance } from '../appearance';
import { Body, SectionLabel } from '../kit';
import { HAS_NIGHT, isNight, MODES, THEMES, typeOf, type ThemeId } from '../lib/appearance';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, openedWith, size, themeOf, useTheme } from '../theme';

const t = strings.appearance;

/**
 * Appearance (design 23): a theme, picked from small pictures of Home in
 * each, and for the themes with a night side whether it follows the phone.
 */
export default function Appearance() {
  const theme = useTheme();
  const { appearance, set } = useAppearance();
  const phoneDark = useColorScheme() === 'dark';

  return (
    <Page title={t.title} back={{ label: strings.more.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      <View style={{ gap: 12 }}>
        <SectionLabel>{t.theme}</SectionLabel>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} accessibilityRole="radiogroup" contentContainerStyle={styles.themes} style={styles.strip}>
          {THEMES.map((id) => (
            <Choice key={id} id={id} chosen={appearance.theme === id} night={isNight({ ...appearance, theme: id }, phoneDark)} onPress={() => set({ ...appearance, theme: id })} />
          ))}
        </ScrollView>
        {supportsAlternateIcons || typeOf(appearance.theme) !== typeOf(openedWith) ? (
          <Body small muted>
            {[supportsAlternateIcons ? t.icon : '', typeOf(appearance.theme) !== typeOf(openedWith) ? t.typeLater : ''].filter(Boolean).join(' ')}
          </Body>
        ) : null}
      </View>

      {HAS_NIGHT.includes(appearance.theme) ? (
        <View style={{ gap: 12 }}>
          <SectionLabel>{t.mode}</SectionLabel>
          <View accessibilityRole="radiogroup" style={[styles.modes, { backgroundColor: theme.card, borderColor: theme.fieldBorder, borderRadius: theme.control }]}>
            {MODES.map((mode) => {
              const on = appearance.mode === mode;
              return (
                <Pressable
                  key={mode}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: on }}
                  onPress={() => set({ ...appearance, mode })}
                  style={[styles.mode, { borderRadius: theme.control }, on ? { backgroundColor: theme.text } : null]}
                >
                  <Text style={[styles.modeText, { color: on ? theme.work : theme.text, fontFamily: on ? font.medium : font.regular }]}>{t.modes[mode]}</Text>
                </Pressable>
              );
            })}
          </View>
          <Body small muted>
            {t.auto}
          </Body>
        </View>
      ) : null}
    </Page>
  );
}

/** A theme as a small picture of Home: its page, its key figure, its cards. */
function Choice({ id, chosen, night, onPress }: { id: ThemeId; chosen: boolean; night: boolean; onPress: () => void }) {
  const theme = useTheme();
  const look = themeOf(id, night);
  const corner = Math.min(look.radius, 10);
  const block = { borderRadius: corner, borderColor: look.cardBorder, borderWidth: look.offset ? 1.5 : 0 };
  return (
    <Pressable accessibilityRole="radio" accessibilityLabel={t.names[id]} accessibilityState={{ checked: chosen }} onPress={onPress} style={styles.choice}>
      <View style={[styles.frame, { borderColor: chosen ? theme.text : 'transparent' }]}>
        <View style={[styles.phone, { backgroundColor: look.work, borderColor: look.rule }]}>
          <View style={[styles.hero, block, { backgroundColor: look.tile }]}>
            <View style={[styles.figure, { backgroundColor: look.tileText }]} />
          </View>
          <View style={{ flexDirection: 'row', gap: 4 }}>
            <View style={[styles.small, block, { backgroundColor: look.card }]} />
            <View style={[styles.small, block, { backgroundColor: look.card }]} />
          </View>
          <View style={[styles.list, block, { backgroundColor: look.card }]} />
          <View style={[styles.button, { backgroundColor: look.button, borderRadius: Math.min(look.control, 8) }]} />
        </View>
      </View>
      <Text style={[styles.name, { color: theme.text, fontFamily: chosen ? font.semibold : font.regular }]}>{t.names[id]}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  strip: { marginHorizontal: -size.gutter },
  themes: { gap: 12, paddingHorizontal: size.gutter, paddingVertical: 2 },
  choice: { width: 104, alignItems: 'center', gap: 8 },
  frame: { borderWidth: 2.5, borderRadius: 22, padding: 3 },
  phone: { width: 92, height: 164, borderRadius: 18, borderWidth: StyleSheet.hairlineWidth, padding: 8, paddingTop: 14, gap: 6, overflow: 'hidden' },
  hero: { height: 40, justifyContent: 'flex-end', padding: 6 },
  figure: { width: '60%', height: 8, borderRadius: 4 },
  small: { flex: 1, height: 28 },
  list: { height: 40 },
  button: { height: 14, width: '50%', alignSelf: 'flex-end' },
  name: { fontSize: size.small, textAlign: 'center' },
  modes: { flexDirection: 'row', borderWidth: 1, padding: 3 },
  mode: { flex: 1, minHeight: 44, alignItems: 'center', justifyContent: 'center' },
  modeText: { fontSize: size.body },
});
