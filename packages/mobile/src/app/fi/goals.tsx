import { accountsList, goalsAllocationsList, goalsAllocationsSet, goalsCreate, goalsDelete, goalsList, goalsUpdate, normalizeAmountInput, type Goal } from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Field, Money, Notice, Press, ProgressBar, Surface, Waiting, useDoneBar } from '../../kit';
import { amountParts, displayMonth, wholeDigits } from '../../lib/display';
import { Page } from '../../shell';
import { Sheet, SheetTitle } from '../../sheet';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.fi;

/**
 * Goals (design 47): each with how far its funding goes towards its target;
 * add one, change or delete it, and fund it from your accounts.
 */
export default function Goals() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const goals = useRead('goals.list', goalsList);
  const [editing, setEditing] = useState<Goal | 'new' | undefined>(undefined);
  const [funding, setFunding] = useState<Goal | undefined>(undefined);
  const again = () => queryClient.invalidateQueries({ queryKey: [api.server] });

  return (
    <Page title={t.goals} back={{ label: t.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/fi')) }} onRefresh={() => goals.refetch()}>
      {goals.data ? (
        goals.data.goals.length ? (
          <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
            {goals.data.goals.map((g, i, all) => {
              const share = Math.min(1, Math.max(0, Number(g.progress))); // eslint-disable-line no-restricted-syntax -- not money: a fraction for a bar
              return (
                <Press
                  highlight
                  key={g.id}
                  accessibilityRole="button"
                  accessibilityLabel={t.goalSpoken(g.name, amountParts(g.allocated_amount, g.currency).spoken, amountParts(g.target_amount, g.currency).spoken)}
                  onPress={() => setEditing(g)}
                  style={[styles.goal, i < all.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line } : null]}
                >
                  <View style={styles.goalHead}>
                    <Body style={{ flex: 1 }}>{g.name}</Body>
                    <Text style={[styles.figure, { color: theme.text }]}>
                      {wholeDigits(g.allocated_amount, g.currency)} <Text style={{ color: theme.muted }}>/ {wholeDigits(g.target_amount, g.currency)}</Text>
                    </Text>
                  </View>
                  <ProgressBar ratio={share} />
                  <View style={styles.goalHead}>
                    <Body small muted style={{ flex: 1 }}>
                      {g.target_date ? t.by(displayMonth(g.target_date)) : t.noDate}
                    </Body>
                    <Button small kind="secondary" label={t.fund} accessibilityLabel={t.fundLabel(g.name)} onPress={() => setFunding(g)} />
                  </View>
                </Press>
              );
            })}
          </Surface>
        ) : (
          <Surface>
            <Body muted>{t.noGoals}</Body>
          </Surface>
        )
      ) : (
        <Waiting query={goals} what="your goals" />
      )}
      <Button kind="secondary" icon="plus" label={t.addGoal} onPress={() => setEditing('new')} />
      <GoalSheet
        key={editing === 'new' ? 'new' : (editing?.id ?? 'none')}
        goal={editing}
        onClose={() => setEditing(undefined)}
        onSave={async (body) => {
          if (editing === 'new') await api.call(goalsCreate, { body });
          else if (editing) await api.call(goalsUpdate, { path: { goal_id: editing.id }, body });
          setEditing(undefined);
          await again();
        }}
        onDelete={
          editing && editing !== 'new'
            ? () =>
                Alert.alert(t.deleteTitle, t.deleteBody(editing.name), [
                  { text: t.cancel, style: 'cancel' },
                  {
                    text: t.delete,
                    style: 'destructive',
                    onPress: () =>
                      void api.call(goalsDelete, { path: { goal_id: editing.id } }).then(() => {
                        setEditing(undefined);
                        return again();
                      }),
                  },
                ])
            : undefined
        }
      />
      <FundSheet key={funding?.id ?? 'none'} goal={funding} onClose={() => setFunding(undefined)} onSaved={() => void again()} />
    </Page>
  );
}

