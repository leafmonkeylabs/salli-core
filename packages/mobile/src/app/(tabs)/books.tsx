import {
  accountsList,
  accountsOverview,
  formatAmount,
  insightsForecast,
  insightsSpending,
  isNegativeAmount,
  negateAmount,
  reportsBalanceSheet,
  statementsList,
  statementsPending,
  type Account,
  type BalanceSheet,
  type BankStatement,
} from '@leafmonkeylabs/salli-sdk';
import { useQueries } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Card, CardHead, Icon, LedgerRow, Money, Row, Waiting, offsetOf } from '../../kit';
import { displayRange, monthNameOf, todayIso } from '../../lib/display';
import { useSession } from '../../session';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.books;

export default function Books() {
  const theme = useTheme();
  const { session } = useSession();
  const accounts = useRead('accounts.list', accountsList);
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  const forecast = useRead('insights.forecast', insightsForecast);
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const waiting = (statements.data?.statements ?? []).filter((s) => s.status === 'pending');
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;

  return (
    <Page underAI title={t.title} onRefresh={() => Promise.all([accounts.refetch(), sheet.refetch(), forecast.refetch(), statements.refetch()])}>
      <View style={styles.actions}>
        <Pressable accessibilityRole="button" accessibilityLabel={t.addLabel} onPress={() => router.push('/add')} style={[styles.action, { backgroundColor: theme.button, borderRadius: theme.control }, offsetOf(theme)]}>
          <Icon name="plus" size={18} colour={theme.buttonText} />
          <Text style={[styles.actionText, { color: theme.buttonText }]}>{t.add}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={strings.imports.importFile}
          onPress={() => router.push('/import')}
          style={[styles.action, { backgroundColor: theme.button2, borderColor: theme.button2Border, borderWidth: 1, borderRadius: theme.control }, offsetOf(theme)]}
        >
          <Icon name="upload" size={18} colour={theme.button2Text} />
          <Text style={[styles.actionText, { color: theme.button2Text }]}>{t.importShort}</Text>
        </Pressable>
      </View>

      {waiting.length ? <Queue waiting={waiting} names={new Map((accounts.data ?? []).map((a) => [a.id, a.name]))} /> : null}

      <Spending />

      <View style={[styles.places, { backgroundColor: theme.card, borderColor: theme.rule, borderRadius: theme.radius, overflow: 'hidden' }]}>
        <Pressable
          accessibilityRole="link"
          onPress={() => router.push('/entries')}
          style={[styles.place, consoleUrl ? { borderRightColor: theme.rule, borderRightWidth: StyleSheet.hairlineWidth } : null]}
        >
          <Icon name="more" size={20} colour={theme.text} />
          <Body>{t.entries}</Body>
        </Pressable>
        {consoleUrl ? (
          // Rules are made and changed in the console: the link opens its page.
          <Pressable accessibilityRole="link" accessibilityLabel={t.rulesLabel} onPress={() => void Linking.openURL(`${consoleUrl}/books/rules`)} style={styles.place}>
            <Icon name="external" size={18} colour={theme.text} />
            <Body>{t.rules}</Body>
          </Pressable>
        ) : null}
      </View>

      {accounts.data && sheet.data && forecast.data ? (
        accounts.data.length ? (
          <Accounts accounts={accounts.data} sheet={sheet.data} cash={new Set(forecast.data.accounts.map((a) => a.account_id))} />
        ) : (
          <Card>
            <Body muted>{t.noAccounts}</Body>
          </Card>
        )
      ) : (
        <Waiting query={accounts.error ? accounts : sheet.error ? sheet : forecast} what="your accounts" />
      )}
    </Page>
  );
}

/**
 * The review queue on one row: how many transactions wait, in how many files.
 * It opens the one file's review; with several, it shows them, each opening its own.
 */
