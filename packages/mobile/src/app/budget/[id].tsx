import { accountsList, budgetsMonthlyGet, budgetsMonthlySet, budgetsTrend, formatAmount, normalizeAmountInput, type MonthlyLineRequest } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../../api';
import { Body, Button, Field, Notice, Press, Surface, Toggle, useDoneBar, radii, shape } from '../../kit';
import { useKeepDraft } from '../../draft';
import { strings } from '../../strings';
import { elevation, font, size, useTheme } from '../../theme';

const t = strings.budget;

/** A category's monthly limit and whether what is left rolls over (design HhBudgetEdit). */
export default function BudgetEdit() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const api = useApi();
  const queryClient = useQueryClient();
  const { id = '' } = useLocalSearchParams<{ id: string }>();
  const monthly = useRead('budgets.monthlyGet', budgetsMonthlyGet);
  const trend = useRead('budgets.trend', budgetsTrend, {
    query: { months: 6 },
  });
  const accounts = useRead('accounts.list', accountsList);
  const name = accounts.data?.find((a) => a.id === id)?.name ?? '';
  const existing = monthly.data?.lines.find((l) => l.account_id === id);
  const currency = monthly.data?.currency ?? trend.data?.currency ?? '';
  const [limit, setLimit] = useState('');
  const [rollover, setRollover] = useState(false);
  useEffect(() => {
    if (existing) {
      setLimit(existing.limit_amount);
      setRollover(existing.rollover);
    }
  }, [existing]);
  // The three full months before this one, newest first.
  const spent =
    trend.data?.categories
      .find((c) => c.account_id === id)
      ?.spent.slice(0, -1)
      .slice(-3)
      .reverse() ?? [];
  const exact = normalizeAmountInput(limit);
  const done = useDoneBar();
  const keep = useKeepDraft(!!monthly.data && (limit !== (existing?.limit_amount ?? '') || rollover !== (existing?.rollover ?? false)));

  const others: MonthlyLineRequest[] = (monthly.data?.lines ?? [])
    .filter((l) => l.account_id !== id)
    .map((l) => ({
      account_id: l.account_id,
      limit_amount: l.limit_amount,
      rollover: l.rollover,
    }));
  // The line in its place among the others, or last when it is new.
  const withLine = (line: MonthlyLineRequest): MonthlyLineRequest[] =>
    existing ? (monthly.data?.lines ?? []).map((l) => (l.account_id === id ? line : { account_id: l.account_id, limit_amount: l.limit_amount, rollover: l.rollover })) : [...others, line];
  const save = useMutation({
    mutationFn: (lines: MonthlyLineRequest[]) => api.call(budgetsMonthlySet, { body: { lines } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: [api.server] });
      keep.done();
      router.back();
    },
  });

  return (
    <View style={{ flex: 1, backgroundColor: theme.ground }} onAccessibilityEscape={() => router.back()}>
      <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? 12 : insets.top }]}>
        <Press accessibilityRole="button" hitSlop={4} onPress={() => router.back()} style={[styles.headerButton, shape(radii.pill), { backgroundColor: theme.surface }, elevation(theme, 'card')]}>
          <Body max={1.5} small>{strings.add.cancel}</Body>
        </Press>
        <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.headerTitle, { color: theme.text }]}>
          {name}
        </Text>
        <View style={styles.headerSpace} />
      </View>
      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: insets.bottom + 24 }]} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" automaticallyAdjustKeyboardInsets>
        <Surface style={{ gap: 12 }}>
          <Field
            {...done.field('limit')}
            label={t.limit(currency)}
            value={limit}
            onChangeText={setLimit}
            keyboardType="decimal-pad"
            placeholder="0.00"
            amount
            {...(limit && !exact ? { error: strings.add.notAnAmount } : {})}
          />
          {spent.length ? (
            <Body small muted>
              {t.lastMonths(spent.map((s) => formatAmount(s, currency, { display: 'none' })).join(', '))}
            </Body>
          ) : null}
        </Surface>
        <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
          <Toggle label={t.rolloverLabel} help={t.rolloverHelp} value={rollover} onChange={setRollover} />
        </Surface>
        {save.error ? <Notice tone="warn">{save.error.message}</Notice> : null}
        <View style={{ gap: 4 }}>
          <Button label={t.save} busy={save.isPending} disabled={!exact || !monthly.data || save.isPending} onPress={() => exact && save.mutate(withLine({ account_id: id, limit_amount: exact, rollover }))} />
          {existing ? <Button kind="tertiary" label={t.remove} disabled={save.isPending} onPress={() => save.mutate(others)} /> : null}
        </View>
      </ScrollView>
      {done.bar}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: size.gutter, paddingBottom: 8, columnGap: 12 },
  headerButton: { minHeight: 40, minWidth: 72, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 16 },
  headerSpace: { minWidth: 72 },
  headerTitle: { flex: 1, textAlign: 'center', fontFamily: font.semibold, fontSize: size.headline },
  page: { padding: size.gutter, gap: size.gap },
});
