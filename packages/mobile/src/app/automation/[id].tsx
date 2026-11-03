import { accountsList } from '@leafmonkeylabs/salli-sdk';
import * as Crypto from 'expo-crypto';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../../api';
import { Drafted, useAutomations } from '../../automations';
import { Body, Button, Chip, Field as KitField, Notice, Section, Segmented, Surface, Toggle } from '../../kit';
import { readWith, type AutomationRule, type DateOrder } from '../../lib/automations';
import { todayIso } from '../../lib/display';
import { useKeepDraft } from '../../draft';
import { Picker } from '../../picker';
import { Page } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.automations;

const BLANK: Omit<AutomationRule, 'id'> = {
  name: '',
  senders: [],
  pattern: '',
  kind: 'template',
  direction: 'out',
  accountId: '',
  dateOrder: 'DMY',
  decimalMark: '.',
};

/**
 * One automation rule: who sends the messages, the pattern that reads them
 * (tried on a sample as it is written), which way the money goes and the
 * account it is on. Saved on this phone only.
 */
export default function AutomationRuleEditor() {
  const theme = useTheme();
  const { id, sample: given } = useLocalSearchParams<{ id: string; sample?: string }>();
  const { rules, save, remove } = useAutomations();
  const accounts = useRead('accounts.list', accountsList);
  const existing = rules?.find((r) => r.id === id);
  const [rule, setRule] = useState<Omit<AutomationRule, 'id'>>(BLANK);
  const [senders, setSenders] = useState('');
  const [sample, setSample] = useState(given ?? '');
  const [picking, setPicking] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [saving, setSaving] = useState(false);

  // The rule as stored, once the keychain has been read.
  useEffect(() => {
    if (!existing) return;
    setRule(existing);
    setSenders(existing.senders.join(', '));
    setAdvanced(existing.kind === 'regex' || existing.dateOrder !== 'DMY' || existing.decimalMark !== '.');
  }, [existing]);

  const set = (change: Partial<AutomationRule>) => setRule((now) => ({ ...now, ...change }));
  const account = accounts.data?.find((a) => a.id === rule.accountId);
  const reading = sample.trim() ? readWith({ ...rule, id: '' }, sample, todayIso()) : undefined;
  const missing = !rule.name.trim() ? t.needs.name : !rule.accountId ? t.needs.account : typeof reading === 'string' ? reading : undefined;
  const leave = () => (router.canGoBack() ? router.back() : router.replace('/automations'));
  const stored = existing ?? { ...BLANK, id: '' };
  const keep = useKeepDraft(rules !== undefined && (JSON.stringify({ ...rule, id: stored.id }) !== JSON.stringify(stored) || senders !== stored.senders.join(', ')));

  const onSave = async () => {
    setSaving(true);
    await save({
      ...rule,
      id: existing?.id ?? Crypto.randomUUID(),
      name: rule.name.trim(),
      senders: senders.split(',').map((s) => s.trim()).filter(Boolean),
    });
    setSaving(false);
    keep.done();
    leave();
  };

  const onRemove = () =>
    Alert.alert(t.removeTitle, t.removeBody, [
      { text: t.cancel, style: 'cancel' },
      { text: t.remove, style: 'destructive', onPress: () => {
        keep.done();
        void (existing ? remove(existing.id).then(leave) : leave());
      } },
    ]);

  return (
    <Page title={existing ? t.editTitle : t.newTitle} back={{ label: t.cancel, onPress: leave }}>
      <Surface style={{ gap: 16 }}>
        <Field label={t.name} value={rule.name} onChange={(name) => set({ name })} placeholder={t.namePlaceholder} />
        <Field label={t.senders} help={t.sendersHelp} value={senders} onChange={setSenders} placeholder="EXAMPLEBANK" mono />
        <Field label={t.sample} help={t.sampleHelp} value={sample} onChange={setSample} placeholder={t.samplePlaceholder} multiline />
        <View style={{ gap: 6 }}>
          <Field
            label={t.pattern}
            help={rule.kind === 'regex' ? t.regexHelp : t.patternHelp}
            shown={rule.kind === 'regex'}
            value={rule.pattern}
            onChange={(pattern) => set({ pattern })}
            multiline
            mono
          />
          {rule.kind === 'template' ? (
            // The parts a pattern can read, each added where the pattern ends.
            <View style={styles.tokens}>
              {TOKENS.map((token) => (
                <View key={token} accessibilityLabel={t.insert(token)}>
                  <Chip role="button" label={token} onPress={() => set({ pattern: `${rule.pattern}${rule.pattern && !rule.pattern.endsWith(' ') ? ' ' : ''}${token}` })} />
                </View>
              ))}
            </View>
          ) : null}
          {rule.kind === 'template' && sample.trim() && !rule.pattern.trim() ? (
            <Button kind="secondary" label={t.useSample} onPress={() => set({ pattern: sample.trim() })} />
          ) : null}
        </View>
      </Surface>

      <Section title={t.preview}>
        <Surface style={{ gap: 12 }}>
          {reading === undefined ? (
            <Body muted>{t.noSample}</Body>
          ) : typeof reading === 'string' ? (
            <Notice tone="warn">{reading}</Notice>
          ) : (
            <Drafted draft={reading} account={account} />
          )}
        </Surface>
      </Section>

      <Surface style={{ gap: 16 }}>
        <Choice
          label={t.fields.direction}
          options={[
            ['out', t.out],
            ['in', t.in],
          ]}
          value={rule.direction}
          onChange={(direction) => set({ direction })}
        />
        <View style={{ gap: 6 }}>
          <Text style={[styles.label, { color: theme.text }]}>{t.account}</Text>
          <Button kind="secondary" label={account?.name ?? t.chooseAccount} onPress={() => setPicking(true)} />
        </View>
      </Surface>

      <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
        <Toggle label={t.advanced} value={advanced} onChange={setAdvanced} />
        {advanced ? (
          <View style={{ gap: 16, paddingBottom: 16 }}>
            <Toggle label={t.regex} help={t.regexToggleHelp} value={rule.kind === 'regex'} onChange={(on) => set({ kind: on ? 'regex' : 'template' })} />
            <Choice
              label={t.dateOrder}
              options={(['DMY', 'MDY', 'YMD'] as const).map((o) => [o, t.orders[o]] as [DateOrder, string])}
              value={rule.dateOrder}
              onChange={(dateOrder) => set({ dateOrder })}
            />
            <Choice
              label={t.decimalMark}
              options={[
                ['.', t.marks['.']],
                [',', t.marks[',']],
              ]}
              value={rule.decimalMark}
              onChange={(decimalMark) => set({ decimalMark })}
            />
          </View>
        ) : null}
      </Surface>

      <View style={{ gap: 6 }}>
        {missing && rule.name.trim() ? (
          <Body small muted>
            {missing}
          </Body>
        ) : null}
        <Button label={t.save} busy={saving} disabled={Boolean(missing) || saving} onPress={() => void onSave()} />
        {existing ? <Button kind="tertiary" label={t.remove} onPress={onRemove} /> : null}
      </View>

      <Picker
        title={picking ? t.accountTitle : undefined}
        subtitle={t.accountSubtitle}
        accounts={accounts.data ?? []}
        chosen={rule.accountId || undefined}
        likely={['asset', 'liability']}
        others={false}
        onClose={() => setPicking(false)}
        onPick={(accountId) => {
          set({ accountId });
          setPicking(false);
        }}
      />
    </Page>
  );
}

