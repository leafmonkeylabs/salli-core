import { supportsAlternateIcons } from 'expo-alternate-app-icons';
import { router } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useColorScheme } from 'react-native';
import { useAppearance } from '../appearance';
import { Body, Press, Section, Segmented, radii, shape } from '../kit';
import { HAS_NIGHT, isNight, MODES, THEMES, typeOf, type ThemeId } from '../lib/appearance';
import { haptic } from '../motion';
import { Page } from '../shell';
import { strings } from '../strings';
import { elevation, font, openedWith, size, space, themeOf, useTheme } from '../theme';

const t = strings.appearance;

/**
 * Appearance (design 23): whether it follows the phone, for the themes with
 * a night side, and a theme, picked from small pictures of Home in each.
 */
export default function Appearance() {
  const { appearance, set } = useAppearance();
  const phoneDark = useColorScheme() === 'dark';

  return (
    <Page title={t.title} back={{ label: strings.more.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      {HAS_NIGHT.includes(appearance.theme) ? (
        <Section title={t.mode}>
          <Segmented label={t.mode} options={MODES.map((m) => ({ id: m, text: t.modes[m] }))} value={appearance.mode} onChange={(mode) => set({ ...appearance, mode })} />
          <Body small muted>
            {t.auto}
          </Body>
        </Section>
      ) : null}

      <View style={{ marginTop: space.s16 }}>
        <Section title={t.theme}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} accessibilityRole="radiogroup" contentContainerStyle={styles.themes} style={styles.strip}>
            {THEMES.map((id) => (
              <Choice
                key={id}
                id={id}
                chosen={appearance.theme === id}
                night={isNight({ ...appearance, theme: id }, phoneDark)}
                onPress={() => {
                  haptic.select();
                  set({ ...appearance, theme: id });
                }}
              />
            ))}
          </ScrollView>
          {supportsAlternateIcons || typeOf(appearance.theme) !== typeOf(openedWith) ? (
            <Body small muted>
              {[supportsAlternateIcons ? t.icon : '', typeOf(appearance.theme) !== typeOf(openedWith) ? t.typeLater : ''].filter(Boolean).join(' ')}
            </Body>
          ) : null}
        </Section>
      </View>
    </Page>
  );
}

/** A theme as a small picture of Home: its ground, its key figure's card, its cards and its button, on the app's own shapes at a third of their size. */
function Choice({ id, chosen, night, onPress }: { id: ThemeId; chosen: boolean; night: boolean; onPress: () => void }) {
  const theme = useTheme();
  const look = themeOf(id, night);
  const card = { backgroundColor: look.surface, ...shape(radii.card / 3), ...elevation(look, 'card') };
  return (
    <Press accessibilityRole="radio" accessibilityLabel={t.names[id]} accessibilityState={{ checked: chosen }} onPress={onPress} style={styles.choice}>
      <View style={[styles.frame, shape(radii.key), { borderColor: chosen ? theme.green : 'transparent' }]}>
        <View style={[styles.phone, shape(radii.card), { backgroundColor: look.ground }]}>
          <View style={[styles.hero, card, shape(radii.key / 3)]}>
            <View style={[styles.figure, shape(radii.pill), { backgroundColor: look.text }]} />
          </View>
          <View style={{ flexDirection: 'row', gap: 4 }}>
            <View style={[styles.small, card]} />
            <View style={[styles.small, card]} />
          </View>
          <View style={[styles.list, card]} />
          <View style={[styles.button, shape(radii.pill), { backgroundColor: look.button }]} />
        </View>
      </View>
      <Text style={[styles.name, { color: theme.text, fontFamily: chosen ? font.semibold : font.regular }]}>{t.names[id]}</Text>
    </Press>
  );
}

const styles = StyleSheet.create({
  strip: { marginHorizontal: -size.gutter },
  themes: { gap: space.s12, paddingHorizontal: size.gutter, paddingVertical: 2 },
  choice: { width: 104, alignItems: 'center', gap: 8 },
  frame: { borderWidth: 2.5, padding: 3 },
  phone: { width: 92, height: 164, padding: 8, paddingTop: 14, gap: 6, overflow: 'hidden' },
  hero: { height: 44, justifyContent: 'flex-end', padding: 6 },
  figure: { width: '60%', height: 8 },
  small: { flex: 1, height: 28 },
  list: { height: 40 },
  button: { height: 14, width: '50%', alignSelf: 'flex-end' },
  name: { fontSize: size.small, textAlign: 'center' },
});
