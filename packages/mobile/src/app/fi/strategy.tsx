import { fiStrategyGenerate, fiStrategyGet } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, SectionLabel, Waiting } from '../../kit';
import { displayDay } from '../../lib/display';
import { percentOf } from '../../lib/fi';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.fi;

/**
 * Strategy (design 48): the style, its withdrawal rate and base return, and
 * the buckets by kind of investment, never named products; generating again
 * asks the server's AI, after asking you.
 */
export default function Strategy() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const strategy = useRead('fi.strategy.get', fiStrategyGet);
  const generate = useMutation({
    mutationFn: () => api.call(fiStrategyGenerate, {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server] }),
  });
  const s = strategy.data;
  const ask = () =>
    Alert.alert(t.generateTitle, t.generateBody, [
      { text: t.cancel, style: 'cancel' },
      { text: t.generate, onPress: () => generate.mutate() },
    ]);

  return (
    <Page title={t.strategy} back={{ label: t.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/fi')) }} onRefresh={() => strategy.refetch()}>
      {s ? (
        <Card style={{ gap: 8 }}>
          <View style={styles.head}>
            <SectionLabel>{t.yourStrategy}</SectionLabel>
            {s.created_at ? <Text style={[styles.note, { color: theme.muted }]}>{displayDay(s.created_at)}</Text> : null}
          </View>
          <Text style={[styles.style, { color: theme.text }]}>{s.fire_style ? (t.styles[s.fire_style] ?? s.fire_style) : t.none}</Text>
          {s.swr !== null && s.swr !== undefined && s.real_return_base !== null && s.real_return_base !== undefined ? (
            <Body small muted>
              {t.strategyLine(percentOf(String(s.swr)), percentOf(String(s.real_return_base)))}
            </Body>
          ) : null}
          {(s.buckets ?? []).map((b, i) => (
            <View key={b.key ?? i} style={[styles.bucket, { borderTopColor: theme.rule }]}>
              <View style={styles.head}>
                <Body>{b.name ?? ''}</Body>
                {b.target_pct !== null && b.target_pct !== undefined ? <Text style={[styles.pct, { color: theme.text }]}>{`${b.target_pct}%`}</Text> : null}
              </View>
              {b.description ? (
                <Body small muted>
                  {b.description}
                </Body>
              ) : null}
            </View>
          ))}
        </Card>
      ) : (
        <Waiting query={strategy} what="your strategy" />
      )}
      {generate.error ? <Body alert>{generate.error.message}</Body> : null}
      <Button kind="secondary" label={generate.isPending ? t.generating : t.generateAgain} busy={generate.isPending} disabled={generate.isPending} onPress={ask} />
      <Body small muted>
        {t.strategyNote}
      </Body>
    </Page>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  note: { fontFamily: font.regular, fontSize: 12 },
  style: { fontFamily: font.semibold, fontSize: 24 },
  bucket: { borderTopWidth: StyleSheet.hairlineWidth, paddingVertical: 10, gap: 2 },
  pct: { fontFamily: font.medium, fontSize: size.body, fontVariant: ['tabular-nums'] },
});
