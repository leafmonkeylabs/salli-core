/**
 * Choosing an account: a sheet of the active accounts by type, the chosen one
 * marked. Adding an entry chooses each side with it, review where money came
 * from or went, and an import the account a statement is for.
 */
import type { Account } from '@leafmonkeylabs/salli-sdk';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body } from './kit';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const ORDER = ['expense', 'asset', 'liability', 'income', 'equity'] as const;

/** Open while `title` is set; `types` limits and orders the kinds shown, `except` leaves one out. */
export function Picker({
  title,
  accounts,
  chosen,
  types = ORDER,
  except,
  onPick,
  onClose,
}: {
  title: string | undefined;
  accounts: readonly Account[];
  chosen: string | undefined;
  types?: readonly string[];
  except?: string | null;
  onPick: (id: string) => void;
  onClose: () => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={title !== undefined} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: theme.chrome }}>
        <View style={[styles.header, { borderBottomColor: theme.rule }]}>
          <View style={styles.headerButton} />
          <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]} numberOfLines={1}>
            {title}
          </Text>
          <Pressable accessibilityRole="button" onPress={onClose} style={styles.headerButton}>
            <Body style={{ textAlign: 'right' }}>{strings.add.close}</Body>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingBottom: insets.bottom + 24 }} accessibilityRole="radiogroup">
          {types.map((type) => {
            const rows = accounts.filter((a) => a.type === type && a.is_active && a.id !== except);
            if (!rows.length) return null;
            return (
              <View key={type} style={{ marginBottom: 16 }}>
                <Body small muted>
                  {strings.books.types[type] ?? type}
                </Body>
                {rows.map((account) => {
                  const on = account.id === chosen;
                  return (
                    <Pressable
                      key={account.id}
                      accessibilityRole="radio"
                      accessibilityState={{ checked: on }}
                      onPress={() => onPick(account.id)}
                      style={[styles.option, { borderBottomColor: theme.rule }]}
                    >
                      <View style={[styles.radio, { borderColor: on ? theme.text : theme.muted }]}>{on ? <View style={[styles.dot, { backgroundColor: theme.text }]} /> : null}</View>
                      <Body style={on ? { fontFamily: font.medium } : undefined}>{account.name}</Body>
                    </Pressable>
                  );
                })}
              </View>
            );
          })}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { flexShrink: 1, fontFamily: font.medium, fontSize: 17 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, borderBottomWidth: StyleSheet.hairlineWidth },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
