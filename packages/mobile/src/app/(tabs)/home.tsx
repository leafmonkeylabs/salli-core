import {
  accountsList,
  decisionsReviewsDue,
  fiScoreGet,
  insightsSafeToSpend,
  insightsSignals,
  ledgerIncomeStatement,
  remindersList,
  remindersMarkDone,
  reportsBalanceSheet,
  statementsList,
} from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead, useReach } from '../../api';
import { Body, Button, Card, Icon, Loading, Money, Row, SectionLabel } from '../../kit';
import { displayDate, displayDateTime, displayMoment, displayRange, monthNameOf, monthOf, todayIso } from '../../lib/display';
import { useSession } from '../../session';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';
import { Header, Pull, UNDER_AI } from '../../shell';

const t = strings.home;

export default function Home() {
  const theme = useTheme();
  const today = todayIso();
  const month = monthOf(today);
  const safe = useRead('insights.safeToSpend', insightsSafeToSpend);
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  const spent = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: month.from, to_date: month.to } });
  const fi = useRead('fi.score.get', fiScoreGet);
  const reads = [safe, sheet, spent, fi];
  const monthName = monthNameOf(today);
  const { session } = useSession();
  const endedOn = session.status === 'signed-in' ? session.endedOn : undefined;
  const [dismissed, setDismissed] = useState<string | undefined>(undefined);
  const reach = useReach();
  const host = session.status === 'signed-in' ? session.server.replace(/^https?:\/\//, '') : '';
  const api = useApi();
  const queryClient = useQueryClient();
  // Everything on screen from this server, Needs attention's reads too.
  const readAgain = () => queryClient.refetchQueries({ queryKey: [api.server], type: 'active' });
  // Out of reach and never answered: a figure isn't loading, it isn't known.
  const missing = reach.unreachable ? <Body small muted>{strings.reach.unknown}</Body> : null;

  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
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
          <View accessibilityRole="alert" style={[styles.reach, { backgroundColor: theme.card, borderColor: theme.text }]}>
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
            <Body alert>{strings.servers.ended(endedOn.replace(/^https?:\/\//, ''))}</Body>
            <Button kind="tertiary" label={strings.servers.dismiss} onPress={() => setDismissed(endedOn)} />
          </Card>
        ) : null}
        <Card tile style={{ gap: 6 }}>
          <SectionLabel onTile>{t.safe}</SectionLabel>
          {safe.data ? (
            <>
              <Money amount={safe.data.amount} currency={safe.data.currency} figure="hero" onTile />
              <Text style={[styles.tileLine, { color: theme.tileText }]}>
                {safe.data.next_income ? t.safeUntil(displayDate(safe.data.until), safe.data.next_income.description) : t.safeNoIncome}
              </Text>
              <Text style={[styles.tileSmall, { color: theme.tileMuted }]}>
                {reach.unreachable && reach.lastAnswer
                  ? strings.reach.asOfThen(displayDateTime(reach.lastAnswer))
                  : t.asOf(displayDate(today))}
              </Text>
            </>
          ) : (
            <Text style={[styles.tileSmall, { color: theme.tileMuted }]}>{reach.unreachable ? strings.reach.notKnown : t.loading('safe to spend')}</Text>
          )}
        </Card>

        <Card style={styles.figures}>
          <Figure label={t.netWorth} divider>
            {sheet.data ? <Money amount={sheet.data.net_worth} currency={sheet.data.currency} figure="key" /> : missing}
          </Figure>
          <Figure label={t.spentIn(monthName)}>
            {spent.data ? <Money amount={spent.data.total_expenses} currency={spent.data.currency} figure="key" /> : missing}
          </Figure>
          {fi.data ? (
            <View style={[styles.fiRow, { borderTopColor: theme.rule }]}>
              <View style={{ flex: 1 }}>
                <Body small muted>
                  {t.fiScore(fi.data.grade)}
                </Body>
                <Body small muted>
                  {fi.data.assumptions?.status === 'placeholder' ? t.placeholders : t.ownAssumptions}
                </Body>
              </View>
              <Text style={[styles.score, { color: theme.text }]}>{fi.data.overall_score}</Text>
            </View>
          ) : null}
        </Card>

        <Attention unreachable={reach.unreachable} />
      </ScrollView>
    </View>
  );
}

