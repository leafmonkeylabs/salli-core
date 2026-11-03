/**
 * Picking a day (design HhAddDate): Today and Yesterday, then a month's
 * calendar to pick any earlier day. Days after today can't be picked.
 */
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Button, Chip, Icon, radii, shape } from './kit';
import { addDays, addMonths, displayDate, displayDay, monthGrid, monthNameOf, todayIso } from './lib/display';
import { Sheet, SheetTitle } from './sheet';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.add;

export function DateSheet({ visible, value, onPick, onClose }: { visible: boolean; value: string; onPick: (iso: string) => void; onClose: () => void }) {
  const theme = useTheme();
  return (
    <Sheet visible={visible} onClose={onClose} label={t.pickDay}>
      <SheetTitle style={[styles.title, { color: theme.text }]}>
        {t.date}
      </SheetTitle>
      <DayChooser value={value} onPick={onPick} />
    </Sheet>
  );
}

/** The days to choose from: drawn in the sheet, or pushed inside one already open (Add), so one sheet is on screen. */
export function DayChooser({ value, onPick }: { value: string; onPick: (iso: string) => void }) {
  const theme = useTheme();
  const today = todayIso();
  const yesterday = addDays(today, -1);
  const [chosen, setChosen] = useState(value);
  const [month, setMonth] = useState(value.slice(0, 7));
  const atLatest = month >= today.slice(0, 7);
  const quick = [
    { label: t.today, iso: today },
    { label: t.yesterday, iso: yesterday },
  ];
  const pick = (iso: string) => {
    setChosen(iso);
    setMonth(iso.slice(0, 7));
  };

  return (
    <>
      <View accessibilityRole="radiogroup" style={styles.quick}>
        {quick.map((q) => (
          <Chip key={q.label} label={q.label} selected={q.iso === chosen} onPress={() => pick(q.iso)} />
        ))}
      </View>
      <View style={styles.monthRow}>
        <Pressable accessibilityRole="button" accessibilityLabel={monthNameOf(`${addMonths(month, -1)}-01`)} onPress={() => setMonth(addMonths(month, -1))} style={[styles.arrow, shape(radii.pill), { backgroundColor: theme.fill }]}>
          <Icon name="back" colour={theme.text} />
        </Pressable>
        <Text style={[styles.monthText, { color: theme.text }]}>{`${monthNameOf(`${month}-01`)} ${month.slice(0, 4)}`}</Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={monthNameOf(`${addMonths(month, 1)}-01`)}
          accessibilityState={{ disabled: atLatest }}
          disabled={atLatest}
          onPress={() => setMonth(addMonths(month, 1))}
          style={[styles.arrow, shape(radii.pill), { backgroundColor: theme.fill }, atLatest ? { backgroundColor: 'transparent' } : null]}
        >
          <Icon name="chevron" colour={atLatest ? theme.muted : theme.text} />
        </Pressable>
      </View>
      <View style={styles.grid}>
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
          <Text key={i} accessibilityElementsHidden importantForAccessibility="no" style={[styles.cell, styles.weekday, { color: theme.muted }]}>
            {d}
          </Text>
        ))}
        {monthGrid(month).map((iso, i) => {
          if (!iso) return <View key={`blank-${i}`} style={styles.cell} />;
          const later = iso > today;
          const on = iso === chosen;
          return (
            <Pressable
              key={iso}
              accessibilityRole="button"
              accessibilityLabel={displayDate(iso)}
              accessibilityState={{ selected: on, disabled: later }}
              disabled={later}
              onPress={() => setChosen(iso)}
              style={[styles.cell, styles.day]}
            >
              {/* The chosen day is a filled circle; today a ring. */}
              <View style={[styles.circle, shape(radii.pill), on ? { backgroundColor: theme.button } : iso === today ? { borderWidth: 1.5, borderColor: theme.green } : null]}>
                <Text style={[styles.dayText, { color: on ? theme.buttonText : later ? theme.muted : theme.text, fontFamily: on ? font.medium : font.regular }]}>{iso.slice(8).replace(/^0/, '')}</Text>
              </View>
            </Pressable>
          );
        })}
      </View>
      <Button label={t.useDay(displayDay(chosen))} onPress={() => onPick(chosen)} />
    </>
  );
}

const styles = StyleSheet.create({
  title: { fontFamily: font.semibold, fontSize: size.title },
  quick: { flexDirection: 'row', gap: 8 },
  monthRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  arrow: { minWidth: size.target, minHeight: size.target, alignItems: 'center', justifyContent: 'center' },
  monthText: { fontFamily: font.medium, fontSize: size.body },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  cell: { width: `${100 / 7}%`, alignItems: 'center', justifyContent: 'center' },
  weekday: { fontFamily: font.regular, fontSize: size.caption, textAlign: 'center', paddingBottom: 4 },
  day: { minHeight: 48 },
  circle: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  dayText: { fontSize: size.body, fontVariant: ['tabular-nums'] },
});
