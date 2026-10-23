import {
  accountsList,
  entriesCreate,
  entriesParse,
  formatAmount,
  ledgerTrialBalance,
  normalizeAmountInput,
  SalliApiError,
  type Account,
} from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Card, CardHead, Icon } from '../kit';
import { displayDate, todayIso } from '../lib/display';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.add;
const TYPES = ['expense', 'asset', 'liability', 'income', 'equity'] as const;
type Side = 'debit' | 'credit';

export default function Add() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const api = useApi();
  const queryClient = useQueryClient();
  const accounts = useRead('accounts.list', accountsList);
  const trial = useRead('ledger.trialBalance', ledgerTrialBalance);
  const currency = trial.data?.currency ?? 'EUR';

  const [said, setSaid] = useState('');
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [debit, setDebit] = useState<string | undefined>(undefined);
  const [credit, setCredit] = useState<string | undefined>(undefined);
  const [drafted, setDrafted] = useState(false);
  const [picking, setPicking] = useState<Side | undefined>(undefined);
  const date = todayIso();

  const draft = useMutation({
    mutationFn: (text: string) => api.call(entriesParse, { body: { text } }),
    onSuccess: (d) => {
      setDescription(d.description);
      setAmount(d.amount);
      setDebit(d.debit_account_id ?? undefined);
      setCredit(d.credit_account_id ?? undefined);
      setDrafted(true);
    },
  });
  const exact = normalizeAmountInput(amount);
  const book = useMutation({
    mutationFn: () =>
      api.call(entriesCreate, {
        body: {
          entry_date: date,
          description: description.trim(),
          postings: [
            { account_id: debit ?? '', direction: 1, amount: exact ?? '', currency },
            { account_id: credit ?? '', direction: -1, amount: exact ?? '', currency },
          ],
        },
      }),
    onSuccess: async (entry) => {
      await queryClient.invalidateQueries({ queryKey: [api.server] });
      router.replace({ pathname: '/entry/[id]', params: { id: entry.id, booked: '1' } });
    },
  });

  const name = (id: string | undefined): string => accounts.data?.find((a) => a.id === id)?.name ?? t.choose;
  const ready = !!exact && !!debit && !!credit && debit !== credit && description.trim().length > 0;
  // 503: the server has no model to draft with; anything else is said as the server said it.
  const noModel = draft.error instanceof SalliApiError && draft.error.status === 503;

  return (
    <View style={{ flex: 1, backgroundColor: theme.chrome }}>
      {/* A sheet on iOS sits below the status bar; full screen elsewhere, it needs the inset. */}
      <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? 8 : insets.top, borderBottomColor: theme.rule }]}>
        <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.headerButton}>
          <Body>{t.cancel}</Body>
        </Pressable>
        <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
          {t.title}
        </Text>
        <View style={styles.headerButton} />
      </View>

      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled">
        <Field label={t.say}>
          <TextInput
            value={said}
            onChangeText={setSaid}
            onSubmitEditing={() => said.trim() && draft.mutate(said.trim())}
            placeholder={t.sayPlaceholder}
            placeholderTextColor={theme.muted}
            returnKeyType="go"
            style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text }]}
          />
        </Field>
        <Button kind="secondary" label={draft.isPending ? t.drafting : t.draft} busy={draft.isPending} disabled={!said.trim() || draft.isPending} onPress={() => draft.mutate(said.trim())} />
        {draft.error ? <Body alert>{noModel ? t.noModel : draft.error.message}</Body> : null}

        <Card style={{ gap: 14, backgroundColor: theme.input }}>
          <CardHead label={t.draftLabel} end={displayDate(date)} />
          <Field label={t.description}>
            <TextInput
              value={description}
              onChangeText={setDescription}
              style={[styles.input, { backgroundColor: theme.card, borderColor: theme.fieldBorder, color: theme.text }]}
            />
          </Field>
          <Field label={t.amount} help={amount && !exact ? t.notAnAmount : t.amountHelp(currency)}>
            <TextInput
              value={amount}
              onChangeText={setAmount}
              keyboardType="decimal-pad"
              style={[styles.input, styles.amountInput, { backgroundColor: theme.card, borderColor: theme.fieldBorder, color: theme.text }]}
            />
          </Field>
          <AccountField label={t.debit} value={name(debit)} onPress={() => setPicking('debit')} />
          <AccountField label={t.credit} value={name(credit)} onPress={() => setPicking('credit')} />
          {ready ? (
            <Body small muted>
              {t.plain(formatAmount(exact, currency), name(credit), name(debit))}
            </Body>
          ) : null}
          {drafted ? (
            <Body small muted>
              {t.byModel}
            </Body>
          ) : null}
        </Card>

        {book.error ? <Body alert>{book.error.message}</Body> : null}
        <Button label={book.isPending ? t.booking : t.book} busy={book.isPending} disabled={!ready || book.isPending} onPress={() => book.mutate()} />
      </ScrollView>

      <Picker
        side={picking}
        accounts={accounts.data ?? []}
        chosen={picking === 'debit' ? debit : credit}
        onClose={() => setPicking(undefined)}
        onPick={(id) => {
          if (picking === 'debit') setDebit(id);
          else setCredit(id);
          setPicking(undefined);
        }}
      />
    </View>
  );
}

function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      {children}
      {help ? (
        <Body small muted>
          {help}
        </Body>
      ) : null}
    </View>
  );
}

function AccountField({ label, value, onPress }: { label: string; value: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Field label={label}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${value}`}
        onPress={onPress}
        style={[styles.input, styles.choose, { backgroundColor: theme.card, borderColor: theme.fieldBorder }]}
      >
        <Body>{value}</Body>
        <Icon name="down" size={16} colour={theme.muted} />
      </Pressable>
    </Field>
  );
}

/** The accounts, by type, to choose one: a sheet over the draft. */
function Picker({ side, accounts, chosen, onPick, onClose }: { side: Side | undefined; accounts: readonly Account[]; chosen: string | undefined; onPick: (id: string) => void; onClose: () => void }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={!!side} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: theme.chrome }}>
        <View style={[styles.header, { borderBottomColor: theme.rule }]}>
          <View style={styles.headerButton} />
          <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
            {side === 'debit' ? t.pickDebit : t.pickCredit}
          </Text>
          <Pressable accessibilityRole="button" onPress={onClose} style={styles.headerButton}>
            <Body>{t.close}</Body>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingBottom: insets.bottom + 24 }} accessibilityRole="radiogroup">
          {TYPES.map((type) => {
            const rows = accounts.filter((a) => a.type === type && a.is_active);
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
  headerTitle: { fontFamily: font.medium, fontSize: 17 },
  page: { padding: size.gutter, gap: 16 },
  label: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  amountInput: { fontVariant: ['tabular-nums'] },
  choose: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, borderBottomWidth: StyleSheet.hairlineWidth },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
