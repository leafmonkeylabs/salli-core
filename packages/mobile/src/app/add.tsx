import {
  accountsList,
  entriesList,
  entriesCreate,
  entriesParse,
  formatAmount,
  ledgerTrialBalance,
  normalizeAmountInput,
  SalliApiError,
} from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useState, type ReactNode } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Card, CardHead, Icon, LinesTable } from '../kit';
import { DateSheet } from '../datesheet';
import { Picker } from '../picker';
import { displayDate, todayIso } from '../lib/display';
import { recentOf } from '../lib/entries';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.add;
type Side = 'debit' | 'credit';

export default function Add() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const api = useApi();
  const queryClient = useQueryClient();
  const accounts = useRead('accounts.list', accountsList);
  const trial = useRead('ledger.trialBalance', ledgerTrialBalance);
  const entries = useRead('entries.list', entriesList);
  const recent = recentOf(entries.data ?? []);
  const currency = trial.data?.currency ?? 'EUR';

  const [said, setSaid] = useState('');
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [debit, setDebit] = useState<string | undefined>(undefined);
  const [credit, setCredit] = useState<string | undefined>(undefined);
  const [drafted, setDrafted] = useState(false);
  // The hand-filled form: opened by the person, or by a server with no model.
  const [byHand, setByHand] = useState(false);
  const [picking, setPicking] = useState<Side | undefined>(undefined);
  const [date, setDate] = useState(todayIso);
  const [dating, setDating] = useState(false);

  const draft = useMutation({
    mutationFn: (text: string) => api.call(entriesParse, { body: { text } }),
    onSuccess: (d) => {
      setDescription(d.description);
      setAmount(d.amount);
      setDebit(d.debit_account_id ?? undefined);
      setCredit(d.credit_account_id ?? undefined);
      setDrafted(true);
      setByHand(false);
    },
    onError: (error) => {
      if (error instanceof SalliApiError && error.status === 503) setByHand(true);
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
      // The app's one success haptic: an entry booked.
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await queryClient.invalidateQueries({ queryKey: [api.server] });
      // The account the money moved in (what you own or owe), for its new balance on the entry.
      const held = (id: string | undefined) => accounts.data?.find((a) => a.id === id && (a.type === 'asset' || a.type === 'liability'));
      const money = held(credit) ?? held(debit);
      router.replace({ pathname: '/entry/[id]', params: { id: entry.id, booked: '1', ...(money ? { account: money.id } : {}) } });
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
        <View style={{ gap: 10 }}>
          <TextInput
            accessibilityLabel={t.say}
            accessibilityHint={t.sayHelp}
            value={draft.isPending ? t.drafting : said}
            onChangeText={setSaid}
            onSubmitEditing={() => said.trim() && draft.mutate(said.trim())}
            placeholder={t.sayPlaceholder}
            placeholderTextColor={theme.muted}
            returnKeyType="go"
            autoCapitalize="none"
            editable={!draft.isPending}
            style={[styles.input, styles.say, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: draft.isPending ? theme.muted : theme.text }]}
          />
          {recent.length && !drafted && !byHand ? (
            <View style={styles.chips}>
              {recent.map((r) => {
                const text = r.amount ? `${r.description} ${r.amount}` : r.description;
                return (
                  <Pressable
                    key={r.description}
                    accessibilityRole="button"
                    accessibilityLabel={t.again(text)}
                    onPress={() => setSaid(text)}
                    style={[styles.chip, { borderColor: theme.rule, backgroundColor: theme.card, borderRadius: Math.min(theme.control, 999) }]}
                  >
                    <Text style={[styles.chipText, { color: theme.muted }]} numberOfLines={1}>
                      {text}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          ) : null}
        </View>
        {draft.error ? <Body alert>{noModel ? t.noModel : draft.error.message}</Body> : null}

        {byHand ? (
          <Card style={{ gap: 14, backgroundColor: theme.input }}>
            <DraftHead date={date} onPress={() => setDating(true)} />
            <Field label={t.description}>
              <TextInput
                value={description}
                onChangeText={setDescription}
                style={[styles.input, { backgroundColor: theme.card, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
              />
            </Field>
            <Field label={t.amount} {...(amount && !exact ? { help: t.notAnAmount } : {})}>
              <TextInput
                value={amount}
                placeholder={t.amountPlaceholder(currency)}
                placeholderTextColor={theme.muted}
                accessibilityHint={t.amountHelp(currency)}
                onChangeText={setAmount}
                keyboardType="decimal-pad"
                style={[styles.input, styles.amountInput, { backgroundColor: theme.card, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
              />
            </Field>
            <AccountField label={t.debit} value={name(debit)} onPress={() => setPicking('debit')} />
            <AccountField label={t.credit} value={name(credit)} onPress={() => setPicking('credit')} />
            {ready ? (
              <Body small muted>
                {t.plain(formatAmount(exact, currency), name(credit), name(debit))}
              </Body>
            ) : null}
          </Card>
        ) : drafted ? (
          // The design's draft: the entry as it would be booked, each account changeable in place.
          <Card style={{ gap: 8, backgroundColor: theme.input }}>
            <DraftHead date={date} onPress={() => setDating(true)} />
            <Text
              accessibilityLabel={exact && debit && credit ? `${description}. ${t.plain(formatAmount(exact, currency), name(credit), name(debit))} ${t.byModel}` : description}
              style={[styles.draftTitle, { color: theme.text }]}
            >
              {description}
            </Text>
            <View style={{ marginTop: 6 }}>
              <LinesTable
                currency={currency}
                changeLabel={t.changeAccount}
                lines={[
                  { key: 'debit', account: name(debit), side: 'debit', amount: exact ?? amount, currency, onChange: () => setPicking('debit') },
                  { key: 'credit', account: name(credit), side: 'credit', amount: exact ?? amount, currency, onChange: () => setPicking('credit') },
                ]}
              />
            </View>
          </Card>
        ) : null}

        {book.error ? <Body alert>{book.error.message}</Body> : null}
        {byHand || drafted ? (
          <Button label={book.isPending ? t.booking : t.book} busy={book.isPending} disabled={!ready || book.isPending} onPress={() => book.mutate()} />
        ) : null}
        {byHand && drafted ? (
          <Button kind="tertiary" label={t.useDraft} onPress={() => setByHand(false)} />
        ) : !byHand ? (
          <Button kind="tertiary" label={t.exactly} onPress={() => setByHand(true)} />
        ) : null}
      </ScrollView>

      <DateSheet
        key={dating ? 'open' : 'closed'}
        visible={dating}
        value={date}
        onClose={() => setDating(false)}
        onPick={(day) => {
          setDate(day);
          setDating(false);
        }}
      />
      <Picker
        title={picking === 'debit' ? t.pickDebit : picking === 'credit' ? t.pickCredit : undefined}
        {...(description.trim() ? { subtitle: exact ? `${description.trim()} · ${formatAmount(exact, currency)}` : description.trim() } : {})}
        accounts={accounts.data ?? []}
        // Into: where money went (spending, mostly); out of: what it came from.
        likely={picking === 'debit' ? ['expense', 'asset'] : ['asset', 'liability']}
        except={picking === 'debit' ? (credit ?? null) : (debit ?? null)}
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

/** The draft's head: its label, and its day, which opens the day picker. */
function DraftHead({ date, onPress }: { date: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <View style={styles.draftHead}>
      <View style={{ flex: 1 }}>
        <CardHead label={t.draftLabel} />
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel={t.changeDay(displayDate(date))} onPress={onPress} style={styles.dateChip}>
        <Text style={[styles.dateText, { color: theme.chart }]}>{displayDate(date)}</Text>
      </Pressable>
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
        style={[styles.input, styles.choose, { backgroundColor: theme.card, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder }]}
      >
        <Body>{value}</Body>
        <Icon name="down" size={16} colour={theme.muted} />
      </Pressable>
    </Field>
  );
}

const styles = StyleSheet.create({
  say: { minHeight: 52, fontSize: 17 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: StyleSheet.hairlineWidth, paddingHorizontal: 12, minHeight: 40, justifyContent: 'center', maxWidth: '100%' },
  chipText: { fontFamily: font.regular, fontSize: size.small },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { fontFamily: font.medium, fontSize: 17 },
  page: { padding: size.gutter, gap: 16 },
  label: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  amountInput: { fontVariant: ['tabular-nums'] },
  draftTitle: { fontFamily: font.medium, fontSize: size.heading, lineHeight: size.heading * 1.3, letterSpacing: -0.2 },
  checked: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 4 },
  draftHead: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  dateChip: { minHeight: size.target, marginTop: -14, justifyContent: 'center', paddingLeft: 12 },
  dateText: { fontFamily: font.medium, fontSize: size.body, fontVariant: ['tabular-nums'] },
  choose: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
