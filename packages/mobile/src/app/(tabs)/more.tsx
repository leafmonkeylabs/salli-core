import { authMe } from '@leafmonkeylabs/salli-sdk';
import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRead } from '../../api';
import { Body, Button, Card, SectionLabel } from '../../kit';
import { useSession } from '../../session';
import { Header } from '../../shell';
import { strings } from '../../strings';
import { font, size, useTheme } from '../../theme';

const t = strings.more;

export default function More() {
  const theme = useTheme();
  const { session, signOut } = useSession();
  const me = useRead('auth.me', authMe);
  const [leaving, setLeaving] = useState(false);
  const server = session.status === 'signed-in' ? session.server : '';
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
              busy={leaving}
              disabled={leaving}
              onPress={() => {
                setLeaving(true);
                void signOut();
              }}
            />
            <Body small muted>
              {t.signOutNote}
            </Body>
          </View>
        </Card>
        <Body small muted>
          {t.footer}
        </Body>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: size.gutter, gap: size.gap },
  host: { fontFamily: font.mono, fontSize: size.body },
});