function Figure({ label, divider, children }: { label: string; divider?: boolean; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={[styles.figure, divider ? { borderRightWidth: StyleSheet.hairlineWidth, borderRightColor: theme.rule } : null]}>
      <Body small muted>
        {label}
      </Body>
      {children ?? <Loading what="…" />}
    </View>
  );
}

/** What needs attention: Salli's signals, reminders due, decisions due for review. */
function Attention({ unreachable }: { unreachable: boolean }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const signals = useRead('insights.signals', insightsSignals);
  const reminders = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  const reviews = useRead('decisions.reviews.due', decisionsReviewsDue);
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const accounts = useRead('accounts.list', accountsList);
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

  const rows: { key: string; title: string; detail?: string; onPress?: () => void; action?: ReactNode }[] = [];
  for (const review of reviews.data?.reviews ?? []) {
    rows.push({ key: `review-${review.id}`, title: t.decision, detail: `${review.question} ${t.reviewDue(displayDate(review.review_on))}`, ...open(() => router.push('/decide')) });
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
            ? displayDate(signal.date)
            : undefined;
      rows.push({
        key: `signal-${signal.kind}`,
        title: signal.title,
        ...(detail ? { detail } : {}),
        ...open(() => (only && waiting.length === 1 ? router.push({ pathname: '/review/[id]', params: { id: only.id } }) : router.push('/books'))),
      });
      continue;
    }
    rows.push({ key: `signal-${signal.kind}-${signal.date ?? ''}`, title: signal.title, ...(signal.date ? { detail: displayDate(signal.date) } : {}) });
  }
  for (const reminder of reminders.data?.reminders ?? []) {
    if (reminder.source_domain === 'decision') continue; // the review above
    const late = reminder.due_date < today;
    rows.push({
      key: `reminder-${reminder.id}`,
      title: reminder.kind,
      detail: late ? t.overdue(displayDate(reminder.due_date)) : t.due(displayDate(reminder.due_date)),
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
      <View style={{ paddingTop: 12, paddingBottom: 4 }}>
        <SectionLabel>{t.attention}</SectionLabel>
      </View>
      {loading && !(unreachable && unknown) ? (
        <Loading what={t.loading('what needs attention')} />
      ) : unknown && rows.length === 0 ? (
        <Body muted style={{ paddingVertical: 12 }}>
          {strings.reach.notKnown}
        </Body>
      ) : rows.length === 0 ? (
        <Body muted style={{ paddingVertical: 12 }}>
          {t.nothingNeedsAttention}
        </Body>
      ) : (
        rows.map(({ key, ...row }, i) => <Row key={key} {...row} last={i === rows.length - 1} />)
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  page: { padding: size.gutter, gap: size.gap },
  plus: { width: size.target, height: size.target, alignItems: 'center', justifyContent: 'center' },
  tileLine: { fontFamily: 'Geist_400Regular', fontSize: 15, lineHeight: 21 },
  tileSmall: { fontFamily: 'Geist_400Regular', fontSize: size.small },
  figures: { padding: 0, flexDirection: 'row', flexWrap: 'wrap' },
  figure: { flexBasis: '50%', flexGrow: 1, padding: 14, gap: 4, minWidth: 150 },
  fiRow: { flexBasis: '100%', flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingVertical: 14, borderTopWidth: StyleSheet.hairlineWidth },
  score: { fontFamily: 'Geist_500Medium', fontSize: size.keyFigure, fontVariant: ['tabular-nums'] },
  reach: { borderWidth: 1, padding: 14, gap: 10 },
});
