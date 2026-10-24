/**
 * What the widgets show (design 15): a small snapshot the app writes to the
 * app group after each read, worded here so the widget holds no words of its
 * own. The phone is the person's own: it carries figures, and what is coming
 * up by name; never a question, a note or a reminder's text.
 */
import { compareAmounts, type BankStatementList, type CashForecast, type DueReviews, type FinanceSignals, type IncomeStatement, type NetWorthByMonth, type ReminderList, type SafeToSpend } from '@leafmonkeylabs/salli-sdk';
import { strings } from '../strings';
import { heights } from './chart';
import { amountParts, displayDate, displayDay, monthNameOf, sameDaysLastMonth, wholeDigits } from './display';

const t = strings.glance;

/** A theme's colours as a widget draws them: opaque ground, and CSS colours. */
export interface Palette {
  paper: string;
  ink: string;
  muted: string;
  rule: string;
  accent: string;
  tile: string;
  tileText: string;
}

/** Version 2 of what `targets/widget` reads; a change of shape is a new version. */
export interface Glance {
  v: 2;
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
  /** The next 60 days as heights from 0 to 1, and where the low is. Never names. */
  forecast?: { label: string; low: string; spoken: string; points: number[]; lowIndex: number };
  spent?: { label: string; figure: string; then: string; spoken: string };
  netWorth?: { label: string; figure: string; spoken: string; points: number[] };
  /** The next few things in and out of cash: day, what, and the amount signed. */
  comingUp?: { label: string; rows: { day: string; title: string; amount: string; in: boolean }[]; spoken: string };
  /** Days until the next income, and how much of a month's ring they leave. */
  payday?: { days: number; unit: string; share: number; spoken: string };
  /** The app's theme, by day and by night (the same for a theme with one side). */
  colors: { light: Palette; dark: Palette };
  open: string;
}

export interface GlanceReads {
  safe: SafeToSpend;
  reviews: DueReviews;
  reminders: ReminderList;
  statements: BankStatementList;
  signals: FinanceSignals;
  forecast?: CashForecast;
  spent?: IncomeStatement;
  /** Last month to the same day. */
  spentBefore?: IncomeStatement;
  history?: NetWorthByMonth;
}

/** The snapshot from the reads; `today` is the phone's ISO date. */
export function glanceOf(reads: GlanceReads, options: { host: string; showAmounts: boolean; at: number; today: string; colors: { light: Palette; dark: Palette } }): Glance {
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

  const show = options.showAmounts;
  const whole = (amount: string, currency: string): string => (show ? wholeDigits(amount, currency) : t.hidden);
  const said = (amount: string, currency: string): string => (show ? amountParts(amount, currency).spoken : t.hidden);
  const { forecast, spent, spentBefore, history } = reads;
  const lowIndex = forecast ? Math.max(0, forecast.daily.findIndex((d) => d.date === forecast.lowest_date)) : 0;
  const points = forecast ? heights(forecast.daily.map((d) => d.balance), 32, lowIndex) : [];
  const thisMonth = monthNameOf(options.today);
  const lastMonth = spentBefore ? monthNameOf(sameDaysLastMonth(options.today).from) : '';
  // Whole days from today to the next income, as dates: never more than a month's ring.
  const days = safe.next_income ? Math.max(0, Math.round((Date.parse(safe.until) - Date.parse(options.today)) / 86_400_000)) : undefined;

  return {
    v: 2,
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
    ...(forecast
      ? {
          forecast: {
            label: t.forecast,
            low: t.low(show ? wholeDigits(forecast.lowest, forecast.currency) : '', displayDay(forecast.lowest_date)),
            spoken: t.lowSpoken(show ? amountParts(forecast.lowest, forecast.currency).spoken : '', displayDate(forecast.lowest_date)),
            points,
            lowIndex: points.length ? Math.round((lowIndex / Math.max(1, forecast.daily.length - 1)) * (points.length - 1)) : 0,
          },
        }
      : {}),
    ...(spent
      ? {
          spent: {
            label: t.spent(thisMonth.slice(0, 3)),
            figure: whole(spent.total_expenses, spent.currency),
            then: spentBefore && show ? t.spentThen(lastMonth.slice(0, 3), wholeDigits(spentBefore.total_expenses, spentBefore.currency), compareAmounts(spent.total_expenses, spentBefore.total_expenses) > 0) : '',
            spoken: spentBefore && show ? t.spentSpoken(thisMonth, said(spent.total_expenses, spent.currency), lastMonth, said(spentBefore.total_expenses, spentBefore.currency)) : said(spent.total_expenses, spent.currency),
          },
        }
      : {}),
    ...(history && history.points.length
      ? {
          netWorth: {
            label: t.netWorth,
            figure: whole(history.points[history.points.length - 1]?.net_worth ?? '0', history.currency),
            spoken: t.netWorthSpoken(said(history.points[history.points.length - 1]?.net_worth ?? '0', history.currency)),
            points: heights(history.points.map((p) => p.net_worth), 12),
          },
        }
      : {}),
    ...(forecast && forecast.flows.length
      ? {
          comingUp: {
            label: t.comingUp,
            rows: forecast.flows.slice(0, 3).map((flow) => {
              const parts = amountParts(flow.amount, flow.currency);
              return { day: displayDay(flow.date), title: flow.description, amount: `${parts.negative ? '−' : '+'}${parts.digits}`, in: !parts.negative };
            }),
            spoken: forecast.flows
              .slice(0, 3)
              .map((flow) => `${displayDate(flow.date)}, ${flow.description}, ${amountParts(flow.amount, flow.currency).spoken}`)
              .join('. '),
          },
        }
      : {}),
    ...(days !== undefined ? { payday: { days, unit: t.days(days), share: Math.min(1, Math.max(0, 1 - days / 31)), spoken: t.daysSpoken(days) } } : {}),
    colors: options.colors,
    open: t.open,
  };
}
