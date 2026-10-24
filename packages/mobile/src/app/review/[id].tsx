import {
  accountsList,
  formatAmount,
  negateAmount,
  rulesList,
  statementsCategorize,
  statementsDiscard,
  statementsList,
  statementsPending,
  statementsPost,
  type StatementTransaction,
} from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../../api';
import { Body, Button, Card, Icon, Money, Waiting } from '../../kit';
import { displayDate, displayDay, displayRange } from '../../lib/display';
import { Picker } from '../../picker';
import { Glow, Header } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.review;
type Txn = StatementTransaction;

/** The account the money moved in: the statement's own, or the side already chosen. */
const moneySide = (x: Txn): string | null => x.account_id ?? ((x.credit_flag ? x.debit_account_id : x.credit_account_id) || null);
/** Where the money came from (in) or went (out): what review chooses. */
const otherSide = (x: Txn): string | null => (x.credit_flag ? x.credit_account_id : x.debit_account_id) || null;
const isComplete = (x: Txn): boolean => Boolean(x.debit_account_id && x.credit_account_id);
const shown = (x: Txn): string => x.description_override || x.description;

/**
 * A statement's review queue, as the console's (`statements.pending`): each
 * transaction as Salli read it, with the account a rule or the model
 * proposed. A choice of account is kept at once; posting and leaving one out
 * ask first. Nothing is booked until it is posted, and nothing twice.
 */
