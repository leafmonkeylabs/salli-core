import { formatAmount, insightsForecast } from '@leafmonkeylabs/salli-sdk';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Circle, Line, Path } from 'react-native-svg';
import { useRead } from '../../api';
import { AmountRow, Body, Card, CardHead, Loading } from '../../kit';
import { stepChart } from '../../lib/chart';
import { displayDate } from '../../lib/display';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.cash;
/** Rows of what's coming up shown here; the console lists the rest. */
const COMING_UP = 12;

export default function Cash() {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const forecast = useRead('insights.forecast', insightsForecast);
  const data = forecast.data;
  const chartWidth = width - 2 * size.gutter - 32;
  const chartHeight = 160;

  return (
    <Page title={t.title} onRefresh={() => forecast.refetch()}>
      <Card style={{ gap: 10 }}>
        <CardHead label={data ? t.forecast(String(data.daily.length - 1)) : t.forecast('60')} />
        {data ? (
          (() => {
            const code = data.currency;
            const money = (amount: string): string => formatAmount(amount, code, { display: 'none' });
            const chart = stepChart(data.daily, { date: data.lowest_date, balance: data.lowest }, chartWidth, chartHeight);
            return (
              <>
                <Svg
                  width={chartWidth}
                  height={chartHeight}
                  accessibilityLabel={t.chartLabel(money(data.today), money(data.lowest), displayDate(data.lowest_date), money(data.end_balance))}
                >
                  {chart.zero !== undefined ? <Line x1={0} x2={chartWidth} y1={chart.zero} y2={chart.zero} stroke={theme.text} strokeWidth={1} /> : null}
                  <Line x1={0} x2={chartWidth} y1={chartHeight - 0.5} y2={chartHeight - 0.5} stroke={theme.rule} strokeWidth={1} />
                  <Path d={chart.path} stroke={theme.chart} strokeWidth={1.5} fill="none" />
                  <Circle cx={chart.low.x} cy={chart.low.y} r={3} fill={theme.text} />
                </Svg>
                <View style={styles.axis}>
                  <Text style={[styles.axisText, { color: theme.muted }]}>{displayDate(data.start)}</Text>
                  <Text style={[styles.axisText, { color: theme.muted }]}>{displayDate(data.end)}</Text>
                </View>
                <Body small muted>
                  {t.forecastCaption(
                    displayDate(data.start),
                    displayDate(data.end),
                    formatAmount(data.today, code),
                    formatAmount(data.lowest, code),
                    displayDate(data.lowest_date),
                    formatAmount(data.end_balance, code),
                  )}
                </Body>
              </>
            );
          })()
        ) : (
          <Loading what={strings.home.loading('the forecast')} />
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
                  <AmountRow
                    key={`${flow.date}-${flow.account_id ?? ''}-${flow.description}-${flow.amount}`}
                    title={flow.description}
                    detail={[displayDate(flow.date), account, source].filter(Boolean).join(' · ')}
                    amount={flow.amount}
                    currency={flow.currency}
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
    </Page>
  );
}

const styles = StyleSheet.create({
  axis: { flexDirection: 'row', justifyContent: 'space-between' },
  axisText: { fontFamily: font.regular, fontSize: 12 },
});
