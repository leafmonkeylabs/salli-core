import type { ComponentProps } from 'react';
import { onboardingStatus } from '@leafmonkeylabs/salli-sdk';
import { router, Tabs } from 'expo-router';
import { useEffect, useRef } from 'react';
import { useRead } from '../../api';
import { BlurView } from 'expo-blur';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, radii, shape, type IconName } from '../../kit';
import { haptic } from '../../motion';
import { TabInset } from '../../shell';
import { strings } from '../../strings';
import { floating, font, size, useTheme } from '../../theme';

/** The console's phone bar, unchanged: Home, Cash, Decide, Books, More. */
const PLACES: { name: string; label: string; icon: IconName }[] = [
  { name: 'home', label: strings.nav.home, icon: 'home' },
  { name: 'cash', label: strings.nav.cash, icon: 'cash' },
  { name: 'decide', label: strings.nav.decide, icon: 'decide' },
  { name: 'books', label: strings.nav.books, icon: 'books' },
  { name: 'more', label: strings.nav.more, icon: 'more' },
];

export default function TabsLayout() {
  const theme = useTheme();
  // First run (designs 37 to 41), once, while the server says onboarding isn't done.
  const status = useRead('onboarding.status', onboardingStatus);
  const asked = useRef(false);
  useEffect(() => {
    if (asked.current || !status.data || status.data.complete) return;
    asked.current = true;
    router.push('/first-run');
  }, [status.data]);
  return (
    <View style={{ flex: 1 }}>
      <Tabs screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: theme.ground } }} tabBar={(props) => <Bar {...props} />}>
        {PLACES.map((place) => (
          <Tabs.Screen key={place.name} name={place.name} options={{ title: place.label }} />
        ))}
      </Tabs>
    </View>
    </TabInset.Provider>
  );
}

type BottomTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];

const BAR = 64;
/** The floating bar's distance from the screen's foot, by the home indicator's room. */
const lift = (bottom: number) => Math.max(bottom - 6, 12);

/**
 * A floating capsule over the page: blurred, inset 16 from each side and
 * lifted by a shadow. The current place is a green-tint pill behind its icon
 * and label (not colour alone: its label is medium weight too). Labels are
 * 12 and stay on one line, growing a little with the text size; pressed and
 * held at the larger sizes, the system shows the place large (the Large
 * Content Viewer), as its own bar does.
 */
function Bar({ state, emitter, navigateToTab }: BottomTabBarProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View pointerEvents="box-none" style={[styles.wrap, { bottom: lift(insets.bottom) }]}>
      <View style={[styles.floating, shape(radii.pill), floating(theme)]}>
        <View style={[StyleSheet.absoluteFill, shape(radii.pill), { overflow: 'hidden' }]}>
          <BlurView intensity={60} tint={theme.blur === 'dark' ? 'dark' : 'light'} style={StyleSheet.absoluteFill} />
          <View style={[StyleSheet.absoluteFill, { backgroundColor: theme.surface, opacity: 0.78 }]} />
        </View>
        <View accessibilityRole="tablist" style={styles.bar}>
          {state.routes.map((route, index) => {
            const place = PLACES.find((p) => p.name === route.name);
            if (!place) return null;
            const current = state.index === index;
            const colour = current ? theme.green : theme.muted;
            return (
              <Pressable
                key={route.key}
                accessibilityRole="tab"
                accessibilityState={{ selected: current }}
                accessibilityLabel={place.label}
                accessibilityShowsLargeContentViewer
                accessibilityLargeContentTitle={place.label}
                onPress={() => {
                  const event = emitter.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
                  if (!current && !event.defaultPrevented) {
                    haptic.select();
                    navigateToTab(route.key);
                  }
                }}
                style={styles.place}
              >
                <View style={[styles.pill, shape(radii.pill), current ? { backgroundColor: theme.greenTint } : null]}>
                  <Icon name={place.icon} size={22} colour={colour} />
                  <Text numberOfLines={1} maxFontSizeMultiplier={1.15} style={[styles.label, { color: colour, fontFamily: current ? font.medium : font.regular }]}>
                    {place.label}
                  </Text>
                </View>
              </Pressable>
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'absolute', left: 16, right: 16 },
  floating: { height: BAR },
  bar: { flex: 1, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 },
  place: { flex: 1, minHeight: size.target, alignItems: 'center', justifyContent: 'center' },
  pill: { minWidth: 56, minHeight: 52, alignItems: 'center', justifyContent: 'center', gap: 2, paddingHorizontal: 10, paddingVertical: 4 },
  label: { fontSize: size.caption },
});
