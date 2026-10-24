import { accountsList } from '@leafmonkeylabs/salli-sdk';
import * as Crypto from 'expo-crypto';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRead } from '../../api';
import { Drafted, useAutomations } from '../../automations';
import { Body, Button, Card, CardHead, Toggle } from '../../kit';
import { readWith, type AutomationRule, type DateOrder } from '../../lib/automations';
import { todayIso } from '../../lib/display';
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

  const onSave = async () => {
    setSaving(true);
    await save({
      ...rule,
      id: existing?.id ?? Crypto.randomUUID(),
      name: rule.name.trim(),
      senders: senders.split(',').map((s) => s.trim()).filter(Boolean),
    });
    setSaving(false);
    leave();
  };

  const onRemove = () =>
    Alert.alert(t.removeTitle, t.removeBody, [
      { text: t.cancel, style: 'cancel' },
      { text: t.remove, style: 'destructive', onPress: () => void (existing ? remove(existing.id).then(leave) : leave()) },
    ]);

  return (
    <Page title={existing ? t.editTitle : t.newTitle} back={{ label: t.cancel, onPress: leave }}>
      <Card style={{ gap: 14 }}>
        <Field label={t.name} value={rule.name} onChange={(name) => set({ name })} placeholder={t.namePlaceholder} />
        <Field label={t.senders} help={t.sendersHelp} value={senders} onChange={setSenders} placeholder="EXAMPLEBANK" mono />
        <Field label={t.sample} help={t.sampleHelp} value={sample} onChange={setSample} multiline />
        <View style={{ gap: 6 }}>
          <Field
            label={t.pattern}
            help={rule.kind === 'regex' ? t.regexHelp : t.patternHelp}
            value={rule.pattern}
            onChange={(pattern) => set({ pattern })}
            multiline
            mono
          />
          {rule.kind === 'template' && sample.trim() && !rule.pattern.trim() ? (
            <Button kind="secondary" label={t.useSample} onPress={() => set({ pattern: sample.trim() })} />
          ) : null}
        </View>
      </Card>

      <Card style={{ gap: 12 }}>
        <CardHead label={t.preview} />
        {reading === undefined ? (
          <Body muted>{t.noSample}</Body>
        ) : typeof reading === 'string' ? (
          <Body alert>{reading}</Body>
        ) : (
          <Drafted draft={reading} account={account} />
        )}
      </Card>

      <Card style={{ gap: 14 }}>
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
      </Card>

      <Card style={{ paddingVertical: 4 }}>
        <Toggle label={t.advanced} value={advanced} onChange={setAdvanced} />
        {advanced ? (
          <View style={{ gap: 14, paddingBottom: 12 }}>
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
      </Card>

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

function Field({ label, help, value, onChange, placeholder, multiline, mono }: { label: string; help?: string; value: string; onChange: (text: string) => void; placeholder?: string; multiline?: boolean; mono?: boolean }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={theme.muted}
        multiline={multiline}
        autoCapitalize="none"
        autoCorrect={false}
        accessibilityLabel={label}
        accessibilityHint={help}
        style={[
          styles.input,
          multiline ? styles.multiline : null,
          { backgroundColor: theme.input, borderColor: theme.fieldBorder, color: theme.text, fontFamily: mono ? font.mono : font.regular },
        ]}
      />
      {help ? (
        <Body small muted>
          {help}
        </Body>
      ) : null}
    </View>
  );
}

/** Two or three choices side by side, one chosen: square, as the kit's switches. */
function Choice<V extends string>({ label, options, value, onChange }: { label: string; options: [V, string][]; value: V; onChange: (value: V) => void }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      <View accessibilityRole="radiogroup" accessibilityLabel={label} style={[styles.choices, { borderColor: theme.fieldBorder }]}>
        {options.map(([option, text], i) => {
          const on = option === value;
          return (
            <Pressable
              key={option}
              accessibilityRole="radio"
              accessibilityState={{ checked: on }}
              onPress={() => onChange(option)}
              style={[styles.choice, { backgroundColor: on ? theme.text : theme.card, borderLeftColor: theme.fieldBorder, borderLeftWidth: i ? 1 : 0 }]}
            >
              <Text style={[styles.choiceText, { color: on ? theme.card : theme.text, fontFamily: on ? font.medium : font.regular }]}>{text}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  label: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontSize: size.body },
  multiline: { minHeight: 96, paddingVertical: 12, textAlignVertical: 'top' },
  choices: { flexDirection: 'row', borderWidth: 1 },
  choice: { flex: 1, minHeight: size.target, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8 },
  choiceText: { fontSize: size.small },
});
