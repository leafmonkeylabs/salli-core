import { decisionsReview, decisionsReviewsDue, decisionsTemplatesList, type DueReview } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, Field, Icon, Notice, Press, Row, Section, SectionLabel, Surface, Tag, Waiting, radii, shape } from '../../kit';
import { amountParts, displayDate, displayDay } from '../../lib/display';
import { useSession } from '../../session';
import { Page } from '../../shell';
import { Sheet, SheetTitle } from '../../sheet';
import { strings } from '../../strings';
import { font, size, space, useTheme } from '../../theme';

const t = strings.decide;

export default function Decide() {
  const theme = useTheme();
  const due = useRead('decisions.reviews.due', decisionsReviewsDue);
  // A review recorded here leaves the due list when it is read again; it stays
  // on the page, said as recorded, until the person leaves.
  const [recorded, setRecorded] = useState<readonly DueReview[]>([]);
  const shown = due.data ? [...due.data.reviews.filter((r) => !recorded.some((d) => d.id === r.id)), ...recorded] : [];
  return (
    <Page ai="decide" title={t.title} onRefresh={() => due.refetch()}>
      {due.data ? (
        shown.length ? (
          <>
            <View style={styles.sectionRow}>
              <SectionLabel>{t.due}</SectionLabel>
              <Text style={[styles.count, { color: theme.muted }]}>{shown.length}</Text>
            </View>
            {shown.map((review) => (
              <Review
                key={review.id}
                review={review}
                done={recorded.some((d) => d.id === review.id)}
                onRecorded={() => setRecorded((r) => [...r, review])}
              />
            ))}
            <StartCard />
          </>
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

/** Start a decision (design Decide): one card; the console is where one is started. */
function StartCard() {
  const theme = useTheme();
  const { session } = useSession();
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  return (
    <Surface style={styles.startCard}>
      <Press
        accessibilityRole="link"
        accessibilityLabel={`${t.start}. ${t.startHelp} ${t.inConsole}`}
        disabled={!consoleUrl}
        onPress={() => consoleUrl && void Linking.openURL(`${consoleUrl}/decide`)}
        style={styles.startRow}
      >
        <View style={[styles.startIcon, shape(radii.field), { backgroundColor: theme.greenTint }]}>
          <Icon name="decide" size={20} colour={theme.green} />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={[styles.startTitle, { color: theme.text }]}>{t.start}</Text>
          <Text style={[styles.startHelp, { color: theme.muted }]}>{t.startHelp}</Text>
          <View style={styles.startHint}>
            <Text style={[styles.startNote, { color: theme.muted }]}>{t.inConsole.replace(/\.$/, '')}</Text>
            <Icon name="external" size={13} colour={theme.muted} />
          </View>
        </View>
      </Press>
    </Surface>
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
      <View style={{ alignSelf: 'flex-start' }}>
        <Tag>{t.dueOn(displayDay(review.review_on))}</Tag>
      </View>
      <Text accessibilityRole="header" style={[styles.question, { color: theme.text }]}>
        {review.question}
      </Text>
      <Text accessibilityLabel={`${t.chose(review.chosen, review.reasons ?? '')} ${t.recorded(displayDate(review.recorded_at), displayDate(review.review_on))}`} style={[styles.chose, { color: theme.muted }]}>
        {t.choseRecorded(review.chosen, displayDay(review.recorded_at))}
      </Text>
      {review.reasons ? (
        <View style={[styles.quote, shape(radii.field), { backgroundColor: theme.fill }]}>
          <Text style={[styles.quoteText, { color: theme.text }]}>{`“${review.reasons}”`}</Text>
        </View>
      ) : null}

      {comparison ? (
        <View accessibilityLabel={t.against(displayDate(comparison.at))} style={{ marginTop: 4 }}>
          <View style={styles.pair} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
            <Text style={[styles.hdr, { color: theme.muted, flex: 1, textAlign: 'left' }]}>{comparison.currency}</Text>
            <Text style={[styles.hdr, styles.col, { color: theme.muted }]}>{t.projected}</Text>
            <Text style={[styles.hdr, styles.col, { color: theme.muted }]}>{t.actual}</Text>
          </View>
          {comparison.figures.map((row) => {
            const name = t.figures[row.figure] ?? row.figure;
            const spoken = (a: string | null | undefined) => (a ? amountParts(a, comparison.currency).spoken : '—');
            const digits = (a: string | null | undefined) => (a ? amountParts(a, comparison.currency).digits : '—');
            const total = row.figure === 'net_worth';
            return (
              <View key={row.figure} accessible accessibilityLabel={t.figureSpoken(name, spoken(row.projected), spoken(row.actual))} style={[styles.pair, styles.line, { borderTopColor: theme.line }]}>
                <Text style={[styles.cell, { color: theme.text, flex: 1, minWidth: 0, fontSize: size.body, fontFamily: total ? font.medium : font.regular }]}>{name}</Text>
                <Text numberOfLines={1} style={[styles.cell, styles.col, { color: theme.muted }]}>{digits(row.projected)}</Text>
                <Text numberOfLines={1} style={[styles.cell, styles.col, { color: theme.text, fontFamily: total ? font.medium : font.regular }]}>{digits(row.actual)}</Text>
              </View>
            );
          })}
          <Text style={[styles.caption, { color: theme.muted }]}>{t.against(displayDate(comparison.at))}</Text>
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
  question: { fontFamily: font.semibold, fontSize: size.title, lineHeight: size.title * 1.25, letterSpacing: -0.02 * size.title },
  chose: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  sectionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 4 },
  count: { fontFamily: font.regular, fontSize: size.small, fontVariant: ['tabular-nums'] },
  quote: { paddingHorizontal: 14, paddingVertical: 12 },
  quoteText: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  pair: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  line: { borderTopWidth: StyleSheet.hairlineWidth, paddingVertical: 10 },
  hdr: { fontFamily: font.medium, fontSize: size.caption },
  col: { flexShrink: 0, minWidth: 84, textAlign: 'right' },
  cell: { fontFamily: font.regular, fontSize: size.small, fontVariant: ['tabular-nums'] },
  caption: { fontFamily: font.regular, fontSize: size.label, marginTop: 8 },
  startCard: { paddingVertical: 18 },
  startRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 14 },
  startIcon: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  startTitle: { fontFamily: font.semibold, fontSize: size.headline },
  startHelp: { fontFamily: font.regular, fontSize: size.small, lineHeight: size.small * 1.4 },
  startHint: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  startNote: { fontFamily: font.regular, fontSize: size.label },
});
