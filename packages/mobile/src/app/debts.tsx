import { baselineGet, debtsList, formatAmount, formatRatio } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../api';
import { Body, Card, CardHead, Icon, Money, Waiting } from '../kit';
import { displayDate, displayMonth } from '../lib/display';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.debts;

/**
 * Debts (design HhDebts): what you owe in all, then each debt with its rate,
 * its minimum and the month it is paid off at minimum payments, as the
 * baseline reads them, and their minimums a month together (the server's
 * sum, from the debts read). Listed in the debts read's order, by rate,
 * highest first; the baseline row is looked up by id, never re-sorted. A
 * debt held in the books opens its account.
 */
export default function Debts() {
  const theme = useTheme();
  const baseline = useRead('baseline.get', baselineGet);
  const debts = useRead('debts.list', debtsList);
  const data = baseline.data;
  const byId = new Map(data?.debts.map((d) => [d.debt_id, d]));
  const rows = (debts.data?.debts ?? []).flatMap((d) => byId.get(d.id) ?? []);
  return (
    <Page
      title={t.title}
      back={{
        label: strings.attention.title,
        onPress: () => (router.canGoBack() ? router.back() : router.replace('/attention')),
      }}
      onRefresh={() => Promise.all([baseline.refetch(), debts.refetch()])}
    >
      {data && debts.data ? (
        <>
          <Card>
            <CardHead label={t.total(displayDate(data.as_of))} />
            <Money amount={data.totals.debts} currency={data.currency} figure="key" />
            {debts.data ? (
              <View style={[styles.line, styles.minimums]}>
                <Text style={[styles.detail, { color: theme.muted }]}>{t.minimums}</Text>
                <Money amount={debts.data.total_minimum_payments} currency={data.currency} style={styles.name} />
              </View>
            ) : null}
          </Card>
          <Card style={{ paddingBottom: 0 }}>
            <CardHead label={t.each(data.currency)} />
            {rows.length ? (
              rows.map((debt) => {
                const row = (
                  <>
                    <View style={{ flex: 1, gap: 4 }}>
                      <View style={styles.line}>
                        <Text style={[styles.name, { color: theme.text }]}>{debt.name}</Text>
                        <Money amount={debt.balance} currency={data.currency} style={styles.name} />
                      </View>
                      <View style={styles.line}>
                        <Text style={[styles.detail, { color: theme.muted }]}>
                          {t.terms(
                            formatRatio(debt.apr),
                            formatAmount(debt.minimum_payment, data.currency, {
                              display: 'none',
                            }),
                          )}
                        </Text>
                        <Text style={[styles.detail, { color: theme.muted }]}>{debt.paid_off ? t.free(displayMonth(debt.paid_off)) : t.notPaidOff}</Text>
                      </View>
                    </View>
                    {debt.account_id ? <Icon name="chevron" size={18} colour={theme.muted} /> : null}
                  </>
                );
                const style = [styles.row, { borderTopColor: theme.rule }];
                return debt.account_id ? (
                  <Pressable
                    key={debt.debt_id}
                    accessibilityRole="button"
                    onPress={() =>
                      router.push({
                        pathname: '/account/[id]',
                        params: { id: debt.account_id ?? '' },
                      })
                    }
                    style={style}
                  >
                    {row}
                  </Pressable>
                ) : (
                  <View key={debt.debt_id} accessible style={style}>
                    {row}
                  </View>
                );
              })
            ) : (
              <Body muted style={{ paddingVertical: 12 }}>
                {t.none}
              </Body>
            )}
          </Card>
          <Body small muted>
            {t.note}
          </Body>
        </>
      ) : (
        <Waiting query={data ? debts : baseline} what="your debts" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minHeight: 48,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  line: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  minimums: { alignItems: 'baseline', marginTop: 8 },
  name: { fontFamily: font.medium, fontSize: size.body },
  detail: {
    fontFamily: font.regular,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
  },
});
