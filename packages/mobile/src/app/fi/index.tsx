import { fiAssumptions, fiProjections, fiScoreGet, goalsList } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Line, Path } from 'react-native-svg';
import { useRead } from '../../api';
import { Body, Icon, Press, ProgressBar, Section, SectionLabel, Surface, Waiting } from '../../kit';
import { bandChart } from '../../lib/chart';
import { amountParts, displayMonth, todayIso, wholeDigits } from '../../lib/display';
import { percentOf, scoreShown } from '../../lib/fi';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.fi;

/**
 * Independence (design 45): when you reach financial independence, how far
 * along you are, and the path, every figure the server's; then where its
 * assumptions, goals and the surplus are.
 */
export default function Independence() {
  const theme = useTheme();
  const score = useRead('fi.score.get', fiScoreGet);
  const projections = useRead('fi.projections', fiProjections);
  const assumptions = useRead('fi.assumptions', fiAssumptions);
  const goals = useRead('goals.list', goalsList);
  const s = score.data;
  const progress = s ? Math.min(1, Math.max(0, Number(s.progress_to_fi))) : 0; // eslint-disable-line no-restricted-syntax -- not money: a fraction for a bar
  const placeholders = assumptions.data?.applied.placeholders.length ?? 0;
  const thisYear = Number(todayIso().slice(0, 4)); // eslint-disable-line no-restricted-syntax -- not money: a year

  return (
    <Page
      title={t.title}
      back={{ label: strings.more.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}
      onRefresh={() => Promise.all([score.refetch(), projections.refetch(), assumptions.refetch(), goals.refetch()])}
    >
      <Surface kind="key" style={{ gap: 6 }}>
        <SectionLabel>{t.label}</SectionLabel>
        {s && !scoreShown(s) ? (
          // As Home: under two full months of income and spending, no month, progress or score.
          <Text style={[styles.tooSoon, { color: theme.text }]}>{strings.home.fiTooSoon}</Text>
        ) : s ? (
          <>
            <Text
              accessibilityLabel={s.projected_fi_month ? t.bySpoken(displayMonth(s.projected_fi_month)) : t.notYet}
              style={[styles.when, { color: theme.text }]}
            >
              {s.projected_fi_month ? displayMonth(s.projected_fi_month) : t.notYet}
            </Text>
            <Text style={[styles.sub, { color: theme.muted }]}>
              {t.at(wholeDigits(s.fi_number, s.currency), percentOf(String(s.swr)))}
            </Text>
            {s.headline_status ? (
              <Text accessibilityLabel={`${t.headline[s.headline_status]}. ${s.headline ?? ''}`} style={[styles.sub, { color: theme.muted }]}>
                {t.headline[s.headline_status]}
                {s.headline ? ` · ${s.headline}` : ''}
              </Text>
            ) : null}
            <View style={{ gap: 8, marginTop: 8 }}>
              <ProgressBar ratio={progress} label={t.progressSpoken(percentOf(s.progress_to_fi), s.overall_score)} height={10} />
              <Text style={[styles.sub, { color: theme.muted }]}>{t.progress(percentOf(s.progress_to_fi).replace(/\..*$/, ''), s.overall_score.replace(/\..*$/, ''))}</Text>
            </View>
          </>
        ) : (
          <Waiting query={score} what="your FI score" />
        )}
      </Surface>

      {projections.data?.points?.length && projections.data.fi_number ? (
        <Section title={t.projection}>
          <Surface style={{ gap: 8 }}>
            <Text style={[styles.note, { color: theme.muted }]}>{t.todaysMoney}</Text>
            <Projection
              // The server counts years from now; the axis says them as calendar years.
              points={projections.data.points.map((p) => ({ low: p.conservative, base: p.base, high: p.growth, year: p.year === null || p.year === undefined ? null : thisYear + p.year }))}
              target={projections.data.fi_number ?? '0'}
              label={t.projectionSpoken(amountParts(projections.data.fi_number ?? '0', projections.data.currency ?? '').spoken)}
            />
          </Surface>
        </Section>
      ) : null}

      <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
        <Place title={t.assumptions} value={placeholders ? t.placeholders(placeholders) : t.allYours} onPress={() => router.push('/fi/assumptions')} />
        <Place title={t.goals} value={goals.data ? String(goals.data.goals.length) : ''} onPress={() => router.push('/fi/goals')} />
        <Place title={t.surplus} value="" onPress={() => router.push('/fi/surplus')} last />
      </Surface>
    </Page>
  );
}

function Place({ title, value, onPress, last }: { title: string; value: string; onPress: () => void; last?: boolean }) {
  const theme = useTheme();
  return (
    <Press
      highlight
      accessibilityRole="button"
      accessibilityLabel={value ? `${title}, ${value}` : title}
      onPress={onPress}
      style={[styles.place, last ? null : { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line }]}
    >
      <Body style={{ flex: 1 }}>{title}</Body>
      {value ? (
        <Body small muted>
          {value}
        </Body>
      ) : null}
      <Icon name="chevron" size={16} colour={theme.muted} />
    </Press>
  );
}

/** The base path with the range from the cautious to the growth scenario behind it, and the FI number dashed across. */
function Projection({ points, target, label }: { points: { low?: string | null; base?: string | null; high?: string | null; year?: number | null }[]; target: string; label: string }) {
  const theme = useTheme();
  const [width, setWidth] = useState(0);
  const height = 140;
  const chart = width ? bandChart(points, target, width, height) : undefined;
  const first = points[0]?.year;
  const last = points[points.length - 1]?.year;
  return (
    <View accessible accessibilityLabel={label}>
      <View onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)} style={{ height }}>
        {chart ? (
          <Svg width={width} height={height}>
            {chart.band ? <Path d={chart.band} fill={theme.green} opacity={0.12} /> : null}
            <Line x1={0} x2={width} y1={chart.target} y2={chart.target} stroke={theme.red} strokeWidth={2} strokeLinecap="round" strokeDasharray="1 7" />
            {chart.base ? <Path d={chart.base} stroke={theme.green} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" fill="none" /> : null}
          </Svg>
        ) : null}
      </View>
      <View style={styles.axis}>
        <Text style={[styles.note, { color: theme.muted }]}>{first ?? ''}</Text>
        <Text style={[styles.note, { color: theme.red }]}>{t.fiNumber}</Text>
        <Text style={[styles.note, { color: theme.muted }]}>{last ?? ''}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  when: { fontFamily: font.semibold, fontSize: size.keyFigure, letterSpacing: -1 },
  sub: { fontFamily: font.regular, fontSize: size.small },
  tooSoon: { fontFamily: font.medium, fontSize: size.body },
  note: { fontFamily: font.regular, fontSize: size.caption },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  place: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
});
