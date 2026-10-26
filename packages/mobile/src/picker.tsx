/**
 * Choosing an account (design 10): a sheet of the active accounts, the
 * likely kinds first (spending for money out, income for money in) and the
 * rest under "Your other accounts", narrowed by a search. Equity is never
 * offered: it is the books' opening, not an everyday side. A tap chooses;
 * a choice can be made again, and the chosen one is checked.
 */
import { formatAmount, type Account } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Option, SectionLabel } from './kit';
import { groupsOf } from './lib/accounts';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.add;

type ListProps = {
  accounts: readonly Account[];
  chosen: string | undefined;
  likely: readonly string[];
  others?: boolean;
  except?: string | null;
  /** Each account's balance in `currency`, as the server sent it, shown under its name. */
  balances?: { currency: string; of: Readonly<Record<string, string>> };
  onPick: (id: string) => void;
};

/**
 * The accounts to choose from: a search, then each group, the chosen one
 * checked. Drawn in the picker's sheet, or pushed inside a sheet that is
 * already open (Add: design AddOneSheet), so one sheet is on screen.
 */
export function AccountList({ accounts, chosen, likely, others = true, except, balances, onPick }: ListProps) {
  const theme = useTheme();
  const [words, setWords] = useState('');
  const groups = groupsOf(accounts, { likely, typeNames: strings.books.types, ...(others ? { others: t.otherAccounts } : {}), ...(except !== undefined ? { except } : {}), words });
  const balanceOf = (account: Account) => {
    const amount = balances && account.currency === balances.currency ? balances.of[account.id] : undefined;
    return amount === undefined ? undefined : formatAmount(amount, account.currency, { display: 'none' });
  };
  return (
    <>
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
      {groups.length ? (
        groups.map((group) => (
          <View key={group.key} accessibilityRole="radiogroup" accessibilityLabel={group.label} style={{ marginBottom: 16 }}>
            <SectionLabel>{group.label}</SectionLabel>
            <View style={{ marginTop: 6 }}>
              {group.rows.map((account) => {
                const balance = balanceOf(account);
                return (
                  <Option
                    key={account.id}
                    label={account.name}
                    {...(balance ? { detail: balance } : {})}
                    chosen={account.id === chosen}
                    onPress={() => {
                      setWords('');
                      onPick(account.id);
                    }}
                  />
                );
              })}
            </View>
          </View>
        ))
      ) : (
        <Body muted>{t.noMatch(words.trim())}</Body>
      )}
      <Body small muted>
        {t.newOnConsole}
      </Body>
    </>
  );
}

/**
 * Open while `title` is set. `likely` lists the kinds to show first, each
 * under its own heading; `others` folds every other kind under "Your other
 * accounts" (off where only the likely kinds belong, as an import's
 * account). `except` leaves one account out.
 */
export function Picker({ title, subtitle, onClose, ...list }: ListProps & { title: string | undefined; subtitle?: string; onClose: () => void }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={title !== undefined} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: theme.chrome }} onAccessibilityEscape={onClose}>
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
          <Pressable accessibilityRole="button" onPress={onClose} style={styles.close}>
            <Body max={1.5}>{t.close}</Body>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingBottom: insets.bottom + 24, gap: 12 }} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive">
          <AccountList {...list} />
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
});
