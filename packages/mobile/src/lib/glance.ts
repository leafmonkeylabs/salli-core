/**
 * What the widgets show (design 15): a small snapshot the app writes to the
 * app group after each read, worded here so the widget holds no words of its
 * own. It carries no name, question, note or anything else from the ledger,
 * and the amount only when the person asked for amounts outside the app.
 */
import type { BankStatementList, DueReviews, FinanceSignals, ReminderList, SafeToSpend } from '@leafmonkeylabs/salli-sdk';
import { strings } from '../strings';
import { amountParts, displayDate } from './display';

const t = strings.glance;

/** Version 1 of what `targets/widget` reads; a change of shape is a new version. */
export interface Glance {
  v: 1;
  /** When the newest of its reads came back, in ms: after a day the widget asks to open the app. */
  at: number;
  /** The server it is from, as the person typed it. */
  host: string;
  safe: {
    label: string;
    /** The figure, or the words for a hidden one. */
    figure: string;
    /** The currency beside a figure; empty when hidden. */
    currency: string;
    /** What VoiceOver says for the figure. */
    spoken: string;
    until: string;
  };
  waiting: { label: string; lines: string[]; more: string };
  open: string;
}

export interface GlanceReads {
  safe: SafeToSpend;
  reviews: DueReviews;
  reminders: ReminderList;
  statements: BankStatementList;
  signals: FinanceSignals;
}

/** The snapshot from the reads; `today` is the phone's ISO date. */
export function glanceOf(reads: GlanceReads, options: { host: string; showAmounts: boolean; at: number; today: string }): Glance {
  const { safe, reviews, reminders, statements, signals } = reads;
  const parts = amountParts(safe.amount, safe.currency);
  const figure = options.showAmounts ? (parts.negative ? `(${parts.digits})` : parts.digits) : t.hidden;

  // Reminders a decision set are its review, counted once as the decision.
  const due = reminders.reminders.filter((r) => r.source_domain !== 'decision' && r.due_date <= options.today).length;
  const pending = statements.statements.filter((s) => s.status === 'pending').length;
  const belowZero = signals.signals.some((s) => s.kind === 'low_balance_ahead' && s.severity === 'high');
  const lines = [
    ...(reviews.reviews.length ? [t.decisions(reviews.reviews.length)] : []),
    ...(due ? [t.reminders(due)] : []),
    ...(pending ? [t.statements(pending)] : []),
    ...(belowZero ? [t.cashBelowZero] : []),
  ];

  return {
    v: 1,
    at: options.at,
    host: options.host,
    safe: {
      label: t.safe,
      figure,
      currency: options.showAmounts ? safe.currency : '',
      spoken: options.showAmounts ? parts.spoken : t.hidden,
      until: safe.next_income ? t.until(displayDate(safe.until)) : t.noIncome,
    },
    waiting: { label: t.waiting, lines: lines.length ? lines : [t.nothingWaiting], more: lines.length > 2 ? t.more(lines.length - 2) : '' },
    open: t.open,
  };
}
