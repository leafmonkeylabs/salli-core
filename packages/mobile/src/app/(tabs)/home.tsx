import {
  accountsList,
  compareAmounts,
  decisionsReviewsDue,
  fiScoreGet,
  insightsForecast,
  insightsNetWorth,
  insightsSafeToSpend,
  insightsSignals,
  isZeroAmount,
  ledgerIncomeStatement,
  remindersList,
  remindersMarkDone,
  reportsBalanceSheet,
  statementsList,
} from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Circle, Path } from 'react-native-svg';
import { useApi, useRead, useReach } from '../../api';
import { Body, Button, Card, Icon, Loading, Money, SectionLabel } from '../../kit';
import { filled, lineChart } from '../../lib/chart';
import { scoreShown } from '../../lib/fi';
import { amountParts, displayDate, displayDateTime, displayDay, displayMoment, displayRange, monthNameOf, monthOf, sameDaysLastMonth, todayIso, wholeDigits } from '../../lib/display';
import { useSession, labelIn } from '../../session';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';
import { Glow, Header, Pull, UNDER_AI } from '../../shell';

const t = strings.home;

export default function Home() {
  const theme = useTheme();
  const today = todayIso();
  const month = monthOf(today);
  const safe = useRead('insights.safeToSpend', insightsSafeToSpend);
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  const spent = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: month.from, to_date: month.to } });
  const before = sameDaysLastMonth(today);
  const spentBefore = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: before.from, to_date: before.to } });
  const thenName = monthNameOf(before.from);
  const more = spent.data && spentBefore.data ? compareAmounts(spent.data.total_expenses, spentBefore.data.total_expenses) > 0 : false;
  const fi = useRead('fi.score.get', fiScoreGet);
  const forecast = useRead('insights.forecast', insightsForecast);
  const history = useRead('insights.netWorth', insightsNetWorth, { query: { months: 12 } });
  const reads = [safe, sheet, spent, fi];
  const monthName = monthNameOf(today);

  const { session } = useSession();
  const endedOn = session.status === 'signed-in' ? session.endedOn : undefined;
  const [dismissed, setDismissed] = useState<string | undefined>(undefined);
  const reach = useReach();
  const host = session.status === 'signed-in' ? labelIn(session, session.server) : '';
  const api = useApi();
  const queryClient = useQueryClient();
  // Everything on screen from this server, Needs attention's reads too.
  const readAgain = () => queryClient.refetchQueries({ queryKey: [api.server], type: 'active' });
  // Out of reach and never answered: a figure isn't loading, it isn't known.
  const missing = reach.unreachable ? <Body small muted>{strings.reach.unknown}</Body> : null;

  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Glow />
      <Header
        server
        unreachable={reach.unreachable}
        action={
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={reach.unreachable ? strings.reach.needsServer(t.add) : t.add}
            accessibilityState={{ disabled: reach.unreachable }}
            disabled={reach.unreachable}
            onPress={() => router.push('/add')}
            style={styles.plus}
          >
            <Icon name="plus" colour={reach.unreachable ? theme.muted : theme.text} />
          </Pressable>
        }
      />
      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: UNDER_AI }]} refreshControl={<Pull read={readAgain} />}>
        {reach.unreachable ? (
          <View accessibilityRole="alert" style={[styles.reach, { backgroundColor: theme.card, borderColor: theme.text, borderRadius: theme.radius }]}>
            <Body>
              <Text style={{ fontFamily: font.medium }}>{strings.reach.cantReach(host)}</Text>
              {reach.lastAnswer ? strings.reach.sentAt(displayMoment(reach.lastAnswer)) : strings.reach.nothingYet}
            </Body>
            <View style={{ alignSelf: 'flex-start' }}>
              <Button label={strings.reach.tryAgain} busy={reads.some((r) => r.isRefetching)} onPress={() => void readAgain()} />
            </View>
          </View>
        ) : null}
        {endedOn && dismissed !== endedOn ? (
          <Card style={{ gap: 8 }}>
            <Body alert>{strings.servers.ended(labelIn(session, endedOn))}</Body>
            <Button kind="tertiary" label={strings.servers.dismiss} onPress={() => setDismissed(endedOn)} />
          </Card>
        ) : null}
        <Card tile style={{ gap: 6 }}>
          <SectionLabel onTile>{safe.data && !safe.data.next_income ? t.safe30 : t.safe}</SectionLabel>
          {safe.data ? (
            <>
              <Money amount={safe.data.amount} currency={safe.data.currency} figure="hero" onTile />
              <Text
                accessibilityLabel={safe.data.next_income ? t.safeUntilSpoken(displayDate(safe.data.until), safe.data.next_income.description) : t.safeNoIncome}
                style={[styles.tileLine, { color: theme.tileMuted }]}
              >
                {safe.data.next_income ? t.safeUntil(displayDay(safe.data.until), safe.data.next_income.description) : t.safeNoIncome}
              </Text>
              {/* As of a time only when the figures are old: the server is out of reach. */}
              {reach.unreachable && reach.lastAnswer ? (
                <Text style={[styles.tileSmall, { color: theme.tileMuted }]}>{strings.reach.asOfThen(displayDateTime(reach.lastAnswer))}</Text>
              ) : null}
              {forecast.data && forecast.data.daily.length > 1 ? (
                <Spark
                  amounts={forecast.data.daily.map((d) => d.balance)}
                  low={forecast.data.daily.findIndex((d) => d.date === forecast.data?.lowest_date)}
                  colour={theme.tileMuted}
                  height={44}
                  label={t.lowSpoken(`${forecast.data.lowest} ${forecast.data.currency}`, displayDate(forecast.data.lowest_date))}
                />
              ) : null}
              {/* What the figure is made of, the server's figures and notes as it sends them. */}
              <View style={styles.parts}>
                <Part label={t.cashToday} amount={safe.data.cash_today} currency={safe.data.currency} />
                <Part label={t.everyday} amount={safe.data.everyday_spending} currency={safe.data.currency} />
                <Part label={t.cushion} amount={safe.data.cushion} currency={safe.data.currency} />
                {!isZeroAmount(safe.data.held_for_goals) ? <Part label={t.goals} amount={safe.data.held_for_goals} currency={safe.data.currency} /> : null}
                <Part label={t.lowPoint(displayDay(safe.data.low_point_date))} amount={safe.data.low_point} currency={safe.data.currency} />
              </View>
              {safe.data.notes.map((note, i) => (
                <Text key={i} style={[styles.tileSmall, { color: theme.tileMuted }]}>
                  {note}
                </Text>
              ))}
            </>
          ) : (
            <Text style={[styles.tileSmall, { color: theme.tileMuted }]}>{reach.unreachable ? strings.reach.notKnown : t.loading('safe to spend')}</Text>
          )}
        </Card>

        <View style={styles.tiles}>
          <Tile label={t.netWorth} spoken={sheet.data ? t.netWorthSpoken(amountParts(sheet.data.net_worth, sheet.data.currency).spoken) : undefined} figure={sheet.data ? wholeDigits(sheet.data.net_worth, sheet.data.currency) : undefined} missing={missing}>
            {history.data && history.data.points.length > 1 ? <Spark amounts={history.data.points.map((p) => p.net_worth)} colour={theme.chart} height={24} /> : null}
          </Tile>
          <Tile
            label={t.spentShort(monthName.slice(0, 3))}
            spoken={
              spent.data && spentBefore.data
                ? t.spentSpoken(monthName, amountParts(spent.data.total_expenses, spent.data.currency).spoken, thenName, amountParts(spentBefore.data.total_expenses, spentBefore.data.currency).spoken, more)
                : spent.data
                  ? `${t.spentIn(monthName)}: ${amountParts(spent.data.total_expenses, spent.data.currency).spoken}`
                  : undefined
            }
            figure={spent.data ? wholeDigits(spent.data.total_expenses, spent.data.currency) : undefined}
            missing={missing}
          >
            {spent.data && spentBefore.data ? (
              <Text style={[styles.tileNote, { color: theme.muted }]} numberOfLines={1}>
                {more ? '↑' : '↓'} {t.spentThen(thenName.slice(0, 3), wholeDigits(spentBefore.data.total_expenses, spentBefore.data.currency))}
              </Text>
            ) : null}
          </Tile>
          <Tile label={t.fiScore} spoken={fi.data ? (scoreShown(fi.data) ? t.fiSpoken(fi.data.overall_score, fi.data.grade) : `${t.fiScore}: ${t.fiTooSoon}`) : undefined} figure={undefined} missing={missing}>
            {fi.data ? (
              scoreShown(fi.data) ? (
                <Ring share={filled(fi.data.overall_score)} text={fi.data.overall_score.replace(/\.\d+$/, '')} />
              ) : (
                <Text style={[styles.tileLabel, { color: theme.text }]}>{t.fiTooSoon}</Text>
              )
            ) : null}
          </Tile>
        </View>

        {/* First run books opening balances, not flows: no month of income and spending yet, and importing a statement comes first. */}
        <Attention unreachable={reach.unreachable} noFlows={fi.data?.months_observed === 0} />
      </ScrollView>
    </View>
  );
}

