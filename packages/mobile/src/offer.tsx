import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Body, Button } from './kit';
import { offerIsFor, panelPathOf } from './lib/panel';
import { onOffer, type Offered } from './offer-store';
import { useSession } from './session';
import { Sheet, SheetTitle } from './sheet';
import { strings } from './strings';
import { font, size, useTheme } from './theme';

const t = strings.panel;

/**
 * The sheet a refusal's offer opens (design PlanLimit): the server's title and
 * words, its button to the panel the offer names, and Not now. Nothing in it
 * is the app's own but "Not now".
 */
export function Offer() {
  const theme = useTheme();
  const { session } = useSession();
  const onScreen = session.status === 'signed-in' ? session.server : undefined;
  const [offered, setOffered] = useState<Offered | undefined>();
  const [open, setOpen] = useState(false);

  useEffect(
    () =>
      onOffer((next) => {
        // One at a time: a second refusal while it is up changes nothing.
        setOffered((now) => (open && now ? now : next));
        setOpen(true);
      }),
    [open],
  );

  const shown = offered && offerIsFor(offered, onScreen) ? offered.offer : undefined;
  const to = shown ? panelPathOf(shown.panel) : undefined;
  const close = () => setOpen(false);
  return (
    <Sheet visible={open && !!shown} onClose={close} label={shown?.title ?? ''}>
      {shown ? (
        <>
          <SheetTitle style={[styles.title, { color: theme.text }]}>{shown.title}</SheetTitle>
          <Body muted>{shown.detail}</Body>
          <View style={{ gap: 12 }}>
            {to ? (
              <Button
                label={shown.label}
                onPress={() => {
                  close();
                  router.push(to as never);
                }}
              />
            ) : null}
            <Button kind="secondary" label={t.notNow} onPress={close} />
          </View>
        </>
      ) : null}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  title: { fontFamily: font.semibold, fontSize: size.title },
});
