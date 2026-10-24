import { accountsList, statementsUpload } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useApi, useRead } from '../api';
import { Body, Button, Icon } from '../kit';
import { Picker } from '../picker';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

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
      // Straight to review, with what the server noted while reading the file.
      router.replace({
        pathname: '/review/[id]',
        params: { id: result.statement_id, read: String(result.parsed), ...(result.errors.length ? { notes: JSON.stringify(result.errors) } : {}) },
      });
    },
  });

  const name = accounts.data?.find((a) => a.id === account)?.name ?? t.noAccount;

  return (
    <View style={{ flex: 1, backgroundColor: theme.chrome }}>
      <View style={[styles.header, { paddingTop: Platform.OS === 'ios' ? 8 : insets.top, borderBottomColor: theme.rule }]}>
        <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.headerButton}>
          <Body>{t.cancel}</Body>
        </Pressable>
        <Text accessibilityRole="header" style={[styles.headerTitle, { color: theme.text }]}>
          {t.title}
        </Text>
        <View style={styles.headerButton} />
      </View>

      <ScrollView contentContainerStyle={[styles.page, { paddingBottom: insets.bottom + 24 }]}>
        <Field label={t.file} help={tooLarge ? t.tooLarge : t.fileHelp}>
          {file ? (
            <View style={[styles.file, { borderColor: theme.fieldBorder, backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12) }]}>
              <Text style={[styles.fileName, { color: theme.text }]} numberOfLines={2}>
                {file.name}
              </Text>
            </View>
          ) : null}
          <Button kind="secondary" label={file ? t.chooseAgain : t.choose} onPress={() => void choose()} />
        </Field>

        <Field label={t.account} help={t.accountHelp}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${t.account}: ${name}`}
            onPress={() => setPicking(true)}
            style={[styles.choose, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder }]}
          >
            <Body>{name}</Body>
            <Icon name="down" size={16} colour={theme.muted} />
          </Pressable>
        </Field>

        {upload.error ? <Body alert>{upload.error.message}</Body> : null}
        <View style={{ gap: 6 }}>
          <Button
            label={upload.isPending ? t.submitting : t.submit}
            busy={upload.isPending}
            disabled={!file || tooLarge || upload.isPending}
            onPress={() => file && upload.mutate(file)}
          />
          <Body small muted>
            {t.nothingBooked}
          </Body>
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
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: StyleSheet.hairlineWidth, paddingHorizontal: 8 },
  headerButton: { minHeight: size.target, minWidth: 72, justifyContent: 'center', paddingHorizontal: 8 },
  headerTitle: { fontFamily: font.medium, fontSize: 17 },
  page: { padding: size.gutter, gap: 20 },
  label: { fontFamily: font.medium, fontSize: size.small },
  file: { borderWidth: 1, paddingHorizontal: 14, paddingVertical: 12 },
  fileName: { fontFamily: font.mono, fontSize: size.small },
  choose: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
