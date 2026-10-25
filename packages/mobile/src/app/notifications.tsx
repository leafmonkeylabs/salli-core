import { devicesAdd, devicesList, devicesRemove } from '@leafmonkeylabs/salli-sdk';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { Platform, StyleSheet, Text, View } from 'react-native';
import { useApi, useRead } from '../api';
import { Body, Card, SectionLabel, Toggle, Waiting } from '../kit';
import { storeKeyOf } from '../lib/servers';
import { Page } from '../shell';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.notifications;

/**
 * Settings › Notifications (design HhPush): push alerts on this phone, on or
 * off. On asks the phone's permission, then gives the server this phone's
 * Expo push token (`POST /v1/devices`); off removes it. The alerts are the
 * server's: what they are about, and how one reads on the lock screen.
 */
export default function NotificationsScreen() {
  const theme = useTheme();
  const api = useApi();
  const queryClient = useQueryClient();
  const devices = useRead('devices.list', devicesList);
  const key = storeKeyOf(api.server, 'push');
  // The device this phone registered as, kept on the phone.
  const mine = useQuery({ queryKey: [api.server, 'push.device'], queryFn: async () => (await SecureStore.getItemAsync(key)) ?? '' });
  const on = !!mine.data && !!devices.data?.devices.some((d) => d.id === mine.data);

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
          <Card style={{ paddingVertical: 0 }}>
            <Toggle
              label={t.push}
              {...(devices.data.push_enabled ? {} : { help: t.serverOff })}
              value={turn.isPending ? !on : on}
              disabled={!devices.data.push_enabled || turn.isPending || mine.isLoading}
              onChange={(next) => turn.mutate(next)}
            />
          </Card>
          {turn.error ? <Body alert>{turn.error.message}</Body> : null}
          <Card style={{ paddingBottom: 4 }}>
            <SectionLabel>{t.alerts}</SectionLabel>
            {t.kinds.map((kind) => (
              <View key={kind} style={[styles.kind, { borderTopColor: theme.rule }]}>
                <Body>{kind}</Body>
              </View>
            ))}
          </Card>
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
  kind: { minHeight: 48, justifyContent: 'center', borderTopWidth: StyleSheet.hairlineWidth },
  lock: { paddingVertical: 16, paddingHorizontal: 12 },
  note: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 10, paddingHorizontal: 12, opacity: 0.94 },
  appIcon: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
  appLetter: { fontFamily: font.semibold, fontSize: 14 },
  noteTop: { flexDirection: 'row', justifyContent: 'space-between' },
  small: { fontFamily: font.regular, fontSize: 13 },
  noteTitle: { fontFamily: font.medium, fontSize: size.body },
  noteBody: { fontFamily: font.regular, fontSize: 14 },
});
