import { accountsList, accountsOverview, entriesGet, entriesProvenance, entriesRecategorise, entriesReverse, formatAmount } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState, type ComponentRef } from 'react';
import { AccessibilityInfo, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import Animated from 'react-native-reanimated';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, LinesTable, Option, Title, Waiting } from '../../kit';
import { displayDate } from '../../lib/display';
import { success, useReducedMotion } from '../../motion';
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
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
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
              <Pressable accessibilityRole="button" onPress={() => (router.canGoBack() ? router.back() : router.replace('/home'))} style={styles.done}>
                <Text style={[styles.doneText, { color: theme.text }]}>{t.done}</Text>
              </Pressable>
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
          <Card>
            <Body alert>{`✓ ${moved && now ? t.bookedNow(moved.name, now) : t.booked}`}</Body>
          </Card>
        </Animated.View>
      ) : null}
      {dated ? (
        <Card>
          <Body alert>{`✓ ${t.categoryChanged}`}</Body>
          <Body small muted>
            {dated === 'today' ? t.datedToday(why ?? '') : t.datedOriginal}
          </Body>
        </Card>
      ) : null}
      {data ? (
        <>
          <View style={{ gap: 6 }}>
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
                <Text key={fact} style={[styles.chip, i === 1 ? styles.mono : null, { color: theme.text, borderColor: theme.rule, backgroundColor: theme.card, borderRadius: Math.min(theme.control, 12), overflow: 'hidden' }]}>
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
          {recategorise.error ? <Body alert>{recategorise.error.message}</Body> : null}
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
          <TextInput
            value={reason}
            onChangeText={setReason}
            placeholder={t.reason}
            placeholderTextColor={theme.muted}
            accessibilityLabel={t.reason}
            maxLength={200}
            style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, borderRadius: Math.min(theme.control, 12) }]}
          />
          {reverse.error ? <Body alert>{reverse.error.message}</Body> : null}
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
  actions: { flexDirection: 'row', gap: 8 },
  moveTitle: { fontFamily: font.medium, fontSize: 17 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { fontFamily: font.regular, fontSize: 13, paddingHorizontal: 8, paddingVertical: 3, borderWidth: StyleSheet.hairlineWidth },
  mono: { fontFamily: font.mono },
  done: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 12 },
  doneText: { fontFamily: font.medium, fontSize: size.body },
  sheetTitle: { fontFamily: font.medium, fontSize: size.heading, lineHeight: size.heading * 1.3 },
  reversal: { borderWidth: StyleSheet.hairlineWidth, paddingHorizontal: 14, paddingTop: 12, paddingBottom: 4, gap: 6 },
  reversalTitle: { fontFamily: font.medium, fontSize: size.body },
  input: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
});
