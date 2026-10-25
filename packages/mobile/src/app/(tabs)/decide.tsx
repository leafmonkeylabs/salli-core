import { decisionsReview, decisionsReviewsDue, type DueReview } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, CardHead, Money, Waiting } from '../../kit';
import { shares } from '../../lib/chart';
import { amountParts, displayDate, displayDay } from '../../lib/display';
import { Page } from '../../shell';
import { Sheet, SheetTitle } from '../../sheet';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.decide;

export default function Decide() {
  const due = useRead('decisions.reviews.due', decisionsReviewsDue);
  // A review recorded here leaves the due list when it is read again; it stays
  // on the page, said as recorded, until the person leaves.
  const [recorded, setRecorded] = useState<readonly DueReview[]>([]);
  const shown = due.data ? [...due.data.reviews.filter((r) => !recorded.some((d) => d.id === r.id)), ...recorded] : [];
  return (
    <Page underAI title={t.title} onRefresh={() => due.refetch()}>
      {due.data ? (
        shown.length ? (
          shown.map((review) => (
            <Review
              key={review.id}
              review={review}
              done={recorded.some((d) => d.id === review.id)}
              onRecorded={() => setRecorded((r) => [...r, review])}
            />
          ))
        ) : (
          <Card>
            <Body muted>{t.noneDue}</Body>
          </Card>
        )
      ) : (
        <Waiting query={due} what="decisions" />
      )}
    </Page>
  );
}

function Review({ review, done, onRecorded }: { review: DueReview; done: boolean; onRecorded: () => void }) {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const [writing, setWriting] = useState(false);
  const [reflection, setReflection] = useState('');
  const record = useMutation({
    mutationFn: () => api.call(decisionsReview, { path: { decision_id: review.id }, body: { reflection: reflection.trim() } }),
    onSuccess: () => {
      setWriting(false);
      onRecorded();
      return queryClient.invalidateQueries({ queryKey: [api.server] });
    },
  });
  const comparison = review.comparison;

  return (
    <Card style={{ gap: 10 }}>
      <CardHead label={t.due} />
      <Text accessibilityRole="header" style={[styles.question, { color: theme.text }]}>
        {review.question}
      </Text>
      <Text accessibilityLabel={`${t.chose(review.chosen, review.reasons ?? '')} ${t.recorded(displayDate(review.recorded_at), displayDate(review.review_on))}`} style={[styles.chose, { color: theme.muted }]}>
        {t.choseShort(review.chosen, displayDay(review.review_on))}
      </Text>

      {comparison ? (
        <View accessibilityLabel={t.against(displayDate(comparison.at))} style={{ gap: 2, marginTop: 4 }}>
          <View style={styles.key} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <View style={[styles.swatch, { backgroundColor: theme.muted }]} />
            <Text style={[styles.keyText, { color: theme.muted }]}>{t.projected}</Text>
            <View style={[styles.swatch, { backgroundColor: theme.chart, marginLeft: 12 }]} />
            <Text style={[styles.keyText, { color: theme.muted }]}>{t.actual}</Text>
            <Text style={[styles.keyText, { color: theme.muted, marginLeft: 'auto' }]}>{comparison.currency}</Text>
          </View>
          {comparison.figures.map((row) => {
            const [projected, actual] = shares([row.projected ?? '0', row.actual ?? '0']);
            const name = t.figures[row.figure] ?? row.figure;
            const spoken = (a: string | null | undefined) => (a ? amountParts(a, comparison.currency).spoken : '—');
            return (
              <View key={row.figure} accessible accessibilityLabel={t.figureSpoken(name, spoken(row.projected), spoken(row.actual))} style={[styles.pair, { borderBottomColor: theme.rule }]}>
                <View style={styles.pairHead}>
                  <Body style={{ flex: 1 }}>{name}</Body>
                  {row.actual ? <Money amount={row.actual} currency={comparison.currency} /> : null}
                </View>
                <View style={[styles.track, { backgroundColor: theme.rule }]}>
                  <View style={[styles.track, { width: `${(projected ?? 0) * 100}%`, backgroundColor: theme.muted }]} />
                </View>
                <View style={[styles.track, { backgroundColor: theme.rule }]}>
                  <View style={[styles.track, { width: `${(actual ?? 0) * 100}%`, backgroundColor: theme.chart }]} />
                </View>
              </View>
            );
          })}
          {comparison.notes.map((note) => (
            <Body key={note} small muted>
              {note}
            </Body>
          ))}
        </View>
      ) : null}

      {done ? <Body alert>{`✓ ${t.recordedReview}`}</Body> : <Button label={t.write} onPress={() => setWriting(true)} />}

      {/* The review is written in a sheet, so the comparison reads first. */}
      <Sheet visible={writing} onClose={() => setWriting(false)} label={t.reflection}>
        <SheetTitle style={[styles.question, { color: theme.text }]}>
          {review.question}
        </SheetTitle>
        <Body muted>{t.chose(review.chosen, review.reasons ?? '')}</Body>
        <View style={{ gap: 6 }}>
          <Text style={[styles.label, { color: theme.text }]}>{t.reflection}</Text>
          <TextInput
            value={reflection}
            onChangeText={setReflection}
            multiline
            autoFocus
            accessibilityLabel={t.reflection}
            accessibilityHint={t.reflectionHelp}
            placeholder={t.reflectionPlaceholder}
            placeholderTextColor={theme.muted}
            style={[styles.input, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
          />
        </View>
        {record.error ? <Body alert>{record.error.message}</Body> : null}
        <View style={{ gap: 4 }}>
          <Button label={t.submit} busy={record.isPending} disabled={!reflection.trim() || record.isPending} onPress={() => record.mutate()} />
          <Button kind="tertiary" label={t.cancel} disabled={record.isPending} onPress={() => setWriting(false)} />
        </View>
      </Sheet>
    </Card>
  );
}

const styles = StyleSheet.create({
  question: { fontFamily: font.medium, fontSize: size.heading, lineHeight: size.heading * 1.3 },
  label: { fontFamily: font.medium, fontSize: size.small },
  chose: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  key: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingBottom: 6 },
  keyText: { fontFamily: font.regular, fontSize: 12 },
  swatch: { width: 10, height: 6 },
  pair: { gap: 4, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  pairHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  track: { height: 6 },
  input: { minHeight: 120, borderWidth: 1, borderRadius: 0, padding: 12, fontFamily: font.regular, fontSize: size.body, textAlignVertical: 'top' },
});
