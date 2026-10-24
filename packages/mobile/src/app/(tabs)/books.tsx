import { accountsList, ledgerTrialBalance, statementsList } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../../api';
import { AmountRow, Body, Card, CardHead, Icon, Row, Waiting } from '../../kit';
import { displayRange } from '../../lib/display';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.books;
const TYPES = ['asset', 'liability', 'income', 'expense', 'equity'] as const;

export default function Books() {
  const theme = useTheme();
  const accounts = useRead('accounts.list', accountsList);
  const trial = useRead('ledger.trialBalance', ledgerTrialBalance);
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const waiting = (statements.data?.statements ?? []).filter((s) => s.status === 'pending');
  const names = new Map((accounts.data ?? []).map((a) => [a.id, a.name]));

  return (
    <Page title={t.title} onRefresh={() => Promise.all([accounts.refetch(), trial.refetch(), statements.refetch()])}>
      <View style={styles.actions}>
        <Pressable accessibilityRole="button" onPress={() => router.push('/add')} style={[styles.action, { backgroundColor: theme.button }]}>
          <Icon name="plus" size={18} colour={theme.buttonText} />
          <Text style={[styles.actionText, { color: theme.buttonText }]}>{t.add}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => router.push('/import')} style={[styles.action, { backgroundColor: theme.button2 }]}>
          <Icon name="upload" size={18} colour={theme.button2Text} />
          <Text style={[styles.actionText, { color: theme.button2Text }]}>{strings.imports.importFile}</Text>
        </Pressable>
      </View>

      {waiting.length ? (
        <Card style={{ paddingVertical: 12 }}>
          <CardHead label={strings.imports.queue} />
          {waiting.map((statement, i) => {
            const account = statement.account_id ? names.get(statement.account_id) : undefined;
            const title = [statement.bank, account].filter(Boolean).join(' · ') || strings.imports.statement;
            const period = statement.period_start && statement.period_end ? displayRange(statement.period_start, statement.period_end) : '';
            return (
              <Row
                key={statement.id}
                title={title}
                detail={[period, strings.imports.waiting].filter(Boolean).join(' · ')}
                onPress={() => router.push({ pathname: '/review/[id]', params: { id: statement.id } })}
                last={i === waiting.length - 1}
              />
            );
          })}
        </Card>
      ) : null}

      {accounts.data && trial.data ? (
        accounts.data.length ? (
          <>
            {TYPES.map((type) => {
              const rows = accounts.data.filter((a) => a.type === type && a.is_active);
              if (!rows.length) return null;
              return (
                <Card key={type} style={{ paddingVertical: 12 }}>
                  <CardHead label={t.types[type] ?? type} end={trial.data.currency} />
                  {rows.map((account, i) => (
                    <AmountRow
                      key={account.id}
                      title={account.name}
                      detail={account.code}
                      amount={trial.data.balances[account.id] ?? '0'}
                      currency={trial.data.currency}
                      onPress={() => router.push({ pathname: '/account/[id]', params: { id: account.id } })}
                      last={i === rows.length - 1}
                    />
                  ))}
                </Card>
              );
            })}
            <Body small muted>
              {t.balancesNote}
            </Body>
          </>
        ) : (
          <Card>
            <Body muted>{t.noAccounts}</Body>
          </Card>
        )
      ) : (
        <Waiting query={accounts.error ? accounts : trial} what="your accounts" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  actions: { flexDirection: 'row', gap: 8 },
  action: { flex: 1, minHeight: size.target, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingHorizontal: 8 },
  actionText: { fontFamily: font.medium, fontSize: size.body },
});
