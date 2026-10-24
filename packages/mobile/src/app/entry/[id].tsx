import { accountsList, entriesGet, entriesProvenance, entriesReverse } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, CardHead, Money, Title, Waiting } from '../../kit';
import { displayDate, displayRange } from '../../lib/display';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.entry;

export default function Entry() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const { id = '', booked } = useLocalSearchParams<{ id: string; booked?: string }>();
  const entry = useRead('entries.get', entriesGet, { path: { entry_id: id } });
  const provenance = useRead('entries.provenance', entriesProvenance, { path: { entry_id: id } });
  const accounts = useRead('accounts.list', accountsList);
  const reverse = useMutation({
    mutationFn: () => api.call(entriesReverse, { path: { entry_id: id } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server] }),
  });
  const data = entry.data;
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
  const statement = provenance.data?.statement;

  const confirm = () => {
    if (!data) return;
    Alert.alert(t.confirmTitle(data.description), t.confirmBody, [
      { text: t.keep, style: 'cancel' },
      { text: t.confirm, style: 'destructive', onPress: () => reverse.mutate() },
    ]);
  };

  return (
    <Page back={{ label: strings.books.back, onPress: () => router.back() }}>
      {booked ? (
        <Card>
          <Body alert>{`✓ ${t.booked}`}</Body>
        </Card>
      ) : null}
      {data ? (
        <>
          <View style={{ gap: 6 }}>
            <Title>{data.description}</Title>
            <Text style={[styles.meta, { color: theme.muted }]}>{`${displayDate(data.entry_date)} · ${data.id.slice(0, 8)}`}</Text>
          </View>

          <Card style={{ paddingVertical: 12 }}>
            <CardHead label={t.lines} end={data.postings[0]?.currency} />
            <View style={[styles.line, styles.head, { borderBottomColor: theme.rule }]}>
              <Text style={[styles.headText, styles.account, { color: theme.muted }]} />
              <Text style={[styles.headText, styles.amount, { color: theme.muted }]}>{t.debit.toUpperCase()}</Text>
              <Text style={[styles.headText, styles.amount, { color: theme.muted }]}>{t.credit.toUpperCase()}</Text>
            </View>
            {data.postings.map((posting) => {
              const debit = posting.direction > 0;
              const name = names.get(posting.account_id) ?? posting.account_id.slice(0, 8);
              return (
                <View
                  key={posting.id}
                  accessible
                  accessibilityLabel={`${name}, ${debit ? t.debit : t.credit}`}
                  style={[styles.line, { borderBottomColor: theme.rule }]}
                >
                  <Body style={styles.account}>{name}</Body>
                  <View style={styles.amount}>{debit ? <Money amount={posting.amount} currency={posting.currency} style={styles.right} /> : null}</View>
                  <View style={styles.amount}>{debit ? null : <Money amount={posting.amount} currency={posting.currency} style={styles.right} />}</View>
                </View>
              );
            })}
          </Card>

          <Card style={{ gap: 6 }}>
            <CardHead label={t.cameFrom} />
            <Body>{t.sources[data.source] ?? data.source}</Body>
            {statement ? (
              <>
                {/* The statement by its bank and period, and the line as it read: never its id. */}
                <Body small muted>
                  {t.statementOf(
                    statement.statement?.bank ?? null,
                    statement.statement?.period_start && statement.statement.period_end
                      ? displayRange(statement.statement.period_start, statement.statement.period_end)
                      : '',
                  )}
                </Body>
                {/* Its amount is left out: the statement sends it without its direction. */}
                <Body small muted>
                  {t.asTheBankWrote(`${statement.raw_description}, ${displayDate(statement.raw_date)}`)}
                </Body>
              </>
            ) : null}
            {data.reversed_by ? (
              <Body small muted>
                {t.reversedBy}
              </Body>
            ) : null}
          </Card>

          {data.reversed_by || reverse.isSuccess ? null : (
            <View style={{ gap: 6 }}>
              <Button kind="secondary" label={t.reverse} busy={reverse.isPending} disabled={reverse.isPending} onPress={confirm} />
              <Body small muted>
                {t.reverseHelp}
              </Body>
            </View>
          )}
          {reverse.isSuccess ? (
            <Card>
              <Body alert>{`✓ ${t.reversed}`}</Body>
            </Card>
          ) : null}
          {reverse.error ? (
            <Card>
              <Body>{reverse.error.message}</Body>
            </Card>
          ) : null}
        </>
      ) : (
        <Waiting query={entry} what="the entry" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  meta: { fontFamily: font.mono, fontSize: 13 },
  line: { flexDirection: 'row', alignItems: 'center', minHeight: 48, borderBottomWidth: StyleSheet.hairlineWidth, gap: 8 },
  head: { minHeight: 32 },
  headText: { fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.12, textAlign: 'right' },
  account: { flex: 1 },
  amount: { width: 88, alignItems: 'flex-end' },
  right: { textAlign: 'right' },
});
