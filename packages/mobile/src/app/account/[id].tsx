import { accountsOverview } from '@leafmonkeylabs/salli-sdk';
import { router, useLocalSearchParams } from 'expo-router';
import { Text, View } from 'react-native';
import { useRead } from '../../api';
import { AmountRow, Body, Card, CardHead, Loading, Money, Title } from '../../kit';
import { displayDate } from '../../lib/display';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, useTheme } from '../../theme';

const t = strings.books;
/** The newest entries shown here; the console has the whole book. */
const SHOWN = 40;

export default function Account() {
  const theme = useTheme();
  const { id = '' } = useLocalSearchParams<{ id: string }>();
  const overview = useRead('accounts.overview', accountsOverview, { path: { account_id: id } });
  const data = overview.data;
  // Newest first, as a phone reads a list; the server sends them oldest first.
  const newest = data ? [...data.transactions].reverse().slice(0, SHOWN) : [];

  return (
    <Page back={{ label: t.back, onPress: () => router.back() }} onRefresh={() => overview.refetch()}>
      {data ? (
        <>
          <View style={{ gap: 6 }}>
            <Title>{data.account.name}</Title>
            <Text style={{ fontFamily: font.mono, fontSize: 13, color: theme.muted }}>{data.account.code}</Text>
          </View>
          <Card style={{ gap: 4 }}>
            <Body small muted>
              {t.balance}
            </Body>
            <Money amount={data.balance ?? data.current_balance} currency={data.account.currency} figure="key" />
          </Card>
          <Card style={{ paddingVertical: 12 }}>
            <CardHead label={t.entries} help={t.runningBalance} end={data.account.currency} />
            {newest.length ? (
              newest.map((row, i) => (
                <AmountRow
                  key={`${row.entry_id}-${i}`}
                  title={row.description}
                  detail={displayDate(row.entry_date)}
                  amount={row.running_balance_native ?? row.running_balance}
                  currency={data.account.currency}
                  onPress={() => router.push({ pathname: '/entry/[id]', params: { id: row.entry_id } })}
                  last={i === newest.length - 1}
                />
              ))
            ) : (
              <Body muted>{t.noEntries}</Body>
            )}
          </Card>
        </>
      ) : (
        <Loading what={strings.home.loading('the account')} />
      )}
    </Page>
  );
}
