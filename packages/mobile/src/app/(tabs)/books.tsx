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
import { Linking, StyleSheet, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Badge, Body, Button, Card, IconTile, LedgerRow, Money, Notice, Press, Icon, Row, Section, Surface, Waiting, radii, shape, useLargeText } from '../../kit';
import { displayRange, monthNameOf, todayIso } from '../../lib/display';
import { useSession } from '../../session';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, space, useTheme } from '../../theme';

const t = strings.books;

export default function Books() {
  const { session } = useSession();
  const accounts = useRead('accounts.list', accountsList);
  const sheet = useRead('reports.balanceSheet', reportsBalanceSheet);
  const forecast = useRead('insights.forecast', insightsForecast);
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const waiting = (statements.data?.statements ?? []).filter((s) => s.status === 'pending');
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;
  // At large text the actions and places go one to a row (design LargeMore).
  const large = useLargeText();

  return (
    <Page ai="books" title={t.title} onRefresh={() => Promise.all([accounts.refetch(), sheet.refetch(), forecast.refetch(), statements.refetch()])}>
      <View style={[styles.actions, large ? styles.column : null]}>
        <View style={large ? undefined : { flex: 1 }}>
          <Button label={t.add} icon="plus" accessibilityLabel={t.addLabel} onPress={() => router.push('/add')} />
        </View>
        <View style={large ? undefined : { flex: 1 }}>
          <Button kind="secondary" label={t.importShort} icon="upload" accessibilityLabel={strings.imports.importFile} onPress={() => router.push('/import')} />
        </View>
      </View>

      {waiting.length ? <Queue waiting={waiting} names={new Map((accounts.data ?? []).map((a) => [a.id, a.name]))} /> : null}

      <Spending />

      <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
        <Row icon="more" title={t.entries} onPress={() => router.push('/entries')} last={!consoleUrl} />
        {consoleUrl ? (
          // Rules are made and changed in the console: the link opens its page.
          <Row icon="external" title={t.rules} hint={t.rulesLabel} onPress={() => void Linking.openURL(`${consoleUrl}/books/rules`)} last />
        ) : null}
      </Surface>

      {accounts.data && sheet.data && forecast.data ? (
        accounts.data.length ? (
          <Accounts accounts={accounts.data} sheet={sheet.data} cash={new Set(forecast.data.accounts.map((a) => a.account_id))} />
        ) : (
          <Notice tone="neutral">{t.noAccounts}</Notice>
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
    <Surface pad={false}>
      <Press
        highlight
        accessibilityRole="button"
        accessibilityLabel={count === undefined ? strings.imports.queue : t.queueSpoken(count, waiting.length)}
        {...(waiting.length > 1 ? { accessibilityState: { expanded: shown } } : {})}
        onPress={open}
        style={styles.queue}
      >
        <IconTile name="upload" />
        <Body style={{ flex: 1 }}>{t.queue(count ?? 0, waiting.length)}</Body>
        <Badge count={count ?? 0} />
        <Icon name={waiting.length > 1 && shown ? 'down' : 'chevron'} size={16} colour={theme.muted} />
      </Press>
      {shown ? (
        <View style={{ paddingHorizontal: size.pad, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.line }}>
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
    </Surface>
  );
}

/** Spending this month: one bar split by category, the largest four named with their amounts, the rest as Other. */
function Spending() {
  const theme = useTheme();
  const large = useLargeText();
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
    <Section title={t.spending(monthNameOf(todayIso()))}>
    <Card style={{ gap: space.s12 }}>
      <Body small muted>{spending.data.currency}</Body>
      <View style={[styles.stack, shape(radii.pill)]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
        {shown.map((line, i) => (
          <View key={line.key} style={[{ flex: share(line.share), backgroundColor: theme.green, opacity: shades[i] }, shape(radii.pill)]} />
        ))}
        {restShare ? <View style={[{ flex: restShare, backgroundColor: theme.fill }, shape(radii.pill)]} /> : null}
      </View>
      {shown.map((line, i) => (
        <View key={line.key} style={[styles.legend, large ? styles.legendLarge : null]}>
          <View style={[styles.swatch, { backgroundColor: theme.green, opacity: shades[i] }, shape(radii.pill)]} />
          <Body style={large ? { flexGrow: 1, flexShrink: 0 } : { flex: 1 }}>{line.key}</Body>
          <Money amount={line.total} currency={spending.data.currency} style={large ? { flexGrow: 1, textAlign: 'right' } : undefined} />
        </View>
      ))}
      {rest.length ? (
        <View style={styles.legend}>
          <View style={[styles.swatch, shape(radii.pill), { backgroundColor: theme.fill }]} />
          <Body muted style={{ flex: 1 }}>
            {t.other(rest.length)}
          </Body>
        </View>
      ) : null}
    </Card>
    </Section>
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
    <Section title={t.accounts}>
      <Body small muted>{sheet.currency}</Body>
      {groups.map((group) => (
        <View key={group.key} style={{ gap: space.s8 }}>
          <Body small muted style={styles.group}>
            {t.roles[group.key] ?? group.key}
          </Body>
          <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
            {group.rows.map((account, i) => (
              <AccountLine key={account.id} account={account} base={sheet.currency} balance={balances.get(account.id) ?? '0'} last={i === group.rows.length - 1} />
            ))}
          </Surface>
        </View>
      ))}
    </Section>
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
  actions: { flexDirection: 'row', gap: space.s12 },
  column: { flexDirection: 'column' },
  legendLarge: { flexWrap: 'wrap' },
  group: { fontFamily: font.medium, paddingHorizontal: 4 },
  queue: { flexDirection: 'row', alignItems: 'center', gap: space.s12, paddingHorizontal: size.pad, minHeight: 68 },
  stack: { flexDirection: 'row', height: 12, gap: 2, overflow: 'hidden' },
  legend: { flexDirection: 'row', alignItems: 'center', gap: space.s12, minHeight: 36 },
  swatch: { width: 10, height: 10 },
});
