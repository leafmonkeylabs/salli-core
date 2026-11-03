import type { ModelMessage } from 'ai';
import * as Crypto from 'expo-crypto';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View, type ScrollViewInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { answers, modelFor, runTurn, type Approval } from '../ai/agent';
import { useYourAI, type Conversation } from '../ai/store';
import { Body, Button, Icon, IconTile, Notice, Press, RoundButton, Surface, radii, shape } from '../kit';
import { Markdown } from '../markdown';
import { blocksOf, changeOf, pendingOf, titleOf } from '../lib/ai';
import { strings } from '../strings';
import { elevation, font, size, useTheme } from '../theme';

const t = strings.ai;

/**
 * Your AI (designs 20 and 21): a conversation of its own page. Opened from
 * Home or Decide with a first question, or from More with one kept on this
 * phone. Changes the AI asks for wait on a card until approved or declined.
 */
export default function Agent() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const ai = useYourAI();
  const params = useLocalSearchParams<{ id?: string; ask?: string; from?: string }>();
  // The tab it was opened from: its starters, and where Back goes.
  const from = params.from && strings.ai.tabs[params.from] ? params.from : undefined;
  const kept = params.id ? ai.conversations.find((c) => c.id === params.id) : undefined;
  const [conversation, setConversation] = useState<Conversation | undefined>(kept);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState<{ reads: number; text: string } | undefined>(undefined);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const abort = useRef<AbortController | undefined>(undefined);
  const scroll = useRef<ScrollViewInstance>(null);
  const asked = useRef(false);

  const messages = conversation?.messages ?? [];
  const pending = pendingOf(messages);

  /** Runs the conversation on from `next` and keeps what it added. */
  const go = useCallback(
    async (next: ModelMessage[], title: string) => {
      const id = conversation?.id ?? Crypto.randomUUID();
      // The page now names its conversation, not its first question: opened
      // again (a restart, a reload) it shows this one rather than ask anew.
      if (!conversation) router.setParams({ id, ask: undefined });
      setBusy(true);
      setProblem(undefined);
      setLive({ reads: 0, text: '' });
      const holding: Conversation = { id, title, at: new Date().toISOString(), messages: next };
      setConversation(holding);
      abort.current = new AbortController();
      try {
        const key = await ai.key();
        const token = await ai.mcpToken();
        if (!ai.provider || !ai.model || !key || !token) throw new Error(t.notReady);
        const turn = await runTurn({
          model: modelFor(ai.provider, key, ai.model),
          mcpUrl: ai.mcpUrl,
          mcpToken: token,
          messages: next,
          signal: abort.current.signal,
          onEvent: (event) =>
            setLive((now) => (event.type === 'text' ? { reads: now?.reads ?? 0, text: (now?.text ?? '') + event.text } : { reads: (now?.reads ?? 0) + 1, text: now?.text ?? '' })),
        });
        const done: Conversation = { ...holding, at: new Date().toISOString(), messages: [...next, ...turn.messages] };
        setConversation(done);
        await ai.save(done);
      } catch (error) {
        if (!abort.current?.signal.aborted) setProblem(t.failed(error instanceof Error ? error.message : String(error)));
        await ai.save(holding);
      } finally {
        setBusy(false);
        setLive(undefined);
      }
    },
    [ai, conversation],
  );

  const send = (text: string) => {
    const question = text.trim();
    if (!question || busy || pending.length) return;
    setDraft('');
    void go([...messages, { role: 'user', content: question }], conversation?.title ?? titleOf(question));
  };

  const answer = (approved: boolean) => {
    if (!conversation) return;
    const approvals: Approval[] = pending.map((p) => ({ approvalId: p.approvalId, tool: p.tool, input: p.input }));
    void go([...messages, answers(approvals, approved)], conversation.title);
  };

  // A first question from Home or Decide is asked as the page opens.
  useEffect(() => {
    if (asked.current || !params.ask || kept || !ai.ready) return;
    asked.current = true;
    send(params.ask);
  }, [ai.ready, params.ask]);

  const back = () => (router.canGoBack() ? router.back() : router.replace(from ? `/${from}` : '/home'));
  const backLabel = from ? (strings.ai.tabs[from] ?? t.home) : params.id ? t.title : t.home;
  const starters = !messages.length && !busy && ai.ready ? (strings.ai.starters[from ?? 'home'] ?? []) : [];
  const blocks = blocksOf(messages);

  const canSend = !!draft.trim() && ai.ready && !pending.length;
  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.ground }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={[styles.header, { paddingTop: insets.top }]}>
        <View style={styles.bar}>
          <RoundButton icon="close" label={backLabel} onPress={back} />
          <View style={styles.headTitle}>
            {/* No heading beyond the one: the page is named once, for VoiceOver too. */}
            <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.headline, { color: theme.text }]}>
              {t.title}
            </Text>
            {ai.model ? (
              <Text maxFontSizeMultiplier={1.5} numberOfLines={1} style={[styles.caption, { color: theme.muted }]}>
                {ai.model}
              </Text>
            ) : null}
          </View>
          <View style={styles.bar40} />
        </View>
      </View>

      <ScrollView
        ref={scroll}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })}
        contentContainerStyle={[styles.page, starters.length ? styles.empty : null]}
      >
        {starters.length ? (
          <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
            <View accessibilityLabel={t.startWith}>
              {starters.map((starter, i) => (
                <Press highlight key={starter} accessibilityRole="button" onPress={() => send(starter)} style={[styles.starter, i < starters.length - 1 ? { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth } : null]}>
                  <Body style={{ flex: 1 }}>{starter}</Body>
                  <Icon name="chevron" size={16} colour={theme.muted} />
                </Press>
              ))}
            </View>
          </Surface>
        ) : null}
        {!ai.ready && ai.loaded ? (
          <Notice tone="neutral" action={<Button small label={t.setUp} onPress={() => router.push('/ai')} />}>
            {t.notReady}
          </Notice>
        ) : null}

        {blocks.map((block, i) =>
          block.kind === 'you' ? (
            <View key={i} style={[styles.you, youShape, { backgroundColor: theme.button }]}>
              <Body style={{ color: theme.buttonText }}>{block.text}</Body>
            </View>
          ) : (
            <Answer key={i} reads={block.reads} text={block.text} />
          ),
        )}
        {live ? <Answer reads={live.reads} text={live.text} /> : null}

        {pending.length && !busy ? (
          <Surface style={{ gap: 12 }}>
            <Text accessibilityRole="header" maxFontSizeMultiplier={1.7} style={[styles.label, { color: theme.muted }]}>
              {t.changes(pending.length)}
            </Text>
            {pending.map((p) => (
              <View key={p.approvalId} style={styles.change}>
                <IconTile name="check" tone="fill" />
                <View style={{ flex: 1 }}>
                  <Body>{changeOf(p.tool, p.input)}</Body>
                </View>
              </View>
            ))}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Button small label={t.approve} onPress={() => answer(true)} />
              </View>
              <View style={{ flex: 1 }}>
                <Button small kind="secondary" label={t.notNow} onPress={() => answer(false)} />
              </View>
            </View>
          </Surface>
        ) : null}
        {problem ? <Notice tone="warn">{problem}</Notice> : null}
      </ScrollView>

      <View style={{ paddingHorizontal: 16, paddingBottom: insets.bottom + 8, paddingTop: 8 }}>
        <View style={[styles.composer, shape(radii.pill), { backgroundColor: theme.surface }, elevation(theme, 'floating')]}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            multiline
            editable={ai.ready && !pending.length}
            placeholder={pending.length ? t.approveFirst : t.placeholder}
            placeholderTextColor={theme.muted}
            selectionColor={theme.green}
            accessibilityLabel={t.placeholder}
            style={[styles.input, { color: theme.text }]}
          />
          {busy ? (
            <Press accessibilityRole="button" accessibilityLabel={t.stop} hitSlop={6} onPress={() => abort.current?.abort()} style={[styles.send, shape(radii.pill), { backgroundColor: theme.fill }]}>
              <View style={[{ width: 12, height: 12, backgroundColor: theme.text }, shape(3)]} />
            </Press>
          ) : (
            <Press
              accessibilityRole="button"
              accessibilityLabel={t.send}
              accessibilityState={{ disabled: !canSend }}
              hitSlop={6}
              disabled={!canSend}
              onPress={() => send(draft)}
              style={[styles.send, shape(radii.pill), { backgroundColor: canSend ? theme.button : theme.fill }]}
            >
              <Icon name="up" size={20} colour={canSend ? theme.buttonText : theme.muted} />
            </Press>
          )}
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

