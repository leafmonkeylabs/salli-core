/**
 * Keeps the widgets' snapshot (src/lib/glance.ts) in step with the reads: the
 * same reads as Home, so it asks the server nothing more. Signed out, the
 * snapshot goes, and the widget asks to open the app.
 */
import { ExtensionStorage } from '@bacons/apple-targets';
import { decisionsReviewsDue, insightsSafeToSpend, insightsSignals, remindersList, statementsList } from '@leafmonkeylabs/salli-sdk';
import { useEffect } from 'react';
import { useRead } from './api';
import { todayIso } from './lib/display';
import { glanceOf } from './lib/glance';
import { usePhone } from './phone';
import { useSession } from './session';

/** The app group the app and `targets/widget` share; in app.json too. */
const GROUP = 'group.money.salli.app';
const KEY = 'glance';
const storage = new ExtensionStorage(GROUP);

export function Glance() {
  const { session } = useSession();
  const signedIn = session.status === 'signed-in';
  useEffect(() => {
    if (signedIn) return;
    storage.remove(KEY);
    ExtensionStorage.reloadWidget();
  }, [signedIn]);
  return signedIn ? <Writer key={session.server} host={session.server.replace(/^https?:\/\//, '')} /> : null;
}

function Writer({ host }: { host: string }) {
  const { settings } = usePhone();
  const safe = useRead('insights.safeToSpend', insightsSafeToSpend);
  const reviews = useRead('decisions.reviews.due', decisionsReviewsDue);
  const reminders = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const signals = useRead('insights.signals', insightsSignals);
  const reads = [safe, reviews, reminders, statements, signals];
  const at = Math.max(...reads.map((r) => r.dataUpdatedAt));

  // Written only from a full set, and again only when a read comes back or the setting changes.
  const snapshot =
    safe.data && reviews.data && reminders.data && statements.data && signals.data
      ? JSON.stringify(
          glanceOf(
            { safe: safe.data, reviews: reviews.data, reminders: reminders.data, statements: statements.data, signals: signals.data },
            { host, showAmounts: settings.showAmounts, at, today: todayIso() },
          ),
        )
      : undefined;
  useEffect(() => {
    if (!snapshot) return;
    storage.set(KEY, snapshot);
    ExtensionStorage.reloadWidget();
  }, [snapshot]);
  return null;
}