function Queue({ waiting, names }: { waiting: readonly BankStatement[]; names: ReadonlyMap<string, string> }) {
  const theme = useTheme();
  const [shown, setShown] = useState(false);
  const api = useApi();
  const pending = useQueries({
    queries: waiting.map((statement) => ({
      queryKey: [api.server, 'statements.pending', { path: { statement_id: statement.id } }],
      queryFn: ({ signal }: { signal: AbortSignal }) => api.call(statementsPending, { path: { statement_id: statement.id }, signal }),
    })),
  });
  const count = pending.every((p) => p.data) ? pending.reduce((n, p) => n + (p.data?.transactions.length ?? 0), 0) : undefined;
  const [only] = waiting;
  const open = () => (only && waiting.length === 1 ? router.push({ pathname: '/review/[id]', params: { id: only.id } }) : setShown((s) => !s));
  return (
    <View style={[{ backgroundColor: theme.card, borderColor: theme.cardBorder, borderWidth: theme.cardBorderWidth < 1 ? StyleSheet.hairlineWidth : theme.cardBorderWidth, borderRadius: theme.radius }, offsetOf(theme)]}>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={count === undefined ? strings.imports.queue : t.queueSpoken(count, waiting.length)}
        {...(waiting.length > 1 ? { accessibilityState: { expanded: shown } } : {})}
        onPress={open}
        style={styles.queue}
      >
        <View style={[styles.badge, { backgroundColor: theme.text, borderRadius: Math.min(theme.control, 10) }]}>
          <Text style={[styles.badgeText, { color: theme.card }]}>{count ?? '–'}</Text>
        </View>
        <Body style={{ flex: 1 }}>{t.queue(count ?? 0, waiting.length)}</Body>
        <Icon name={waiting.length > 1 && shown ? 'down' : 'chevron'} size={16} colour={theme.muted} />
      </Pressable>
      {shown ? (
        <View style={{ paddingHorizontal: 14, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.rule }}>
          {waiting.map((statement, i) => (
            <Row
              key={statement.id}
              title={[statement.bank, statement.account_id ? names.get(statement.account_id) : undefined].filter(Boolean).join(' · ') || strings.imports.statement}
              detail={[statement.period_start && statement.period_end ? displayRange(statement.period_start, statement.period_end) : '', pending[i]?.data ? strings.imports.toReview(pending[i]?.data?.transactions.length ?? 0) : ''].filter(Boolean).join(' · ')}
              onPress={() => router.push({ pathname: '/review/[id]', params: { id: statement.id } })}
              last={i === waiting.length - 1}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}

/** Spending this month: one bar split by category, the largest four named with their amounts, the rest as Other. */
function Spending() {
  const theme = useTheme();
  const spending = useRead('insights.spending', insightsSpending, { query: { months: 1, by: 'category' } });
  const lines = spending.data?.lines ?? [];
  if (!spending.data || !lines.length) return null;
  const shown = lines.slice(0, 4);
  const rest = lines.slice(4);
  // Shades of the chart's colour, largest first; Other in the rule's.
  const shades = [1, 0.7, 0.45, 0.25];
  const share = (s: string | null | undefined): number => {
    // eslint-disable-next-line no-restricted-syntax -- not money: a share the server computed, for a bar's width
    return Math.max(0, Number(s ?? 0));
  };
  const restShare = rest.reduce((n, l) => n + share(l.share), 0);
  return (
    <Card style={{ gap: 10 }}>
      <CardHead label={t.spending(monthNameOf(todayIso()))} end={spending.data.currency} />
      <View style={[styles.stack, { borderRadius: Math.min(theme.radius, 6) }]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        {shown.map((line, i) => (
          <View key={line.key} style={{ flex: share(line.share), backgroundColor: theme.chart, opacity: shades[i] }} />
        ))}
        {restShare ? <View style={{ flex: restShare, backgroundColor: theme.rule }} /> : null}
      </View>
      {shown.map((line, i) => (
        <View key={line.key} style={styles.legend}>
          <View style={[styles.swatch, { backgroundColor: theme.chart, opacity: shades[i], borderRadius: theme.marker === 'dot' ? 5 : 0 }]} />
          <Body style={{ flex: 1 }}>{line.key}</Body>
          <Money amount={line.total} currency={spending.data.currency} />
        </View>
      ))}
      {rest.length ? (
        <View style={styles.legend}>
          <View style={[styles.swatch, { backgroundColor: theme.rule, borderRadius: theme.marker === 'dot' ? 5 : 0 }]} />
          <Body muted style={{ flex: 1 }}>
            {t.other(rest.length)}
          </Body>
        </View>
      ) : null}
    </Card>
  );
}

/**
 * What you own and owe, as the design groups it: the cash accounts (the
 * server's own list, cards among them), then investments and the rest. One
 * line an account, in its own currency; what you owe in brackets. Income,
 * spending and equity accounts are reached from Entries and the picker.
 */
function Accounts({ accounts, sheet, cash }: { accounts: readonly Account[]; sheet: BalanceSheet; cash: ReadonlySet<string> }) {
  const held = accounts.filter((a) => a.is_active && (a.type === 'asset' || a.type === 'liability'));
  const balances = new Map([...sheet.assets, ...sheet.liabilities].map((line) => [line.account_id, line.balance]));
  const groups = [
    { key: 'cash', rows: held.filter((a) => cash.has(a.id)) },
    { key: 'other', rows: held.filter((a) => !cash.has(a.id)) },
  ].filter((g) => g.rows.length);
  return (
    <Card style={{ paddingVertical: 12 }}>
      <CardHead label={t.accounts} end={sheet.currency} />
      {groups.map((group) => (
        <View key={group.key}>
          <Body small muted style={styles.group}>
            {t.roles[group.key] ?? group.key}
          </Body>
          {group.rows.map((account, i) => (
            <AccountLine key={account.id} account={account} base={sheet.currency} balance={balances.get(account.id) ?? '0'} last={i === group.rows.length - 1} />
          ))}
        </View>
      ))}
    </Card>
  );
}

function AccountLine({ account, base, balance, last }: { account: Account; base: string; balance: string; last: boolean }) {
  // An account in another currency shows its own balance, from its overview.
  const foreign = account.currency !== base;
  const overview = useRead('accounts.overview', accountsOverview, { path: { account_id: account.id } }, { enabled: foreign });
  const own = foreign ? (overview.data?.balance ?? undefined) : balance;
  const currency = foreign ? account.currency : base;
  // The balance sheet keeps what you owe positive: it reads as owed, in brackets.
  const amount = own === undefined ? undefined : account.type === 'liability' ? negateAmount(own) : own;
  // Read out as owed only when it is: a card in credit is said as what it holds.
  const label =
    amount === undefined
      ? account.name
      : isNegativeAmount(amount)
        ? t.owesLabel(account.name, formatAmount(negateAmount(amount), currency, { display: 'name' }))
        : `${account.name}, ${formatAmount(amount, currency, { display: 'name' })}`;
  return (
    <LedgerRow
      title={account.name}
      {...(amount !== undefined ? { amount } : {})}
      currency={currency}
      label={label}
      onPress={() => router.push({ pathname: '/account/[id]', params: { id: account.id } })}
      last={last}
    />
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', gap: 8 },
  action: { flex: 1, minHeight: size.target, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingHorizontal: 8 },
  actionText: { fontFamily: font.medium, fontSize: size.body },
  places: { flexDirection: 'row', borderWidth: StyleSheet.hairlineWidth },
  place: { flex: 1, minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14 },
  group: { fontFamily: font.medium, marginTop: 8 },
  queue: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 14, minHeight: 60 },
  badge: { minWidth: 32, height: 32, paddingHorizontal: 8, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontFamily: font.semibold, fontSize: size.body, fontVariant: ['tabular-nums'] },
  stack: { flexDirection: 'row', height: 14, overflow: 'hidden' },
  legend: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 32 },
  swatch: { width: 10, height: 10 },
});
