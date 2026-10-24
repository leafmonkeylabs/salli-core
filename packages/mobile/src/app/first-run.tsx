import {
  entriesList,
  notificationsPreferencesUpdate,
  onboardingBalanceSheet,
  onboardingComplete,
  onboardingGoals,
  onboardingIncome,
  onboardingRiskQuestionnaire,
} from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Card, SectionLabel } from '../kit';
import { balancesOf, DRAWDOWNS, EXPERIENCE, goalsOf, HORIZONS, incomesOf, ROLES, rolesGiven, STABILITY, type Line } from '../lib/firstrun';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.firstRun;
type Step = 'you' | 'own' | 'income' | 'goals' | 'risk';

/**
 * First run (designs 37 to 41): shown once after signing in to a server whose
 * onboarding isn't done. You, then (only on books with nothing in them yet,
 * since they book entries) what you own (each with its kind: cash,
 * investment or other) and owe, and where income comes from (named only:
 * nothing is booked until you are paid), then goals
 * and four risk questions. Every step after You can be skipped.
 */
export default function FirstRun() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const api = useApi();
  const queryClient = useQueryClient();
  const entries = useRead('entries.list', entriesList);
  const empty = entries.data ? entries.data.length === 0 : false;
  const steps: Step[] = empty ? ['you', 'own', 'income', 'goals', 'risk'] : ['you', 'goals', 'risk'];
  const [at, setAt] = useState(0);
  const step = steps[Math.min(at, steps.length - 1)] ?? 'you';
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);

  // What has been typed, kept across steps.
  const [name, setName] = useState('');
  const [currency, setCurrency] = useState('');
  const [residency, setResidency] = useState('');
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const [own, setOwn] = useState<Line[]>([{ name: '', amount: '' }]);
  const [owe, setOwe] = useState<Line[]>([{ name: '', amount: '' }]);
  const [incomes, setIncomes] = useState<Line[]>([{ name: '', amount: '' }]);
  const [goals, setGoals] = useState<(Line & { date: string })[]>([{ name: '', amount: '', date: '' }]);
  const [horizon, setHorizon] = useState<number | undefined>(undefined);
  const [drawdown, setDrawdown] = useState<(typeof DRAWDOWNS)[number] | undefined>(undefined);
  const [stability, setStability] = useState<(typeof STABILITY)[number] | undefined>(undefined);
  const [experience, setExperience] = useState<(typeof EXPERIENCE)[number] | undefined>(undefined);

  const finish = async () => {
    await queryClient.invalidateQueries({ queryKey: [api.server] });
    router.replace('/home');
  };
  const next = () => (at + 1 < steps.length ? setAt(at + 1) : void finish());

  /** Sends this step, then goes on; a refusal stays on the step, said as the server said it. */
  const send = async (call: () => Promise<unknown>) => {
    setBusy(true);
    setProblem(undefined);
    try {
      await call();
      next();
    } catch (error) {
      setProblem(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const submit = () => {
    switch (step) {
      case 'you':
        return send(async () => {
          await api.call(onboardingComplete, {
            body: { name: name.trim(), ...(currency.trim() ? { base_currency: currency.trim().toUpperCase() } : {}), ...(residency.trim() ? { tax_residency: residency.trim().toUpperCase() } : {}) },
          });
          // The digest's preferences keep the time zone; only once one is known.
          if (timeZone) await api.call(notificationsPreferencesUpdate, { body: { time_zone: timeZone } }).catch(() => undefined);
        });
      case 'own': {
        const balances = balancesOf(own, owe);
        return balances.length ? send(() => api.call(onboardingBalanceSheet, { body: { balances } })) : next();
      }
      case 'income': {
        const items = incomesOf(incomes, own);
        return items.length ? send(() => api.call(onboardingIncome, { body: { incomes: items } })) : next();
      }
      case 'goals': {
        const items = goalsOf(goals);
        return items.length ? send(() => api.call(onboardingGoals, { body: { goals: items } })) : next();
      }
      case 'risk':
        return horizon !== undefined && drawdown && stability && experience
          ? send(() =>
              api.call(onboardingRiskQuestionnaire, {
                body: { time_horizon_years: horizon, drawdown_reaction: drawdown, income_stability: stability, investment_experience: experience },
              }),
            )
          : next();
    }
  };

  const ready = step === 'you' ? name.trim().length > 0 : step !== 'own' || rolesGiven(own);
  const last = at + 1 >= steps.length;
  const cta = step === 'own' ? t.bookOpening : last ? t.finish : t.next;

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.work }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={[styles.header, { paddingTop: insets.top + 8, backgroundColor: theme.chrome, borderBottomColor: theme.rule }]}>
        <View style={styles.headerRow}>
          {at > 0 ? (
            <Pressable accessibilityRole="button" onPress={() => setAt(at - 1)} style={styles.headerButton}>
              <Body muted>{t.back}</Body>
            </Pressable>
          ) : (
            <View />
          )}
          {step !== 'you' ? (
            <Pressable accessibilityRole="button" onPress={next} style={styles.headerButton}>
              <Body muted>{t.skip}</Body>
            </Pressable>
          ) : null}
        </View>
        <View accessible accessibilityLabel={t.stepOf(at + 1, steps.length)} style={styles.progress}>
          {steps.map((s, i) => (
            <View key={s} style={[styles.bar, { backgroundColor: i <= at ? theme.chart : theme.rule }]} />
          ))}
        </View>
        <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
          {t.titles[step]}
        </Text>
      </View>

      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: 120 }]} keyboardShouldPersistTaps="handled">
        {step === 'you' ? (
          <>
            <Field label={t.name} value={name} onChange={setName} placeholder={t.namePlaceholder} />
            <Field label={t.currency} value={currency} onChange={setCurrency} placeholder="EUR" caps hint={t.currencyHint} />
            <Field label={t.residency} value={residency} onChange={setResidency} placeholder={t.residencyPlaceholder} caps hint={t.residencyHint} />
            <View style={{ gap: 4 }}>
              <Text style={[styles.label, { color: theme.text }]}>{t.timeZone}</Text>
              <Body muted>{timeZone}</Body>
            </View>
          </>
        ) : step === 'own' ? (
          <>
            <Lines label={t.own} lines={own} onChange={setOwn} placeholder={t.ownPlaceholder} roles />
            <Lines label={t.owe} lines={owe} onChange={setOwe} placeholder={t.owePlaceholder} />
          </>
        ) : step === 'income' ? (
          <>
            <Lines label={t.paidBy} lines={incomes} onChange={setIncomes} placeholder={t.incomePlaceholder} names />
            <Body muted>{t.incomeNote}</Body>
          </>
        ) : step === 'goals' ? (
          <Goals goals={goals} onChange={setGoals} />
        ) : (
          <>
            <Choice label={t.horizon} options={HORIZONS.map((h) => ({ id: h.years, text: h.label }))} chosen={horizon} onPick={setHorizon} />
            <Choice label={t.drawdown} options={DRAWDOWNS.map((d) => ({ id: d, text: t.drawdowns[d] ?? d }))} chosen={drawdown} onPick={setDrawdown} />
            <Choice label={t.stability} options={STABILITY.map((d) => ({ id: d, text: t.stabilities[d] ?? d }))} chosen={stability} onPick={setStability} />
            <Choice label={t.experience} options={EXPERIENCE.map((d) => ({ id: d, text: t.experiences[d] ?? d }))} chosen={experience} onPick={setExperience} />
          </>
        )}
        {problem ? <Body alert>{problem}</Body> : null}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + 12, backgroundColor: theme.work }]}>
        <Button label={cta} busy={busy} disabled={!ready || busy || (step === 'own' && !entries.data)} onPress={() => void submit()} />
      </View>
    </KeyboardAvoidingView>
  );
}