function Answer({ reads, text }: { reads: number; text: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 10, maxWidth: '92%' }}>
      {reads ? (
        <View style={[styles.read, shape(radii.pill), { backgroundColor: theme.fill }]}>
          <Icon name="check" size={16} colour={theme.muted} />
          <Text maxFontSizeMultiplier={1.6} style={[styles.caption, { color: theme.muted, fontSize: size.label, fontFamily: font.medium }]}>
            {t.read(reads)}
          </Text>
        </View>
      ) : null}
      {text ? <Markdown text={text} /> : null}
    </View>
  );
}

/** A message from the person: the one rounded corner tucked in at its foot. */
const youShape = { borderTopLeftRadius: radii.card, borderTopRightRadius: radii.card, borderBottomLeftRadius: radii.card, borderBottomRightRadius: radii.tag, borderCurve: 'continuous' } as const;

const styles = StyleSheet.create({
  header: { paddingHorizontal: size.gutter },
  bar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: size.target },
  bar40: { width: 40 },
  headTitle: { flex: 1, alignItems: 'center', paddingHorizontal: 8 },
  headline: { fontFamily: font.semibold, fontSize: size.headline },
  caption: { fontFamily: font.regular, fontSize: size.caption },
  label: { fontFamily: font.medium, fontSize: size.label },
  page: { paddingHorizontal: size.gutter, paddingTop: size.gap, paddingBottom: size.gutter, gap: 16 },
  empty: { flexGrow: 1, justifyContent: 'flex-end' },
  starter: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  you: { alignSelf: 'flex-end', maxWidth: '82%', paddingHorizontal: 16, paddingVertical: 12 },
  change: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  read: { alignSelf: 'flex-start', minHeight: 28, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, minHeight: 56, paddingLeft: 20, paddingRight: 8, paddingVertical: 8 },
  input: { flex: 1, minHeight: 40, maxHeight: 140, paddingVertical: 8, fontFamily: font.regular, fontSize: size.body },
  send: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
});
