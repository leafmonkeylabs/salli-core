import { decisionsReview, decisionsReviewsDue, type DueReview } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Share, StyleSheet, Text, TextInput, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, CardHead, Money, Waiting } from '../../kit';
import { displayDate } from '../../lib/display';
import { useSession } from '../../session';
import { Page } from '../../shell';
import { Sheet } from '../../sheet';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.decide;

export default function Decide() {
  const { session } = useSession();
  const due = useRead('decisions.reviews.due', decisionsReviewsDue);
  // A review recorded here leaves the due list when it is read again; it stays
  // on the page, said as recorded, until the person leaves.
  const [recorded, setRecorded] = useState<readonly DueReview[]>([]);
  const shown = due.data ? [...due.data.reviews.filter((r) => !recorded.some((d) => d.id === r.id)), ...recorded] : [];
  return (
    <Page title={t.title} onRefresh={() => due.refetch()}>
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
      <View style={{ gap: 6 }}>
        <Button kind="secondary" label={t.think} onPress={() => void Share.share({ message: t.thinkPrompt(session.status === 'signed-in' ? session.server : '') })} />
        <Body small muted>
          {t.thinkNote}
        </Body>
      </View>
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
      <Body>{t.chose(review.chosen, review.reasons ?? '')}</Body>
      <Body small muted>
        {t.recorded(displayDate(review.recorded_at), displayDate(review.review_on))}
      </Body>

      {comparison ? (
        <View style={{ gap: 6, marginTop: 4 }}>
          <Body small muted>
            {t.against(displayDate(comparison.at))}
          </Body>
          <View style={[styles.line, { borderBottomColor: theme.rule }]}>
            <Text style={[styles.head, styles.name, { color: theme.muted }]}>{comparison.currency}</Text>
            <Text style={[styles.head, styles.figure, { color: theme.muted }]}>{t.projected.toUpperCase()}</Text>
            <Text style={[styles.head, styles.figure, { color: theme.muted }]}>{t.actual.toUpperCase()}</Text>
          </View>
          {comparison.figures.map((row) => (
            <View key={row.figure} accessible style={[styles.line, { borderBottomColor: theme.rule }]}>
              <Body style={styles.name}>{t.figures[row.figure] ?? row.figure}</Body>
              <View style={styles.figure}>{row.projected ? <Money amount={row.projected} currency={comparison.currency} /> : null}</View>
              <View style={styles.figure}>{row.actual ? <Money amount={row.actual} currency={comparison.currency} /> : null}</View>
            </View>
          ))}
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
        <Text accessibilityRole="header" style={[styles.question, { color: theme.text }]}>
          {review.question}
        </Text>
        <View style={{ gap: 6 }}>
          <Text style={[styles.label, { color: theme.text }]}>{t.reflection}</Text>
          <TextInput
            value={reflection}
            onChangeText={setReflection}
            multiline
            autoFocus
            accessibilityLabel={t.reflection}
            accessibilityHint={t.reflectionHelp}
            style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text }]}
          />
          <Body small muted>
            {t.reflectionHelp}
          </Body>
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
  // Read-only rows: 40 px, as the design's table; the 48 px rule is for what is tapped.
  line: { flexDirection: 'row', alignItems: 'center', minHeight: 40, borderBottomWidth: StyleSheet.hairlineWidth, gap: 8 },
  head: { fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.12 },
  name: { flex: 1 },
  figure: { width: 104, alignItems: 'flex-end', textAlign: 'right' },
  label: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: 120, borderWidth: 1, borderRadius: 0, padding: 12, fontFamily: font.regular, fontSize: size.body, textAlignVertical: 'top' },
});
