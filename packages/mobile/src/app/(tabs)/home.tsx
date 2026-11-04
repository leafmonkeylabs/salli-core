import {
  accountsList,
  compareAmounts,
  decisionsReviewsDue,
  fiScoreGet,
  insightsForecast,
  insightsNetWorth,
  insightsSafeToSpend,
  insightsSignals,
  ledgerIncomeStatement,
  remindersList,
  reportsBalanceSheet,
  statementsList,
} from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useContext, useState, type ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native';
import Animated from 'react-native-reanimated';
import Svg, { Circle, Defs, LinearGradient, Path, Stop } from 'react-native-svg';
import { useApi, useRead, useReach } from '../../api';
import { Body, Button, Card, Icon, Money, Notice, Press, Ring, Section, Skeleton, Surface, radii, shape, useLargeText } from '../../kit';
import { filled, lineChart } from '../../lib/chart';
import { scoreShown } from '../../lib/fi';
import { listMotion, useReducedMotion } from '../../motion';
import { useMarkDone } from '../../reminders';
import { amountParts, displayDate, displayDateTime, displayDay, displayMoment, displayRange, monthNameOf, monthOf, sameDaysLastMonth, todayIso, wholeDigits } from '../../lib/display';
import { useSession, labelIn } from '../../session';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';
import { Glow, Header, HeaderActions, Pull, TabInset } from '../../shell';
import { WorkedOut } from '../../workedout';

const t = strings.home;