export default function Review() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const api = useApi();
  const queryClient = useQueryClient();
  const { id = '', read, notes: notesParam } = useLocalSearchParams<{ id: string; read?: string; notes?: string }>();
  // What the server noted while reading the file, handed on by the import.
  const notes: string[] = (() => {
    try {
      const parsed: unknown = notesParam ? JSON.parse(notesParam) : [];
      return Array.isArray(parsed) ? parsed.filter((n): n is string => typeof n === 'string') : [];
    } catch {
      return [];
    }
  })();
  const pending = useRead('statements.pending', statementsPending, { path: { statement_id: id } });
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const accounts = useRead('accounts.list', accountsList);
  const rules = useRead('rules.list', rulesList);
  // Possible duplicates the person said to book all the same.
  const [anyway, setAnyway] = useState<ReadonlySet<string>>(new Set());
  const [picking, setPicking] = useState<Txn | undefined>(undefined);
  const [said, setSaid] = useState<string | undefined>(read ? strings.imports.read(read) : undefined);

  const refresh = () => queryClient.invalidateQueries({ queryKey: [api.server] });
  const choose = useMutation({
    mutationFn: (input: { txn: Txn; account: string }) =>
      api.call(statementsCategorize, { body: { choices: [{ transaction_id: input.txn.id, account_id: input.account }] } }),
    onSuccess: async (_, input) => {
      await refresh();
      setSaid(t.kept(shown(input.txn)));
    },
  });
  const post = useMutation({
    mutationFn: (ids: string[]) => api.call(statementsPost, { path: { statement_id: id }, body: { approved_ids: ids }, timeoutMs: 120_000 }),
    onSuccess: async (result) => {
      await refresh();
      setSaid(t.posted(result.posted));
    },
  });
  const discard = useMutation({
    mutationFn: (ids: string[] | null) => api.call(statementsDiscard, { path: { statement_id: id }, body: { ids } }),
    onSuccess: async (result) => {
      await refresh();
      setSaid(t.discarded(result.discarded));
    },
  });
  const failed = [choose, post, discard].find((m) => m.error)?.error;

  const statement = statements.data?.statements.find((s) => s.id === id);
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
  const ruleNames = new Map((rules.data ?? []).map((r) => [r.id, r.name]));
  // In the order they happened, as a statement reads.
  const transactions = [...(pending.data?.transactions ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const ready = transactions.filter((x) => isComplete(x) && moneySide(x) && (x.dedup_status !== 'fuzzy_match' || anyway.has(x.id)));
  const waiting = transactions.filter((x) => !isComplete(x)).length;
  const facts = [
    statement?.bank,
    statement?.account_id ? names.get(statement.account_id) : undefined,
    statement?.period_start && statement.period_end ? displayRange(statement.period_start, statement.period_end) : undefined,
  ].filter((f): f is string => !!f);

  const askPost = () =>
    Alert.alert(t.postTitle(ready.length), t.postBody(ready.length), [
      { text: t.cancel, style: 'cancel' },
      { text: t.postConfirm(ready.length), onPress: () => post.mutate(ready.map((x) => x.id)) },
    ]);
  const askDiscardAll = () =>
    Alert.alert(t.discardAllTitle, t.discardAllBody, [
      { text: t.keep, style: 'cancel' },
      { text: t.discardConfirm, style: 'destructive', onPress: () => discard.mutate(null) },
    ]);
  const askLeaveOut = (txn: Txn) =>
    Alert.alert(t.leaveOutTitle, t.leaveOutBody, [
      { text: t.cancel, style: 'cancel' },
      { text: t.leaveOutConfirm, style: 'destructive', onPress: () => discard.mutate([txn.id]) },
    ]);

  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Glow />
      <Header
        back={{ label: t.back, onPress: () => router.back() }}
        action={
          transactions.length ? (
            <Pressable accessibilityRole="button" onPress={askDiscardAll} style={styles.action}>
              <Body>{t.discardAll}</Body>
            </Pressable>
          ) : undefined
        }
      />
      <ScrollView contentContainerStyle={styles.page}>
        <View style={{ gap: 8 }}>
          <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
            {t.title}
          </Text>
          {facts.length ? (
            <View style={styles.facts}>
              {facts.map((fact) => (
                <Text key={fact} style={[styles.fact, { color: theme.text, borderColor: theme.rule, backgroundColor: theme.card, borderRadius: Math.min(theme.control, 12), overflow: 'hidden' }]}>
                  {fact}
                </Text>
              ))}
            </View>
          ) : null}
          <Body small muted>
            {t.note}
          </Body>
        </View>

        {said || notes.length ? (
          // What was done, and what the server noted while reading the file, in one box.
          <Card style={{ gap: 6 }}>
            {said ? <Body alert>{`✓ ${said}`}</Body> : null}
            {notes.map((note) => (
              <Body key={note} small={!!said} muted={!!said}>
                {note}
              </Body>
            ))}
          </Card>
        ) : null}
        {failed ? (
          <Card>
            <Body alert>{failed.message}</Body>
          </Card>
        ) : null}


        {pending.data ? (
          transactions.length ? (
            <Card style={{ paddingVertical: 4 }}>
              <Text style={[styles.currency, { color: theme.muted }]}>{transactions[0]?.currency}</Text>
              {transactions.map((txn, i) => (
                <Row
                  key={txn.id}
                  txn={txn}
                  first={i === 0}
                  accountName={(account) => names.get(account) ?? account.slice(0, 8)}
                  ruleName={txn.rule_id ? ruleNames.get(txn.rule_id) : undefined}
                  bookedAnyway={anyway.has(txn.id)}
                  busy={choose.isPending && choose.variables?.txn.id === txn.id}
                  onChoose={() => setPicking(txn)}
                  onLeaveOut={() => askLeaveOut(txn)}
                  onBookAnyway={() => setAnyway((now) => new Set(now).add(txn.id))}
                />
              ))}
            </Card>
          ) : (
            <Card style={{ gap: 12 }}>
              <Body muted>{t.nothing}</Body>
              <Button kind="secondary" label={t.back} onPress={() => router.back()} />
            </Card>
          )
        ) : (
          <Waiting query={pending} what="the import" />
        )}
      </ScrollView>

      {transactions.length ? (
        <View style={[styles.footer, { paddingBottom: insets.bottom + 10, backgroundColor: theme.chrome, borderTopColor: theme.rule }]}>
          <Text accessibilityLiveRegion="polite" style={[styles.status, { color: theme.muted }]}>
            {t.status(ready.length, waiting)}
          </Text>
          <Button label={t.post(ready.length)} busy={post.isPending} disabled={!ready.length || post.isPending} onPress={askPost} />
        </View>
      ) : null}

      <Picker
        title={picking ? t.accountFor(shown(picking)) : undefined}
        {...(picking
          ? {
              subtitle: (picking.credit_flag ? t.movedIn : t.movedOut)(
                displayDate(picking.date),
                formatAmount(picking.amount, picking.currency),
                names.get(moneySide(picking) ?? '') ?? strings.imports.statement,
              ),
            }
          : {})}
        accounts={accounts.data ?? []}
        // Money out mostly went on spending; money in mostly came from income.
        likely={picking?.credit_flag ? ['income', 'expense'] : ['expense', 'income']}
        chosen={picking ? (otherSide(picking) ?? undefined) : undefined}
        except={picking ? moneySide(picking) : null}
        onClose={() => setPicking(undefined)}
        onPick={(account) => {
          if (picking) choose.mutate({ txn: picking, account });
          setPicking(undefined);
        }}
      />
    </View>
  );
}

