import { accountsList, accountsOverview, entriesGet, entriesProvenance, entriesRecategorise, entriesReverse, formatAmount } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { AccessibilityInfo, ScrollView, StyleSheet, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, Field, LinesTable, Notice, Option, Press, Surface, Tag, Title, Waiting } from '../../kit';
import { displayDate } from '../../lib/display';
import { haptic, success, useReducedMotion } from '../../motion';
import { Page } from '../../shell';
import { Sheet, SheetTitle } from '../../sheet';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.entry;

export default function Entry() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const { id = '', booked, account, dated, why } = useLocalSearchParams<{ id: string; booked?: string; account?: string; dated?: string; why?: string }>();
  const entry = useRead('entries.get', entriesGet, { path: { entry_id: id } });
  const provenance = useRead('entries.provenance', entriesProvenance, { path: { entry_id: id } });
  const accounts = useRead('accounts.list', accountsList);
  // Just booked: the balance of the account the money moved in, read after the booking.
  const moved = accounts.data?.find((a) => a.id === account && a.type === 'asset');
  const overview = useRead('accounts.overview', accountsOverview, { path: { account_id: account ?? '' } }, { enabled: !!booked && !!moved });
  const now = moved && overview.data?.balance != null ? formatAmount(overview.data.balance, moved.currency) : undefined;
  const reverse = useMutation({
    mutationFn: (reason: string) => api.call(entriesReverse, { path: { entry_id: id }, body: { reason } }),
    onSuccess: () => {
      setAsking(false);
      haptic.warn();
      return queryClient.invalidateQueries({ queryKey: [api.server] });
    },
  });
  const data = entry.data;
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
  // The category: the line on a spending or income account, moved to another of the same type.
  const typeOf = new Map((accounts.data ?? []).map((a) => [a.id, a.type]));
  const line = data?.postings.find((p) => typeOf.get(p.account_id) === 'expense' || typeOf.get(p.account_id) === 'income');
  const categories = (accounts.data ?? []).filter((a) => line && a.is_active && a.type === typeOf.get(line.account_id));
  const [moving, setMoving] = useState(false);
  const [moveTo, setMoveTo] = useState<string | undefined>(undefined);
  const recategorise = useMutation({
    mutationFn: (to: string) => api.call(entriesRecategorise, { path: { entry_id: id }, body: { posting_id: line?.id ?? '', account_id: to, reason: t.recategoriseReason } }),
    onSuccess: async (made) => {
      setMoving(false);
      await queryClient.invalidateQueries({ queryKey: [api.server] });
      router.replace({ pathname: '/entry/[id]', params: { id: made.corrected_id, dated: made.dated, why: made.dated_reason ?? '' } });
    },
  });
  const statement = provenance.data?.statement;
  const reduced = useReducedMotion();
  // Just booked, VoiceOver moves to the confirmation as it arrives.
  const confirmation = useRef<ComponentRef<typeof View>>(null);
  useEffect(() => {
    if (booked && confirmation.current) AccessibilityInfo.sendAccessibilityEvent(confirmation.current, 'focus');
  }, [booked]);

  // The reversal as Salli will book it: each line on the other side, on its day (today if closed), with why.
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState('');

  return (
    <Page
      // Opened from a link there is nothing behind it, and just booked Books is not behind it: then back goes to Books.
      back={{ label: strings.books.back, onPress: () => (router.canGoBack() && !booked ? router.back() : router.replace('/books')) }}
      // Just booked, Done returns to where Add was opened (Home or Books).
      {...(booked
        ? {
            action: (
              <Press accessibilityRole="button" onPress={() => (router.canGoBack() ? router.back() : router.replace('/home'))} style={styles.done}>
                <Text style={[styles.doneText, { color: theme.green }]}>{t.done}</Text>
              </Press>
            ),
          }
        : {})}
    >
      {booked ? (
        <Animated.View
          ref={confirmation}
          entering={success(reduced)}
          accessible
        >
          <Notice tone="good">{moved && now ? t.bookedNow(moved.name, now) : t.booked}</Notice>
        </Animated.View>
      ) : null}
      {dated ? (
        <Notice tone="good">
          <Body small>{`${t.categoryChanged} ${dated === 'today' ? t.datedToday(why ?? '') : t.datedOriginal}`}</Body>
        </Notice>
      ) : null}
      {data ? (
        <>
          <View style={{ gap: 12 }}>
            <Title>{data.description}</Title>
            <View style={styles.chips}>
              {[
                displayDate(data.entry_date),
                data.id.slice(0, 8),
                t.sourceChip[data.source] ?? data.source,
                // The statement by its bank: never its id.
                ...(statement?.statement?.bank ? [statement.statement.bank] : []),
                ...(data.reversed_by ? [strings.entries.reversed] : []),
              ].map((fact, i) => (
                <Tag key={fact} {...(i === 1 ? { mono: true } : {})}>
                  {fact}
                </Tag>
              ))}
            </View>
          </View>

          <Card>
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

          {data.reversed_by || reverse.isSuccess ? null : (
            <View style={styles.actions}>
              {line ? (
                <View style={{ flex: 1 }}>
                  <Button
                    kind="secondary"
                    label={t.changeCategory}
                    accessibilityHint={t.changeCategoryHelp}
                    onPress={() => {
                      setMoveTo(undefined);
                      setMoving(true);
                    }}
                  />
                </View>
              ) : null}
              <View style={{ flex: 1 }}>
                <Button kind="secondary" label={line ? t.reverseShort : t.reverse} accessibilityHint={t.reverseHelp} busy={reverse.isPending} disabled={reverse.isPending} onPress={() => setAsking(true)} />
              </View>
            </View>
          )}
          {reverse.isSuccess ? (
            <Notice tone="good">{t.reversed}</Notice>
          ) : null}
          {reverse.error && !asking ? (
            <Notice tone="warn">{reverse.error.message}</Notice>
          ) : null}
        </>
      ) : (
        <Waiting query={entry} what="the entry" />
      )}
      {data && line ? (
        <Sheet visible={moving} onClose={() => setMoving(false)} label={t.changeCategory}>
          <SheetTitle style={[styles.moveTitle, { color: theme.text }]}>
            {t.moveTo(formatAmount(line.amount, line.currency))}
          </SheetTitle>
          <ScrollView accessibilityRole="radiogroup" style={{ maxHeight: 340 }}>
            {categories.map((a) => {
              const current = a.id === line.account_id;
              return (
                <Option
                  key={a.id}
                  label={a.name}
                  chosen={a.id === moveTo}
                  disabled={current}
                  {...(current ? { end: <Body small muted>{t.current}</Body> } : {})}
                  onPress={() => setMoveTo(a.id)}
                />
              );
            })}
          </ScrollView>
          <Body small muted>
            {t.moveBody}
          </Body>
          {recategorise.error ? <Notice tone="warn">{recategorise.error.message}</Notice> : null}
          <Button
            label={moveTo ? t.moveButton(names.get(moveTo) ?? '') : t.chooseCategory}
            busy={recategorise.isPending}
            disabled={!moveTo || recategorise.isPending}
            onPress={() => moveTo && recategorise.mutate(moveTo)}
          />
        </Sheet>
      ) : null}
      {data ? (
        <Sheet visible={asking} onClose={() => setAsking(false)} label={t.confirmTitle(data.description)}>
          <SheetTitle style={[styles.sheetTitle, { color: theme.text }]}>
            {t.confirmTitle(data.description)}
          </SheetTitle>
          <Body>{t.confirmBody}</Body>
          <Surface kind="inset" pad={false} style={styles.reversal}>
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
          </Surface>
          <Field value={reason} onChangeText={setReason} placeholder={t.reason} accessibilityLabel={t.reason} maxLength={200} />
          {reverse.error ? <Notice tone="warn">{reverse.error.message}</Notice> : null}
          <View style={{ gap: 4 }}>
            <Button label={t.confirm} busy={reverse.isPending} disabled={reverse.isPending || !reason.trim()} onPress={() => reverse.mutate(reason.trim())} />
            <Button kind="tertiary" label={t.keep} disabled={reverse.isPending} onPress={() => setAsking(false)} />
          </View>
        </Sheet>
      ) : null}
    </Page>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', gap: 12 },
  moveTitle: { fontFamily: font.semibold, fontSize: size.title },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  done: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 12 },
  doneText: { fontFamily: font.medium, fontSize: size.body },
  sheetTitle: { fontFamily: font.semibold, fontSize: size.title, lineHeight: size.title * 1.25 },
  reversal: { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 6, gap: 6 },
  reversalTitle: { fontFamily: font.medium, fontSize: size.body },
});