/** One part of free until payday, on the tile: what it is and the server's amount. */
function Part({ label, amount, currency }: { label: string; amount: string; currency: string }) {
  const theme = useTheme();
  return (
    <View accessible accessibilityLabel={`${label}: ${amountParts(amount, currency).spoken}`} style={styles.part}>
      <Text style={[styles.tileSmall, { color: theme.tileMuted, flex: 1 }]} numberOfLines={1}>
        {label}
      </Text>
      <Money amount={amount} currency={currency} onTile style={styles.partFigure} />
    </View>
  );
}

/** A key figure at a glance: its label, the figure in whole units, a small chart under it; read out in full. */
function Tile({ label, figure, spoken, missing, children }: { label: string; figure: string | undefined; spoken: string | undefined; missing: ReactNode; children?: ReactNode }) {
  const theme = useTheme();
  return (
    <Card style={styles.tile}>
      <View accessible accessibilityLabel={spoken ?? label} style={{ gap: 6 }}>
        <Text style={[styles.tileLabel, { color: theme.muted }]} numberOfLines={1}>
          {label}
        </Text>
        {figure === undefined && children ? null : figure !== undefined ? (
          <Text style={[styles.tileFigure, { color: theme.text }]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
            {figure}
          </Text>
        ) : (
          (missing ?? <Loading what="…" />)
        )}
        {children}
      </View>
    </Card>
  );
}

/** A small line of amounts, oldest first, filling the width it is given; the low point marked when given. */
function Spark({ amounts, colour, height, low, label }: { amounts: readonly string[]; colour: string; height: number; low?: number; label?: string }) {
  const [width, setWidth] = useState(0);
  const chart = width ? lineChart(amounts, width, height) : undefined;
  const dot = chart && low !== undefined && low >= 0 ? chart.points[low] : undefined;
  return (
    <View
      onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
      style={{ height }}
      {...(label ? { accessible: true, accessibilityLabel: label } : { accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants' as const })}
    >
      {chart ? (
        <Svg width={width} height={height}>
          <Path d={chart.path} stroke={colour} strokeWidth={1.5} fill="none" />
          {dot ? <Circle cx={dot.x} cy={dot.y} r={3.5} fill={colour} /> : null}
        </Svg>
      ) : null}
    </View>
  );
}

/** How far a score fills its ring, the score inside it. */
function Ring({ share, text }: { share: number; text: string }) {
  const theme = useTheme();
  const box = 56;
  const r = 24;
  const round = 2 * Math.PI * r;
  return (
    <View style={{ width: box, height: box, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={box} height={box} style={StyleSheet.absoluteFill}>
        <Circle cx={box / 2} cy={box / 2} r={r} stroke={theme.rule} strokeWidth={5} fill="none" />
        <Circle cx={box / 2} cy={box / 2} r={r} stroke={theme.chart} strokeWidth={5} fill="none" strokeDasharray={`${share * round} ${round}`} transform={`rotate(-90 ${box / 2} ${box / 2})`} />
      </Svg>
      <Text style={[styles.tileFigure, { color: theme.text, fontSize: 16 }]}>{text}</Text>
    </View>
  );
}

/** What needs attention: Salli's signals, reminders due, decisions due for review. */
function Attention({ unreachable, noFlows }: { unreachable: boolean; noFlows: boolean }) {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const signals = useRead('insights.signals', insightsSignals);
  const reminders = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  const reviews = useRead('decisions.reviews.due', decisionsReviewsDue);
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const accounts = useRead('accounts.list', accountsList);
  // Nothing put by: no cash or savings account at all.
  const noBuffer = accounts.data ? !accounts.data.some((a) => a.is_active && a.type === 'asset' && (a.asset_role === 'cash' || a.asset_role === 'savings')) : false;
  const waiting = (statements.data?.statements ?? []).filter((x) => x.status === 'pending');
  const [only] = waiting;
  // A statement's bank may be an empty string: then its account, then just "Statement".
  const onlyName = only ? only.bank || (only.account_id ? accounts.data?.find((a) => a.id === only.account_id)?.name : undefined) || strings.imports.statement : '';
  // Away from the server, a row opens a place that can't load: it stays text.
  const open = (go: () => void) => (unreachable ? {} : { onPress: go });
  const done = useMutation({
    mutationFn: (id: string) => api.call(remindersMarkDone, { path: { reminder_id: id } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server, 'reminders.list'] }),
  });
  const today = todayIso();

  const rows: { key: string; title: string; detail?: string; spoken?: string; late?: boolean; onPress?: () => void; action?: ReactNode }[] = [];
  for (const review of reviews.data?.reviews ?? []) {
    rows.push({ key: `review-${review.id}`, title: t.decision, detail: displayDay(review.review_on), spoken: `${t.decision}: ${review.question} ${t.reviewDue(displayDate(review.review_on))}`, ...open(() => router.push('/decide')) });
  }
  for (const signal of signals.data?.signals ?? []) {
    if (signal.kind === 'decision_review_due') continue; // listed above, from the journal
    if (signal.kind === 'review_waiting') {
      // Named by the statement waiting, and opening its review; with several, Books' queue.
      const detail = only && waiting.length === 1
        ? t.statementWaiting(onlyName, only.period_start && only.period_end ? displayRange(only.period_start, only.period_end) : '')
        : waiting.length > 1
          ? t.statementsWaiting(waiting.length)
          : signal.date
            ? displayDay(signal.date)
            : undefined;
      rows.push({
        key: `signal-${signal.kind}`,
        title: signal.title,
        ...(detail ? { detail } : {}),
        ...open(() => (only && waiting.length === 1 ? router.push({ pathname: '/review/[id]', params: { id: only.id } }) : router.push('/books'))),
      });
      continue;
    }
    rows.push({ key: `signal-${signal.kind}-${signal.date ?? ''}`, title: signal.title, ...(signal.date ? { detail: displayDay(signal.date) } : {}) });
  }
  for (const reminder of reminders.data?.reminders ?? []) {
    if (reminder.source_domain === 'decision') continue; // the review above
    const late = reminder.due_date < today;
    rows.push({
      key: `reminder-${reminder.id}`,
      title: reminder.kind,
      detail: late ? t.overdue : displayDay(reminder.due_date),
      spoken: `${reminder.kind}, ${late ? t.overdueSpoken(displayDate(reminder.due_date)) : t.due(displayDate(reminder.due_date))}`,
      late,
      action: (
        <Button
          label={t.done}
          kind="secondary"
          accessibilityLabel={unreachable ? strings.reach.needsServer(t.markDone(reminder.kind)) : t.markDone(reminder.kind)}
          busy={done.isPending && done.variables === reminder.id}
          disabled={unreachable}
          onPress={() => done.mutate(reminder.id)}
        />
      ),
    });
  }
  const loading = signals.isPending || reminders.isPending || reviews.isPending;
  // Nothing can be said to need nothing when a read never came back.
  const unknown = !signals.data || !reminders.data || !reviews.data;

  return (
    <Card style={{ paddingVertical: 4 }}>
      <View style={styles.attentionHead}>
        <SectionLabel>{t.attention}</SectionLabel>
        <Pressable accessibilityRole="link" onPress={() => router.push('/attention')} style={styles.seeAll}>
          <Text style={[styles.seeAllText, { color: theme.muted }]}>{strings.attention.seeAll}</Text>
          <Icon name="chevron" size={14} colour={theme.muted} />
        </Pressable>
      </View>
      {loading && !(unreachable && unknown) ? (
        <Loading what={t.loading('what needs attention')} />
      ) : unknown && rows.length === 0 ? (
        <Body muted style={{ paddingVertical: 12 }}>
          {strings.reach.notKnown}
        </Body>
      ) : rows.length === 0 && noBuffer ? (
        <Line title={t.addOwn} {...open(() => router.push({ pathname: '/first-run', params: { own: '1' } }))} last />
      ) : rows.length === 0 && noFlows ? (
        <Line title={t.importStatement} {...open(() => router.push('/import'))} last />
      ) : rows.length === 0 ? (
        <Body muted style={{ paddingVertical: 12 }}>
          {t.nothingNeedsAttention}
        </Body>
      ) : (
        rows.map(({ key, ...row }, i) => <Line key={key} {...row} last={i === rows.length - 1} />)
      )}
    </Card>
  );
}

/**
 * One thing that needs attention, on one line: what, when, and its action or
 * where it opens. One that opens nothing shows its whole title when tapped.
 */
function Line({ title, detail, spoken, late, onPress, action, last }: { title: string; detail?: string; spoken?: string; late?: boolean; onPress?: () => void; action?: ReactNode; last?: boolean }) {
  const theme = useTheme();
  const [whole, setWhole] = useState(false);
  const style = [styles.line, last ? null : { borderBottomColor: theme.rule, borderBottomWidth: StyleSheet.hairlineWidth }];
  const content = (
    <>
      <View style={[styles.marker, { backgroundColor: late ? theme.negative : theme.muted, borderRadius: theme.marker === 'dot' ? 3 : 0 }]} />
      <Text style={[styles.lineTitle, { color: theme.text }]} numberOfLines={whole ? undefined : 1}>
        {title}
      </Text>
      {detail ? <Text style={[styles.lineDetail, { color: late ? theme.negative : theme.muted }]}>{detail}</Text> : null}
      {action}
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  );
  const label = spoken ?? [title, detail].filter(Boolean).join(', ');
  return onPress ? (
    <Pressable accessibilityRole="link" accessibilityLabel={label} onPress={onPress} style={style}>
      {content}
    </Pressable>
  ) : (
    <Pressable accessibilityLabel={label} accessibilityHint={whole ? undefined : strings.home.showWhole} onPress={() => setWhole((w) => !w)} style={style}>
      {content}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { padding: size.gutter, gap: size.gap },
  plus: { width: size.target, height: size.target, alignItems: 'center', justifyContent: 'center' },
  tileLine: { fontFamily: font.regular, fontSize: 15, lineHeight: 21 },
  tileSmall: { fontFamily: font.regular, fontSize: size.small },
  parts: { gap: 2, marginTop: 4 },
  part: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  partFigure: { fontSize: size.small },
  tiles: { flexDirection: 'row', gap: 8 },
  tile: { flex: 1, padding: 12 },
  tileLabel: { fontFamily: font.regular, fontSize: 13 },
  tileNote: { fontFamily: font.regular, fontSize: 13, fontVariant: ['tabular-nums'] },
  tileFigure: { fontFamily: font.medium, fontSize: 18, fontVariant: ['tabular-nums'] },
  attentionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: 4 },
  seeAll: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: size.target },
  seeAllText: { fontFamily: font.regular, fontSize: size.small },
  line: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, paddingVertical: 6 },
  marker: { width: 6, height: 6 },
  lineTitle: { flex: 1, fontFamily: font.regular, fontSize: size.body },
  lineDetail: { fontFamily: font.regular, fontSize: size.small, fontVariant: ['tabular-nums'] },
  reach: { borderWidth: 1, padding: 14, gap: 10 },
});
