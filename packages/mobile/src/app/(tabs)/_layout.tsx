import type { ComponentProps } from 'react';
import { Tabs } from 'expo-router';
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
  return (
    <Tabs screenOptions={{ headerShown: false, sceneStyle: { backgroundColor: theme.work } }} tabBar={(props) => <Bar {...props} />}>
      {PLACES.map((place) => (
        <Tabs.Screen key={place.name} name={place.name} options={{ title: place.label }} />
      ))}
    </Tabs>
  );
}

type BottomTabBarProps = Parameters<NonNullable<ComponentProps<typeof Tabs>['tabBar']>>[0];

/** The current place in ink at weight 500 with a 2 px bar above it: not colour alone. */
function Bar({ state, emitter, navigateToTab }: BottomTabBarProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View accessibilityRole="tablist" style={[styles.bar, { backgroundColor: theme.chrome, borderTopColor: theme.rule, paddingBottom: insets.bottom }]}>
      {state.routes.map((route, index) => {
        const place = PLACES.find((p) => p.name === route.name);
        if (!place) return null;
        const current = state.index === index;
        const colour = current ? theme.text : theme.muted;
        return (
          <Pressable
            key={route.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: current }}
            accessibilityLabel={place.label}
            onPress={() => {
              const event = emitter.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
              if (!current && !event.defaultPrevented) navigateToTab(route.key);
            }}
            style={[styles.place, { borderTopColor: current ? theme.text : 'transparent' }]}
          >
            <Icon name={place.icon} colour={colour} />
            <Text style={[styles.label, { color: colour, fontFamily: current ? font.medium : font.regular }]}>{place.label}</Text>
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
