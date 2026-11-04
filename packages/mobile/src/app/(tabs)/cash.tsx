import { budgetsCurrent, formatAmount, insightsForecast, isNegativeAmount, type CashForecast } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { Modal, ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop, Text as SvgText } from 'react-native-svg';
import { useRead } from '../../api';
import { AmountRow, Body, Button, LedgerRow, Row, Section, SectionLabel, Skeleton, Surface, Waiting, radii, shape, useLargeText } from '../../kit';
import { placeLabels, stepChart } from '../../lib/chart';
import { amountParts, displayDate, displayDay, wholeDigits } from '../../lib/display';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.cash;
/** Rows of what's coming up shown here; the console lists the rest. */
const COMING_UP = 12;
const LABEL_SIZE = 12;

export default function Cash() {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const forecast = useRead('insights.forecast', insightsForecast);
  const budget = useRead('budgets.current', budgetsCurrent);
  const [days, setDays] = useState(false);
  const data = forecast.data;
  const lines = budget.data?.lines ?? [];
  const over = lines.filter((l) => isNegativeAmount(l.left)).length;
  const chartWidth = width - 2 * size.gutter - 2 * size.pad;
  const chartHeight = 180;

  return (
    <Page ai="cash" title={t.title} onRefresh={() => Promise.all([forecast.refetch(), budget.refetch()])}>
      <Surface style={{ gap: 12 }}>
        <View style={styles.cardHead}>
          <Text accessibilityRole="header" maxFontSizeMultiplier={1.7} style={[styles.heading, { color: theme.text }]}>
            {data ? t.forecast(String(data.daily.length - 1)) : t.forecast('60')}
          </Text>
          {data ? (
            <Text maxFontSizeMultiplier={1.7} style={[styles.lowLine, { color: theme.muted, flexShrink: 1, textAlign: 'right' }]}>
              {t.low(wholeDigits(data.lowest, data.currency), displayDay(data.lowest_date))}
            </Text>
          ) : null}
        </View>
        {data ? (
          <>
            <Chart data={data} width={chartWidth} height={chartHeight} />
            <View style={{ alignSelf: 'flex-start' }}>
              <Button small kind="secondary" icon="more" label={t.dayByDay} onPress={() => setDays(true)} />
            </View>
          </>
        ) : (
          <View style={{ gap: 12 }}>
            <Skeleton width="50%" height={14} />
            <Skeleton height={chartHeight} radius={radii.card} />
            <Waiting query={forecast} what="the forecast" />
          </View>
        )}
      </Surface>

      <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
        <Row icon="independence" title={strings.budget.title} detail={budget.data ? t.budgetDetail(lines.length, over) : undefined} onPress={() => router.push('/budget')} last />
      </Surface>

      <View style={{ marginTop: size.section - size.gap }}>
        <View style={{ gap: size.heading }}>
          <View style={styles.cardHead}>
            <SectionLabel>{t.comingUp}</SectionLabel>
            {data ? <Text maxFontSizeMultiplier={1.4} style={[styles.code, { color: theme.muted }]}>{data.currency}</Text> : null}
          </View>
          <Surface pad={false} style={{ paddingHorizontal: size.pad, paddingVertical: 4 }}>
            {data ? (
              data.flows.length ? (
                <>
                  {data.flows.slice(0, COMING_UP).map((flow, i, shown) => {
                    const account = data.accounts.find((a) => a.account_id === flow.account_id)?.name;
                    const source = t.sources[flow.source] ?? flow.source;
                    return (
                      // One line: its day, what, and the amount signed; the account and the source are read out with it.
                      <Flow
                        key={`${flow.date}-${flow.account_id ?? ''}-${flow.description}-${flow.amount}`}
                        date={flow.date}
                        title={flow.description}
                        detail={[source, account].filter(Boolean).join(' · ')}
                        amount={flow.amount}
                        currency={flow.currency}
                        label={t.flowLabel(displayDate(flow.date), flow.description, formatAmount(flow.amount, flow.currency, { display: 'name' }), [account, source].filter(Boolean).join(', '))}
                        last={i === shown.length - 1}
                      />
                    );
                  })}
                  {data.flows.length > COMING_UP ? (
                    <Body small muted style={{ paddingVertical: 12 }}>
                      {t.more(data.flows.length - COMING_UP)}
                    </Body>
                  ) : null}
                </>
              ) : (
                <Body muted style={{ paddingVertical: 16 }}>{t.nothingComing}</Body>
              )
            ) : (
              <View style={{ gap: 14, paddingVertical: 16 }}>
                <Skeleton height={20} />
                <Skeleton width="75%" height={20} />
              </View>
            )}
          </Surface>
        </View>
      </View>

      {data?.accounts.length ? (
        <View style={{ marginTop: size.section - size.gap }}>
          <Section title={t.accounts}>
            <Surface pad={false} style={{ paddingHorizontal: size.pad, paddingVertical: 4 }}>
              {data.accounts.map((account, i) => (
                <AmountRow
                  key={account.account_id}
                  title={account.name}
                  detail={t.lowest(displayDate(account.lowest_date))}
                  amount={account.lowest}
                  currency={account.currency}
                  last={i === data.accounts.length - 1}
                />
              ))}
            </Surface>
          </Section>
        </View>
      ) : null}

      {data ? <DayByDay data={data} visible={days} onClose={() => setDays(false)} /> : null}
    </Page>
  );
}

