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
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Card, Choice, Field as KitField, Icon, Notice, Press, SectionLabel, radii, shape, useDoneBar } from '../kit';
import { balancesOf, DRAWDOWNS, EXPERIENCE, goalsOf, HORIZONS, incomesOf, ROLES, rolesGiven, STABILITY, type Line } from '../lib/firstrun';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.firstRun;
type Step = 'you' | 'own' | 'owe' | 'income' | 'goals' | 'risk';

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
  // From Home with nothing in cash or savings: just what you own, owe and earn.
  const { own: ownOnly } = useLocalSearchParams<{ own?: string }>();
  const steps: Step[] = ownOnly ? ['own', 'owe', 'income'] : empty ? ['you', 'own', 'owe', 'income', 'goals', 'risk'] : ['you', 'goals', 'risk'];
  const [at, setAt] = useState(0);
  const step = steps[Math.min(at, steps.length - 1)] ?? 'you';
  const [busy, setBusy] = useState(false);
  const done = useDoneBar();
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
      case 'own':
        return next();
      case 'owe': {
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
  const cta = step === 'owe' ? t.continue : last ? t.finish : t.next;

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.ground }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={[styles.header, { paddingTop: insets.top + 8, backgroundColor: theme.ground }]}>
        <View style={styles.headerRow}>
          {at > 0 ? (
            <Press accessibilityRole="button" onPress={() => setAt(at - 1)} style={[styles.headerButton, styles.back]}>
              <Icon name="back" colour={theme.text} />
              <Text style={[styles.headerText, { color: theme.text }]}>{t.back}</Text>
            </Press>
          ) : (
            <View />
          )}
          {step !== 'you' ? <Button kind="tertiary" label={t.skip} onPress={next} /> : null}
        </View>
        <View accessible accessibilityRole="progressbar" accessibilityLabel={t.titles[step]} accessibilityValue={{ min: 1, max: steps.length, now: at + 1, text: t.stepOf(at + 1, steps.length) }} style={styles.progress}>
          {steps.map((s, i) => (
            <View key={s} style={[styles.bar, shape(radii.pill), { backgroundColor: i <= at ? theme.green : theme.fill }]} />
          ))}
        </View>
        <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.title, { color: theme.text }]}>
          {t.titles[step]}
        </Text>
      </View>

      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: 120 }]} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive">
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
            <Lines label={t.own} lines={own} onChange={setOwn} placeholder={t.ownPlaceholder} roles done={done} />
          </>
        ) : step === 'owe' ? (
          <Owe lines={owe} onChange={setOwe} currency={currency.trim().toUpperCase()} done={done} />
        ) : step === 'income' ? (
          <>
            <Lines label={t.paidBy} lines={incomes} onChange={setIncomes} placeholder={t.incomePlaceholder} names done={done} />
            <Body muted>{t.incomeNote}</Body>
          </>
        ) : step === 'goals' ? (
          <Goals goals={goals} onChange={setGoals} done={done} />
        ) : (
          <>
            <Choice label={t.horizon} options={HORIZONS.map((h) => ({ id: h.years, text: h.label }))} chosen={horizon} onPick={setHorizon} />
            <Choice label={t.drawdown} options={DRAWDOWNS.map((d) => ({ id: d, text: t.drawdowns[d] ?? d }))} chosen={drawdown} onPick={setDrawdown} />
            <Choice label={t.stability} options={STABILITY.map((d) => ({ id: d, text: t.stabilities[d] ?? d }))} chosen={stability} onPick={setStability} />
            <Choice label={t.experience} options={EXPERIENCE.map((d) => ({ id: d, text: t.experiences[d] ?? d }))} chosen={experience} onPick={setExperience} />
          </>
        )}
        {problem ? <Notice tone="warn">{problem}</Notice> : null}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + 12, backgroundColor: theme.ground }]}>
        <Button label={cta} busy={busy} disabled={!ready || busy || (step === 'owe' && !entries.data)} onPress={() => void submit()} />
        {step === 'owe' ? (
          <Button
            kind="tertiary"
            label={t.oweNothing}
            disabled={busy || !entries.data}
            onPress={() => {
              setOwe([{ name: '', amount: '' }]);
              const balances = balancesOf(own, []);
              void (balances.length ? send(() => api.call(onboardingBalanceSheet, { body: { balances } })) : next());
            }}
          />
        ) : null}
      </View>
      {done.bar}
    </KeyboardAvoidingView>
  );
}

function Field({ label, value, onChange, placeholder, caps, hint }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; caps?: boolean; hint?: string }) {
  return (
    <KitField
      label={label}
      value={value}
      onChangeText={onChange}
      placeholder={placeholder}
      autoCapitalize={caps ? 'characters' : 'words'}
      autoCorrect={false}
      {...(hint ? { accessibilityHint: hint, help: hint } : {})}
    />
  );
}

/**
 * A list of named amounts, one more row each time the last is filled; with
 * `roles`, each named one asks what kind it is; with `names`, names alone.
 */
type DoneBar = ReturnType<typeof useDoneBar>;