function GoalSheet({
  goal,
  onClose,
  onSave,
  onDelete,
}: {
  goal: Goal | 'new' | undefined;
  onClose: () => void;
  onSave: (body: { name: string; target_amount: string; target_date?: string }) => Promise<void>;
  onDelete: (() => void) | undefined;
}) {
  const theme = useTheme();
  const existing = goal && goal !== 'new' ? goal : undefined;
  const [name, setName] = useState(existing?.name ?? '');
  const [amount, setAmount] = useState(existing?.target_amount ?? '');
  const [year, setYear] = useState(existing?.target_date?.slice(0, 4) ?? '');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const exact = normalizeAmountInput(amount);
  const done = useDoneBar(true);
  return (
    <Sheet visible={!!goal} onClose={onClose} label={existing ? existing.name : t.newGoal}>
      <SheetTitle style={[styles.title, { color: theme.text }]}>
        {existing ? existing.name : t.newGoal}
      </SheetTitle>
      <Field {...done.field('name')} value={name} onChangeText={setName} placeholder={t.goalName} accessibilityLabel={t.goalName} />
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Field {...done.field('amount')} value={amount} onChangeText={setAmount} placeholder={t.target} keyboardType="decimal-pad" accessibilityLabel={t.target} style={{ flex: 1 }} />
        <Field {...done.field('year')} value={year} onChangeText={setYear} placeholder={t.byYear} keyboardType="number-pad" accessibilityLabel={t.byYear} style={{ flex: 1 }} />
      </View>
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      <Button
        label={t.save}
        busy={busy}
        disabled={!name.trim() || !exact || busy}
        onPress={() => {
          if (!exact) return;
          setBusy(true);
          setProblem(undefined);
          onSave({ name: name.trim(), target_amount: exact, ...(/^\d{4}$/.test(year.trim()) ? { target_date: `${year.trim()}-12-31` } : {}) })
            .catch((error: unknown) => setProblem(error instanceof Error ? error.message : String(error)))
            .finally(() => setBusy(false));
        }}
      />
      {onDelete ? <Button kind="tertiary" label={t.delete} onPress={onDelete} /> : null}
      {done.bar}
    </Sheet>
  );
}

/** Funding a goal: an amount from each account that holds money towards it. */
function FundSheet({ goal, onClose, onSaved }: { goal: Goal | undefined; onClose: () => void; onSaved: () => void }) {
  const theme = useTheme();
  const api = useApi();
  const accounts = useRead('accounts.list', accountsList);
  const current = useRead('goals.allocations', goalsAllocationsList, { path: { goal_id: goal?.id ?? '' } }, { enabled: !!goal });
  const held = (accounts.data ?? []).filter((a) => a.is_active && a.type === 'asset');
  const [typed, setTyped] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const done = useDoneBar(true);
  const valueOf = (id: string) => typed[id] ?? current.data?.allocations.find((a) => a.account_id === id)?.allocated_amount ?? '';

  return (
    <Sheet visible={!!goal} onClose={onClose} label={goal ? t.fundTitle(goal.name) : ''}>
      <SheetTitle style={[styles.title, { color: theme.text }]}>
        {goal ? t.fundTitle(goal.name) : ''}
      </SheetTitle>
      {held.map((a) => (
        <View key={a.id} style={styles.fundRow}>
          <Body style={{ flex: 1 }}>{a.name}</Body>
          <Field {...done.field(a.id)} value={valueOf(a.id)} onChangeText={(v) => setTyped((now) => ({ ...now, [a.id]: v }))} placeholder="0.00" keyboardType="decimal-pad" accessibilityLabel={t.fromAccount(a.name)} style={styles.amount} />
        </View>
      ))}
      {goal ? (
        <Body small muted>
          {t.target}: <Money amount={goal.target_amount} currency={goal.currency} />
        </Body>
      ) : null}
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      <Button
        label={t.save}
        busy={busy}
        disabled={busy || !Object.keys(typed).length}
        onPress={() => {
          if (!goal) return;
          setBusy(true);
          setProblem(undefined);
          const changes = Object.entries(typed).map(([account_id, v]) => ({ account_id, allocated_amount: normalizeAmountInput(v || '0') ?? '0' }));
          Promise.all(changes.map((body) => api.call(goalsAllocationsSet, { path: { goal_id: goal.id }, body })))
            .then(() => {
              onSaved();
              onClose();
            })
            .catch((error: unknown) => setProblem(error instanceof Error ? error.message : String(error)))
            .finally(() => setBusy(false));
        }}
      />
      {done.bar}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  goal: { paddingVertical: 14, gap: 10 },
  goalHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  figure: { fontFamily: font.regular, fontSize: size.body, fontVariant: ['tabular-nums'] },
  title: { fontFamily: font.semibold, fontSize: size.title },
  amount: { width: 140 },
  fundRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
});
