/**
 * Panels: pages a server describes (`salli.panel/1`) and the app only draws.
 * Every word is the server's; the app adds "Done", "Try again" and "Not now".
 * A row that is a link opens in the phone's secure browser sheet; an action
 * asks the server to do what the row says (after the system alert, when the
 * row has words to confirm with) and then refreshes the panel or closes it;
 * a form sends what was typed. A refusal is shown in the row that asked.
 */
import { describeDetail, formBody, missingFields, panelsList, panelsShow, parsePanel, SalliApiError, type PanelDocument, type PanelEntry, type PanelField, type PanelRow, type PanelSection } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Alert, StyleSheet, Text, TextInput, View } from 'react-native';
import { useApi, useRead } from './api';
import { Body, Button, Card, Choice, Icon, Press, SectionLabel, useLargeText } from './kit';
import { placesOf } from './lib/panel';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.panel;

/** Whether this server has panels: what `/v1/meta` says, read once. */
function usePanelsOn(): boolean {
  const api = useApi();
  const meta = useQuery({ queryKey: [api.server, 'meta'], queryFn: () => api.meta(), staleTime: 5 * 60_000 });
  return meta.data?.panels === true;
}

/** The panels the server lists (title and where each is placed), when it has any. */
export function usePanelList(): PanelEntry[] {
  const on = usePanelsOn();
  const list = useRead('panels.list', panelsList, undefined, { enabled: on });
  return on ? (list.data?.panels ?? []) : [];
}

/** The panels placed at `entry`, for More's and Settings' rows. */
export function usePanelPlaces(entry: 'more' | 'settings'): PanelEntry[] {
  return placesOf(usePanelList(), entry);
}

/** One panel: `undefined` data with no error means the server's document is not one the app can draw. */
export function usePanel(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: [api.server, 'panels.show', id],
    queryFn: async () => parsePanel(await api.call(panelsShow, { path: { panel_id: id } })) ?? null,
  });
}

/** The words of a refusal, as the server sent them. */
function whyOf(error: unknown): string {
  if (error instanceof SalliApiError) return error.message || describeDetail(error.detail);
  return error instanceof Error ? error.message : String(error);
}

/** The panel's sections as cards, then its note. `after` is told what a row's `then` asks for. */
export function PanelView({ panel, after }: { panel: PanelDocument; after: (then: 'refresh' | 'close') => void }) {
  const theme = useTheme();
  return (
    <>
      {panel.sections.map((section, i) => (
        <Section key={i} section={section} after={after} />
      ))}
      {panel.note ? (
        <View style={[styles.note, { backgroundColor: theme.tile, borderColor: theme.line }]}>
          <Body>{panel.note}</Body>
        </View>
      ) : null}
    </>
  );
}

function Section({ section, after }: { section: PanelSection; after: (then: 'refresh' | 'close') => void }) {
  if (!section.rows.length && !section.heading) return null;
  return (
    <View style={{ gap: 6 }}>
      <Card style={{ gap: 12 }}>
        {section.heading ? <SectionLabel>{section.heading}</SectionLabel> : null}
        {section.rows.map((row, i) => (
          <RowView key={i} row={row} after={after} last={i === section.rows.length - 1} />
        ))}
      </Card>
      {section.footnote ? (
        <Body small muted>
          {section.footnote}
        </Body>
      ) : null}
    </View>
  );
}

function RowView({ row, after, last }: { row: PanelRow; after: (then: 'refresh' | 'close') => void; last: boolean }) {
  const theme = useTheme();
  const rule = last ? null : { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth, paddingBottom: 12 };
  switch (row.kind) {
    case 'text':
      return <TextRow row={row} rule={rule} />;
    case 'link':
      return <LinkRow row={row} rule={rule} />;
    case 'action':
      return <ActionRow row={row} after={after} rule={rule} />;
    case 'form':
      return <FormRow row={row} after={after} rule={rule} />;
  }
}

type Rule = { borderBottomColor: string; borderBottomWidth: number; paddingBottom: number } | null;

function TextRow({ row, rule }: { row: Extract<PanelRow, { kind: 'text' }>; rule: Rule }) {
  const large = useLargeText();
  return (
    <View accessible accessibilityLabel={row.value ? `${row.label}, ${row.value}` : row.label} style={[large ? null : styles.line, rule, { gap: 4 }]}>
      <Body style={{ flex: 1 }}>{row.label}</Body>
      {row.value ? <Body muted style={large ? undefined : { textAlign: 'right', flexShrink: 1 }}>{row.value}</Body> : null}
    </View>
  );
}

function LinkRow({ row, rule }: { row: Extract<PanelRow, { kind: 'link' }>; rule: Rule }) {
  const theme = useTheme();
  return (
    <Press
      accessibilityRole="link"
      accessibilityLabel={[row.label, row.detail].filter(Boolean).join(', ')}
      accessibilityHint={t.opensBrowser}
      onPress={() => void WebBrowser.openBrowserAsync(row.url, { presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET })}
      style={[styles.line, styles.target, rule]}
    >
      <View style={{ flex: 1, gap: 2 }}>
        <Body>{row.label}</Body>
        {row.detail ? (
          <Body small muted>
            {row.detail}
          </Body>
        ) : null}
      </View>
      <Icon name="external" size={18} colour={theme.muted} />
    </Press>
  );
}