/**
 * The next days as a step line. Its gridlines sit at the highest and lowest
 * days, and its labels are those days', today's and the last day's own
 * balances: no value on it is one Salli didn't send. At large text only the
 * lowest and highest are labelled, and the axis has only its first and last
 * days. VoiceOver reads it as one image, with its figures said.
 */
function Chart({ data, width, height }: { data: CashForecast; width: number; height: number }) {
  const theme = useTheme();
  const large = useLargeText();
  const code = data.currency;
  const money = (amount: string): string => formatAmount(amount, code, { display: 'none' });
  const chart = stepChart(data.daily, { date: data.lowest_date, balance: data.lowest }, width, height, 10);
  const high = chart.points[chart.highIndex];
  const last = data.daily.length - 1;
  const start = chart.points[0];
  const end = chart.points[last];
  // Most wanted first: the lowest day, the highest, the last, today. A day already labelled isn't again.
  const wanted = [
    { index: chart.lowIndex, key: 'low', point: chart.low, text: t.lowestLabel(displayDay(data.lowest_date), money(data.lowest)), below: true },
    { index: chart.highIndex, key: 'high', point: high, text: money(data.daily[chart.highIndex]?.balance ?? '') },
    { index: last, key: 'end', point: end, text: money(data.end_balance) },
    { index: 0, key: 'start', point: start, text: money(data.today) },
  ];
  const seen = new Set<number>();
  const labels = placeLabels(
    wanted.flatMap((w) => {
      if (!w.point || seen.has(w.index) || (large && (w.key === 'end' || w.key === 'start'))) return [];
      seen.add(w.index);
      return [{ key: w.key, x: w.point.x, y: w.point.y, text: w.text, ...(w.below ? { below: true } : {}) }];
    }),
    width,
    height,
    LABEL_SIZE,
  );
  const mid = data.daily[Math.floor(last / 2)];

  return (
    <View style={{ gap: 6 }}>
      <View accessible accessibilityRole="image" accessibilityLabel={t.chartLabel(money(data.today), money(data.lowest), displayDate(data.lowest_date), money(data.end_balance))}>
      <Svg width={width} height={height}>
        <Defs>
          <LinearGradient id="forecastArea" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={theme.green} stopOpacity={0.2} />
            <Stop offset="1" stopColor={theme.green} stopOpacity={0} />
          </LinearGradient>
        </Defs>
        {high && chart.highIndex !== chart.lowIndex ? <Line x1={0} x2={width} y1={high.y} y2={high.y} stroke={theme.line} strokeWidth={1} /> : null}
        <Line x1={0} x2={width} y1={chart.low.y} y2={chart.low.y} stroke={theme.line} strokeWidth={1} />
        {chart.zero !== undefined ? <Line x1={0} x2={width} y1={chart.zero} y2={chart.zero} stroke={theme.red} strokeWidth={1} /> : null}
        <Path d={`${chart.path} V${height} H${start?.x ?? 0} Z`} fill="url(#forecastArea)" />
        <Path d={chart.path} stroke={theme.green} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <Circle cx={chart.low.x} cy={chart.low.y} r={5} fill={theme.surface} stroke={theme.green} strokeWidth={2} />
        {labels.map((label) => (
          <SvgText key={label.key} x={label.x} y={label.y} textAnchor={label.anchor} fontFamily={font.regular} fontSize={LABEL_SIZE} fill={theme.muted}>
            {label.text}
          </SvgText>
        ))}
      </Svg>
      </View>
      <View style={styles.axis} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        <Text style={[styles.axisText, { color: theme.muted }]}>{displayDay(data.start)}</Text>
        {mid && !large ? <Text style={[styles.axisText, { color: theme.muted }]}>{displayDay(mid.date)}</Text> : null}
        <Text style={[styles.axisText, { color: theme.muted }]}>{displayDay(data.end)}</Text>
      </View>
    </View>
  );
}

