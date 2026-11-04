import { router, useLocalSearchParams } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Icon } from '../kit';
import { radii, shape } from '../kit';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.accountDeleted;

/** After erasing an account (design AccountDeleted): said once, with the way back to choosing a server. */
export default function AccountDeleted() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { host = '' } = useLocalSearchParams<{ host: string }>();
  return (
    <View style={[styles.page, { backgroundColor: theme.ground, paddingTop: insets.top + 120, paddingBottom: insets.bottom + 24 }]}>
      <View style={styles.centre}>
        <View style={[styles.mark, shape(radii.pill), { backgroundColor: theme.greenTint }]}>
          <Icon name="check" size={30} colour={theme.green} />
        </View>
        <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
          {t.title}
        </Text>
        <Body muted style={{ textAlign: 'center' }}>{t.body(host)}</Body>
      </View>
      <Button label={t.choose} onPress={() => router.replace('/welcome')} />
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, paddingHorizontal: size.gutter, justifyContent: 'space-between' },
  centre: { alignItems: 'center', gap: 14, paddingHorizontal: 4 },
  mark: { width: 72, height: 72, alignItems: 'center', justifyContent: 'center' },
  title: { fontFamily: font.semibold, fontSize: size.title + 4, textAlign: 'center' },
});
