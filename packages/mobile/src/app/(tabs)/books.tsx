import { accountsList, ledgerTrialBalance } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';
import { useRead } from '../../api';
import { AmountRow, Body, Card, CardHead, Icon, Loading } from '../../kit';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.books;
const TYPES = ['asset', 'liability', 'income', 'expense', 'equity'] as const;

export default function Books() {
  const theme = useTheme();
  const accounts = useRead('accounts.list', accountsList);
  const trial = useRead('ledger.trialBalance', ledgerTrialBalance);

  return (
    <Page
      title={t.title}
      action={
        <Pressable accessibilityRole="button" onPress={() => router.push('/add')} style={styles.add}>
          <Icon name="plus" size={20} colour={theme.text} />
          <Text style={[styles.addText, { color: theme.text }]}>{t.add}</Text>
        </Pressable>
      }
      onRefresh={() => Promise.all([accounts.refetch(), trial.refetch()])}
    >
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
        <Loading what={strings.home.loading('your accounts')} />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  add: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 8 },
  addText: { fontFamily: font.medium, fontSize: size.body },
});
