import type { ComponentProps } from 'react';
import { onboardingStatus } from '@leafmonkeylabs/salli-sdk';
import { router, Tabs } from 'expo-router';
import { useEffect, useRef } from 'react';
import { useRead } from '../../api';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, type IconName } from '../../kit';
import { strings } from '../../strings';
import { font, useTheme } from '../../theme';

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
      <Tabs screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: theme.work } }} tabBar={(props) => <Bar {...props} />}>
        {PLACES.map((place) => (
          <Tabs.Screen key={place.name} name={place.name} options={{ title: place.label }} />
        ))}
      </Tabs>
    </View>
  );
}

type BottomTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];

/**
 * The current place in ink (the theme's own colour) at weight 500 with a 2 px
 * bar above it: not colour alone. Its labels stay on one line, growing a
 * little with the text size; pressed and held at the larger sizes, the
 * system shows the place large (the Large Content Viewer), as its own bar does.
 */
function Bar({ state, emitter, navigateToTab }: BottomTabBarProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View accessibilityRole="tablist" style={[styles.bar, { backgroundColor: theme.chrome, borderTopColor: theme.rule, paddingBottom: insets.bottom }]}>
      {state.routes.map((route, index) => {
        const place = PLACES.find((p) => p.name === route.name);
        if (!place) return null;
        const current = state.index === index;
        const colour = current ? theme.current : theme.muted;
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
              if (!current && !event.defaultPrevented) navigateToTab(route.key);
            }}
            style={[styles.place, { borderTopColor: current ? theme.current : 'transparent' }]}
          >
            <Icon name={place.icon} colour={colour} {...(current && theme.currentFill ? { fill: theme.currentFill } : {})} />
            <Text numberOfLines={1} maxFontSizeMultiplier={1.15} style={[styles.label, { color: colour, fontFamily: current ? font.medium : font.regular }]}>
              {place.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', borderTopWidth: StyleSheet.hairlineWidth },
  place: { flex: 1, minHeight: 56, alignItems: 'center', justifyContent: 'center', gap: 2, paddingVertical: 6, borderTopWidth: 2 },
  label: { fontSize: 12 },
});