function Lines({ label, lines, onChange, placeholder, roles, names, done }: { label: string; lines: Line[]; onChange: (l: Line[]) => void; placeholder: string; roles?: boolean; names?: boolean; done: DoneBar }) {
  const set = (i: number, patch: Partial<Line>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  return (
    <Card style={{ gap: 12 }}>
      <SectionLabel>{label}</SectionLabel>
      {lines.map((line, i) => (
        <View key={i} style={{ gap: 8 }}>
          <View style={styles.lineRow}>
            <KitField
              {...done.field(`${label}-${i}-name`)}
              value={line.name}
              onChangeText={(name) => set(i, { name })}
              placeholder={i === 0 ? placeholder : t.another}
              accessibilityLabel={`${label} ${i + 1}: ${t.what}`}
              style={{ flex: 1 }}
            />
            {names ? null : (
              <KitField
                {...done.field(`${label}-${i}-amount`)}
                value={line.amount}
                onChangeText={(amount) => set(i, { amount })}
                placeholder="0.00"
                keyboardType="decimal-pad"
                accessibilityLabel={`${label} ${i + 1}: ${t.amount}`}
                style={{ width: 132 }}
              />
            )}
          </View>
          {roles && line.name.trim() ? (
            <Choice list label={t.kindOf(line.name.trim())} options={ROLES.map((r) => ({ id: r, text: t.roles[r] ?? r }))} chosen={line.role} onPick={(role) => set(i, { role })} />
          ) : null}
        </View>
      ))}
      <Button kind="tertiary" label={t.addOne} onPress={() => onChange([...lines, { name: '', amount: '' }])} />
    </Card>
  );
}

/** What you owe (design HhObOwe): each debt's name and amount, then its rate and minimum, both optional. */
function Owe({ lines, onChange, currency, done }: { lines: Line[]; onChange: (l: Line[]) => void; currency: string; done: DoneBar }) {
  const set = (i: number, patch: Partial<Line>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const field = (key: string, label: string, optional: boolean, value: string, onText: (v: string) => void, props: { width?: number; amount?: boolean; percent?: boolean; placeholder?: string }) => (
    <KitField
      {...done.field(key)}
      style={props.width ? { width: props.width } : { flex: 1 }}
      label={optional ? `${label} ${t.optional}` : label}
      value={value}
      onChangeText={onText}
      accessibilityLabel={optional ? `${label}, ${t.optional}` : label}
      {...(props.placeholder ? { placeholder: props.placeholder } : {})}
      {...(props.amount || props.percent ? { keyboardType: 'decimal-pad' as const } : {})}
      {...(props.percent ? { end: <Body muted>%</Body> } : {})}
    />
  );
  return (
    <>
      {lines.map((line, i) => (
        <Card key={i} style={{ gap: 12 }}>
          <View style={styles.lineRow}>
            {field(`${i}-name`, t.oweName, false, line.name, (name) => set(i, { name }), i === 0 ? { placeholder: t.owePlaceholder } : {})}
            {field(`${i}-owed`, t.owed(currency), false, line.amount, (amount) => set(i, { amount }), { width: 132, amount: true, placeholder: '0.00' })}
          </View>
          <View style={styles.lineRow}>
            {field(`${i}-rate`, t.rate, true, line.rate ?? '', (rate) => set(i, { rate }), { percent: true, placeholder: '18' })}
            {field(`${i}-minimum`, t.minimum(currency), true, line.minimum ?? '', (minimum) => set(i, { minimum }), { amount: true })}
          </View>
        </Card>
      ))}
      <Button kind="secondary" icon="plus" label={t.addAnother} onPress={() => onChange([...lines, { name: '', amount: '' }])} />
    </>
  );
}

function Goals({ goals, onChange, done }: { goals: (Line & { date: string })[]; onChange: (g: (Line & { date: string })[]) => void; done: DoneBar }) {
  const set = (i: number, patch: Partial<Line & { date: string }>) => onChange(goals.map((g, j) => (j === i ? { ...g, ...patch } : g)));
  return (
    <Card style={{ gap: 16 }}>
      {goals.map((goal, i) => (
        <View key={i} style={{ gap: 12 }}>
          <KitField {...done.field(`${i}-name`)} value={goal.name} onChangeText={(name) => set(i, { name })} placeholder={t.goalPlaceholder} accessibilityLabel={t.goalName} />
          <View style={styles.lineRow}>
            <KitField {...done.field(`${i}-amount`)} style={{ flex: 1 }} value={goal.amount} onChangeText={(amount) => set(i, { amount })} placeholder={t.goalAmount} keyboardType="decimal-pad" accessibilityLabel={t.goalAmount} />
            <KitField {...done.field(`${i}-date`)} style={{ flex: 1 }} value={goal.date} onChangeText={(date) => set(i, { date })} placeholder={t.goalBy} keyboardType="numbers-and-punctuation" accessibilityLabel={t.goalBy} />
          </View>
        </View>
      ))}
      <Button kind="tertiary" label={t.addGoal} onPress={() => onChange([...goals, { name: '', amount: '', date: '' }])} />
    </Card>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: size.gutter, paddingBottom: 12, gap: 12 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: size.target },
  headerButton: { minHeight: size.target, justifyContent: 'center' },
  back: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingRight: 12 },
  headerText: { fontFamily: font.medium, fontSize: size.body },
  progress: { flexDirection: 'row', gap: 4 },
  bar: { flex: 1, height: 6 },
  title: { fontFamily: font.semibold, fontSize: size.largeTitle, letterSpacing: -0.025 * size.largeTitle },
  page: { padding: size.gutter, gap: size.gap },
  label: { fontFamily: font.medium, fontSize: size.small },
  lineRow: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  footer: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: size.gutter, paddingTop: 10 },
});
