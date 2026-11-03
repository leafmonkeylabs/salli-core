import { fiAssumptions, fiAssumptionsSet, type FiAssumption } from '@leafmonkeylabs/salli-sdk';
import { useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../../api';
import { Body, Button, Field, Icon, Notice, Press, Surface, Tag, Waiting, useDoneBar } from '../../kit';
import { fractionOf, percentOf } from '../../lib/fi';
import { Page } from '../../shell';
import { Sheet, SheetTitle } from '../../sheet';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.fi;
type Key = 'real_return' | 'inflation' | 'safe_withdrawal_rate' | 'surplus_invested';
const KEYS: readonly Key[] = ['real_return', 'inflation', 'safe_withdrawal_rate', 'surplus_invested'];

/**
 * Assumptions (design 46): the four figures projections rest on, each yours
 * or a labelled placeholder; tap one to set your own, with where it comes from.
 */
export default function Assumptions() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const read = useRead('fi.assumptions', fiAssumptions);
  const [editing, setEditing] = useState<Key | undefined>(undefined);
  const applied = read.data?.applied;

  const save = async (key: Key, value: string, source: string) => {
    await api.call(fiAssumptionsSet, { body: { [key]: { value, ...(source.trim() ? { source: source.trim() } : {}) } } });
    setEditing(undefined);
    await queryClient.invalidateQueries({ queryKey: [api.server] });
  };

  return (
    <Page title={t.assumptions} back={{ label: t.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/fi')) }} onRefresh={() => read.refetch()}>
      {applied ? (
        <Surface pad={false} style={{ paddingHorizontal: size.pad }}>
          {KEYS.map((key, i) => {
            const a: FiAssumption | null | undefined = applied[key];
            const placeholder = a?.origin === 'placeholder';
            return (
              <Press
                highlight
                key={key}
                accessibilityRole="button"
                accessibilityLabel={`${t.names[key]}: ${a ? `${percentOf(a.value)}%` : t.notSet}, ${placeholder ? t.placeholder : a ? t.origins[a.origin] : ''}`}
                onPress={() => setEditing(key)}
                style={[styles.row, i < KEYS.length - 1 ? { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: theme.line } : null]}
              >
                <Body style={{ flex: 1 }}>{t.names[key] ?? key}</Body>
                {a ? (
                  <Tag tone={placeholder ? 'red' : 'neutral'}>{(placeholder ? t.placeholder : t.origins[a.origin]) ?? ''}</Tag>
                ) : null}
                <Text style={[styles.value, { color: theme.text }]}>{a ? `${percentOf(a.value)}%` : t.notSet}</Text>
                <Icon name="chevron" size={16} colour={theme.muted} />
              </Press>
            );
          })}
        </Surface>
      ) : (
        <Waiting query={read} what="the assumptions" />
      )}
      <Body small muted>
        {t.placeholderNote}
      </Body>
      <EditSheet
        key={editing ?? 'none'}
        name={editing ? (t.names[editing] ?? editing) : ''}
        current={editing && applied?.[editing] ? percentOf(applied[editing]?.value ?? '') : ''}
        visible={!!editing}
        onClose={() => setEditing(undefined)}
        onSave={(value, source) => (editing ? save(editing, value, source) : Promise.resolve())}
      />
    </Page>
  );
}

function EditSheet({ name, current, visible, onClose, onSave }: { name: string; current: string; visible: boolean; onClose: () => void; onSave: (fraction: string, source: string) => Promise<void> }) {
  const theme = useTheme();
  const [typed, setTyped] = useState(current);
  const [source, setSource] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | undefined>(undefined);
  const fraction = fractionOf(typed);
  const done = useDoneBar(true);
  return (
    <Sheet visible={visible} onClose={onClose} label={name}>
      <SheetTitle style={[styles.title, { color: theme.text }]}>
        {name}
      </SheetTitle>
      <View style={styles.percentRow}>
        <Field {...done.field('value')} value={typed} onChangeText={setTyped} keyboardType="decimal-pad" accessibilityLabel={`${name}, ${t.percent}`} autoFocus style={{ flex: 1 }} />
        <Body>%</Body>
      </View>
      <Field {...done.field('source')} value={source} onChangeText={setSource} placeholder={t.sourcePlaceholder} accessibilityLabel={t.source} />
      {problem ? <Notice tone="warn">{problem}</Notice> : null}
      <Button
        label={t.save}
        busy={busy}
        disabled={!fraction || busy}
        onPress={() => {
          if (!fraction) return;
          setBusy(true);
          setProblem(undefined);
          onSave(fraction, source)
            .catch((error: unknown) => setProblem(error instanceof Error ? error.message : String(error)))
            .finally(() => setBusy(false));
        }}
      />
      {done.bar}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  value: { fontFamily: font.medium, fontSize: size.body, fontVariant: ['tabular-nums'], minWidth: 44, textAlign: 'right' },
  title: { fontFamily: font.semibold, fontSize: size.title },
  percentRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
