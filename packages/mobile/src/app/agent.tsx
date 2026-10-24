import type { ModelMessage } from 'ai';
import * as Crypto from 'expo-crypto';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, type ScrollViewInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { answers, modelFor, runTurn, type Approval } from '../ai/agent';
import { useYourAI, type Conversation } from '../ai/store';
import { Body, Button, Icon } from '../kit';
import { Markdown } from '../markdown';
import { blocksOf, changeOf, pendingOf, titleOf } from '../lib/ai';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

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
  const params = useLocalSearchParams<{ id?: string; ask?: string }>();
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

  const back = () => (router.canGoBack() ? router.back() : router.replace('/home'));
  const blocks = blocksOf(messages);

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: theme.chrome }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={[styles.header, { paddingTop: insets.top, borderBottomColor: theme.rule }]}>
        <Pressable accessibilityRole="button" onPress={back} style={styles.back}>
          <Icon name="back" size={24} colour={theme.text} />
          <Body>{t.home}</Body>
        </Pressable>
        {ai.model ? (
          <Body small muted style={{ marginLeft: 'auto', paddingRight: 8 }}>
            {ai.model}
          </Body>
        ) : null}
      </View>

      <ScrollView ref={scroll} onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })} contentContainerStyle={styles.page}>
        <Text accessibilityRole="header" style={[styles.title, { color: theme.text }]}>
          {t.title}
        </Text>
        {!ai.ready && ai.loaded ? (
          <View style={{ gap: 12 }}>
            <Body muted>{t.notReady}</Body>
            <Button label={t.setUp} onPress={() => router.push('/ai')} />
          </View>
        ) : null}

        {blocks.map((block, i) =>
          block.kind === 'you' ? (
            <View key={i} style={[styles.you, { backgroundColor: theme.work }]}>
              <Body>{block.text}</Body>
            </View>
          ) : (
            <Answer key={i} reads={block.reads} text={block.text} />
          ),
        )}
        {live ? <Answer reads={live.reads} text={live.text} /> : null}

        {pending.length && !busy ? (
          <View style={[styles.card, { borderColor: theme.text }]}>
            <Text style={[styles.cardHead, { color: theme.muted }]}>{t.changes(pending.length).toUpperCase()}</Text>
            <View style={{ borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.rule }}>
              {pending.map((p, i) => (
                <View key={p.approvalId} style={[styles.change, i < pending.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.rule } : null]}>
                  <Body>{changeOf(p.tool, p.input)}</Body>
                </View>
              ))}
            </View>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Button label={t.approve} onPress={() => answer(true)} />
              </View>
              <View style={{ flex: 1 }}>
                <Button kind="secondary" label={t.notNow} onPress={() => answer(false)} />
              </View>
            </View>
          </View>
        ) : null}
        {problem ? <Body alert>{problem}</Body> : null}
      </ScrollView>

      <View style={[styles.composer, { borderTopColor: theme.rule, paddingBottom: insets.bottom + 10 }]}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          multiline
          editable={ai.ready && !pending.length}
          placeholder={pending.length ? t.approveFirst : t.placeholder}
          placeholderTextColor={theme.muted}
          accessibilityLabel={t.placeholder}
          style={[styles.input, { backgroundColor: theme.work, borderColor: pending.length ? theme.rule : theme.fieldBorder, color: theme.text }]}
        />
        {busy ? (
          <Pressable accessibilityRole="button" accessibilityLabel={t.stop} onPress={() => abort.current?.abort()} style={[styles.send, { borderColor: theme.fieldBorder, borderWidth: 1 }]}>
            <View style={{ width: 12, height: 12, backgroundColor: theme.text }} />
          </Pressable>
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t.send}
            accessibilityState={{ disabled: !draft.trim() || !ai.ready || pending.length > 0 }}
            disabled={!draft.trim() || !ai.ready || pending.length > 0}
            onPress={() => send(draft)}
            style={[styles.send, { backgroundColor: draft.trim() && ai.ready && !pending.length ? theme.button : theme.chrome, borderColor: theme.fieldBorder, borderWidth: draft.trim() ? 0 : 1 }]}
          >
            <Icon name="up" size={20} colour={draft.trim() && ai.ready && !pending.length ? theme.buttonText : theme.muted} />
          </Pressable>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

function Answer({ reads, text }: { reads: number; text: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 8 }}>
      {reads ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Icon name="check" size={16} colour={theme.muted} />
          <Body small muted>
            {t.read(reads)}
          </Body>
        </View>
      ) : null}
      {text ? <Markdown text={text} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  back: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: size.target, paddingRight: 12 },
  page: { padding: size.gutter, gap: 14 },
  title: { fontFamily: font.semibold, fontSize: 28, letterSpacing: -0.7 },
  you: { alignSelf: 'flex-end', maxWidth: '82%', paddingHorizontal: 14, paddingVertical: 12 },
  card: { borderWidth: 1, padding: 14, gap: 12 },
  cardHead: { fontFamily: font.medium, fontSize: size.label, letterSpacing: size.label * 0.12 },
  change: { paddingVertical: 10 },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: size.gutter, paddingTop: 10, borderTopWidth: StyleSheet.hairlineWidth },
  input: { flex: 1, minHeight: size.target, maxHeight: 140, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, paddingVertical: 12, fontFamily: font.regular, fontSize: size.body },
  send: { width: size.target, height: size.target, alignItems: 'center', justifyContent: 'center' },
});