export default function Home() {
  const theme = useTheme();
  const large = useLargeText();
  const inset = useContext(TabInset);
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
  const [explain, setExplain] = useState(false);
  const reach = useReach();
  const host = session.status === 'signed-in' ? labelIn(session, session.server) : '';
  const api = useApi();
  const queryClient = useQueryClient();
  // Everything on screen from this server, Needs attention's reads too.
  const readAgain = () => queryClient.refetchQueries({ queryKey: [api.server], type: 'active' });
  // Out of reach and never answered: a figure isn't loading, it isn't known.
  const missing = reach.unreachable ? <Body small muted>{strings.reach.unknown}</Body> : null;

  return (
    <View style={{ flex: 1, backgroundColor: theme.ground }}>
      <Glow />
      <Header
        server
        unreachable={reach.unreachable}
        action={
          <HeaderActions
            from="home"
            add={{ label: reach.unreachable ? strings.reach.needsServer(t.add) : t.add, onPress: () => router.push('/add'), disabled: reach.unreachable }}
          />
        }
      />
      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: inset }]} refreshControl={<Pull read={readAgain} />}>
        {reach.unreachable ? (
          <Notice
            tone="warn"
            action={
              <View style={{ alignSelf: 'flex-start' }}>
                <Button small kind="secondary" label={strings.reach.tryAgain} busy={reads.some((r) => r.isRefetching)} onPress={() => void readAgain()} />
              </View>
            }
          >
            <Body small>
              <Text style={{ fontFamily: font.medium }}>{strings.reach.cantReach(host)}</Text>
              {reach.lastAnswer ? strings.reach.sentAt(displayMoment(reach.lastAnswer)) : strings.reach.nothingYet}
            </Body>
          </Notice>
        ) : null}
        {endedOn && dismissed !== endedOn ? (
          <Card style={{ gap: 8 }}>
            <Body alert>{strings.servers.ended(labelIn(session, endedOn))}</Body>
            <Button kind="tertiary" label={strings.servers.dismiss} onPress={() => setDismissed(endedOn)} />
          </Card>
        ) : null}
        <Surface kind="key" style={{ gap: 6 }}>
          <Text maxFontSizeMultiplier={1.7} style={[styles.tileLabel, { color: theme.muted }]}>
            {t.left}
          </Text>
          {safe.data ? (
            <>
              <Money amount={safe.data.amount} currency={safe.data.currency} figure="hero" />
              <Text style={[styles.tileLine, { color: theme.muted }]}>
                {safe.data.next_income ? t.leftUntil(displayDay(safe.data.until), safe.data.next_income.description) : t.leftNoIncome}
              </Text>
              {/* As of a time only when the figures are old: the server is out of reach. */}
              {reach.unreachable && reach.lastAnswer ? (
                <Text style={[styles.tileSmall, { color: theme.muted }]}>{strings.reach.asOfThen(displayDateTime(reach.lastAnswer))}</Text>
              ) : null}
              {forecast.data && forecast.data.daily.length > 1 ? (
                <View style={{ marginTop: 10 }}>
                  <Spark
                    amounts={forecast.data.daily.map((d) => d.balance)}
                    low={forecast.data.daily.findIndex((d) => d.date === forecast.data?.lowest_date)}
                    colour={theme.green}
                    height={72}
                    area
                    label={t.lowSpoken(`${forecast.data.lowest} ${forecast.data.currency}`, displayDate(forecast.data.lowest_date))}
                  />
                </View>
              ) : null}
              <Press accessibilityRole="button" onPress={() => setExplain(true)} style={[styles.workedOut, shape(radii.pill), { backgroundColor: theme.fill }]}>
                <Text maxFontSizeMultiplier={1.6} style={[styles.workedOutText, { color: theme.text }]}>
                  {t.workedOut}
                </Text>
                <Icon name="chevron" size={16} colour={theme.muted} />
              </Press>
              <WorkedOut safe={safe.data} visible={explain} onClose={() => setExplain(false)} />
            </>
          ) : reach.unreachable ? (
            <Text style={[styles.tileSmall, { color: theme.muted }]}>{strings.reach.notKnown}</Text>
          ) : (
            <View accessible accessibilityLabel={t.loading('left to spend')} style={{ gap: 10, paddingTop: 4 }}>
              <Skeleton width="70%" height={46} radius={radii.field} />
              <Skeleton width="55%" height={14} />
              <Skeleton height={72} radius={radii.card} />
              <Skeleton width={170} height={40} radius={radii.pill} />
            </View>
          )}
        </Surface>

        {/* Net worth takes a row; Spent and the FI score share the next, and at large text each has a row (design LargeHome). */}
        <Tile
          row
          label={t.netWorth}
          spoken={sheet.data ? t.netWorthSpoken(amountParts(sheet.data.net_worth, sheet.data.currency).spoken) : undefined}
          figure={sheet.data ? wholeDigits(sheet.data.net_worth, sheet.data.currency) : undefined}
          missing={missing}
        >
          {history.data && history.data.points.length > 1 ? <Spark amounts={history.data.points.map((p) => p.net_worth)} colour={theme.green} height={36} width={96} /> : null}
        </Tile>
        <View style={[styles.tiles, large ? { flexDirection: 'column' } : null]}>
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
              <Text style={[styles.tileNote, { color: theme.muted }]} numberOfLines={large ? undefined : 1}>
                {more ? '↑' : '↓'} {t.spentThen(thenName.slice(0, 3), wholeDigits(spentBefore.data.total_expenses, spentBefore.data.currency))}
              </Text>
            ) : null}
          </Tile>
          <Tile label={t.fiScore} spoken={fi.data ? (scoreShown(fi.data) ? t.fiSpoken(fi.data.overall_score, fi.data.grade) : `${t.fiScore}: ${t.fiTooSoon}`) : undefined} figure={undefined} missing={missing}>
            {fi.data ? (
              scoreShown(fi.data) ? (
                <ScoreRing share={filled(fi.data.overall_score)} text={fi.data.overall_score.replace(/\.\d+$/, '')} />
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

/**
 * A key figure at a glance: its label, the figure in whole units, a small
 * chart beside or under it; read out in full. A `row` tile has the screen's
 * width, its label and figure on the left and its line at the end.
 */
function Tile({ label, figure, spoken, missing, children, row }: { label: string; figure: string | undefined; spoken: string | undefined; missing: ReactNode; children?: ReactNode; row?: boolean }) {
  const theme = useTheme();
  const large = useLargeText();
  const side = row && !large;
  const body = (
    <View style={{ gap: 6, flexShrink: 1 }}>
      <Text maxFontSizeMultiplier={1.7} style={[styles.tileLabel, { color: theme.muted }]}>
        {label}
      </Text>
      {figure === undefined && children ? null : figure !== undefined ? (
        // Never shrunk to fit: it wraps, and Spent and FI score stack at large text.
        <Text style={[styles.tileFigure, { color: theme.text }]}>{figure}</Text>
      ) : (
        (missing ?? <Skeleton width={96} height={22} />)
      )}
      {side ? null : children}
    </View>
  );
  return (
    <Surface style={[styles.tile, side ? styles.tileRow : null]}>
      <View accessible accessibilityLabel={spoken ?? label} style={side ? styles.tileSide : { gap: 6 }}>
        {body}
        {side ? children : null}
      </View>
    </Surface>
  );
}

/** A small line of amounts, oldest first, filling the width it is given (or `width`): 2 wide with round ends, an area that fades to nothing, the low point as a ring. */
function Spark({ amounts, colour, height, low, label, area, width: fixed }: { amounts: readonly string[]; colour: string; height: number; low?: number; label?: string; area?: boolean; width?: number }) {
  const theme = useTheme();
  const [measured, setWidth] = useState(0);
  const width = fixed ?? measured;
  const chart = width ? lineChart(amounts, width, height, 5) : undefined;
  const dot = chart && low !== undefined && low >= 0 ? chart.points[low] : undefined;
  const first = chart?.points[0];
  const last = chart?.points[chart.points.length - 1];
  const fill = chart && area && first && last ? `${chart.path} L${last.x.toFixed(1)} ${height} L${first.x.toFixed(1)} ${height} Z` : undefined;
  return (
    <View
      onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
      style={fixed ? { height, width: fixed } : { height }}
      {...(label ? { accessible: true, accessibilityLabel: label } : { accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants' as const })}
    >
      {chart ? (
        <Svg width={width} height={height}>
          {fill ? (
            <>
              <Defs>
                <LinearGradient id="area" x1="0" y1="0" x2="0" y2="1">
                  <Stop offset="0" stopColor={colour} stopOpacity={0.22} />
                  <Stop offset="1" stopColor={colour} stopOpacity={0} />
                </LinearGradient>
              </Defs>
              <Path d={fill} fill="url(#area)" />
            </>
          ) : null}
          <Path d={chart.path} stroke={colour} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
          {dot ? <Circle cx={dot.x} cy={dot.y} r={5} fill={theme.surface} stroke={colour} strokeWidth={2} /> : null}
        </Svg>
      ) : null}
    </View>
  );
}

/** How far a score fills its ring, the score inside it. */
function ScoreRing({ share, text }: { share: number; text: string }) {
  const theme = useTheme();
  return (
    <Ring ratio={share} diameter={56} stroke={6}>
      <Text style={[styles.tileFigure, { color: theme.text, fontSize: size.body }]}>{text}</Text>
    </Ring>
  );
}

/** What needs attention: Salli's signals, reminders due, decisions due for review. */
function Attention({ unreachable, noFlows }: { unreachable: boolean; noFlows: boolean }) {
  const list = listMotion(useReducedMotion());
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
  const done = useMarkDone();
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
    if (reminder.status !== 'pending') continue; // just marked done, before the list is read again
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
          disabled={unreachable}
          onPress={() => done.mutate(reminder)}
        />
      ),
    });
  }
  const loading = signals.isPending || reminders.isPending || reviews.isPending;
  // Nothing can be said to need nothing when a read never came back.
  const unknown = !signals.data || !reminders.data || !reviews.data;

  const empty = (text: string) => (
    <View style={styles.attentionNote}>
      <Body muted>{text}</Body>
    </View>
  );
  return (
    <View style={{ marginTop: size.section - size.gap }}>
      <Section title={t.attention} action={{ label: strings.attention.seeAll, onPress: () => router.push('/attention') }}>
        <Surface pad={false} style={styles.attentionCard}>
          {loading && !(unreachable && unknown) ? (
            <View accessible accessibilityLabel={t.loading('what needs attention')} style={{ gap: 14, paddingVertical: 16 }}>
              <Skeleton height={20} />
              <Skeleton width="80%" height={20} />
              <Skeleton width="60%" height={20} />
            </View>
          ) : unknown && rows.length === 0 ? (
            empty(strings.reach.notKnown)
          ) : rows.length === 0 && noBuffer ? (
            <Line title={t.addOwn} {...open(() => router.push({ pathname: '/first-run', params: { own: '1' } }))} last />
          ) : rows.length === 0 && noFlows ? (
            <Line title={t.importStatement} {...open(() => router.push('/import'))} last />
          ) : rows.length === 0 ? (
            empty(t.nothingNeedsAttention)
          ) : (
            rows.map(({ key, ...row }, i) => (
              <Animated.View key={key} {...list}>
                <Line {...row} last={i === rows.length - 1} />
              </Animated.View>
            ))
          )}
        </Surface>
      </Section>
    </View>
  );
}

/**
 * One thing that needs attention, on one line: what, when, and its action or
 * where it opens. One that opens nothing shows its whole title when tapped.
 * At large text its title comes first and whole, then when, then its action.
 */
function Line({ title, detail, spoken, late, onPress, action, last }: { title: string; detail?: string; spoken?: string; late?: boolean; onPress?: () => void; action?: ReactNode; last?: boolean }) {
  const theme = useTheme();
  const large = useLargeText();
  const [whole, setWhole] = useState(false);
  const style = [styles.line, last ? null : { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth }];
  // On one line the title comes first: the detail takes at most half and ends in an ellipsis.
  const when = detail ? (
    <Text numberOfLines={large ? undefined : 2} style={[styles.lineDetail, large ? null : styles.lineDetailShort, { color: late ? theme.red : theme.muted }]}>
      {detail}
    </Text>
  ) : null;
  const content = large ? (
    <>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[styles.lineTitle, { color: theme.text, flex: 0 }]}>{title}</Text>
        {when}
        {action ? <View style={{ alignSelf: 'flex-start', marginTop: 6 }}>{action}</View> : null}
      </View>
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  ) : (
    <>
      <View style={[styles.marker, shape(radii.pill), { backgroundColor: late ? theme.red : theme.muted }]} />
      <Text style={[styles.lineTitle, { color: theme.text }]} numberOfLines={whole ? undefined : 2}>
        {title}
      </Text>
      {when}
      {action}
      {onPress ? <Icon name="chevron" size={16} colour={theme.muted} /> : null}
    </>
  );
  const label = spoken ?? [title, detail].filter(Boolean).join(', ');
  return onPress ? (
    <Press highlight accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={style}>
      {content}
    </Press>
  ) : (
    <Press highlight accessibilityLabel={label} accessibilityHint={whole || large ? undefined : strings.home.showWhole} onPress={() => setWhole((w) => !w)} style={style}>
      {content}
    </Press>
  );
}

const styles = StyleSheet.create({
  page: { paddingHorizontal: size.gutter, paddingTop: size.gap, gap: size.gap },
  tileLine: { fontFamily: font.regular, fontSize: size.small, lineHeight: 21 },
  tileSmall: { fontFamily: font.regular, fontSize: size.small },
  workedOut: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 40, paddingHorizontal: 16, marginTop: 10 },
  workedOutText: { fontFamily: font.medium, fontSize: size.small },
  tiles: { flexDirection: 'row', gap: size.gap },
  tile: { flex: 1, minWidth: 0 },
  tileRow: { flex: 0, alignSelf: 'stretch' },
  tileSide: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  tileLabel: { fontFamily: font.medium, fontSize: size.label },
  tileNote: { fontFamily: font.regular, fontSize: size.label, fontVariant: ['tabular-nums'] },
  tileFigure: { fontFamily: font.medium, fontSize: size.figure, fontVariant: ['tabular-nums'], letterSpacing: -0.01 * size.figure },
  attentionCard: { paddingHorizontal: size.pad, paddingVertical: 4 },
  attentionNote: { paddingVertical: 16 },
  line: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingVertical: 8 },
  marker: { width: 6, height: 6 },
  lineTitle: { flex: 1, fontFamily: font.regular, fontSize: size.body },
  lineDetailShort: { flexShrink: 1, maxWidth: '38%' },
  lineDetail: { fontFamily: font.regular, fontSize: size.small, fontVariant: ['tabular-nums'] },
});