/** Sends what a row asks for; `then` is what the screen does once the server has accepted it. */
function useSend(then: 'refresh' | 'close', after: (then: 'refresh' | 'close') => void) {
  const api = useApi();
  return useMutation({
    mutationFn: (request: { method: 'POST' | 'DELETE'; path: string; body?: Record<string, unknown> }) => api.send(request),
    onSuccess: () => after(then),
  });
}

function ActionRow({ row, after, rule }: { row: Extract<PanelRow, { kind: 'action' }>; after: (then: 'refresh' | 'close') => void; rule: Rule }) {
  const send = useSend(row.action.then, after);
  const go = () => send.mutate({ method: row.action.method, path: row.action.path, ...(row.action.body ? { body: row.action.body } : {}) });
  const ask = () => {
    if (!row.confirm) return go();
    // The system's own alert, in the server's words.
    Alert.alert(row.confirm, undefined, [
      { text: t.notNow, style: 'cancel' },
      { text: row.label, style: row.action.method === 'DELETE' ? 'destructive' : 'default', onPress: go },
    ]);
  };
  return (
    <View style={[{ gap: 8 }, rule]}>
      {row.detail ? <Body muted>{row.detail}</Body> : null}
      <Button label={row.label} kind={row.action.method === 'DELETE' ? 'secondary' : 'primary'} busy={send.isPending} disabled={send.isPending} onPress={ask} />
      <Why error={send.error} onAgain={ask} />
    </View>
  );
}

function FormRow({ row, after, rule }: { row: Extract<PanelRow, { kind: 'form' }>; after: (then: 'refresh' | 'close') => void; rule: Rule }) {
  const send = useSend(row.submit.then, after);
  const theme = useTheme();
  const [values, setValues] = useState<Record<string, string>>({});
  const missing = missingFields(row.fields, values);
  const submit = () => send.mutate({ method: row.submit.method, path: row.submit.path, body: formBody(row.fields, values) });
  return (
    <View style={[{ gap: 12 }, rule]}>
      <Text accessibilityRole="header" maxFontSizeMultiplier={1.7} style={[styles.formTitle, { color: theme.text }]}>
        {row.label}
      </Text>
      {row.fields.map((field) => (
        <Field key={field.name} field={field} value={values[field.name] ?? ''} onChange={(v) => setValues((now) => ({ ...now, [field.name]: v }))} />
      ))}
      <Button label={row.submit.label} busy={send.isPending} disabled={send.isPending || missing.length > 0} onPress={submit} />
      <Why error={send.error} onAgain={submit} />
    </View>
  );
}

function Field({ field, value, onChange }: { field: PanelField; value: string; onChange: (value: string) => void }) {
  const theme = useTheme();
  if (field.type === 'select') {
    return <Choice list label={field.label} options={(field.options ?? []).map((o) => ({ id: o.value, text: o.label }))} chosen={value || undefined} onPick={onChange} />;
  }
  return (
    <View style={{ gap: 6 }}>
      <Text style={[styles.fieldLabel, { color: theme.text }]}>{field.label}</Text>
      <TextInput
        accessibilityLabel={field.label}
        value={value}
        onChangeText={onChange}
        keyboardType={field.type === 'number' ? 'decimal-pad' : 'default'}
        autoCorrect={false}
        placeholderTextColor={theme.muted}
        style={[styles.input, { backgroundColor: theme.fill, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
      />
    </View>
  );
}

/** What the server said when it refused, in the row that asked, with a way to ask again. */
function Why({ error, onAgain }: { error: unknown; onAgain: () => void }) {
  if (!error) return null;
  return (
    <View accessibilityLiveRegion="polite" style={{ gap: 6 }}>
      <Body alert>{whyOf(error)}</Body>
      <View style={{ alignSelf: 'flex-start' }}>
        <Button kind="tertiary" label={t.tryAgain} onPress={onAgain} />
      </View>
    </View>
  );
}

/** Refreshes what the panels' pages read after an action. */
export function useRefreshPanels(id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return () => Promise.all([queryClient.invalidateQueries({ queryKey: [api.server, 'panels.show', id] }), queryClient.invalidateQueries({ queryKey: [api.server, 'panels.list'] })]);
}

const styles = StyleSheet.create({
  line: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  target: { minHeight: size.target },
  note: { borderWidth: StyleSheet.hairlineWidth, padding: 14 },
  formTitle: { fontFamily: font.medium, fontSize: size.body },
  fieldLabel: { fontFamily: font.medium, fontSize: size.small },
  input: { minHeight: size.target, borderWidth: 1, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
});
