import { accountsList, statementsDraft, type Account, type DraftedTransactions } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';
import { useApi, useRead, useReach } from '../api';
import { Drafted, useAutomations } from '../automations';
import { useUnread } from '../inbox';
import { Body, Button, Card, CardHead, Row, Waiting } from '../kit';
import { read, type Reading } from '../lib/automations';
import { displayMoment, todayIso } from '../lib/display';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.automations;

/**
 * Automations (docs/design/mobile.md): the rules on this phone that read a
 * bank's messages, and a message pasted to draft it now. Shortcuts hand
 * messages over the same way, in the background.
 */
export default function Automations() {
  const { rules } = useAutomations();
  const accounts = useRead('accounts.list', accountsList);
  const nameOf = (id: string) => accounts.data?.find((a) => a.id === id)?.name ?? '';

  return (
    <Page title={t.title} back={{ label: t.back, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      <Body muted>{t.intro}</Body>
      <Card style={{ paddingVertical: 4 }}>
        <View style={{ paddingTop: 8 }}>
          <CardHead label={t.rules} />
        </View>
        {rules === undefined ? null : rules.length === 0 ? (
          <Body muted style={{ paddingVertical: 12 }}>
            {t.noRules}
          </Body>
        ) : (
          rules.map((rule) => (
            <Row
              key={rule.id}
              title={rule.name}
              detail={t.ruleDetail(nameOf(rule.accountId), rule.senders.join(', '))}
              onPress={() => router.push({ pathname: '/automation/[id]', params: { id: rule.id } })}
            />
          ))
        )}
        <View style={{ paddingVertical: 12 }}>
          <Button kind="secondary" icon="plus" label={t.add} onPress={() => router.push({ pathname: '/automation/[id]', params: { id: 'new' } })} />
        </View>
      </Card>
      <Unread />
      {accounts.data ? <TryMessage accounts={accounts.data} /> : <Waiting query={accounts} what="your accounts" />}
      <Card style={{ gap: 8 }}>
        <CardHead label={t.shortcutTitle} />
        <Body small muted>
          {t.shortcutHelp}
        </Body>
      </Card>
    </Page>
  );
}

/** Messages from a watched sender that no rule reads: kept here, on the phone, until one does. */
function Unread() {
  const theme = useTheme();
  const { messages, discard, readAgain } = useUnread();
  // A rule written or changed since may read them now.
  useEffect(() => {
    void readAgain();
  }, [readAgain]);
  if (!messages.length) return null;
  return (
    <Card style={{ gap: 12 }}>
      <CardHead label={t.unreadTitle} />
      <Body small muted>
        {t.unreadHelp}
      </Body>
      {messages.map((message) => (
        <View key={message.id} style={[styles.unread, { borderTopColor: theme.rule }]}>
          <Body small muted>
            {t.unreadFrom(message.sender, displayMoment(new Date(message.at)))}
          </Body>
          <Body>{message.text}</Body>
          <View style={styles.unreadActions}>
            <Button kind="secondary" label={t.makeRule} onPress={() => router.push({ pathname: '/automation/[id]', params: { id: 'new', sample: message.text } })} />
            <Button kind="tertiary" label={t.discard} onPress={() => void discard(message.id)} />
          </View>
        </View>
      ))}
    </Card>
  );
}

/** A message pasted by hand, read by every rule, and sent for review on a tap. */
function TryMessage({ accounts }: { accounts: readonly Account[] }) {
  const theme = useTheme();
  const accountOf = (id: string) => accounts.find((a) => a.id === id);
  const api = useApi();
  const reach = useReach();
  const queryClient = useQueryClient();
  const { rules } = useAutomations();
  const [text, setText] = useState('');
  const [reading, setReading] = useState<Reading | undefined>(undefined);
  const send = useMutation({
    mutationFn: (found: Extract<Reading, { kind: 'draft' }>) =>
      api.call(statementsDraft, {
        body: { account_id: found.rule.accountId, source: t.source, transactions: [found.draft] },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [api.server] }),
  });
  const sent: DraftedTransactions | undefined = send.data;

  return (
    <Card style={{ gap: 12 }}>
      <CardHead label={t.tryTitle} />
      <View style={{ gap: 6 }}>
        <Text style={[styles.label, { color: theme.text }]}>{t.tryLabel}</Text>
        <TextInput
          value={text}
          onChangeText={(next) => {
            setText(next);
            setReading(undefined);
            send.reset();
          }}
          multiline
          accessibilityLabel={t.tryLabel}
          accessibilityHint={t.tryHelp}
          style={[styles.input, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
        />
        <Body small muted>
          {t.tryHelp}
        </Body>
      </View>
      {reading === undefined ? (
        <Button kind="secondary" label={t.read} disabled={!text.trim() || rules === undefined} onPress={() => setReading(read(rules ?? [], { text }, todayIso()))} />
      ) : reading.kind === 'draft' ? (
        <View style={{ gap: 12 }}>
          <Body small muted>
            {t.readBy(reading.rule.name)}
          </Body>
          <Drafted draft={reading.draft} account={accountOf(reading.rule.accountId)} />
          {sent ? (
            <View style={{ gap: 8 }} accessibilityLiveRegion="polite">
              <Body>{sent.drafted ? `✓ ${t.drafted(accountOf(reading.rule.accountId)?.name ?? '')}` : t.draftedBefore}</Body>
              {sent.statement_id ? <Button kind="secondary" label={t.openReview} onPress={() => router.push({ pathname: '/review/[id]', params: { id: sent.statement_id } })} /> : null}
            </View>
          ) : (
            <>
              {send.error ? <Body alert>{send.error.message}</Body> : null}
              <Button
                label={t.send}
                busy={send.isPending}
                disabled={send.isPending || reach.unreachable}
                accessibilityLabel={reach.unreachable ? strings.reach.needsServer(t.send) : t.send}
                onPress={() => send.mutate(reading)}
              />
            </>
          )}
        </View>
      ) : (
        <View style={{ gap: 8 }}>
          <Body>{t.unread}</Body>
          <Button kind="secondary" label={t.makeRule} onPress={() => router.push({ pathname: '/automation/[id]', params: { id: 'new', sample: text } })} />
        </View>
      )}
    </Card>
  );

}

const styles = StyleSheet.create({
  unread: { gap: 8, paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth },
  unreadActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  label: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: 96, borderWidth: 1, borderRadius: 0, padding: 12, fontFamily: font.regular, fontSize: size.body, textAlignVertical: 'top' },
});
