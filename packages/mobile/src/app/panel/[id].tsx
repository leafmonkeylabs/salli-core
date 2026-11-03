import { isPanelId } from '@leafmonkeylabs/salli-sdk';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Body, Button, Loading } from '../../kit';
import { PanelView, usePanel, useRefreshPanels } from '../../panel';
import { Page } from '../../shell';
import { strings } from '../../strings';

const t = strings.panel;

/**
 * A page the server describes (design MorePlan, PlanRequested): its sections
 * of rows, drawn as the server sent them. After an action it reads the page
 * again, which is how "requested" shows; or it goes back, as the row says.
 */
export default function PanelScreen() {
  const { id = '' } = useLocalSearchParams<{ id: string }>();
  const panel = usePanel(isPanelId(id) ? id : '');
  const refresh = useRefreshPanels(id);
  const [again, setAgain] = useState(false);
  const back = { label: strings.more.title, onPress: () => (router.canGoBack() ? router.back() : router.replace('/more')) };
  const read = () => {
    setAgain(true);
    void panel.refetch().finally(() => setAgain(false));
  };

  if (panel.data) {
    return (
      <Page title={panel.data.title} back={back} onRefresh={() => refresh()}>
        <PanelView
          panel={panel.data}
          after={(then) => {
            if (then === 'close') router.back();
            void refresh();
          }}
        />
        {panel.data.sections.every((s) => !s.rows.length) && !panel.data.note ? <Body muted>{t.empty}</Body> : null}
      </Page>
    );
  }
  return (
    <Page back={back}>
      {panel.isLoading ? (
        <Loading what={t.loading} />
      ) : (
        <>
          <Body alert>{panel.error ? panel.error.message : t.cantShow}</Body>
          <Button kind="secondary" label={t.tryAgain} busy={again} disabled={again} onPress={read} />
        </>
      )}
    </Page>
  );
}
