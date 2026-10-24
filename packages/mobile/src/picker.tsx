/**
 * Choosing an account (design 10): a sheet of the active accounts, the
 * likely kinds first (spending for money out, income for money in) and the
 * rest under "Your other accounts", narrowed by a search. Equity is never
 * offered: it is the books' opening, not an everyday side. A tap chooses;
 * a choice can be made again.
 */
import type { Account } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body } from './kit';
import { groupsOf } from './lib/accounts';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.add;
/**
 * Open while `title` is set. `likely` lists the kinds to show first, each
 * under its own heading; `others` folds every other kind under "Your other
 * accounts" (off where only the likely kinds belong, as an import's
 * account). `except` leaves one account out.
 */
export function Picker({
  title,
  subtitle,
  accounts,
  chosen,
  likely,
  others = true,
  except,
  onPick,
  onClose,
}: {
  title: string | undefined;
  subtitle?: string;
  accounts: readonly Account[];
  chosen: string | undefined;
  likely: readonly string[];
  others?: boolean;
  except?: string | null;
  onPick: (id: string) => void;
  onClose: () => void;
}) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [words, setWords] = useState('');
  const groups = groupsOf(accounts, { likely, typeNames: strings.books.types, ...(others ? { others: t.otherAccounts } : {}), ...(except !== undefined ? { except } : {}), words });
  const close = () => {
    setWords('');
    onClose();
  };

  return (
    <Modal visible={title !== undefined} animationType="slide" presentationStyle="pageSheet" onRequestClose={close}>
      <View style={{ flex: 1, backgroundColor: theme.chrome }}>
        <View style={[styles.header, { borderBottomColor: theme.rule }]}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]} numberOfLines={2}>
              {title}
            </Text>
            {subtitle ? (
              <Body small muted>
                {subtitle}
              </Body>
            ) : null}
          </View>
          <Pressable accessibilityRole="button" onPress={close} style={styles.close}>
            <Body>{t.close}</Body>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingBottom: insets.bottom + 24, gap: 12 }} keyboardShouldPersistTaps="handled">
          <TextInput
            value={words}
            onChangeText={setWords}
            placeholder={t.find}
            placeholderTextColor={theme.muted}
            accessibilityLabel={t.find}
            autoCapitalize="none"
            autoCorrect={false}
            clearButtonMode="while-editing"
            returnKeyType="search"
            style={[styles.input, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
          />
          <View accessibilityRole="radiogroup">
            {groups.length ? (
              groups.map((group) => (
                <View key={group.key} style={{ marginBottom: 16 }}>
                  <Body small muted style={styles.group}>
                    {group.label}
                  </Body>
                  {group.rows.map((account) => {
                    const on = account.id === chosen;
                    return (
                      <Pressable
                        key={account.id}
                        accessibilityRole="radio"
                        accessibilityState={{ checked: on }}
                        onPress={() => {
                          setWords('');
                          onPick(account.id);
                        }}
                        style={[styles.option, { borderBottomColor: theme.rule }]}
                      >
                        <View style={[styles.radio, { borderColor: on ? theme.text : theme.muted }]}>{on ? <View style={[styles.dot, { backgroundColor: theme.text }]} /> : null}</View>
                        <Body style={on ? { fontFamily: font.medium } : undefined}>{account.name}</Body>
                      </Pressable>
                    );
                  })}
                </View>
              ))
            ) : (
              <Body muted>{t.noMatch(words.trim())}</Body>
            )}
          </View>
          <Body small muted>
            {t.newOnConsole}
          </Body>
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: size.gutter, paddingTop: 16, paddingBottom: 12 },
  title: { fontFamily: font.medium, fontSize: size.heading, lineHeight: size.heading * 1.25 },
  close: { minHeight: size.target, minWidth: 56, alignItems: 'flex-end', justifyContent: 'flex-start', paddingTop: 2 },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  group: { fontFamily: font.medium },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, borderBottomWidth: StyleSheet.hairlineWidth },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
