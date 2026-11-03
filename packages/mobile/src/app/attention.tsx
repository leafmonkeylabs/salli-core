import { insightsSignals, remindersCreate, remindersDelete, remindersList, type FinanceSignal, type Reminder } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, type Href } from 'expo-router';
import { useState } from 'react';
import { ActionSheetIOS, Alert, Platform, StyleSheet, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';
import { useApi, useRead } from '../api';
import { Body, Button, Card, Chip, Field, Icon, Notice, Press, RoundButton, Section, Waiting, radii, shape } from '../kit';
import { displayDate, displayDay, todayIso } from '../lib/display';
import { listMotion, useReducedMotion } from '../motion';
import { useMarkDone } from '../reminders';
import { Page } from '../shell';
import { Sheet, SheetTitle } from '../sheet';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.attention;

/** Where a signal points in the app: a budget signal opens its own line. */
function placeOf(signal: FinanceSignal): Href | undefined {
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
      return signal.refs[0] ? { pathname: '/budget/[id]', params: { id: signal.refs[0] } } : '/budget';
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

  const list = listMotion(useReducedMotion());
  const done = useMarkDone();
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
          { text: t.done, onPress: () => done.mutate(r) },
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
      action={<RoundButton icon="plus" tone="ink" label={t.add} onPress={plus} />}
      onRefresh={() => Promise.all([signals.refetch(), reminders.refetch()])}
    >
      <View style={{ gap: size.section }}>
      <Section title={t.noticed}>
      <Card style={{ paddingVertical: 8 }}>
        {signals.data ? (
          signals.data.signals.length ? (
            signals.data.signals.map((s, i) => {
              const place = placeOf(s);
              const row = (
                <>
                  <View style={[styles.marker, shape(radii.pill), { backgroundColor: s.severity === 'info' ? theme.muted : theme.red }]} />
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
              const style = [styles.row, i < signals.data.signals.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line } : null];
              return (
                <Animated.View key={`${s.kind}-${i}`} {...list}>
                  {place ? (
                    <Press highlight accessibilityRole="button" onPress={() => router.push(place)} style={style}>
                      {row}
                    </Press>
                  ) : (
                    <View accessible style={style}>
                      {row}
                    </View>
                  )}
                </Animated.View>
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
      </Section>

      <Section title={t.reminders}>
      <Card style={{ paddingVertical: 8 }}>
        {reminders.data ? (
          <>
            {overdue.length ? <Group label={t.overdue} items={overdue} late onDone={askDone} list={list} /> : null}
            {coming.length ? <Group label={t.coming} items={coming} onDone={askDone} list={list} /> : null}
            {!pending.length ? (
              <Body muted style={{ paddingVertical: 12 }}>
                {t.nothingDue}
              </Body>
            ) : null}
            {finished.length ? (
              <Press
                highlight
                accessibilityRole="button"
                accessibilityState={{ expanded: showDone }}
                onPress={() => setShowDone((s) => !s)}
                style={[styles.row, { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.line }]}
              >
                <Body muted style={{ flex: 1 }}>
                  {t.doneCount(finished.length)}
                </Body>
                <Icon name={showDone ? 'down' : 'chevron'} size={16} colour={theme.muted} />
              </Press>
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
      </Section>
      </View>

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

function Group({ label, items, late, onDone, list }: { label: string; items: Reminder[]; late?: boolean; onDone: (r: Reminder) => void; list: ReturnType<typeof listMotion> }) {
  const theme = useTheme();
  return (
    <Animated.View {...list}>
      <Text style={[styles.sub, { color: theme.muted }]}>{label}</Text>
      {items.map((r, i) => (
        <Animated.View key={r.id} {...list} style={[styles.row, i < items.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line } : null]}>
          <View accessible accessibilityLabel={`${r.kind}, ${displayDate(r.due_date)}`} style={{ flex: 1 }}>
            <Body>{r.kind}</Body>
          </View>
          <Text style={[styles.when, { color: late ? theme.red : theme.muted }]}>{displayDay(r.due_date)}</Text>
          <Button kind="secondary" label={r.source_domain === 'decision' ? t.review : t.done} accessibilityLabel={t.doneLabel(r.kind)} onPress={() => onDone(r)} />
        </Animated.View>
      ))}
    </Animated.View>
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
      <SheetTitle style={[styles.sheetTitle, { color: theme.text }]}>
        {t.newReminder}
      </SheetTitle>
      <Field value={kind} onChangeText={setKind} placeholder={t.what} accessibilityLabel={t.what} autoFocus />
      <View accessibilityRole="radiogroup" style={styles.chips}>
        {quick.map((q) => {
          const on = !typed.trim() && q.due === due;
          return (
            <Chip
              key={q.label}
              label={q.label}
              selected={on}
              onPress={() => {
                setDue(q.due);
                setTyped('');
              }}
            />
          );
        })}
      </View>
      <Field value={typed} onChangeText={setTyped} placeholder={t.orDate} accessibilityLabel={t.orDate} keyboardType="numbers-and-punctuation" />
      <Body small muted>
        {displayDate(chosen)}
      </Body>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
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
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 8 },
  marker: { width: 8, height: 8 },
  sub: { fontFamily: font.medium, fontSize: size.label, paddingTop: 10 },
  when: { fontFamily: font.regular, fontSize: size.small, fontVariant: ['tabular-nums'] },
  sheetTitle: { fontFamily: font.semibold, fontSize: size.title },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
