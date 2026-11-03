import { decisionsReview, decisionsReviewsDue, decisionsTemplatesList, type DueReview } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, Field, Money, Notice, ProgressBar, Row, Section, Surface, Tag, Waiting, radii, shape } from '../../kit';
import { shares } from '../../lib/chart';
import { amountParts, displayDate, displayDay } from '../../lib/display';
import { useSession } from '../../session';
import { Page } from '../../shell';
import { Sheet, SheetTitle } from '../../sheet';
import { strings } from '../../strings';
import { font, size, space, useTheme } from '../../theme';

const t = strings.decide;

export default function Decide() {
  const due = useRead('decisions.reviews.due', decisionsReviewsDue);
  // A review recorded here leaves the due list when it is read again; it stays
  // on the page, said as recorded, until the person leaves.
  const [recorded, setRecorded] = useState<readonly DueReview[]>([]);
  const shown = due.data ? [...due.data.reviews.filter((r) => !recorded.some((d) => d.id === r.id)), ...recorded] : [];
  return (
    <Page ai="decide" title={t.title} onRefresh={() => due.refetch()}>
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
          <>
            <Notice tone="neutral" icon="check">
              {t.noneDue}
            </Notice>
            <Start />
          </>
        )
      ) : (
        <Waiting query={due} what="decisions" />
      )}
    </Page>
  );
}

/**
 * Nothing due (design DecideEmpty): the server's decision templates, A to Z
 * and never ranked, each opening its page in the console, where a decision
 * is started.
 */
function Start() {
  const templates = useRead('decisions.templates', decisionsTemplatesList);
  const { session } = useSession();
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  const shown = [...(templates.data?.templates ?? [])].sort((a, b) => a.title.localeCompare(b.title));
  if (!shown.length) return null;
  return (
    <View style={{ marginTop: space.s16 }}>
    <Section title={t.start}>
    <Body small muted>{t.startHelp}</Body>
    <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
      {shown.map((template, i) => (
        <Row
          key={template.id}
          title={template.title}
          detail={template.summary}
          hint={t.inConsole}
          {...(consoleUrl ? { onPress: () => void Linking.openURL(`${consoleUrl}/decide/templates/${template.id}`) } : {})}
          last={i === shown.length - 1}
        />
      ))}
    </Surface>
    </Section>
    </View>
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
    <Card style={{ gap: 12 }}>
      <Tag tone="green">{t.due}</Tag>
      <Text accessibilityRole="header" style={[styles.question, { color: theme.text }]}>
        {review.question}
      </Text>
      <Text accessibilityLabel={`${t.chose(review.chosen, review.reasons ?? '')} ${t.recorded(displayDate(review.recorded_at), displayDate(review.review_on))}`} style={[styles.chose, { color: theme.muted }]}>
        {t.choseShort(review.chosen, displayDay(review.review_on))}
      </Text>

      {comparison ? (
        <View accessibilityLabel={t.against(displayDate(comparison.at))} style={{ gap: 2, marginTop: 4 }}>
          <View style={styles.key} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <View style={[styles.swatch, shape(radii.pill), { backgroundColor: theme.muted }]} />
            <Text style={[styles.keyText, { color: theme.muted }]}>{t.projected}</Text>
            <View style={[styles.swatch, shape(radii.pill), { backgroundColor: theme.green, marginLeft: 12 }]} />
            <Text style={[styles.keyText, { color: theme.muted }]}>{t.actual}</Text>
            <Text style={[styles.keyText, { color: theme.muted, marginLeft: 'auto' }]}>{comparison.currency}</Text>
          </View>
          {comparison.figures.map((row) => {
            const [projected, actual] = shares([row.projected ?? '0', row.actual ?? '0']);
            const name = t.figures[row.figure] ?? row.figure;
            const spoken = (a: string | null | undefined) => (a ? amountParts(a, comparison.currency).spoken : '—');
            return (
              <View key={row.figure} accessible accessibilityLabel={t.figureSpoken(name, spoken(row.projected), spoken(row.actual))} style={[styles.pair, { borderBottomColor: theme.line }]}>
                <View style={styles.pairHead}>
                  <Body style={{ flex: 1 }}>{name}</Body>
                  {row.actual ? <Money amount={row.actual} currency={comparison.currency} /> : null}
                </View>
                <ProgressBar ratio={projected ?? 0} height={6} />
                <ProgressBar ratio={actual ?? 0} height={6} />
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

      {done ? <Notice tone="good">{t.recordedReview}</Notice> : <Button label={t.write} onPress={() => setWriting(true)} />}

      {/* The review is written in a sheet, so the comparison reads first. */}
      <Sheet visible={writing} onClose={() => setWriting(false)} label={t.reflection}>
        <SheetTitle style={[styles.question, { color: theme.text }]}>
          {review.question}
        </SheetTitle>
        <Body muted>{t.chose(review.chosen, review.reasons ?? '')}</Body>
        <Field
          label={t.reflection}
          value={reflection}
          onChangeText={setReflection}
          multiline
          autoFocus
          accessibilityHint={t.reflectionHelp}
          placeholder={t.reflectionPlaceholder}
        />
        {record.error ? <Notice tone="warn">{record.error.message}</Notice> : null}
        <View style={{ gap: 4 }}>
          <Button label={t.submit} busy={record.isPending} disabled={!reflection.trim() || record.isPending} onPress={() => record.mutate()} />
          <Button kind="tertiary" label={t.cancel} disabled={record.isPending} onPress={() => setWriting(false)} />
        </View>
      </Sheet>
    </Card>
  );
}

const styles = StyleSheet.create({
  question: { fontFamily: font.medium, fontSize: size.title, lineHeight: size.title * 1.25 },
  chose: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  key: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingBottom: 6 },
  keyText: { fontFamily: font.regular, fontSize: size.caption },
  swatch: { width: 10, height: 10 },
  pair: { gap: 4, paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  pairHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
