import { insightsSignals, remindersCreate, remindersDelete, remindersList, remindersMarkDone, type FinanceSignal, type Reminder } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { ActionSheetIOS, Alert, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useApi, useRead } from '../api';
import { Body, Button, Card, Icon, SectionLabel, Waiting } from '../kit';
import { displayDate, displayDay, todayIso } from '../lib/display';
import { Page } from '../shell';
import { Sheet } from '../sheet';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.attention;

/** Where a signal points in the app. */
function placeOf(signal: FinanceSignal): '/cash' | '/books' | '/decide' | '/debts' | '/budget' | undefined {
  switch (signal.action) {
    case 'see_forecast':
    case 'see_recurring':
    case 'see_spending':
    case 'see_cash_flow':
      return '/cash';
    case 'review':
      return '/books';
    case 'see_debts':
      return '/debts';
    case 'see_budget':
      return '/budget';
    case 'review_decision':
      return '/decide';
    default:
      return undefined;
  }
}

/** A date a few days from today, as ISO. */
function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return todayIso(d);
}

/**
 * Attention (design 42): what Salli has noticed, then your reminders by when
 * they are due, the finished ones folded at the end. + adds a reminder or
 * opens the filing dates your tax rules set.
 */
export default function Attention() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const signals = useRead('insights.signals', insightsSignals);
  const reminders = useRead('reminders.list', remindersList);
  const [adding, setAdding] = useState(false);
  const [showDone, setShowDone] = useState(false);
  const today = todayIso();
  const again = () => queryClient.invalidateQueries({ queryKey: [api.server] });

  const done = useMutation({ mutationFn: (id: string) => api.call(remindersMarkDone, { path: { reminder_id: id } }), onSuccess: again });
  const remove = useMutation({ mutationFn: (id: string) => api.call(remindersDelete, { path: { reminder_id: id } }), onSuccess: again });

  const all = reminders.data?.reminders ?? [];
  const pending = all.filter((r) => r.status === 'pending').sort((a, b) => a.due_date.localeCompare(b.due_date));
  const finished = all.filter((r) => r.status !== 'pending');
  const overdue = pending.filter((r) => r.due_date < today);
  const coming = pending.filter((r) => r.due_date >= today);

  const askDone = (r: Reminder) =>
    // A decision's review is recorded in Decide, not marked done here.
    r.source_domain === 'decision'
      ? router.push('/decide')
      : Alert.alert(t.doneTitle, t.doneBody(r.kind), [
          { text: t.cancel, style: 'cancel' },
          { text: t.done, onPress: () => done.mutate(r.id) },
        ]);
  const askDelete = (r: Reminder) =>
    Alert.alert(t.deleteTitle, r.source_domain === 'tax_rules' ? t.deleteFiling : t.deleteBody(r.kind), [
      { text: t.cancel, style: 'cancel' },
      { text: t.delete, style: 'destructive', onPress: () => remove.mutate(r.id) },
    ]);
  const plus = () => {
    const choices = [t.newReminder, t.filing];
    const pick = (i: number) => (i === 0 ? setAdding(true) : i === 1 ? router.push('/filing') : undefined);
    if (Platform.OS === 'ios') ActionSheetIOS.showActionSheetWithOptions({ options: [...choices, t.cancel], cancelButtonIndex: 2 }, pick);
    else Alert.alert(t.add, undefined, [...choices.map((text, i) => ({ text, onPress: () => pick(i) })), { text: t.cancel, style: 'cancel' as const }]);
  };

  return (
    <Page
      title={t.title}
      back={{ label: strings.more.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}
      action={
        <Pressable accessibilityRole="button" accessibilityLabel={t.add} onPress={plus} style={styles.plus}>
          <Icon name="plus" colour={theme.text} />
        </Pressable>
      }
      onRefresh={() => Promise.all([signals.refetch(), reminders.refetch()])}
    >
      <Card style={{ paddingVertical: 4 }}>
        <View style={{ paddingTop: 8 }}>
          <SectionLabel>{t.noticed}</SectionLabel>
        </View>
        {signals.data ? (
          signals.data.signals.length ? (
            signals.data.signals.map((s, i) => {
              const place = placeOf(s);
              const row = (
                <>
                  <View style={[styles.marker, { backgroundColor: s.severity === 'info' ? theme.muted : theme.negative, borderRadius: theme.marker === 'dot' ? 4 : 0 }]} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <Body>{s.title}</Body>
                    {s.detail ? (
                      <Body small muted>
                        {s.detail}
                      </Body>
                    ) : null}
                  </View>
                  {place ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
                </>
              );
              const style = [styles.row, i < signals.data.signals.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.rule } : null];
              return place ? (
                <Pressable key={`${s.kind}-${i}`} accessibilityRole="link" onPress={() => router.push(place)} style={style}>
                  {row}
                </Pressable>
              ) : (
                <View key={`${s.kind}-${i}`} accessible style={style}>
                  {row}
                </View>
              );
            })
          ) : (
            <Body muted style={{ paddingVertical: 12 }}>
              {t.nothingNoticed}
            </Body>
          )
        ) : (
          <Waiting query={signals} what="what Salli noticed" />
        )}
      </Card>

      <Card style={{ paddingVertical: 4 }}>
        <View style={{ paddingTop: 8 }}>
          <SectionLabel>{t.reminders}</SectionLabel>
        </View>
        {reminders.data ? (
          <>
            {overdue.length ? <Group label={t.overdue} items={overdue} late onDone={askDone} /> : null}
            {coming.length ? <Group label={t.coming} items={coming} onDone={askDone} /> : null}
            {!pending.length ? (
              <Body muted style={{ paddingVertical: 12 }}>
                {t.nothingDue}
              </Body>
            ) : null}
            {finished.length ? (
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ expanded: showDone }}
                onPress={() => setShowDone((s) => !s)}
                style={[styles.row, { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.rule }]}
              >
                <Body muted style={{ flex: 1 }}>
                  {t.doneCount(finished.length)}
                </Body>
                <Icon name={showDone ? 'down' : 'chevron'} size={16} colour={theme.muted} />
              </Pressable>
            ) : null}
            {showDone
              ? finished.map((r) => (
                  <View key={r.id} style={styles.row}>
                    <Body muted style={{ flex: 1 }}>
                      {r.kind}
                    </Body>
                    <Button kind="tertiary" label={t.delete} accessibilityLabel={t.deleteLabel(r.kind)} onPress={() => askDelete(r)} />
                  </View>
                ))
              : null}
          </>
        ) : (
          <Waiting query={reminders} what="your reminders" />
        )}
      </Card>

      <AddSheet
        key={adding ? 'open' : 'closed'}
        visible={adding}
        onClose={() => setAdding(false)}
        onAdd={(kind, due) =>
          api.call(remindersCreate, { body: { kind, due_date: due } }).then(() => {
            setAdding(false);
            return again();
          })
        }
      />
    </Page>
  );
}

