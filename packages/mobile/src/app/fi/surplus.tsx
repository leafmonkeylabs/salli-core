import { fiSurplus } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';
import { useRead } from '../../api';
import { Body, Card, Money, SectionLabel, Waiting } from '../../kit';
import { shares } from '../../lib/chart';
import { amountParts, wholeDigits } from '../../lib/display';
import { percentOf } from '../../lib/fi';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.fi;

/**
 * Where the surplus goes (design 49): what's left each month and the savings
 * rate, spending by need as one bar, and income by source; every figure is a
 * monthly average the server worked out.
 */
export default function Surplus() {
  const theme = useTheme();
  const read = useRead('fi.surplus', fiSurplus);
  const d = read.data;
  const needs = d ? Object.entries(d.expense_by_need as Record<string, string>) : [];
  const incomes = d ? Object.entries(d.income_by_source as Record<string, string>) : [];
  const widths = shares(needs.map(([, v]) => v));
  const shades = [1, 0.6, 0.35, 0.2];

  return (
    <Page title={t.surplus} back={{ label: t.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/fi')) }} onRefresh={() => read.refetch()}>
      {d ? (
        <>
          <Card style={{ gap: 8 }}>
            <SectionLabel>{t.eachMonth}</SectionLabel>
            <Text accessibilityLabel={t.leftSpoken(amountParts(d.monthly_surplus, d.currency).spoken, percentOf(d.savings_rate))} style={[styles.big, { color: theme.text }]}>
              {wholeDigits(d.monthly_surplus, d.currency)} <Text style={[styles.small, { color: theme.muted }]}>{t.left(percentOf(d.savings_rate).replace(/\..*$/, ''))}</Text>
            </Text>
            {needs.length ? (
              <View style={[styles.stack, { borderRadius: Math.min(theme.radius, 6) }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
                {needs.map(([k], i) => (
                  <View key={k} style={{ flex: widths[i] ?? 0, backgroundColor: theme.chart, opacity: shades[i] ?? 0.2 }} />
                ))}
              </View>
            ) : null}
            {needs.map(([k, v], i) => (
              <View key={k} style={styles.legend}>
                <View style={[styles.swatch, { backgroundColor: theme.chart, opacity: shades[i] ?? 0.2, borderRadius: theme.marker === 'dot' ? 5 : 0 }]} />
                <Body style={{ flex: 1 }}>{t.needs[k] ?? k}</Body>
                <Money amount={v} currency={d.currency} />
              </View>
            ))}
          </Card>
          <Card style={{ gap: 4 }}>
            <SectionLabel>{t.comingIn}</SectionLabel>
            {incomes.map(([k, v]) => (
              <View key={k} style={styles.legend}>
                <Body style={{ flex: 1 }}>{k}</Body>
                <Money amount={v} currency={d.currency} />
              </View>
            ))}
          </Card>
          <Body small muted>
            {t.averaged(d.months_observed.length)}
          </Body>
        </>
      ) : (
        <Waiting query={read} what="your surplus" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  big: { fontFamily: font.semibold, fontSize: 28, fontVariant: ['tabular-nums'] },
  small: { fontFamily: font.regular, fontSize: size.body },
  stack: { flexDirection: 'row', height: 14, overflow: 'hidden' },
  legend: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 34 },
  swatch: { width: 10, height: 10 },
});
