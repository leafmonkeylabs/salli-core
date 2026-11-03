import { accountsList, statementsDraft, type Account, type DraftedTransactions } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useApi, useRead, useReach } from '../api';
import { Drafted, useAutomations } from '../automations';
import { useUnread } from '../inbox';
import { Body, Button, Field, Icon, Notice, Press, Row, Section, Surface, Waiting } from '../kit';
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
  const theme = useTheme();
  const { rules } = useAutomations();
  const accounts = useRead('accounts.list', accountsList);
  const nameOf = (id: string) => accounts.data?.find((a) => a.id === id)?.name ?? '';

  return (
    <Page title={t.title} back={{ label: t.back, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      <Text accessibilityLabel={t.introSpoken} style={[styles.intro, { color: theme.muted }]}>
        {t.intro}
      </Text>
      <Section title={t.rules}>
        <Surface pad={false} style={styles.list}>
          {rules === undefined ? null : rules.length === 0 ? (
            <Body muted style={{ paddingVertical: 16 }}>
              {t.noRules}
            </Body>
          ) : (
            rules.map((rule, i) => (
              <Row
                key={rule.id}
                last={i === rules.length - 1}
                title={rule.name}
                detail={t.ruleDetail(nameOf(rule.accountId), rule.senders.join(', '))}
                onPress={() => router.push({ pathname: '/automation/[id]', params: { id: rule.id } })}
              />
            ))
          )}
          <View style={{ paddingVertical: 12 }}>
            <Button kind="secondary" icon="plus" label={t.add} onPress={() => router.push({ pathname: '/automation/[id]', params: { id: 'new' } })} />
          </View>
        </Surface>
      </Section>
      <Unread />
      {accounts.data ? <TryMessage accounts={accounts.data} /> : <Waiting query={accounts} what="your accounts" />}
      <HowTo />
    </Page>
  );
}

/** How to hand messages over from Shortcuts, folded until asked for. */
function HowTo() {
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <Surface pad={false} style={[styles.list, { gap: 8 }]}>
      <Press highlight accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((o) => !o)} style={styles.howTo}>
        <Body style={{ flex: 1 }}>{t.howTo}</Body>
        <Icon name={open ? 'down' : 'chevron'} size={16} colour={theme.muted} />
      </Press>
      {open ? (
        <Body small muted style={{ paddingBottom: 16 }}>
          {t.shortcutHelp}
        </Body>
      ) : null}
    </Surface>
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
    <Section title={t.unreadTitle}>
    <Surface style={{ gap: 12 }}>
      <Body small muted>{t.unreadHelp}</Body>
      {messages.map((message, i) => (
        <View key={message.id} style={[styles.unread, i > 0 ? { borderTopColor: theme.line, borderTopWidth: StyleSheet.hairlineWidth } : null]}>
          <Body small muted>
            {t.unreadFrom(message.sender, displayMoment(new Date(message.at)))}
          </Body>
          <Body>{message.text}</Body>
          <View style={styles.unreadActions}>
            <Button small kind="secondary" label={t.makeRule} onPress={() => router.push({ pathname: '/automation/[id]', params: { id: 'new', sample: message.text } })} />
            <Button small kind="tertiary" label={t.discard} onPress={() => void discard(message.id)} />
          </View>
        </View>
      ))}
    </Surface>
    </Section>
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
    <Section title={t.tryTitle}>
    <Surface style={{ gap: 12 }}>
      <Field
        label={t.tryLabel}
        value={text}
        onChangeText={(next) => {
          setText(next);
          setReading(undefined);
          send.reset();
        }}
        multiline
        accessibilityHint={t.tryHelp}
        placeholder={t.tryPlaceholder}
      />
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
              <Notice tone="good">{sent.drafted ? t.drafted(accountOf(reading.rule.accountId)?.name ?? '') : t.draftedBefore}</Notice>
              {sent.statement_id ? <Button small kind="secondary" label={t.openReview} onPress={() => router.push({ pathname: '/review/[id]', params: { id: sent.statement_id } })} /> : null}
            </View>
          ) : (
            <>
              {send.error ? <Notice tone="warn">{send.error.message}</Notice> : null}
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
    </Surface>
    </Section>
  );
}

const styles = StyleSheet.create({
  intro: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.45 },
  list: { paddingHorizontal: size.pad },
  howTo: { flexDirection: 'row', alignItems: 'center', minHeight: 56 },
  unread: { gap: 8, paddingTop: 12 },
  unreadActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
});