function Field({ label, value, onChange, placeholder, caps, hint }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; caps?: boolean; hint?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={theme.muted}
        autoCapitalize={caps ? 'characters' : 'words'}
        autoCorrect={false}
        accessibilityLabel={label}
        {...(hint ? { accessibilityHint: hint } : {})}
        style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
      />
    </View>
  );
}

/**
 * A list of named amounts, one more row each time the last is filled; with
 * `roles`, each named one asks what kind it is; with `names`, names alone.
 */
function Lines({ label, lines, onChange, placeholder, roles, names }: { label: string; lines: Line[]; onChange: (l: Line[]) => void; placeholder: string; roles?: boolean; names?: boolean }) {
  const theme = useTheme();
  const set = (i: number, patch: Partial<Line>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  return (
    <Card style={{ gap: 10 }}>
      <SectionLabel>{label}</SectionLabel>
      {lines.map((line, i) => (
        <View key={i} style={{ gap: 8 }}>
          <View style={styles.lineRow}>
            <TextInput
              value={line.name}
              onChangeText={(name) => set(i, { name })}
              placeholder={i === 0 ? placeholder : t.another}
              placeholderTextColor={theme.muted}
              accessibilityLabel={`${label} ${i + 1}: ${t.what}`}
              style={[styles.input, { flex: 1, backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
            />
            {names ? null : (
              <TextInput
                value={line.amount}
                onChangeText={(amount) => set(i, { amount })}
                placeholder="0.00"
                placeholderTextColor={theme.muted}
                keyboardType="decimal-pad"
                accessibilityLabel={`${label} ${i + 1}: ${t.amount}`}
                style={[styles.input, styles.amount, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
              />
            )}
          </View>
          {roles && line.name.trim() ? (
            <Choice label={t.kindOf(line.name.trim())} options={ROLES.map((r) => ({ id: r, text: t.roles[r] ?? r }))} chosen={line.role} onPick={(role) => set(i, { role })} />
          ) : null}
        </View>
      ))}
      <Button kind="tertiary" label={t.addOne} onPress={() => onChange([...lines, { name: '', amount: '' }])} />
    </Card>
  );
}

function Goals({ goals, onChange }: { goals: (Line & { date: string })[]; onChange: (g: (Line & { date: string })[]) => void }) {
  const theme = useTheme();
  const set = (i: number, patch: Partial<Line & { date: string }>) => onChange(goals.map((g, j) => (j === i ? { ...g, ...patch } : g)));
  const input = [styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }];
  return (
    <Card style={{ gap: 14 }}>
      {goals.map((goal, i) => (
        <View key={i} style={{ gap: 8 }}>
          <TextInput value={goal.name} onChangeText={(name) => set(i, { name })} placeholder={t.goalPlaceholder} placeholderTextColor={theme.muted} accessibilityLabel={t.goalName} style={input} />
          <View style={styles.lineRow}>
            <TextInput value={goal.amount} onChangeText={(amount) => set(i, { amount })} placeholder={t.goalAmount} placeholderTextColor={theme.muted} keyboardType="decimal-pad" accessibilityLabel={t.goalAmount} style={[...input, { flex: 1 }]} />
            <TextInput value={goal.date} onChangeText={(date) => set(i, { date })} placeholder={t.goalBy} placeholderTextColor={theme.muted} keyboardType="numbers-and-punctuation" accessibilityLabel={t.goalBy} style={[...input, { flex: 1 }]} />
          </View>
        </View>
      ))}
      <Button kind="tertiary" label={t.addGoal} onPress={() => onChange([...goals, { name: '', amount: '', date: '' }])} />
    </Card>
  );
}

function Choice<V extends string | number>({ label, options, chosen, onPick }: { label: string; options: readonly { id: V; text: string }[]; chosen: V | undefined; onPick: (v: V) => void }): ReactNode {
  const theme = useTheme();
  return (
    <View style={{ gap: 8 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      <View accessibilityRole="radiogroup" style={styles.choices}>
        {options.map((o) => {
          const on = o.id === chosen;
          return (
            <Pressable
              key={String(o.id)}
              accessibilityRole="radio"
              accessibilityState={{ checked: on }}
              onPress={() => onPick(o.id)}
              style={[styles.choice, { borderColor: on ? theme.text : theme.rule, backgroundColor: on ? theme.text : theme.card, borderRadius: Math.min(theme.control, 999) }]}
            >
              <Text style={[styles.choiceText, { color: on ? theme.work : theme.text }]}>{o.text}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: size.gutter, paddingBottom: 12, gap: 12 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', minHeight: 36 },
  headerButton: { minHeight: 36, justifyContent: 'center' },
  progress: { flexDirection: 'row', gap: 4 },
  bar: { flex: 1, height: 4 },
  title: { fontFamily: font.semibold, fontSize: 26, letterSpacing: -0.5 },
  page: { padding: size.gutter, gap: 16 },
  label: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
  amount: { width: 120, textAlign: 'right', fontVariant: ['tabular-nums'] },
  lineRow: { flexDirection: 'row', gap: 8 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: { borderWidth: 1, paddingHorizontal: 14, minHeight: 44, justifyContent: 'center' },
  choiceText: { fontFamily: font.regular, fontSize: size.body },
  footer: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: size.gutter, paddingTop: 10 },
});
