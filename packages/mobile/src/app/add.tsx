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
import { useState } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Chip, Field, Icon, LinesTable, Notice, Press, SectionLabel, Surface, Tag, useDoneBar } from '../kit';
import { haptic } from '../motion';
import { DayChooser } from '../datesheet';
import { useKeepDraft } from '../draft';
import { AccountList } from '../picker';
import { displayDate, todayIso } from '../lib/display';
import { recentOf } from '../lib/entries';
import { strings } from '../strings';
import { font, radii, shape, size, useTheme } from '../theme';

const t = strings.add;
type Side = 'debit' | 'credit';
/** What Add shows: its form, or pushed inside it an account or the day to choose (one sheet on screen). */
type Showing = 'form' | Side | 'date';

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
  const [showing, setShowing] = useState<Showing>('form');
  const [date, setDate] = useState(todayIso);
  const done = useDoneBar();
  const keep = useKeepDraft(said.trim() !== '' || drafted || description.trim() !== '' || amount.trim() !== '');

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
      haptic.success();
      await queryClient.invalidateQueries({ queryKey: [api.server] });
      // The account the money moved in (what you own or owe), for its new balance on the entry.
      const held = (id: string | undefined) => accounts.data?.find((a) => a.id === id && (a.type === 'asset' || a.type === 'liability'));
      const money = held(credit) ?? held(debit);
      keep.done();
      router.replace({ pathname: '/entry/[id]', params: { id: entry.id, booked: '1', ...(money ? { account: money.id } : {}) } });
    },
  });

  const name = (id: string | undefined): string => accounts.data?.find((a) => a.id === id)?.name ?? t.choose;
  const ready = !!exact && !!debit && !!credit && debit !== credit && description.trim().length > 0;
  // 503: the server has no model to draft with; anything else is said as the server said it.
  const noModel = draft.error instanceof SalliApiError && draft.error.status === 503;
  // What Book it still waits for, said above it rather than only drawn unavailable.
  const missing = !description.trim()
    ? t.missing.description
    : !exact
      ? amount.trim()
        ? t.notAnAmount
        : t.missing.amount
      : !credit
        ? t.missing.credit
        : !debit
          ? t.missing.debit
          : debit === credit
            ? t.missing.same
            : undefined;
  const pick = (side: Side) => setShowing(side);

  if (showing !== 'form') {
    return (
      <View style={{ flex: 1, backgroundColor: theme.surface }} onAccessibilityEscape={() => setShowing('form')}>
        <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? 8 : insets.top, }]}>
          <Press accessibilityRole="button" onPress={() => setShowing('form')} style={[styles.headerButton, styles.back]}>
            <Icon name="back" colour={theme.text} />
            <Body max={1.5}>{t.back}</Body>
          </Press>
          <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.headerTitle, { color: theme.text }]}>
            {showing === 'date' ? t.date : showing === 'debit' ? t.pickDebit : t.pickCredit}
          </Text>
          <View style={styles.headerButton} />
        </View>
        <ScrollView contentContainerStyle={[styles.page, { paddingBottom: insets.bottom + 24, gap: 12 }]} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" automaticallyAdjustKeyboardInsets>
          {showing === 'date' ? (
            <DayChooser
              value={date}
              onPick={(day) => {
                setDate(day);
                setShowing('form');
              }}
            />
          ) : (
            <AccountList
              accounts={accounts.data ?? []}
              // Into: where money went (spending, mostly); out of: what it came from.
              likely={showing === 'debit' ? ['expense', 'asset'] : ['asset', 'liability']}
              except={showing === 'debit' ? (credit ?? null) : (debit ?? null)}
              chosen={showing === 'debit' ? debit : credit}
              {...(trial.data ? { balances: { currency: trial.data.currency, of: trial.data.balances } } : {})}
              onPick={(id) => {
                if (showing === 'debit') setDebit(id);
                else setCredit(id);
                setShowing('form');
              }}
            />
          )}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.surface }} onAccessibilityEscape={() => router.back()}>
      {/* A sheet on iOS sits below the status bar; full screen elsewhere, it needs the inset. */}
      <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? 8 : insets.top }]}>
        <Press accessibilityRole="button" onPress={() => router.back()} style={styles.headerButton}>
          <Body max={1.5}>{t.cancel}</Body>
        </Press>
        <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.headerTitle, { color: theme.text }]}>
          {t.title}
        </Text>
        <View style={styles.headerButton} />
      </View>

      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" automaticallyAdjustKeyboardInsets>
        <View style={{ gap: 12 }}>
          <Field
            label={t.say}
            accessibilityHint={t.sayHelp}
            value={draft.isPending ? t.drafting : said}
            onChangeText={setSaid}
            onSubmitEditing={() => said.trim() && draft.mutate(said.trim())}
            placeholder={t.sayPlaceholder}
            returnKeyType="go"
            autoCapitalize="none"
            editable={!draft.isPending}
          />
          {recent.length && !drafted && !byHand ? (
            <View style={styles.chips}>
              {recent.map((r) => {
                const text = r.amount ? `${r.description} ${r.amount}` : r.description;
                return <Chip key={r.description} role="button" label={text} onPress={() => setSaid(text)} />;
              })}
            </View>
          ) : null}
        </View>
        {draft.error ? <Notice tone="warn">{noModel ? t.noModel : draft.error.message}</Notice> : null}

        {byHand ? (
          <Surface style={{ gap: 16 }}>
            <DraftHead date={date} onPress={() => setShowing('date')} exact />
            <Field {...done.field('description')} label={t.description} value={description} onChangeText={setDescription} />
            <Field
              {...done.field('amount')}
              amount
              label={t.amountIn(currency)}
              value={amount}
              placeholder={t.amountPlaceholder(currency)}
              accessibilityHint={t.amountHelp(currency)}
              onChangeText={setAmount}
              keyboardType="decimal-pad"
              {...(amount && !exact ? { error: t.notAnAmount } : {})}
            />
            <AccountField label={t.credit} value={name(credit)} unset={!credit} onPress={() => pick('credit')} />
            <AccountField label={t.debit} value={name(debit)} unset={!debit} onPress={() => pick('debit')} />
            {ready ? (
              <Body small muted>
                {t.plain(formatAmount(exact, currency), name(credit), name(debit))}
              </Body>
            ) : null}
          </Surface>
        ) : drafted ? (
          // The design's draft: the entry as it would be booked, each account changeable in place.
          <Surface style={{ gap: 12 }}>
            <DraftHead date={date} onPress={() => setShowing('date')} />
            <Text
              accessibilityLabel={exact && debit && credit ? `${description}. ${t.plain(formatAmount(exact, currency), name(credit), name(debit))} ${t.byModel}` : description}
              style={[styles.draftTitle, { color: theme.text }]}
            >
              {description}
            </Text>
            <LinesTable
              currency={currency}
              changeLabel={t.changeAccount}
              lines={[
                { key: 'debit', account: name(debit), side: 'debit', amount: exact ?? amount, currency, onChange: () => pick('debit') },
                { key: 'credit', account: name(credit), side: 'credit', amount: exact ?? amount, currency, onChange: () => pick('credit') },
              ]}
            />
            <Body small muted>{t.byModel}</Body>
          </Surface>
        ) : null}

        {book.error ? <Notice tone="warn">{book.error.message}</Notice> : null}
        {byHand || drafted ? (
          <View style={{ gap: 12 }}>
            {missing && !book.isPending ? <Notice tone="neutral">{missing}</Notice> : null}
            <Button label={book.isPending ? t.booking : t.book} busy={book.isPending} disabled={!ready || book.isPending} {...(missing ? { accessibilityHint: missing } : {})} onPress={() => book.mutate()} />
          </View>
        ) : null}
        {byHand && drafted ? (
          <Button kind="tertiary" label={t.useDraft} onPress={() => setByHand(false)} />
        ) : !byHand ? (
          <Button kind="tertiary" label={t.exactly} onPress={() => setByHand(true)} />
        ) : null}
      </ScrollView>

      {done.bar}
    </View>
  );
}

