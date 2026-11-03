/**
 * Choosing an account (design 10): a sheet of the active accounts, the
 * likely kinds first (spending for money out, income for money in) and the
 * rest under "Your other accounts", narrowed by a search. Equity is never
 * offered: it is the books' opening, not an everyday side. A tap chooses;
 * a choice can be made again, and the chosen one is checked.
 */
import { formatAmount, type Account } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { Modal, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Body, Button, Field, Option, SectionLabel, Surface } from './kit';
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
  const [words, setWords] = useState('');
  const groups = groupsOf(accounts, { likely, typeNames: strings.books.types, ...(others ? { others: t.otherAccounts } : {}), ...(except !== undefined ? { except } : {}), words });
  const balanceOf = (account: Account) => {
    const amount = balances && account.currency === balances.currency ? balances.of[account.id] : undefined;
    return amount === undefined ? undefined : formatAmount(amount, account.currency, { display: 'none' });
  };
  return (
    <>
      <Field
        value={words}
        onChangeText={setWords}
        placeholder={t.find}
        accessibilityLabel={t.find}
        autoCapitalize="none"
        autoCorrect={false}
        clearButtonMode="while-editing"
        returnKeyType="search"
      />
      {groups.length ? (
        groups.map((group) => (
          <View key={group.key} accessibilityRole="radiogroup" accessibilityLabel={group.label} style={{ marginBottom: 16, gap: size.heading }}>
            <SectionLabel>{group.label}</SectionLabel>
            <Surface kind="inset" pad={false} style={{ paddingHorizontal: 16 }}>
              {group.rows.map((account, i) => {
                const balance = balanceOf(account);
                return (
                  <Option
                    key={account.id}
                    label={account.name}
                    {...(balance ? { detail: balance } : {})}
                    chosen={account.id === chosen}
                    last={i === group.rows.length - 1}
                    onPress={() => {
                      setWords('');
                      onPick(account.id);
                    }}
                  />
                );
              })}
            </Surface>
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
      <View style={{ flex: 1, backgroundColor: theme.ground }} onAccessibilityEscape={onClose}>
        <View style={styles.header}>
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
          <Button small kind="secondary" label={t.close} onPress={onClose} />
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingBottom: insets.bottom + 24, gap: 12 }} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive">
          <AccountList {...list} />
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, paddingHorizontal: size.gutter, paddingTop: 20, paddingBottom: 12 },
  title: { fontFamily: font.semibold, fontSize: size.title, lineHeight: size.title * 1.25 },
});
