import { devicesAdd, devicesList, devicesRemove, notificationsPreferencesGet, notificationsPreferencesUpdate, type NotificationPreferences, type NotificationPreferencesUpdate } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { useState } from 'react';
import { Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../api';
import { Body, Button, Card, Choice, Icon, SectionLabel, Toggle, Waiting } from '../kit';
import { storeKeyOf } from '../lib/servers';
import { Sheet } from '../sheet';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.notifications;

type PushItem = NotificationPreferences['push_items'][number];
const KINDS: readonly PushItem[] = ['budget_over', 'cash_below_zero_ahead', 'reminder_due'];
const HOURS = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}:00`);
const QUIET = { start: '22:00', end: '08:00' };

/**
 * Settings › Notifications (design HhPush): push alerts on this phone, on or
 * off. On asks the phone's permission, then gives the server this phone's
 * Expo push token (`POST /v1/devices`); off removes it. Which alerts come
 * and the quiet hours (in the person's time zone) are their preferences on
 * the server, for every phone of theirs; and how one reads on the lock screen.
 * Once the phone's settings refuse them, it says so with a way to Settings
 * (design NotificationsRefused), read again whenever the app comes back.
 */
export default function NotificationsScreen() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const devices = useRead('devices.list', devicesList);
  const prefs = useRead('notifications.preferences', notificationsPreferencesGet);
  const [editing, setEditing] = useState<'start' | 'end' | undefined>();
  const save = useMutation({
    mutationFn: (body: NotificationPreferencesUpdate) => api.call(notificationsPreferencesUpdate, { body }),
    onSuccess: (saved) => queryClient.setQueryData([api.server, 'notifications.preferences', null], saved),
  });
  const chosen = prefs.data?.push_items ?? [];
  const quiet = prefs.data?.quiet_hours ?? null;
  const key = storeKeyOf(api.server, 'push');
  // The device this phone registered as, kept on the phone.
  const mine = useQuery({ queryKey: [api.server, 'push.device'], queryFn: async () => (await SecureStore.getItemAsync(key)) ?? '' });
  const on = !!mine.data && !!devices.data?.devices.some((d) => d.id === mine.data);
  const permission = useQuery({ queryKey: [api.server, 'push.permission'], queryFn: () => Notifications.getPermissionsAsync() });
  const refused = permission.data?.status === 'denied';

  const turn = useMutation({
    mutationFn: async (next: boolean) => {
      if (!next) {
        if (mine.data) await api.call(devicesRemove, { path: { device_id: mine.data } }).catch(() => undefined);
        await SecureStore.deleteItemAsync(key);
        return;
      }
      const asked = await Notifications.requestPermissionsAsync();
      if (!asked.granted) throw new Error(t.denied);
      const projectId = (Constants.expoConfig?.extra?.eas as { projectId?: string } | undefined)?.projectId;
      const token = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : {});
      const device = await api.call(devicesAdd, { body: { token: token.data, platform: Platform.OS === 'android' ? 'android' : 'ios' } });
      await SecureStore.setItemAsync(key, device.id);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: [api.server] }),
  });

  return (
    <Page title={t.title} back={{ label: strings.more.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) }}>
      {devices.data ? (
        <>
          {refused ? (
            <Card style={{ gap: 12 }}>
              <View style={styles.refused}>
                <Icon name="silent" size={22} colour={theme.text} />
                <Body style={{ flex: 1 }}>{t.denied}</Body>
              </View>
              <Button kind="secondary" label={t.openSettings} onPress={() => void Linking.openSettings()} />
            </Card>
          ) : null}
          <Card style={{ paddingVertical: 0 }}>
            <Toggle
              label={t.push}
              {...(devices.data.push_enabled ? {} : { help: t.serverOff })}
              value={turn.isPending ? !on : on}
              disabled={!devices.data.push_enabled || turn.isPending || mine.isLoading}
              onChange={(next) => turn.mutate(next)}
            />
          </Card>
          {turn.error && !refused ? <Body alert>{turn.error.message}</Body> : null}
          {prefs.data ? (
            <>
              <Card style={{ paddingBottom: 4 }}>
                <SectionLabel>{t.alerts}</SectionLabel>
                {KINDS.map((kind) => (
                  <View key={kind} style={[styles.kind, { borderTopColor: theme.rule }]}>
                    <Toggle
                      label={t.kinds[kind]}
                      value={chosen.includes(kind)}
                      disabled={save.isPending}
                      onChange={(next) => save.mutate({ push_items: next ? [...chosen, kind] : chosen.filter((k) => k !== kind) })}
                    />
                  </View>
                ))}
              </Card>
              {refused ? (
                <Body small muted>
                  {t.kept}
                </Body>
              ) : null}
              <Card style={{ gap: 8 }}>
                <SectionLabel>{t.quiet}</SectionLabel>
                <Toggle label={t.quietOn} help={t.quietHelp} value={!!quiet} disabled={save.isPending} onChange={(next) => save.mutate({ quiet_hours: next ? QUIET : null })} />
                {quiet ? (
                  <View style={styles.times}>
                    {(['start', 'end'] as const).map((end) => (
                      <Pressable
                        key={end}
                        accessibilityRole="button"
                        accessibilityLabel={`${t[end]} ${quiet[end]}`}
                        onPress={() => setEditing(end)}
                        style={[styles.time, { backgroundColor: theme.input, borderColor: theme.fieldBorder, borderRadius: Math.min(theme.control, 12) }]}
                      >
                        <Text style={[styles.small, { color: theme.muted }]}>{t[end]}</Text>
                        <Text style={[styles.clock, { color: theme.text }]}>{quiet[end]}</Text>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
              </Card>
              {save.error ? <Body alert>{save.error.message}</Body> : null}
              <Sheet visible={!!editing && !!quiet} onClose={() => setEditing(undefined)} label={editing ? t[editing] : t.quiet}>
                {editing && quiet ? (
                  <Choice
                    label={t[editing]}
                    options={HOURS.filter((h) => h !== quiet[editing === 'start' ? 'end' : 'start']).map((h) => ({ id: h, text: h }))}
                    chosen={quiet[editing]}
                    onPick={(h) => {
                      setEditing(undefined);
                      save.mutate({ quiet_hours: { ...quiet, [editing]: h } });
                    }}
                  />
                ) : null}
              </Sheet>
            </>
          ) : (
            <Waiting query={prefs} what="your alerts" />
          )}
          <View style={{ gap: 8 }}>
            <SectionLabel>{t.lockScreen}</SectionLabel>
            <View accessible accessibilityLabel={`${t.sampleTitle} ${t.sampleBody}`} style={[styles.lock, { backgroundColor: theme.text }]}>
              <View style={[styles.note, { backgroundColor: theme.chrome }]}>
                <View style={[styles.appIcon, { backgroundColor: theme.button }]}>
                  <Text style={[styles.appLetter, { color: theme.buttonText }]}>S</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <View style={styles.noteTop}>
                    <Text style={[styles.small, { color: theme.muted }]}>Salli</Text>
                    <Text style={[styles.small, { color: theme.muted }]}>{t.now}</Text>
                  </View>
                  <Text style={[styles.noteTitle, { color: theme.text }]}>{t.sampleTitle}</Text>
                  <Text style={[styles.noteBody, { color: theme.muted }]}>{t.sampleBody}</Text>
                </View>
              </View>
            </View>
            <Body small muted>
              {t.noAmounts}
            </Body>
          </View>
        </>
      ) : (
        <Waiting query={devices} what="push alerts" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  refused: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  kind: { justifyContent: 'center', borderTopWidth: StyleSheet.hairlineWidth },
  times: { flexDirection: 'row', gap: 12 },
  time: { borderWidth: 1, minHeight: 48, minWidth: 110, paddingHorizontal: 12, paddingVertical: 6, justifyContent: 'center' },
  clock: { fontFamily: font.regular, fontSize: size.body, fontVariant: ['tabular-nums'] },
  lock: { paddingVertical: 16, paddingHorizontal: 12 },
  note: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 10, paddingHorizontal: 12, opacity: 0.94 },
  appIcon: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
  appLetter: { fontFamily: font.semibold, fontSize: 14 },
  noteTop: { flexDirection: 'row', justifyContent: 'space-between' },
  small: { fontFamily: font.regular, fontSize: 13 },
  noteTitle: { fontFamily: font.medium, fontSize: size.body },
  noteBody: { fontFamily: font.regular, fontSize: 14 },
});
