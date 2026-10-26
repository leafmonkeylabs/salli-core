import { accountsList, budgetsCurrent, budgetsTrend, formatAmount, isNegativeAmount, isZeroAmount, negateAmount, type CurrentBudgetLine } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../../api';
import { Body, Button, Card, CardHead, Waiting, useLargeText } from '../../kit';
import { monthBars, shareOf } from '../../lib/chart';
import { displayMonth, monthNameOf, wholeDigits } from '../../lib/display';
import { Picker } from '../../picker';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.budget;

/**
 * Budget (design HhBudget): this month's limits as the server reads them,
 * each with what is left, a bar of what is spent and a mark for the share
 * of the month gone; then spending over the last six months.
 */
export default function Budget() {
  const theme = useTheme();
  const current = useRead('budgets.current', budgetsCurrent);
  const trend = useRead('budgets.trend', budgetsTrend, {
    query: { months: 6 },
  });
  const accounts = useRead('accounts.list', accountsList);
  const [choosing, setChoosing] = useState(false);
  const data = current.data;
  const edit = (id: string) => router.push({ pathname: '/budget/[id]', params: { id } });
  // eslint-disable-next-line no-restricted-syntax -- not money: the share of the month gone
  const gone = data ? Math.min(1, Math.max(0, Number(data.month_gone))) : 0;
  const day = data ? data.as_of.slice(8).replace(/^0/, '') : '';
  const days = data ? String(new Date(Number(data.month.slice(0, 4)), Number(data.month.slice(5, 7)), 0).getDate()) : ''; // eslint-disable-line no-restricted-syntax -- not money: a date's year and month

  return (
    <Page
      back={{
        label: strings.cash.title,
        onPress: () => (router.canGoBack() ? router.back() : router.replace('/cash')),
      }}
      title={t.title}
      onRefresh={() => Promise.all([current.refetch(), trend.refetch()])}
    >
      {data ? (
        <Card style={{ paddingBottom: 4 }}>
          <CardHead label={t.month(monthNameOf(`${data.month.slice(0, 7)}-01`), data.currency)} end={t.day(day, days)} />
          {data.lines.length ? (
            data.lines.map((line) => <Line key={line.account_id} line={line} currency={data.currency} gone={gone} onPress={() => edit(line.account_id)} />)
          ) : (
            <Body muted style={{ paddingVertical: 12 }}>
              {t.none}
            </Body>
          )}
          {data.lines.length ? (
            <View style={styles.legend}>
              <View style={[styles.legendMark, { backgroundColor: theme.text }]} />
              <Text style={[styles.small, { color: theme.muted }]}>{t.monthGone}</Text>
            </View>
          ) : null}
        </Card>
      ) : (
        <Waiting query={current} what="your budget" />
      )}
      <Button kind="secondary" label={t.edit} onPress={() => setChoosing(true)} />
      {trend.data && trend.data.months.length ? (
        <Card>
          <CardHead label={t.trend(String(trend.data.months.length))} />
          <View accessible accessibilityLabel={t.trendLabel(trend.data.months.map((m, i) => `${displayMonth(m)} ${wholeDigits(trend.data?.totals[i] ?? '0', trend.data?.currency ?? '')}`).join(', '))} style={styles.bars}>
            {monthBars(trend.data.categories, trend.data.months.length).map((h, i, all) => (
              <View key={trend.data.months[i]} style={styles.barCol}>
                {/* A chart's labels grow a little only: six columns share the width. */}
                <Text maxFontSizeMultiplier={1.3} numberOfLines={1} style={[styles.barFigure, { color: theme.muted }]}>{wholeDigits(trend.data.totals[i] ?? '0', trend.data.currency)}</Text>
                <View
                  style={{
                    width: 24,
                    height: Math.max(2, h * 64),
                    backgroundColor: i === all.length - 1 ? theme.muted : theme.chart,
                  }}
                />
                <Text maxFontSizeMultiplier={1.3} style={[styles.small, { color: theme.muted }]}>{displayMonth(trend.data.months[i] ?? '').slice(0, 3)}</Text>
              </View>
            ))}
          </View>
        </Card>
      ) : null}
      <Picker
        title={choosing ? t.which : undefined}
        accounts={(accounts.data ?? []).filter((a) => a.type === 'expense')}
        likely={['expense']}
        others={false}
        chosen={undefined}
        onClose={() => setChoosing(false)}
        onPick={(id) => {
          setChoosing(false);
          edit(id);
        }}
      />
    </Page>
  );
}

