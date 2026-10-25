/**
 * How left to spend is worked out: the server's parts top to bottom, as it
 * sends them, then its total, its low point and its notes. Every figure is
 * the server's; the app adds and takes away nothing.
 */
import { isZeroAmount, type SafeToSpend } from '@leafmonkeylabs/salli-sdk';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Money } from './kit';
import { amountParts, displayDay } from './lib/display';
import { Sheet } from './sheet';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.workedOut;

export function WorkedOut({ safe, visible, onClose }: { safe: SafeToSpend; visible: boolean; onClose: () => void }) {
  const theme = useTheme();
  const { currency } = safe;
  const low = amountParts(safe.low_point, currency);
  return (
    <Sheet visible={visible} onClose={onClose} label={t.title}>
      <View style={styles.head}>
        <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
          {t.title}
        </Text>
        <Pressable accessibilityRole="button" onPress={onClose} style={styles.done}>
          <Text style={[styles.doneText, { color: theme.text }]}>{t.done}</Text>
        </Pressable>
      </View>
      <Text style={[styles.note, { color: theme.muted }]}>{safe.next_income ? t.window(safe.next_income.description, displayDay(safe.until)) : t.window30}</Text>
      <View>
        <Part label={t.cashToday} amount={safe.cash_today} currency={currency} />
        <Part label={t.everyday} amount={safe.everyday_spending} currency={currency} less />
        <Part label={t.cushion} amount={safe.cushion} currency={currency} less />
        {isZeroAmount(safe.held_for_goals) ? null : <Part label={t.goals} amount={safe.held_for_goals} currency={currency} less />}
        <Part label={t.total} amount={safe.amount} currency={currency} total />
      </View>
      <Text accessibilityLabel={t.lowest(low.spoken, displayDay(safe.low_point_date))} style={[styles.small, { color: theme.muted }]}>
        {t.lowest(low.negative ? `(${low.digits})` : low.digits, displayDay(safe.low_point_date))}
      </Text>
      {safe.notes.map((note, i) => (
        <Text key={i} style={[styles.small, { color: theme.muted }]}>
          {note}
        </Text>
      ))}
      {safe.next_income ? <Text style={[styles.small, { color: theme.muted }]}>{t.noIncome}</Text> : null}
    </Sheet>
  );
}

/** One of the server's parts: its label and amount, marked "−" where it is kept back, as the design draws it. */
function Part({ label, amount, currency, less, total }: { label: string; amount: string; currency: string; less?: boolean; total?: boolean }) {
  const theme = useTheme();
  const spoken = amountParts(amount, currency).spoken;
  const weight = total ? { fontFamily: font.medium } : null;
  return (
    <View
      accessible
      accessibilityLabel={less ? t.less(label, spoken) : `${label}: ${spoken}`}
      style={[styles.part, { borderTopColor: total ? theme.text : theme.rule, borderTopWidth: total ? 1 : StyleSheet.hairlineWidth }]}
    >
      <Text style={[styles.label, { color: theme.text }, weight]}>{label}</Text>
      <View style={styles.amount}>
        {less ? <Text style={[styles.label, { color: theme.text }]}>−</Text> : null}
        <Money amount={amount} currency={currency} style={weight ?? {}} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontFamily: font.medium, fontSize: 20 },
  done: { minHeight: size.target, minWidth: size.target, justifyContent: 'center', alignItems: 'flex-end' },
  doneText: { fontFamily: font.medium, fontSize: size.body },
  note: { fontFamily: font.regular, fontSize: 15 },
  part: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, minHeight: 48, paddingVertical: 12 },
  label: { flexShrink: 1, fontFamily: font.regular, fontSize: size.body },
  amount: { flexDirection: 'row', alignItems: 'baseline', gap: 6 },
  small: { fontFamily: font.regular, fontSize: size.small },
});