function Row({
  txn,
  first,
  accountName,
  ruleName,
  bookedAnyway,
  busy,
  onChoose,
  onLeaveOut,
  onBookAnyway,
}: {
  txn: Txn;
  first: boolean;
  accountName: (id: string) => string;
  ruleName: string | undefined;
  bookedAnyway: boolean;
  busy: boolean;
  onChoose: () => void;
  onLeaveOut: () => void;
  onBookAnyway: () => void;
}) {
  const theme = useTheme();
  const other = otherSide(txn);
  const duplicate = txn.dedup_status === 'fuzzy_match' && !bookedAnyway;
  // Out is money leaving the account: shown as the brand shows a negative.
  const amount = txn.credit_flag ? txn.amount : negateAmount(txn.amount);
  const how = txn.rule_id
    ? ruleName
      ? t.byRule(ruleName)
      : t.byARule
    : txn.confidence > 0 && txn.confidence < 1
      ? t.byModel(new Intl.NumberFormat('en-GB', { style: 'percent', maximumFractionDigits: 0 }).format(txn.confidence))
      : t.yours;

  return (
    <View style={[styles.row, first ? null : { borderTopColor: theme.rule, borderTopWidth: StyleSheet.hairlineWidth }]}>
      <View accessible style={styles.rowHead}>
        <Text style={[styles.day, { color: theme.muted }]}>{displayDay(txn.date)}</Text>
        <Body style={{ flex: 1 }}>{shown(txn)}</Body>
        <Money amount={amount} currency={txn.currency} />
      </View>
      <View style={styles.rowBody}>
        {txn.description_override ? (
          <Body small muted>
            {t.asTheBankWrote(txn.description)}
          </Body>
        ) : null}
        {!moneySide(txn) ? (
          <Body small muted>
            {t.noMoneySide}
          </Body>
        ) : duplicate ? (
          <>
            <Body small muted>
              {t.maybeBooked(displayDate(txn.date))}
            </Body>
            <View style={styles.buttons}>
              <Button kind="secondary" label={t.leaveOut} onPress={onLeaveOut} />
              <Button kind="tertiary" label={t.bookAnyway} onPress={onBookAnyway} />
            </View>
          </>
        ) : other ? (
          <View style={styles.chosen}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t.change(accountName(other), how)}
              disabled={busy}
              onPress={onChoose}
              style={[styles.chip, { backgroundColor: theme.work, borderColor: theme.rule }]}
            >
              <Body>{accountName(other)}</Body>
              <Icon name="down" size={14} colour={theme.muted} />
            </Pressable>
            <Body small muted>
              {how}
            </Body>
          </View>
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${t.chooseAccount}: ${shown(txn)}, ${txn.credit_flag ? t.cameFrom : t.wentTo}`}
            disabled={busy}
            onPress={onChoose}
            style={[styles.chooseButton, { borderColor: theme.chart }]}
          >
            <Text style={[styles.chooseText, { color: theme.chart }]}>{t.chooseAccount}</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: size.gutter, gap: size.gap },
  action: { minHeight: size.target, justifyContent: 'center', paddingHorizontal: 12 },
  title: { fontFamily: font.semibold, fontSize: 26, letterSpacing: -0.5 },
  facts: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  fact: { fontFamily: font.regular, fontSize: 13, paddingHorizontal: 8, paddingVertical: 3, borderWidth: StyleSheet.hairlineWidth },
  row: { paddingVertical: 12, gap: 8 },
  rowHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  day: { width: 52, fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  rowBody: { marginLeft: 60, gap: 8 },
  buttons: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chosen: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 },
  chip: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, borderWidth: StyleSheet.hairlineWidth },
  chooseButton: { alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center', paddingHorizontal: 12, borderWidth: 1 },
  chooseText: { fontFamily: font.medium, fontSize: size.small },
  currency: { alignSelf: 'flex-end', paddingTop: 10, paddingBottom: 2, fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.12 },
  footer: { borderTopWidth: StyleSheet.hairlineWidth, paddingHorizontal: size.gutter, paddingTop: 10, gap: 8 },
  status: { fontFamily: font.regular, fontSize: size.small },
});
