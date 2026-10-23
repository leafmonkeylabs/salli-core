import { authMe } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { useRead } from '../../api';
import { Body, Button, Card, Icon, SectionLabel } from '../../kit';
import { usePhone } from '../../phone';
import { useSession } from '../../session';
import { Header } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.more;

export default function More() {
  const theme = useTheme();
  const { session, signOut } = useSession();
  const me = useRead('auth.me', authMe);
  const phone = usePhone();
  // The server being signed out of: once it goes, the next one's button is ready.
  const [leaving, setLeaving] = useState<string | undefined>(undefined);
  const server = session.status === 'signed-in' ? session.server : '';
  const count = session.status === 'signed-in' ? session.servers.length : 1;
  const how = strings.phone.how[phone.unlockWith ?? 'passcode'];
  const host = server.replace(/^https?:\/\//, '');

  return (
    <View style={{ flex: 1, backgroundColor: theme.work }}>
      <Header title={t.title} />
      <ScrollView contentContainerStyle={styles.page}>
        <Card style={{ gap: 10 }}>
          <SectionLabel>{t.server}</SectionLabel>
          <Text style={[styles.host, { color: theme.text }]}>{server}</Text>
          {me.data?.email ? (
            <Body small muted>
              {t.as(me.data.email)}
            </Body>
          ) : null}
          <View style={{ marginTop: 6, gap: 6 }}>
            <Button
              kind="secondary"
              label={t.signOut(host)}
              busy={leaving === server}
              disabled={leaving === server}
              onPress={() => {
                setLeaving(server);
                void signOut();
              }}
            />
            <Body small muted>
              {count > 1 ? t.signOutNoteOthers : t.signOutNote}
            </Body>
          </View>
          <Pressable accessibilityRole="button" onPress={() => router.push('/servers')} style={[styles.row, { borderTopColor: theme.rule }]}>
            <Body>{t.servers(count)}</Body>
            <Icon name="chevron" size={18} colour={theme.muted} />
          </Pressable>
        </Card>
        <Card style={{ gap: 10 }}>
          <SectionLabel>{strings.phone.title}</SectionLabel>
          <Setting
            label={strings.phone.lock(how)}
            help={phone.unlockWith ? strings.phone.lockHelp : strings.phone.noLock}
            value={phone.settings.lock}
            disabled={!phone.unlockWith}
            onChange={(on) => void phone.setLock(on)}
          />
          <Setting
            label={strings.phone.showAmounts}
            help={phone.settings.showAmounts ? strings.phone.showAmountsOnHelp : strings.phone.showAmountsHelp}
            value={phone.settings.showAmounts}
            onChange={phone.setShowAmounts}
          />
        </Card>
        <Body small muted>
          {t.footer}
        </Body>
      </ScrollView>
    </View>
  );
}

function Setting({ label, help, value, disabled, onChange }: { label: string; help: string; value: boolean; disabled?: boolean; onChange: (on: boolean) => void }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 4 }}>
      <View style={styles.setting}>
        <Body style={{ flex: 1 }}>{label}</Body>
        <Switch
          accessibilityLabel={label}
          accessibilityHint={help}
          value={value}
          disabled={!!disabled}
          onValueChange={onChange}
          trackColor={{ false: theme.rule, true: theme.button }}
        />
      </View>
      <Body small muted>
        {help}
      </Body>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderTopWidth: StyleSheet.hairlineWidth, marginTop: 6 },
  setting: { minHeight: size.target, flexDirection: 'row', alignItems: 'center', gap: 12 },
  page: { padding: size.gutter, gap: size.gap },
  host: { fontFamily: font.mono, fontSize: size.body },
});