/**
 * A category's line: its name, what is left, what is spent of what is
 * available, and the bar. At large text the name has its own line, then
 * Limit, Spent and Over or Left, one to a line (design LargeBudget).
 */
function Line({ line, currency, gone, onPress }: { line: CurrentBudgetLine; currency: string; gone: number; onPress: () => void }) {
  const theme = useTheme();
  const large = useLargeText();
  const digits = (amount: string) => formatAmount(amount, currency, { display: 'none' });
  const over = isNegativeAmount(line.left);
  const left = over ? t.over(digits(negateAmount(line.left))) : t.left(digits(line.left));
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${line.category}, ${left}, ${t.of(digits(line.spent), digits(line.available))}`} onPress={onPress} style={[styles.line, { borderTopColor: theme.rule }]}>
      {large ? (
        <>
          <Text style={[styles.title, { color: theme.text }]}>{line.category}</Text>
          {!isZeroAmount(line.carried) ? <Text style={[styles.carried, { color: theme.muted, borderColor: theme.rule, alignSelf: 'flex-start' }]}>{t.rollover(digits(line.carried))}</Text> : null}
          {[
            { key: 'limit', label: t.limitLabel, figure: digits(line.available), colour: theme.text },
            { key: 'spent', label: t.spentLabel, figure: digits(line.spent), colour: theme.text },
            { key: 'left', label: over ? t.overLabel : t.leftLabel, figure: digits(over ? negateAmount(line.left) : line.left), colour: over ? theme.negative : theme.text },
          ].map((row) => (
            <View key={row.key} style={styles.stackRow}>
              <Text style={[styles.small, { color: theme.muted, flexGrow: 1, flexShrink: 0 }]}>{row.label}</Text>
              <Text style={[styles.figure, { color: row.colour, flexGrow: 1, textAlign: 'right' }]}>{row.figure}</Text>
            </View>
          ))}
        </>
      ) : (
        <>
          <View style={styles.top}>
            <View style={styles.name}>
              <Text style={[styles.title, { color: theme.text }]}>{line.category}</Text>
              {!isZeroAmount(line.carried) ? <Text style={[styles.carried, { color: theme.muted, borderColor: theme.rule }]}>{t.rollover(digits(line.carried))}</Text> : null}
            </View>
            <Text style={[styles.figure, { color: over ? theme.negative : theme.text }]}>{left}</Text>
          </View>
          <Text style={[styles.small, { color: theme.muted }]}>{t.of(digits(line.spent), digits(line.available))}</Text>
        </>
      )}
      <View style={[styles.track, { backgroundColor: theme.work }]}>
        <View
          style={{
            width: `${shareOf(line.spent, line.available) * 100}%`,
            height: '100%',
            backgroundColor: over ? theme.negative : theme.chart,
          }}
        />
        <View style={[styles.mark, { left: `${gone * 100}%`, backgroundColor: theme.text }]} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  line: {
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingVertical: 12,
    gap: 2,
  },
  stackRow: { flexDirection: 'row', alignItems: 'baseline', columnGap: 12, flexWrap: 'wrap' },
  top: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  name: { flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1 },
  title: { fontFamily: font.medium, fontSize: size.body },
  carried: {
    fontFamily: font.regular,
    fontSize: 12,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  figure: {
    fontFamily: font.regular,
    fontSize: size.body,
    fontVariant: ['tabular-nums'],
  },
  small: {
    fontFamily: font.regular,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
  },
  track: { height: 8, marginTop: 8, position: 'relative' },
  mark: { position: 'absolute', top: -3, bottom: -3, width: 2 },
  legend: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingBottom: 8,
  },
  legendMark: { width: 2, height: 12 },
  bars: { flexDirection: 'row', alignItems: 'flex-end', height: 104, gap: 6 },
  barCol: { flex: 1, alignItems: 'center', gap: 4 },
  barFigure: { fontFamily: font.regular, fontSize: 11, fontVariant: ['tabular-nums'] },
});
