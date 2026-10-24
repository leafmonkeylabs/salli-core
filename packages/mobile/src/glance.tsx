/**
 * Keeps the widgets' snapshot (src/lib/glance.ts) in step with the reads: the
 * same reads as Home, so it asks the server nothing more. Signed out, the
 * snapshot goes, and the widget asks to open the app. Figures show: the phone is the person's own.
 */
import { ExtensionStorage } from '@bacons/apple-targets';
import { decisionsReviewsDue, insightsForecast, insightsNetWorth, insightsSafeToSpend, insightsSignals, ledgerIncomeStatement, remindersList, statementsList } from '@leafmonkeylabs/salli-sdk';
import { useEffect } from 'react';
import { useRead } from './api';
import { useAppearance } from './appearance';
import { isNight } from './lib/appearance';
import { monthOf, sameDaysLastMonth, todayIso } from './lib/display';
import { glanceOf, type Palette } from './lib/glance';
import { useSession } from './session';
import { themeOf, type Theme } from './theme';

/** A theme as a widget draws it: its bars' opaque colour for the ground. */
function paletteOf(theme: Theme): Palette {
  return { paper: theme.chrome, ink: theme.text, muted: theme.muted, rule: theme.rule, accent: theme.chart, tile: theme.tile, tileText: theme.tileText };
}

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
  const safe = useRead('insights.safeToSpend', insightsSafeToSpend);
  const reviews = useRead('decisions.reviews.due', decisionsReviewsDue);
  const reminders = useRead('reminders.list', remindersList, { query: { status: 'pending' } });
  const statements = useRead('statements.list', statementsList, { query: { limit: 200 } });
  const signals = useRead('insights.signals', insightsSignals);
  // The same reads as Home's, so the widgets ask the server nothing more.
  const today = todayIso();
  const month = monthOf(today);
  const before = sameDaysLastMonth(today);
  const forecast = useRead('insights.forecast', insightsForecast);
  const spent = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: month.from, to_date: month.to } });
  const spentBefore = useRead('ledger.incomeStatement', ledgerIncomeStatement, { query: { from_date: before.from, to_date: before.to } });
  const history = useRead('insights.netWorth', insightsNetWorth, { query: { months: 12 } });
  const { appearance } = useAppearance();
  const reads = [safe, reviews, reminders, statements, signals];
  const at = Math.max(...reads.map((r) => r.dataUpdatedAt));

  // Written only from a full set, and again only when a read comes back or the setting changes.
  const snapshot =
    safe.data && reviews.data && reminders.data && statements.data && signals.data
      ? JSON.stringify(
          glanceOf(
            {
              safe: safe.data,
              reviews: reviews.data,
              reminders: reminders.data,
              statements: statements.data,
              signals: signals.data,
              ...(forecast.data ? { forecast: forecast.data } : {}),
              ...(spent.data ? { spent: spent.data } : {}),
              ...(spentBefore.data ? { spentBefore: spentBefore.data } : {}),
              ...(history.data ? { history: history.data } : {}),
            },
            {
              host,
              showAmounts: true,
              at,
              today,
              colors: {
                light: paletteOf(themeOf(appearance.theme, isNight({ ...appearance, mode: 'light' }, false))),
                dark: paletteOf(themeOf(appearance.theme, isNight({ ...appearance, mode: 'dark' }, true))),
              },
            },
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