/** A field; its help is VoiceOver's, and on screen too only where it is `shown`. */
function Field({ label, help, shown, value, onChange, placeholder, multiline, mono }: { label: string; help?: string; shown?: boolean; value: string; onChange: (text: string) => void; placeholder?: string; multiline?: boolean; mono?: boolean }) {
  return (
    <KitField
      label={label}
      value={value}
      onChangeText={onChange}
      {...(placeholder ? { placeholder } : {})}
      {...(multiline ? { multiline } : {})}
      {...(mono ? { mono } : {})}
      {...(help ? { accessibilityHint: help } : {})}
      {...(help && shown ? { help } : {})}
      autoCapitalize="none"
      autoCorrect={false}
    />
  );
}

/** Two or three choices side by side, one chosen: the kit's capsule. */
function Choice<V extends string>({ label, options, value, onChange }: { label: string; options: [V, string][]; value: V; onChange: (value: V) => void }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      <Segmented label={label} options={options.map(([id, text]) => ({ id, text }))} value={value} onChange={onChange} />
    </View>
  );
}

/** What a template pattern can mark, as the help says. */
const TOKENS = ['{amount}', '{payee}', '{date}', '{ref}', '{skip}'] as const;

const styles = StyleSheet.create({
  tokens: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  label: { fontFamily: font.medium, fontSize: size.small },
});
