import {
  accountsList,
  accountsOverview,
  formatAmount,
  insightsForecast,
  isNegativeAmount,
  negateAmount,
  reportsBalanceSheet,
  statementsList,
  statementsPending,
  type Account,
  type BalanceSheet,
  type BankStatement,
} from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../../api';
import { Body, Card, CardHead, Icon, LedgerRow, Row, Waiting } from '../../kit';
import { displayRange } from '../../lib/display';
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
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));
  const consoleUrl = session.status === 'signed-in' ? session.consoleUrl : null;

  return (
    <Page underAI title={t.title} onRefresh={() => Promise.all([accounts.refetch(), sheet.refetch(), forecast.refetch(), statements.refetch()])}>
      <View style={styles.actions}>
        <Pressable accessibilityRole="button" onPress={() => router.push('/add')} style={[styles.action, { backgroundColor: theme.button }]}>
          <Icon name="plus" size={18} colour={theme.buttonText} />
          <Text style={[styles.actionText, { color: theme.buttonText }]}>{t.add}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/import')}
          style={[styles.action, { backgroundColor: theme.button2, borderColor: theme.button2Border, borderWidth: 1 }]}
        >
          <Icon name="upload" size={18} colour={theme.button2Text} />
          <Text style={[styles.actionText, { color: theme.button2Text }]}>{strings.imports.importFile}</Text>
        </Pressable>
      </View>

      {waiting.length ? (
        <Card style={{ paddingVertical: 12 }}>
          <CardHead label={strings.imports.queue} />
          {waiting.map((statement, i) => (
            <QueueRow key={statement.id} statement={statement} account={statement.account_id ? names.get(statement.account_id) : undefined} last={i === waiting.length - 1} />
          ))}
        </Card>
      ) : null}

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

/** A statement in the review queue, with how many of its transactions wait. */
function QueueRow({ statement, account, last }: { statement: BankStatement; account: string | undefined; last: boolean }) {
  const pending = useRead('statements.pending', statementsPending, { path: { statement_id: statement.id } });
  const title = [statement.bank, account].filter(Boolean).join(' · ') || strings.imports.statement;
  const period = statement.period_start && statement.period_end ? displayRange(statement.period_start, statement.period_end) : '';
  const count = pending.data ? strings.imports.toReview(pending.data.transactions.length) : strings.imports.waiting;
  return (
    <Row
      title={title}
      detail={[period, count].filter(Boolean).join(' · ')}
      onPress={() => router.push({ pathname: '/review/[id]', params: { id: statement.id } })}
      last={last}
    />
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
});
