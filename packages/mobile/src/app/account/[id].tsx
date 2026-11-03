import { accountsOverview, accountsUpdate, type UpdateAccountRequest } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { AmountRow, Body, Card, Choice, Money, Notice, Section, Title, Waiting } from '../../kit';
import { displayDate } from '../../lib/display';
import { ROLES } from '../../lib/firstrun';
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
  const api = useApi();
  const queryClient = useQueryClient();
  // What an asset account is (as First run asks): savings are kept apart from cash to spend.
  const role = useMutation({
    mutationFn: (body: UpdateAccountRequest) => api.call(accountsUpdate, { path: { account_id: id }, body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server] }),
  });

  return (
    <Page back={{ label: t.back, onPress: () => router.back() }} onRefresh={() => overview.refetch()}>
      {data ? (
        <>
          <View style={{ gap: 4 }}>
            <Title>{data.account.name}</Title>
            <Text style={{ fontFamily: font.mono, fontSize: 13, color: theme.muted }}>{data.account.code}</Text>
          </View>
          <Card style={{ gap: 6, paddingVertical: 24 }}>
            <Body small muted>
              {t.balance}
            </Body>
            <Money amount={data.balance ?? data.current_balance} currency={data.account.currency} figure="hero" />
          </Card>
          {data.account.type === 'asset' ? (
            <Card style={{ gap: 8 }}>
              <Choice
                label={strings.firstRun.kindOf(data.account.name)}
                options={ROLES.map((r) => ({ id: r, text: strings.firstRun.roles[r] ?? r }))}
                chosen={role.isPending ? (role.variables.asset_role ?? undefined) : (data.account.asset_role ?? undefined)}
                onPick={(asset_role) => role.mutate({ code: data.account.code, name: data.account.name, type: data.account.type, asset_role })}
              />
              {role.error ? <Notice tone="warn">{role.error.message}</Notice> : null}
            </Card>
          ) : null}
          <Section title={t.entries}>
          <Body small muted>{`${t.runningBalance} ${data.account.currency}`}</Body>
          <Card style={{ paddingVertical: 8 }}>
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
          </Section>
        </>
      ) : (
        <Waiting query={overview} what="the account" />
      )}
    </Page>
  );
}
