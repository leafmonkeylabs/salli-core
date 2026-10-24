import { formatAmount, insightsForecast, type CashForecast } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Circle, Line, Path, Text as SvgText } from 'react-native-svg';
import { useRead } from '../../api';
import { AmountRow, Body, Button, Card, CardHead, LedgerRow, Waiting } from '../../kit';
import { placeLabels, stepChart } from '../../lib/chart';
import { displayDate, displayDay } from '../../lib/display';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.cash;
/** Rows of what's coming up shown here; the console lists the rest. */
const COMING_UP = 12;
const LABEL_SIZE = 12;

export default function Cash() {
  const { width } = useWindowDimensions();
  const forecast = useRead('insights.forecast', insightsForecast);
  const [days, setDays] = useState(false);
  const data = forecast.data;
  const chartWidth = width - 2 * size.gutter - 32;
  const chartHeight = 180;

  return (
    <Page title={t.title} onRefresh={() => forecast.refetch()}>
      <Card style={{ gap: 10 }}>
        <CardHead label={data ? t.forecast(String(data.daily.length - 1)) : t.forecast('60')} />
        {data ? (
          <>
            <Chart data={data} width={chartWidth} height={chartHeight} />
            <Body small muted>
              {t.forecastCaption(
                displayDate(data.start),
                displayDate(data.end),
                formatAmount(data.today, data.currency),
                formatAmount(data.lowest, data.currency),
                displayDate(data.lowest_date),
                formatAmount(data.end_balance, data.currency),
              )}
            </Body>
            {/* A text link, aligned with the caption: the button's own padding sits outside it. */}
            <View style={{ alignSelf: 'flex-start', marginLeft: -18 }}>
              <Button kind="tertiary" label={t.dayByDay} onPress={() => setDays(true)} />
            </View>
          </>
        ) : (
          <Waiting query={forecast} what="the forecast" />
        )}
      </Card>

      <Card style={{ paddingVertical: 12 }}>
        <CardHead label={t.comingUp} help={t.comingUpHelp} end={data?.currency} />
        {data ? (
          data.flows.length ? (
            <>
              {data.flows.slice(0, COMING_UP).map((flow, i, shown) => {
                const account = data.accounts.find((a) => a.account_id === flow.account_id)?.name;
                const source = t.sources[flow.source] ?? flow.source;
                return (
                  // One line, as the design's table; the account and the source are read out with it.
                  <LedgerRow
                    key={`${flow.date}-${flow.account_id ?? ''}-${flow.description}-${flow.amount}`}
                    lead={displayDay(flow.date)}
                    title={flow.description}
                    amount={flow.amount}
                    currency={flow.currency}
                    label={t.flowLabel(displayDate(flow.date), flow.description, formatAmount(flow.amount, flow.currency, { display: 'name' }), [account, source].filter(Boolean).join(', '))}
                    last={i === shown.length - 1}
                  />
                );
              })}
              {data.flows.length > COMING_UP ? (
                <Body small muted style={{ paddingTop: 8 }}>
                  {t.more(data.flows.length - COMING_UP)}
                </Body>
              ) : null}
            </>
          ) : (
            <Body muted>{t.nothingComing}</Body>
          )
        ) : null}
      </Card>

      {data?.accounts.length ? (
        <Card style={{ paddingVertical: 12 }}>
          <CardHead label={t.accounts} help={t.accountsHelp} />
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
        </Card>
      ) : null}

      {data ? <DayByDay data={data} visible={days} onClose={() => setDays(false)} /> : null}
    </Page>
  );
}

/**
 * The next days as a step line. Its gridlines sit at the highest and lowest
 * days, and its labels are those days', today's and the last day's own
 * balances: no value on it is one Salli didn't send.
 */
function Chart({ data, width, height }: { data: CashForecast; width: number; height: number }) {
  const theme = useTheme();
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
      if (!w.point || seen.has(w.index)) return [];
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
      <Svg width={width} height={height} accessibilityLabel={t.chartLabel(money(data.today), money(data.lowest), displayDate(data.lowest_date), money(data.end_balance))}>
        {high && chart.highIndex !== chart.lowIndex ? <Line x1={0} x2={width} y1={high.y} y2={high.y} stroke={theme.rule} strokeWidth={1} /> : null}
        <Line x1={0} x2={width} y1={chart.low.y} y2={chart.low.y} stroke={theme.rule} strokeWidth={1} />
        {chart.zero !== undefined ? <Line x1={0} x2={width} y1={chart.zero} y2={chart.zero} stroke={theme.text} strokeWidth={1} /> : null}
        <Line x1={0} x2={width} y1={height - 0.5} y2={height - 0.5} stroke={theme.text} strokeWidth={1} />
        <Path d={chart.path} stroke={theme.chart} strokeWidth={1.5} fill="none" />
        <Circle cx={chart.low.x} cy={chart.low.y} r={3.5} fill={theme.text} />
        {labels.map((label) => (
          <SvgText key={label.key} x={label.x} y={label.y} textAnchor={label.anchor} fontFamily={font.regular} fontSize={LABEL_SIZE} fill={theme.text}>
            {label.text}
          </SvgText>
        ))}
      </Svg>
      <View style={styles.axis}>
        <Text style={[styles.axisText, { color: theme.muted }]}>{displayDay(data.start)}</Text>
        {mid ? <Text style={[styles.axisText, { color: theme.muted }]}>{displayDay(mid.date)}</Text> : null}
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
      <View style={{ flex: 1, backgroundColor: theme.chrome }}>
        <View style={[styles.header, { borderBottomColor: theme.rule }]}>
          <View style={styles.headerButton} />
          <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
            {t.dayByDayTitle}
          </Text>
          <Pressable accessibilityRole="button" onPress={onClose} style={styles.headerButton}>
            <Body style={{ textAlign: 'right' }}>{t.close}</Body>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: size.gutter, paddingBottom: insets.bottom + 24, gap: 8 }}>
          <Body small muted>
            {t.dayByDayHelp}
          </Body>
          <View>
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
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  axis: { flexDirection: 'row', justifyContent: 'space-between' },
  axisText: { fontFamily: font.regular, fontSize: 12 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { flexShrink: 1, fontFamily: font.medium, fontSize: 17 },
});
