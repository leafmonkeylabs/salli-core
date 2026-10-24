import { router } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { listModels } from '../ai/agent';
import { useYourAI } from '../ai/store';
import { Body, Button, Card, CardHead, Icon } from '../kit';
import { PROVIDERS, providerOf, type Model, type ProviderId } from '../lib/ai';
import { displayMoment } from '../lib/display';
import { Page } from '../shell';
import { Sheet } from '../sheet';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.ai;

/** Your AI (design 18): one row each for the provider, its key, the model and Salli's tools; then the conversations. */
export default function YourAISettings() {
  const theme = useTheme();
  const ai = useYourAI();
  const [open, setOpen] = useState<'provider' | 'key' | 'model' | undefined>(undefined);
  const [connecting, setConnecting] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const provider = providerOf(ai.provider);

  const connect = async () => {
    setConnecting(true);
    setProblem(undefined);
    const result = await ai.connect();
    setConnecting(false);
    if (result !== 'connected' && result !== 'denied') setProblem(t.connectFailed(result));
  };

  const confirmDelete = () =>
    Alert.alert(t.deleteTitle, t.deleteBody, [
      { text: t.cancel, style: 'cancel' },
      { text: t.delete, style: 'destructive', onPress: () => void ai.deleteConversations() },
    ]);

  return (
    <Page title={t.title} back={{ label: t.back, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      <Card style={{ paddingVertical: 0 }}>
        <SettingRow label={t.provider} value={provider?.name ?? t.notSet} onPress={() => setOpen('provider')} />
        <SettingRow label={t.key} value={ai.keyEnd ? `••••${ai.keyEnd}` : t.notSet} mono={Boolean(ai.keyEnd)} disabled={!provider} onPress={() => setOpen('key')} />
        <SettingRow label={t.model} value={ai.model ?? t.notSet} disabled={!ai.keyEnd} onPress={() => setOpen('model')} />
        <View style={[styles.row, { minHeight: 56 }]}>
          <Text style={[styles.label, { color: theme.muted }]}>{t.tools}</Text>
          {ai.connectedSince ? (
            <>
              <Text accessibilityLabel={`${t.connected}, ${displayMoment(new Date(ai.connectedSince))}`} style={[styles.value, { color: theme.text }]}>
                ✓ {t.connected}
              </Text>
              <Button kind="secondary" label={t.disconnect} onPress={() => void ai.disconnect()} />
            </>
          ) : (
            <Button kind="secondary" label={t.connect} busy={connecting} disabled={connecting} onPress={() => void connect()} />
          )}
        </View>
      </Card>
      {problem ? <Body alert>{problem}</Body> : null}
      <Body small muted>
        {provider ? t.note(provider.name) : t.setUpNote}
      </Body>

      <Card style={{ paddingVertical: 4 }}>
        <View style={{ paddingTop: 8 }}>
          <CardHead label={t.conversations} />
        </View>
        {ai.conversations.length === 0 ? (
          <Body muted style={{ paddingVertical: 12 }}>
            {t.noConversations}
          </Body>
        ) : (
          ai.conversations.map((c, i) => (
            <Pressable
              key={c.id}
              accessibilityRole="link"
              onPress={() => router.push({ pathname: '/agent', params: { id: c.id } })}
              style={[styles.conversation, i < ai.conversations.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.rule } : null]}
            >
              <Text style={[styles.title, { color: theme.text }]} numberOfLines={1}>
                {c.title}
              </Text>
              <Body small muted>
                {displayMoment(new Date(c.at))}
              </Body>
            </Pressable>
          ))
        )}
      </Card>
      {ai.conversations.length ? <Button kind="tertiary" label={t.deleteAll} onPress={confirmDelete} /> : null}

      <ProviderSheet visible={open === 'provider'} chosen={ai.provider} onClose={() => setOpen(undefined)} onPick={(id) => void ai.setProvider(id).then(() => setOpen(undefined))} />
      <KeySheet visible={open === 'key'} onClose={() => setOpen(undefined)} />
      <ModelSheet visible={open === 'model'} onClose={() => setOpen(undefined)} />
    </Page>
  );
}

function SettingRow({ label, value, mono, disabled, onPress }: { label: string; value: string; mono?: boolean; disabled?: boolean; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${label}: ${value}`}
      accessibilityState={{ disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.row, { borderBottomColor: theme.rule, borderBottomWidth: StyleSheet.hairlineWidth, opacity: disabled ? 0.5 : 1 }]}
    >
      <Text style={[styles.label, { color: theme.muted }]}>{label}</Text>
      <Text style={[styles.value, { color: theme.text, fontFamily: mono ? font.mono : font.regular }]} numberOfLines={1}>
        {value}
      </Text>
      <Icon name="chevron" size={16} colour={theme.muted} />
    </Pressable>
  );
}

function Heading({ children }: { children: string }) {
  const theme = useTheme();
  return (
    <Text accessibilityRole="header" style={[styles.sheetTitle, { color: theme.text }]}>
      {children}
    </Text>
  );
}

function Choices<V extends string>({ options, chosen, onPick }: { options: readonly { id: V; name: string }[]; chosen: V | undefined; onPick: (id: V) => void }) {
  const theme = useTheme();
  return (
    <View accessibilityRole="radiogroup">
      {options.map((o) => {
        const on = o.id === chosen;
        return (
          <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ checked: on }} onPress={() => onPick(o.id)} style={[styles.option, { borderBottomColor: theme.rule }]}>
            <View style={[styles.radio, { borderColor: on ? theme.text : theme.muted }]}>{on ? <View style={[styles.dot, { backgroundColor: theme.text }]} /> : null}</View>
            <Body style={on ? { fontFamily: font.medium } : undefined}>{o.name}</Body>
          </Pressable>
        );
      })}
    </View>
  );
}

function ProviderSheet({ visible, chosen, onClose, onPick }: { visible: boolean; chosen: ProviderId | undefined; onClose: () => void; onPick: (id: ProviderId) => void }) {
  return (
    <Sheet visible={visible} onClose={onClose} label={t.provider}>
      <Heading>{t.provider}</Heading>
      <Choices options={PROVIDERS} chosen={chosen} onPick={onPick} />
    </Sheet>
  );
}

function KeySheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const theme = useTheme();
  const ai = useYourAI();
  const [key, setKey] = useState('');
  const name = providerOf(ai.provider)?.name ?? '';
  const close = () => {
    setKey('');
    onClose();
  };
  return (
    <Sheet visible={visible} onClose={close} label={t.keyTitle(name)}>
      <Heading>{t.keyTitle(name)}</Heading>
      <View style={{ gap: 6 }}>
        <TextInput
          value={key}
          onChangeText={setKey}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          autoFocus
          accessibilityLabel={t.key}
          style={[styles.input, { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text }]}
        />
        <Body small muted>
          {t.keyHelp}
        </Body>
      </View>
      <View style={{ gap: 4 }}>
        <Button label={t.save} disabled={!key.trim()} onPress={() => void ai.setKey(key).then(close)} />
        {ai.keyEnd ? <Button kind="tertiary" label={t.removeKey} onPress={() => void ai.removeKey().then(close)} /> : null}
      </View>
    </Sheet>
  );
}

function ModelSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const theme = useTheme();
  const ai = useYourAI();
  const [models, setModels] = useState<Model[] | undefined>(undefined);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const load = async () => {
    setModels(undefined);
    setProblem(undefined);
    const key = await ai.key();
    if (!ai.provider || !key) return setProblem(t.needKey);
    try {
      setModels(await listModels(ai.provider, key));
    } catch (error) {
      setProblem(error instanceof Error ? error.message : String(error));
    }
  };
  return (
    <Sheet visible={visible} onClose={onClose} label={t.model}>
      <View onLayout={() => (models === undefined && !problem ? void load() : undefined)} style={{ gap: 12 }}>
        <Heading>{t.model}</Heading>
        {problem ? (
          <Body alert>{problem}</Body>
        ) : models === undefined ? (
          <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
            <ActivityIndicator color={theme.muted} />
            <Body muted>{t.loadingModels}</Body>
          </View>
        ) : (
          <Choices options={models} chosen={ai.model} onPick={(id) => void ai.setModel(id).then(onClose)} />
        )}
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingHorizontal: 0 },
  label: { flex: 1, fontFamily: font.regular, fontSize: size.body },
  value: { fontFamily: font.regular, fontSize: size.body, flexShrink: 1 },
  title: { flex: 1, fontFamily: font.regular, fontSize: size.body },
  conversation: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, borderBottomWidth: StyleSheet.hairlineWidth },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  sheetTitle: { fontFamily: font.medium, fontSize: size.heading },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.mono, fontSize: size.body },
});
