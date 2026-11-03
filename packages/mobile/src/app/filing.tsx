import { remindersList, remindersSeedFilingCalendar } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useApi, useRead } from '../api';
import { Body, Button, Card, Chip, Notice, SectionLabel, Waiting } from '../kit';
import { displayDay, todayIso } from '../lib/display';
import { Page } from '../shell';
import { strings } from '../strings';
import { useTheme } from '../theme';

const t = strings.attention;

/**
 * Filing dates (design 44): the deadlines your active tax rules set for a
 * year, as reminders. Bringing a year up to date asks the server to add,
 * change or remove them; it is safe to do again.
 */
export default function Filing() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const thisYear = Number(todayIso().slice(0, 4)); // eslint-disable-line no-restricted-syntax -- not money: a year
  const years = [thisYear - 1, thisYear, thisYear + 1];
  const [year, setYear] = useState(thisYear);
  const reminders = useRead('reminders.list', remindersList);
  const seed = useMutation({
    mutationFn: () => api.call(remindersSeedFilingCalendar, { query: { year: String(year) } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server] }),
  });
  const filing = (reminders.data?.reminders ?? []).filter((r) => r.source_domain === 'tax_rules' && r.due_date.startsWith(String(year))).sort((a, b) => a.due_date.localeCompare(b.due_date));

  return (
    <Page title={t.filing} back={{ label: t.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/attention')) }}>
      <Card style={{ gap: 12 }}>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {years.map((y) => {
            const on = y === year;
            return (
              <Chip
                key={y}
                label={String(y)}
                selected={on}
                onPress={() => {
                  setYear(y);
                  seed.reset();
                }}
              />
            );
          })}
        </View>
        <SectionLabel>{t.inReminders(filing.length)}</SectionLabel>
        {reminders.data ? (
          filing.map((r, i) => (
            <View key={r.id} style={[styles.row, i < filing.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line } : null]}>
              <Body style={{ flex: 1 }}>{r.kind}</Body>
              <Body small muted>
                {displayDay(r.due_date)}
              </Body>
            </View>
          ))
        ) : (
          <Waiting query={reminders} what="your reminders" />
        )}
        {seed.data ? <Notice tone="good">{t.seeded(seed.data.created, seed.data.updated.length, seed.data.removed.length)}</Notice> : null}
        {seed.error ? <Notice tone="warn">{seed.error.message}</Notice> : null}
        <Button label={t.bringUpToDate(year)} busy={seed.isPending} disabled={seed.isPending} onPress={() => seed.mutate()} />
      </Card>
      <Body small muted>
        {t.filingNote}
      </Body>
    </Page>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48 },
});
