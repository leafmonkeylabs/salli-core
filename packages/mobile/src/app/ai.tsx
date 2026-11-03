import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { listModels } from '../ai/agent';
import { useYourAI } from '../ai/store';
import { Body, Button, Field, Icon, Notice, Option, Press, Section, Skeleton, Surface, Tag, Toggle, useLargeText } from '../kit';
import { PROVIDERS, providerOf, type Model, type ProviderId } from '../lib/ai';
import { displayMoment } from '../lib/display';
import { Page } from '../shell';
import { Sheet, SheetTitle } from '../sheet';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.ai;

/** Your AI (designs 18, 32 and 33): a switch to use it at all, then one row each for the provider, its key, the model and Salli's tools; then the conversations. */
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
      <Surface pad={false} style={styles.list}>
        <Toggle label={t.use} value={ai.enabled} onChange={(on) => void ai.setEnabled(on)} />
      </Surface>
      {ai.enabled ? (
        <>
          <Surface pad={false} style={styles.list}>
            <SettingRow label={t.provider} value={provider?.name ?? t.choose} unset={!provider} onPress={() => setOpen('provider')} />
            <SettingRow label={t.key} value={ai.keyEnd ? `••••${ai.keyEnd}` : t.notSet} unset={!ai.keyEnd} mono={Boolean(ai.keyEnd)} {...(!provider ? { needs: t.needProvider } : {})} onPress={() => setOpen('key')} />
            <SettingRow label={t.model} value={ai.model ?? t.notSet} unset={!ai.model} {...(!provider ? { needs: t.needProvider } : !ai.keyEnd ? { needs: t.needKeyFirst } : {})} onPress={() => setOpen('model')} />
            <View style={[styles.row, { minHeight: 56 }]}>
              <Text style={[styles.label, { color: theme.muted }]}>{t.tools}</Text>
              {ai.connectedSince ? (
                <>
                  <View accessible accessibilityLabel={`${t.connected}, ${displayMoment(new Date(ai.connectedSince))}`}>
                    <Tag tone="green">{t.connected}</Tag>
                  </View>
                  <Button small kind="secondary" label={t.disconnect} onPress={() => void ai.disconnect()} />
                </>
              ) : (
                <Button small kind="secondary" label={t.connect} busy={connecting} disabled={connecting} onPress={() => void connect()} />
              )}
            </View>
          </Surface>
          {problem ? <Notice tone="warn">{problem}</Notice> : null}
          <Body small muted>
            {provider ? t.note(provider.name) : t.setUpNote}
          </Body>

          <Section title={t.conversations}>
            <Surface pad={false} style={styles.list}>
              {ai.conversations.length === 0 ? (
                <Body muted style={{ paddingVertical: 16 }}>
                  {t.noConversations}
                </Body>
              ) : (
                ai.conversations.map((c, i) => (
                  <Press
                    highlight
                    key={c.id}
                    accessibilityRole="button"
                    onPress={() => router.push({ pathname: '/agent', params: { id: c.id } })}
                    style={[styles.conversation, i < ai.conversations.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line } : null]}
                  >
                    <Text style={[styles.title, { color: theme.text }]} numberOfLines={1}>
                      {c.title}
                    </Text>
                    <Body small muted>
                      {displayMoment(new Date(c.at))}
                    </Body>
                  </Press>
                ))
              )}
            </Surface>
          </Section>
          {ai.conversations.length ? <Button kind="tertiary" label={t.deleteAll} onPress={confirmDelete} /> : null}
        </>
      ) : (
        <Body small muted>
          {t.offNote}
        </Body>
      )}

      <ProviderSheet visible={open === 'provider'} chosen={ai.provider} onClose={() => setOpen(undefined)} onPick={(id) => void ai.setProvider(id).then(() => setOpen(undefined))} />
      <KeySheet visible={open === 'key'} onClose={() => setOpen(undefined)} />
      <ModelSheet visible={open === 'model'} onClose={() => setOpen(undefined)} />
    </Page>
  );
}

/**
 * A setting, its value at its end. One that waits on another says what it
 * needs under its name, in the muted ink, and opens nothing: never dimmed
 * (design DisabledState).
 */
function SettingRow({ label, value, mono, unset, needs, onPress }: { label: string; value: string; mono?: boolean; unset?: boolean; needs?: string; onPress: () => void }) {
  const theme = useTheme();
  // At large text the value goes under its name, so neither breaks inside a word.
  const large = useLargeText();
  const rule = { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth };
  if (needs) {
    return (
      <View accessible accessibilityLabel={`${label}: ${needs}`} accessibilityState={{ disabled: true }} style={[styles.waiting, rule]}>
        <Text style={[styles.waitingLabel, { color: theme.muted }]}>{label}</Text>
        <Body small muted>
          {needs}
        </Body>
      </View>
    );
  }
  return (
    <Press highlight accessibilityRole="button" accessibilityLabel={`${label}: ${value}`} onPress={onPress} style={[styles.row, rule, large ? styles.rowLarge : null]}>
      <Text style={[styles.label, { color: theme.text }, large ? { flexBasis: '100%' } : null]}>{label}</Text>
      <Text style={[styles.value, { color: unset ? theme.muted : theme.text, fontFamily: mono ? font.mono : font.regular }]} numberOfLines={1}>
        {value}
      </Text>
      <Icon name="chevron" size={16} colour={theme.muted} />
    </Press>
  );
}

function Heading({ children }: { children: string }) {
  const theme = useTheme();
  return (
    <SheetTitle style={[styles.sheetTitle, { color: theme.text }]}>{children}</SheetTitle>
  );
}

function Choices<V extends string>({ options, chosen, onPick }: { options: readonly { id: V; name: string }[]; chosen: V | undefined; onPick: (id: V) => void }) {
  return (
    <View accessibilityRole="radiogroup">
      {options.map((o) => {
        return <Option key={o.id} label={o.name} chosen={o.id === chosen} onPress={() => onPick(o.id)} />;
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
      <Field value={key} onChangeText={setKey} secureTextEntry autoCapitalize="none" autoCorrect={false} autoFocus mono label={t.key} help={t.keyHelp} />
      <View style={{ gap: 4 }}>
        <Button label={t.save} disabled={!key.trim()} onPress={() => void ai.setKey(key).then(close)} />
        {ai.keyEnd ? <Button kind="tertiary" label={t.removeKey} onPress={() => void ai.removeKey().then(close)} /> : null}
      </View>
    </Sheet>
  );
}

function ModelSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
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
          <Notice tone="warn">{problem}</Notice>
        ) : models === undefined ? (
          <View accessible accessibilityLabel={t.loadingModels} style={{ gap: 10 }}>
            <Skeleton height={20} />
            <Skeleton height={20} width="70%" />
          </View>
        ) : (
          <Choices options={models} chosen={ai.model} onPick={(id) => void ai.setModel(id).then(onClose)} />
        )}
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: size.pad },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  label: { flex: 1, fontFamily: font.regular, fontSize: size.body },
  rowLarge: { flexWrap: 'wrap', paddingVertical: 8, rowGap: 2 },
  waiting: { justifyContent: 'center', gap: 2, minHeight: 64, paddingVertical: 8 },
  waitingLabel: { fontFamily: font.regular, fontSize: size.body },
  value: { fontFamily: font.regular, fontSize: size.body, flexShrink: 1 },
  title: { flex: 1, fontFamily: font.regular, fontSize: size.body },
  conversation: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  sheetTitle: { fontFamily: font.semibold, fontSize: size.title },
});
