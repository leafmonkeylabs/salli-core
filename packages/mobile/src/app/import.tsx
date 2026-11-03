import { accountsList, statementsUpload } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Icon, Notice, Press, Tag } from '../kit';
import { useKeepDraft } from '../draft';
import { Picker } from '../picker';
import { strings } from '../strings';
import { font, radii, shape, size, useTheme } from '../theme';

const t = strings.imports;
/** The most the server reads (`salli import`, the console). */
const MAX_BYTES = 10 * 1024 * 1024;

type Chosen = { uri: string; name: string; type: string; size: number | undefined };

/**
 * A statement from the phone's files, read on the server: the file goes up
 * as it is, and nothing is booked until it is reviewed and posted.
 */
export default function Import() {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const api = useApi();
  const queryClient = useQueryClient();
  const accounts = useRead('accounts.list', accountsList);
  const [file, setFile] = useState<Chosen | undefined>(undefined);
  const [account, setAccount] = useState<string | undefined>(undefined);
  const [picking, setPicking] = useState(false);
  const [tooLarge, setTooLarge] = useState(false);
  const keep = useKeepDraft(!!file);

  const choose = async () => {
    const result = await DocumentPicker.getDocumentAsync({ type: '*/*', copyToCacheDirectory: true, multiple: false });
    const asset = result.canceled ? undefined : result.assets[0];
    if (!asset) return;
    setTooLarge(asset.size !== undefined && asset.size > MAX_BYTES);
    setFile({ uri: asset.uri, name: asset.name, type: asset.mimeType ?? 'application/octet-stream', size: asset.size });
  };

  const upload = useMutation({
    mutationFn: (chosen: Chosen) => {
      // The phone's fetch reads a part through `bytes()`, which a file on the
      // phone has (expo-file-system's File): the form is built here, with the
      // file's own name.
      const file = new File(chosen.uri);
      return api.call(statementsUpload, {
        body: { file },
        bodySerializer: () => {
          const form = new FormData();
          form.append('file', file, chosen.name);
          return form;
        },
        ...(account ? { query: { account_id: account } } : {}),
        timeoutMs: 5 * 60_000,
      });
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: [api.server] });
      keep.done();
      // Straight to review, with what the server noted while reading the file.
      router.replace({
        pathname: '/review/[id]',
        params: { id: result.statement_id, read: String(result.parsed), ...(result.errors.length ? { notes: JSON.stringify(result.errors) } : {}) },
      });
    },
  });

  const name = accounts.data?.find((a) => a.id === account)?.name ?? t.noAccount;

  return (
    <View style={{ flex: 1, backgroundColor: theme.surface }} onAccessibilityEscape={() => router.back()}>
      <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? 8 : insets.top }]}>
        <Press accessibilityRole="button" onPress={() => router.back()} style={styles.headerButton}>
          <Body max={1.5}>{t.cancel}</Body>
        </Press>
        <Text accessibilityRole="header" maxFontSizeMultiplier={1.5} style={[styles.headerTitle, { color: theme.text }]}>
          {t.title}
        </Text>
        <View style={styles.headerButton} />
      </View>

      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: insets.bottom + 24 }]}>
        <Field label={t.file} {...(tooLarge ? { help: t.tooLarge } : {})}>
          {file ? (
            <View style={[styles.file, shape(radii.field), { backgroundColor: theme.fill }]}>
              <Text style={[styles.fileName, { color: theme.text }]} numberOfLines={2}>
                {file.name}
              </Text>
            </View>
          ) : null}
          <Button kind="secondary" label={file ? t.chooseAgain : t.choose} accessibilityHint={t.fileHelp} onPress={() => void choose()} />
          {file ? null : (
            <View style={styles.formats} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              {t.formats.map((f) => (
                <Tag key={f}>{f}</Tag>
              ))}
            </View>
          )}
        </Field>

        <Field label={t.account}>
          <Press
            accessibilityRole="button"
            accessibilityLabel={`${t.account}: ${name}`}
            accessibilityHint={t.accountHelp}
            onPress={() => setPicking(true)}
            style={[styles.choose, shape(radii.field), { backgroundColor: theme.fill }]}
          >
            <Body>{name}</Body>
            <Icon name="down" size={16} colour={theme.muted} />
          </Press>
        </Field>

        {upload.error ? <Notice tone="warn">{upload.error.message}</Notice> : null}
        <View style={{ gap: 6 }}>
          <Button
            label={upload.isPending ? t.submitting : t.submit}
            busy={upload.isPending}
            disabled={!file || tooLarge || upload.isPending}
            onPress={() => file && upload.mutate(file)}
          />
        </View>
      </ScrollView>

      <Picker
        title={picking ? t.pickAccount : undefined}
        accounts={accounts.data ?? []}
        chosen={account}
        likely={['asset', 'liability']}
        others={false}
        onClose={() => setPicking(false)}
        onPick={(id) => {
          setAccount(id);
          setPicking(false);
        }}
      />
    </View>
  );
}

function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 8 }}>
      <Text style={[styles.label, { color: theme.text }]}>{label}</Text>
      {children}
      {help ? (
        <Body small muted>
          {help}
        </Body>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  formats: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: size.gutter - 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { flex: 1, textAlign: 'center', fontFamily: font.semibold, fontSize: size.headline },
  page: { padding: size.gutter, gap: size.section },
  label: { fontFamily: font.medium, fontSize: size.small },
  file: { paddingHorizontal: 16, paddingVertical: 14 },
  fileName: { fontFamily: font.mono, fontSize: size.small },
  choose: { minHeight: size.control, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
