/**
 * A page a server describes (`/console/panel/<id>`, `salli.panel/1`): the
 * account, a request, a move. The console draws what the server's document
 * says (kit/PanelView.tsx) and adds nothing; after an action it reads the
 * page again, or goes back, as the row says.
 */
import { isPanelId } from '@leafmonkeylabs/salli-sdk';
import { useParams, useRouter } from '@tanstack/react-router';
import { PanelView } from '../../kit/PanelView';
import { Empty, Loading, Page } from '../../kit/layout';
import { ProblemView } from '../../kit/Problem';
import { usePanel } from '../../panels';
import { strings } from '../../strings';

export function PanelPage() {
  const { id } = useParams({ strict: false }) as { id?: string };
  const router = useRouter();
  const panel = usePanel(isPanelId(id) ? id : '');
  if (panel.isPending) {
    return (
      <Page title={strings.loading}>
        <Loading what={strings.panel.loadingWhat} />
      </Page>
    );
  }
  if (panel.isError) {
    return (
      <Page title={strings.problem.title}>
        <ProblemView error={panel.error} onRetry={() => void panel.refetch()} />
      </Page>
    );
  }
  if (!panel.data) {
    return (
      <Page title={strings.panel.cantShow}>
        <Empty>{strings.panel.cantShow}</Empty>
      </Page>
    );
  }
  const empty = panel.data.sections.every((s) => !s.rows.length) && !panel.data.note;
  return (
    <Page title={panel.data.title}>
      <PanelView
        panel={panel.data}
        after={(then) => {
          // `refresh` is the write's own invalidation; `close` leaves the page.
          if (then === 'close') void (router.history.canGoBack() ? router.history.back() : router.navigate({ to: '/' }));
        }}
      />
      {empty ? <Empty>{strings.panel.nothing}</Empty> : null}
    </Page>
  );
}

export default PanelPage;
