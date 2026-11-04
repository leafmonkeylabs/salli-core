import { devicesAdd, devicesList, devicesRemove, notificationsPreferencesGet, notificationsPreferencesUpdate, type NotificationPreferences, type NotificationPreferencesUpdate } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { useState } from 'react';
import { Linking, Platform, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../api';
import { Body, Button, Choice, Notice, Press, Section, Surface, Toggle, Waiting, radii, shape } from '../kit';
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
            <Notice tone="warn" icon="silent" action={<Button small kind="secondary" label={t.openSettings} onPress={() => void Linking.openSettings()} />}>
              {t.denied}
            </Notice>
          ) : null}
          <Surface pad={false} style={styles.list}>
            <Toggle
              label={t.push}
              {...(devices.data.push_enabled ? {} : { help: t.serverOff })}
              value={turn.isPending ? !on : on}
              disabled={!devices.data.push_enabled || turn.isPending || mine.isLoading}
              onChange={(next) => turn.mutate(next)}
            />
          </Surface>
          {turn.error && !refused ? <Notice tone="warn">{turn.error.message}</Notice> : null}
          {prefs.data ? (
            <>
              <Section title={t.alerts}>
              <Surface pad={false} style={styles.list}>
                {KINDS.map((kind, i) => (
                  <View key={kind} style={[styles.kind, i < KINDS.length - 1 ? { borderBottomColor: theme.line, borderBottomWidth: StyleSheet.hairlineWidth } : null]}>
                    <Toggle
                      label={t.kinds[kind]}
                      value={chosen.includes(kind)}
                      disabled={save.isPending}
                      onChange={(next) => save.mutate({ push_items: next ? [...chosen, kind] : chosen.filter((k) => k !== kind) })}
                    />
                  </View>
                ))}
              </Surface>
              </Section>
              {refused ? (
                <Body small muted>
                  {t.kept}
                </Body>
              ) : null}
              <Section title={t.quiet}>
              <Surface pad={false} style={[styles.list, { gap: 8 }]}>
                <Toggle label={t.quietOn} help={t.quietHelp} value={!!quiet} disabled={save.isPending} onChange={(next) => save.mutate({ quiet_hours: next ? QUIET : null })} />
                {quiet ? (
                  <View style={styles.times}>
                    {(['start', 'end'] as const).map((end) => (
                      <Press
                        key={end}
                        accessibilityRole="button"
                        accessibilityLabel={`${t[end]} ${quiet[end]}`}
                        onPress={() => setEditing(end)}
                        style={[styles.time, shape(radii.field), { backgroundColor: theme.fill }]}
                      >
                        <Text style={[styles.small, { color: theme.muted }]}>{t[end]}</Text>
                        <Text style={[styles.clock, { color: theme.text }]}>{quiet[end]}</Text>
                      </Press>
                    ))}
                  </View>
                ) : null}
              </Surface>
              </Section>
              {save.error ? <Notice tone="warn">{save.error.message}</Notice> : null}
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
          <Body small muted>
            {t.noAmounts}
          </Body>
        </>
      ) : (
        <Waiting query={devices} what="push alerts" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: size.pad },
  kind: { justifyContent: 'center' },
  times: { flexDirection: 'row', gap: 12 },
  time: { minHeight: 52, minWidth: 110, paddingHorizontal: 12, paddingVertical: 6, justifyContent: 'center' },
  clock: { fontFamily: font.regular, fontSize: size.body, fontVariant: ['tabular-nums'] },
  small: { fontFamily: font.regular, fontSize: size.label },
});
