import {
  decisionsReviewsDue,
  fiScoreGet,
  insightsSafeToSpend,
  insightsSignals,
  ledgerIncomeStatement,
  remindersList,
  remindersMarkDone,
  reportsBalanceSheet,
} from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, Icon, Loading, Money, Row, SectionLabel } from '../../kit';
import { displayDate, monthNameOf, monthOf, todayIso } from '../../lib/display';
import { strings } from '../../strings';
import { size, useTheme } from '../../theme';
import { Header, Pull } from '../../shell';

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

  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Header
        server
        action={
          <Pressable accessibilityRole="button" accessibilityLabel={t.add} onPress={() => router.push('/add')} style={styles.plus}>
            <Icon name="plus" colour={theme.text} />
          </Pressable>
        }
      />
      <ScrollView
        contentContainerStyle={styles.page}
        refreshControl={<Pull read={() => Promise.all(reads.map((r) => r.refetch()))} />}
      >
        <Card tile style={{ gap: 6 }}>
          <SectionLabel onTile>{t.safe}</SectionLabel>
          {safe.data ? (
            <>
              <Money amount={safe.data.amount} currency={safe.data.currency} figure="hero" onTile />
              <Text style={[styles.tileLine, { color: theme.tileText }]}>
                {safe.data.next_income ? t.safeUntil(displayDate(safe.data.until), safe.data.next_income.description) : t.safeNoIncome}
              </Text>
              <Text style={[styles.tileSmall, { color: theme.tileMuted }]}>{t.asOf(displayDate(today))}</Text>
            </>
          ) : (
            <Text style={[styles.tileSmall, { color: theme.tileMuted }]}>{t.loading('safe to spend')}</Text>
          )}
        </Card>

        <Card style={styles.figures}>
          <Figure label={t.netWorth}>{sheet.data ? <Money amount={sheet.data.net_worth} currency={sheet.data.currency} figure="key" /> : null}</Figure>
          <Figure label={t.spentIn(monthName)}>
            {spent.data ? <Money amount={spent.data.total_expenses} currency={spent.data.currency} figure="key" /> : null}
          </Figure>
          {fi.data ? (
            <View style={styles.fiRow}>
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

        <Attention />
      </ScrollView>
    </View>
  );
}

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View style={styles.figure}>
      <Body small muted>
        {label}
      </Body>
      {children ?? <Loading what="…" />}
    </View>
  );
}

/** What needs attention: Salli's signals, reminders due, decisions due for review. */
function Attention() {
  const api = useApi();
  const queryClient = useQueryClient();
  const signals = useRead('insights.signals', insightsSignals);
  const reminders = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  const reviews = useRead('decisions.reviews.due', decisionsReviewsDue);
  const done = useMutation({
    mutationFn: (id: string) => api.call(remindersMarkDone, { path: { reminder_id: id } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server, 'reminders.list'] }),
  });
  const today = todayIso();

  const rows: { key: string; title: string; detail?: string; onPress?: () => void; action?: ReactNode }[] = [];
  for (const review of reviews.data?.reviews ?? []) {
    rows.push({ key: `review-${review.id}`, title: t.decision, detail: `${review.question} ${t.reviewDue(displayDate(review.review_on))}`, onPress: () => router.push('/decide') });
  }
  for (const signal of signals.data?.signals ?? []) {
    if (signal.kind === 'decision_review_due') continue; // listed above, from the journal
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
          accessibilityLabel={t.markDone(reminder.kind)}
          busy={done.isPending && done.variables === reminder.id}
          onPress={() => done.mutate(reminder.id)}
        />
      ),
    });
  }
  const loading = signals.isPending || reminders.isPending || reviews.isPending;

  return (
    <Card style={{ paddingVertical: 4 }}>
      <View style={{ paddingTop: 12, paddingBottom: 4 }}>
        <SectionLabel>{t.attention}</SectionLabel>
      </View>
      {loading ? (
        <Loading what={t.loading('what needs attention')} />
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
  fiRow: { flexBasis: '100%', flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, paddingBottom: 14 },
  score: { fontFamily: 'Geist_500Medium', fontSize: size.keyFigure, fontVariant: ['tabular-nums'] },
});