function Group({ label, items, late, onDone }: { label: string; items: Reminder[]; late?: boolean; onDone: (r: Reminder) => void }) {
  const theme = useTheme();
  return (
    <View>
      <Text style={[styles.sub, { color: theme.muted }]}>{label.toUpperCase()}</Text>
      {items.map((r, i) => (
        <View key={r.id} style={[styles.row, i < items.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.rule } : null]}>
          <View accessible accessibilityLabel={`${r.kind}, ${displayDate(r.due_date)}`} style={{ flex: 1 }}>
            <Body>{r.kind}</Body>
          </View>
          <Text style={[styles.when, { color: late ? theme.negative : theme.muted }]}>{displayDay(r.due_date)}</Text>
          <Button kind="secondary" label={r.source_domain === 'decision' ? t.review : t.done} accessibilityLabel={t.doneLabel(r.kind)} onPress={() => onDone(r)} />
        </View>
      ))}
    </View>
  );
}

/** A new reminder: what, and when from a few quick dates. */
function AddSheet({ visible, onClose, onAdd }: { visible: boolean; onClose: () => void; onAdd: (kind: string, due: string) => Promise<unknown> }) {
  const theme = useTheme();
  const [kind, setKind] = useState('');
  const quick = [
    { label: t.tomorrow, due: inDays(1) },
    { label: t.inAWeek, due: inDays(7) },
    { label: t.inAMonth, due: inDays(30) },
  ];
  const [due, setDue] = useState(quick[1]?.due ?? inDays(7));
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const chosen = /^\d{4}-\d{2}-\d{2}$/.test(typed.trim()) ? typed.trim() : due;
  return (
    <Sheet visible={visible} onClose={onClose} label={t.newReminder}>
      <Text accessibilityRole="header" style={[styles.sheetTitle, { color: theme.text }]}>
        {t.newReminder}
      </Text>
      <TextInput
        value={kind}
        onChangeText={setKind}
        placeholder={t.what}
        placeholderTextColor={theme.muted}
        accessibilityLabel={t.what}
        autoFocus
        style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
      />
      <View accessibilityRole="radiogroup" style={styles.chips}>
        {quick.map((q) => {
          const on = !typed.trim() && q.due === due;
          return (
            <Pressable
              key={q.label}
              accessibilityRole="radio"
              accessibilityState={{ checked: on }}
              onPress={() => {
                setDue(q.due);
                setTyped('');
              }}
              style={[styles.chip, { borderColor: on ? theme.text : theme.rule, backgroundColor: on ? theme.text : theme.card, borderRadius: Math.min(theme.control, 999) }]}
            >
              <Text style={[styles.chipText, { color: on ? theme.work : theme.text }]}>{q.label}</Text>
            </Pressable>
          );
        })}
      </View>
      <TextInput
        value={typed}
        onChangeText={setTyped}
        placeholder={t.orDate}
        placeholderTextColor={theme.muted}
        accessibilityLabel={t.orDate}
        keyboardType="numbers-and-punctuation"
        style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
      />
      <Body small muted>
        {displayDate(chosen)}
      </Body>
      {problem ? <Body alert>{problem}</Body> : null}
      <Button
        label={t.addReminder}
        busy={busy}
        disabled={!kind.trim() || busy}
        onPress={() => {
          setBusy(true);
          setProblem(undefined);
          onAdd(kind.trim(), chosen)
            .catch((error: unknown) => setProblem(error instanceof Error ? error.message : String(error)))
            .finally(() => setBusy(false));
        }}
      />
    </Sheet>
  );
}

const styles = StyleSheet.create({
  plus: { width: size.target, height: size.target, alignItems: 'center', justifyContent: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, paddingVertical: 8 },
  marker: { width: 8, height: 8 },
  sub: { fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.1, paddingTop: 10 },
  when: { fontFamily: font.regular, fontSize: size.small, fontVariant: ['tabular-nums'] },
  sheetTitle: { fontFamily: font.medium, fontSize: size.heading },
  input: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, paddingHorizontal: 14, minHeight: 44, justifyContent: 'center' },
  chipText: { fontFamily: font.regular, fontSize: size.body },
});