/** The draft's head: a Draft tag, and its day, which opens the day picker. */
function DraftHead({ date, onPress, exact }: { date: string; onPress: () => void; exact?: boolean }) {
  const theme = useTheme();
  return (
    <View style={styles.draftHead}>
      {exact ? <View /> : <Tag tone="green">{t.draftLabel}</Tag>}
      <Press accessibilityRole="button" accessibilityLabel={t.changeDay(displayDate(date))} hitSlop={8} onPress={onPress} style={styles.dateChip}>
        <Text style={[styles.dateText, { color: theme.green }]}>{displayDate(date)}</Text>
      </Press>
    </View>
  );
}

/** An account to choose: a filled row that opens the list. */
function AccountField({ label, value, unset, onPress }: { label: string; value: string; unset: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <SectionLabel>{label}</SectionLabel>
      <Press accessibilityRole="button" accessibilityLabel={`${label}: ${value}`} onPress={onPress} style={[styles.choose, shape(radii.field), { backgroundColor: theme.fill }]}>
        <Body muted={unset} style={{ flex: 1 }}>
          {value}
        </Body>
        <Icon name="chevron" size={16} colour={theme.muted} />
      </Press>
    </View>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: size.gutter - 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { flex: 1, textAlign: 'center', fontFamily: font.semibold, fontSize: size.headline },
  back: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 0 },
  page: { padding: size.gutter, gap: size.gap },
  draftTitle: { fontFamily: font.semibold, fontSize: size.title, lineHeight: size.title * 1.25, letterSpacing: -0.01 * size.title },
  draftHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  dateChip: { minHeight: size.target, justifyContent: 'center', paddingLeft: 12 },
  dateText: { fontFamily: font.medium, fontSize: size.body, fontVariant: ['tabular-nums'] },
  choose: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: size.control, paddingHorizontal: 16 },
});
