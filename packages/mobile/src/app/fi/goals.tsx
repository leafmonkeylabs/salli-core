import { accountsList, goalsAllocationsList, goalsAllocationsSet, goalsCreate, goalsDelete, goalsList, goalsUpdate, normalizeAmountInput, type Goal } from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, Money, Waiting } from '../../kit';
import { amountParts, displayMonth, wholeDigits } from '../../lib/display';
import { Page } from '../../shell';
import { Sheet } from '../../sheet';
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
          <Card style={{ paddingVertical: 0 }}>
            {goals.data.goals.map((g, i, all) => {
              const share = Math.min(1, Math.max(0, Number(g.progress))); // eslint-disable-line no-restricted-syntax -- not money: a fraction for a bar
              return (
                <Pressable
                  key={g.id}
                  accessibilityRole="button"
                  accessibilityLabel={t.goalSpoken(g.name, amountParts(g.allocated_amount, g.currency).spoken, amountParts(g.target_amount, g.currency).spoken)}
                  onPress={() => setEditing(g)}
                  style={[styles.goal, i < all.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.rule } : null]}
                >
                  <View style={styles.goalHead}>
                    <Body style={{ flex: 1 }}>{g.name}</Body>
                    <Text style={[styles.figure, { color: theme.text }]}>
                      {wholeDigits(g.allocated_amount, g.currency)} <Text style={{ color: theme.muted }}>/ {wholeDigits(g.target_amount, g.currency)}</Text>
                    </Text>
                  </View>
                  <View style={[styles.track, { backgroundColor: theme.rule }]}>
                    <View style={[styles.track, { width: `${share * 100}%`, backgroundColor: theme.chart }]} />
                  </View>
                  <View style={styles.goalHead}>
                    <Body small muted style={{ flex: 1 }}>
                      {g.target_date ? t.by(displayMonth(g.target_date)) : t.noDate}
                    </Body>
                    <Pressable accessibilityRole="button" accessibilityLabel={t.fundLabel(g.name)} onPress={() => setFunding(g)} style={styles.fund}>
                      <Text style={[styles.fundText, { color: theme.chart }]}>{t.fund}</Text>
                    </Pressable>
                  </View>
                </Pressable>
              );
            })}
          </Card>
        ) : (
          <Card>
            <Body muted>{t.noGoals}</Body>
          </Card>
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
  const input = [styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }];
  return (
    <Sheet visible={!!goal} onClose={onClose} label={existing ? existing.name : t.newGoal}>
      <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
        {existing ? existing.name : t.newGoal}
      </Text>
      <TextInput value={name} onChangeText={setName} placeholder={t.goalName} placeholderTextColor={theme.muted} accessibilityLabel={t.goalName} style={input} />
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <TextInput value={amount} onChangeText={setAmount} placeholder={t.target} placeholderTextColor={theme.muted} keyboardType="decimal-pad" accessibilityLabel={t.target} style={[...input, { flex: 1 }]} />
        <TextInput value={year} onChangeText={setYear} placeholder={t.byYear} placeholderTextColor={theme.muted} keyboardType="number-pad" accessibilityLabel={t.byYear} style={[...input, { flex: 1 }]} />
      </View>
      {problem ? <Body alert>{problem}</Body> : null}
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
  const valueOf = (id: string) => typed[id] ?? current.data?.allocations.find((a) => a.account_id === id)?.allocated_amount ?? '';

  return (
    <Sheet visible={!!goal} onClose={onClose} label={goal ? t.fundTitle(goal.name) : ''}>
      <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
        {goal ? t.fundTitle(goal.name) : ''}
      </Text>
      {held.map((a) => (
        <View key={a.id} style={styles.fundRow}>
          <Body style={{ flex: 1 }}>{a.name}</Body>
          <TextInput
            value={valueOf(a.id)}
            onChangeText={(v) => setTyped((now) => ({ ...now, [a.id]: v }))}
            placeholder="0.00"
            placeholderTextColor={theme.muted}
            keyboardType="decimal-pad"
            accessibilityLabel={t.fromAccount(a.name)}
            style={[styles.input, styles.amount, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
          />
        </View>
      ))}
      {goal ? (
        <Body small muted>
          {t.target}: <Money amount={goal.target_amount} currency={goal.currency} />
        </Body>
      ) : null}
      {problem ? <Body alert>{problem}</Body> : null}
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
    </Sheet>
  );
}

const styles = StyleSheet.create({
  goal: { paddingVertical: 12, gap: 8 },
  goalHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  figure: { fontFamily: font.regular, fontSize: size.body, fontVariant: ['tabular-nums'] },
  track: { height: 6 },
  fund: { minHeight: 36, justifyContent: 'center', paddingLeft: 12 },
  fundText: { fontFamily: font.medium, fontSize: size.small },
  title: { fontFamily: font.medium, fontSize: size.heading },
  input: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  amount: { width: 130, textAlign: 'right', fontVariant: ['tabular-nums'] },
  fundRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
});