/** The chart's figures as text, each day's balance: for reading, and for screen readers. */
function DayByDay({ data, visible, onClose }: { data: CashForecast; visible: boolean; onClose: () => void }) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: theme.ground }} onAccessibilityEscape={onClose}>
        <View style={styles.header}>
          <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
            {t.dayByDayTitle}
          </Text>
          <Button small kind="secondary" label={t.close} onPress={onClose} />
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingTop: 4, paddingBottom: insets.bottom + 24, gap: size.gap }}>
          <Body small muted>
            {t.dayByDayHelp}
          </Body>
          <Surface pad={false} style={{ paddingHorizontal: size.pad, paddingVertical: 4 }}>
            {data.daily.map((day, i) => (
              <LedgerRow
                key={day.date}
                lead={displayDay(day.date)}
                title={day.date === data.lowest_date ? t.lowestDay : ''}
                amount={day.balance}
                currency={data.currency}
                label={`${displayDate(day.date)}, ${formatAmount(day.balance, data.currency, { display: 'name' })}`}
                last={i === data.daily.length - 1}
              />
            ))}
          </Surface>
        </ScrollView>
      </View>
    </Modal>
  );
}

/** Something coming up: the month over the day, what it is, and the amount with its sign, money in in the chart's colour. */
function Flow({ date, title, detail, amount, currency, label, last }: { date: string; title: string; detail?: string; amount: string; currency: string; label: string; last: boolean }) {
  const theme = useTheme();
  const parts = amountParts(amount, currency);
  const [month, day] = displayDay(date).split(' ');
  return (
    <View accessible accessibilityLabel={label} style={[styles.flow, last ? null : { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line }]}>
      <View style={[styles.when, shape(radii.tile), { backgroundColor: theme.fill }]}>
        <Text style={[styles.month, { color: theme.muted }]}>{(month ?? '').toUpperCase()}</Text>
        <Text style={[styles.day, { color: theme.text }]}>{day}</Text>
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[styles.flowTitle, { color: theme.text }]} numberOfLines={1}>
          {title}
        </Text>
        {detail ? (
          <Text style={[styles.axisText, { color: theme.muted }]} numberOfLines={1}>
            {detail}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.flowAmount, { color: parts.negative ? theme.text : theme.green }]}>{parts.negative ? `(${parts.digits})` : parts.digits}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, paddingVertical: 8 },
  when: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  month: { fontFamily: font.medium, fontSize: size.caption, letterSpacing: 0.4 },
  day: { fontFamily: font.medium, fontSize: size.headline, fontVariant: ['tabular-nums'] },
  flowTitle: { fontFamily: font.regular, fontSize: size.body },
  flowAmount: { fontFamily: font.regular, fontSize: size.body, fontVariant: ['tabular-nums'] },
  cardHead: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 },
  heading: { fontFamily: font.semibold, fontSize: size.headline, letterSpacing: -0.01 * size.headline },
  code: { fontFamily: font.mono, fontSize: size.label },
  lowLine: { fontFamily: font.regular, fontSize: size.small },
  axis: { flexDirection: 'row', justifyContent: 'space-between' },
  axisText: { fontFamily: font.regular, fontSize: size.caption },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: size.gutter, paddingTop: 20, paddingBottom: 12, gap: 12 },
  headerTitle: { flexShrink: 1, fontFamily: font.semibold, fontSize: size.title },
});
