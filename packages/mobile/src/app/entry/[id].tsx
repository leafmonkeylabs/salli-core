import { accountsList, accountsOverview, entriesGet, entriesProvenance, entriesReverse, formatAmount } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, CardHead, LinesTable, Title, Waiting } from '../../kit';
import { displayDate, displayRange } from '../../lib/display';
import { Page } from '../../shell';
import { Sheet } from '../../sheet';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.entry;

export default function Entry() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const { id = '', booked, account } = useLocalSearchParams<{ id: string; booked?: string; account?: string }>();
  const entry = useRead('entries.get', entriesGet, { path: { entry_id: id } });
  const provenance = useRead('entries.provenance', entriesProvenance, { path: { entry_id: id } });
  const accounts = useRead('accounts.list', accountsList);
  // Just booked: the balance of the account the money moved in, read after the booking.
  const moved = accounts.data?.find((a) => a.id === account && a.type === 'asset');
  const overview = useRead('accounts.overview', accountsOverview, { path: { account_id: account ?? '' } }, { enabled: !!booked && !!moved });
  const now = moved && overview.data?.balance != null ? formatAmount(overview.data.balance, moved.currency) : undefined;
  const reverse = useMutation({
    mutationFn: () => api.call(entriesReverse, { path: { entry_id: id } }),
    onSuccess: () => {
      setAsking(false);
      return queryClient.invalidateQueries({ queryKey: [api.server] });
    },
  });
  const data = entry.data;
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
  const statement = provenance.data?.statement;

  // The reversal as Salli will book it: each line on the other side.
  const [asking, setAsking] = useState(false);

  return (
    <Page
      // Opened from a link there is nothing behind it, and just booked Books is not behind it: then back goes to Books.
      back={{ label: strings.books.back, onPress: () => (router.canGoBack() && !booked ? router.back() : router.replace('/books')) }}
      // Just booked, Done returns to where Add was opened (Home or Books).
      {...(booked
        ? {
            action: (
              <Pressable accessibilityRole="button" onPress={() => (router.canGoBack() ? router.back() : router.replace('/home'))} style={styles.done}>
                <Text style={[styles.doneText, { color: theme.text }]}>{t.done}</Text>
              </Pressable>
            ),
          }
        : {})}
    >
      {booked ? (
        <Card>
          <Body alert>{`✓ ${moved && now ? t.bookedNow(moved.name, now) : t.booked}`}</Body>
        </Card>
      ) : null}
      {data ? (
        <>
          <View style={{ gap: 6 }}>
            <Title>{data.description}</Title>
            <View style={styles.chips}>
              {[displayDate(data.entry_date), data.id.slice(0, 8), t.sourceChip[data.source] ?? data.source].map((fact, i) => (
                <Text key={fact} style={[styles.chip, i === 1 ? styles.mono : null, { color: theme.text, borderColor: theme.rule, backgroundColor: theme.card }]}>
                  {fact}
                </Text>
              ))}
            </View>
          </View>

          <Card style={{ paddingVertical: 12 }}>
            <LinesTable
              currency={data.postings[0]?.currency ?? ''}
              lines={data.postings.map((posting) => ({
                key: posting.id,
                account: names.get(posting.account_id) ?? posting.account_id.slice(0, 8),
                side: posting.direction > 0 ? 'debit' : 'credit',
                amount: posting.amount,
                currency: posting.currency,
              }))}
            />
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
              <Button kind="secondary" label={t.reverse} busy={reverse.isPending} disabled={reverse.isPending} onPress={() => setAsking(true)} />
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
          {reverse.error && !asking ? (
            <Card>
              <Body>{reverse.error.message}</Body>
            </Card>
          ) : null}
        </>
      ) : (
        <Waiting query={entry} what="the entry" />
      )}
      {data ? (
        <Sheet visible={asking} onClose={() => setAsking(false)} label={t.confirmTitle(data.description)}>
          <Text accessibilityRole="header" style={[styles.sheetTitle, { color: theme.text }]}>
            {t.confirmTitle(data.description)}
          </Text>
          <Body>{t.confirmBody(displayDate(data.entry_date))}</Body>
          <View style={[styles.reversal, { borderColor: theme.rule, backgroundColor: theme.card, borderRadius: theme.radius }]}>
            <Text style={[styles.reversalTitle, { color: theme.text }]}>{t.reversalOf(data.description)}</Text>
            <LinesTable
              total={false}
              currency={data.postings[0]?.currency ?? ''}
              // Each line on the other side, debits first as a ledger lists them.
              lines={[...data.postings]
                .sort((a, b) => a.direction - b.direction)
                .map((posting) => ({
                  key: posting.id,
                  account: names.get(posting.account_id) ?? posting.account_id.slice(0, 8),
                  side: posting.direction > 0 ? 'credit' : 'debit',
                  amount: posting.amount,
                  currency: posting.currency,
                }))}
            />
          </View>
          {reverse.error ? <Body alert>{reverse.error.message}</Body> : null}
          <View style={{ gap: 4 }}>
            <Button label={t.confirm} busy={reverse.isPending} disabled={reverse.isPending} onPress={() => reverse.mutate()} />
            <Button kind="tertiary" label={t.keep} disabled={reverse.isPending} onPress={() => setAsking(false)} />
          </View>
        </Sheet>
      ) : null}
    </Page>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { fontFamily: font.regular, fontSize: 13, paddingHorizontal: 8, paddingVertical: 3, borderWidth: StyleSheet.hairlineWidth },
  mono: { fontFamily: font.mono },
  done: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 12 },
  doneText: { fontFamily: font.medium, fontSize: size.body },
  sheetTitle: { fontFamily: font.medium, fontSize: size.heading, lineHeight: size.heading * 1.3 },
  reversal: { borderWidth: StyleSheet.hairlineWidth, paddingHorizontal: 14, paddingTop: 12, paddingBottom: 4, gap: 6 },
  reversalTitle: { fontFamily: font.medium, fontSize: size.body },
});
