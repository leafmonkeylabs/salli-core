import { fiAssumptions, fiProjections, fiScoreGet, fiStrategyGet, goalsList } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Line, Path } from 'react-native-svg';
import { useRead } from '../../api';
import { Body, Card, Icon, SectionLabel, Waiting } from '../../kit';
import { bandChart } from '../../lib/chart';
import { amountParts, displayMonth, todayIso, wholeDigits } from '../../lib/display';
import { percentOf } from '../../lib/fi';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.fi;

/**
 * Independence (design 45): when you reach financial independence, how far
 * along you are, and the path, every figure the server's; then where its
 * assumptions, goals, strategy and the surplus are.
 */
export default function Independence() {
  const theme = useTheme();
  const score = useRead('fi.score.get', fiScoreGet);
  const projections = useRead('fi.projections', fiProjections);
  const assumptions = useRead('fi.assumptions', fiAssumptions);
  const goals = useRead('goals.list', goalsList);
  const strategy = useRead('fi.strategy.get', fiStrategyGet);
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
      <Card tile style={{ gap: 6 }}>
        <SectionLabel onTile>{t.label}</SectionLabel>
        {s ? (
          <>
            <Text
              accessibilityLabel={s.projected_fi_month ? t.bySpoken(displayMonth(s.projected_fi_month)) : t.notYet}
              style={[styles.when, { color: theme.tileText }]}
            >
              {s.projected_fi_month ? displayMonth(s.projected_fi_month) : t.notYet}
            </Text>
            <Text style={[styles.sub, { color: theme.tileMuted }]}>
              {t.at(wholeDigits(s.fi_number, s.currency), percentOf(String(s.swr)))}
            </Text>
            <View accessible accessibilityLabel={t.progressSpoken(percentOf(s.progress_to_fi), s.overall_score)} style={{ gap: 6, marginTop: 4 }}>
              <View style={[styles.track, { backgroundColor: theme.tileMuted, opacity: 0.35 }]} />
              <View style={[styles.track, styles.fill, { width: `${progress * 100}%`, backgroundColor: theme.tileText }]} />
              <Text style={[styles.sub, { color: theme.tileMuted }]}>{t.progress(percentOf(s.progress_to_fi).replace(/\..*$/, ''), s.overall_score.replace(/\..*$/, ''))}</Text>
            </View>
          </>
        ) : (
          <Waiting query={score} what="your FI score" />
        )}
      </Card>

      {projections.data?.points?.length && projections.data.fi_number ? (
        <Card style={{ gap: 8 }}>
          <View style={styles.head}>
            <SectionLabel>{t.projection}</SectionLabel>
            <Text style={[styles.note, { color: theme.muted }]}>{t.todaysMoney}</Text>
          </View>
          <Projection
            // The server counts years from now; the axis says them as calendar years.
            points={projections.data.points.map((p) => ({ low: p.conservative, base: p.base, high: p.growth, year: p.year === null || p.year === undefined ? null : thisYear + p.year }))}
            target={projections.data.fi_number ?? '0'}
            label={t.projectionSpoken(amountParts(projections.data.fi_number ?? '0', projections.data.currency ?? '').spoken)}
          />
        </Card>
      ) : null}

      <Card style={{ paddingVertical: 0 }}>
        <Place title={t.assumptions} value={placeholders ? t.placeholders(placeholders) : t.allYours} onPress={() => router.push('/fi/assumptions')} />
        <Place title={t.goals} value={goals.data ? String(goals.data.goals.length) : ''} onPress={() => router.push('/fi/goals')} />
        <Place title={t.strategy} value={strategy.data?.fire_style ? (t.styles[strategy.data.fire_style] ?? strategy.data.fire_style) : ''} onPress={() => router.push('/fi/strategy')} />
        <Place title={t.surplus} value="" onPress={() => router.push('/fi/surplus')} last />
      </Card>
    </Page>
  );
}

function Place({ title, value, onPress, last }: { title: string; value: string; onPress: () => void; last?: boolean }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={value ? `${title}, ${value}` : title}
      onPress={onPress}
      style={[styles.place, last ? null : { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.rule }]}
    >
      <Body style={{ flex: 1 }}>{title}</Body>
      {value ? (
        <Body small muted>
          {value}
        </Body>
      ) : null}
      <Icon name="chevron" size={16} colour={theme.muted} />
    </Pressable>
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
            {chart.band ? <Path d={chart.band} fill={theme.chart} opacity={0.12} /> : null}
            <Line x1={0} x2={width} y1={chart.target} y2={chart.target} stroke={theme.negative} strokeWidth={1} strokeDasharray="4 4" />
            {chart.base ? <Path d={chart.base} stroke={theme.chart} strokeWidth={1.5} fill="none" /> : null}
          </Svg>
        ) : null}
      </View>
      <View style={styles.axis}>
        <Text style={[styles.note, { color: theme.muted }]}>{first ?? ''}</Text>
        <Text style={[styles.note, { color: theme.negative }]}>{t.fiNumber}</Text>
        <Text style={[styles.note, { color: theme.muted }]}>{last ?? ''}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  when: { fontFamily: font.semibold, fontSize: 34, letterSpacing: -0.6 },
  sub: { fontFamily: font.regular, fontSize: size.small },
  track: { height: 8 },
  fill: { position: 'absolute', top: 0, left: 0 },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  note: { fontFamily: font.regular, fontSize: 12 },
  axis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  place: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, paddingHorizontal: 0 },
});
