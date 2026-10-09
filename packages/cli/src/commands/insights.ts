/**
 * salli insights cash-flow | spending | net-worth | recurring | forecast | safe-to-spend | signals
 *
 * What the ledger says about where you stand and where you are heading,
 * every figure computed by the server.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  insightsCashFlow,
  insightsForecast,
  insightsNetWorth,
  insightsRecurring,
  insightsSafeToSpend,
  insightsSignals,
  insightsSpending,
  isNegativeAmount,
  type FinanceSignal,
  type SafeToSpend,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import type { Output } from '../output/output';
import { plural, singleLine } from '../output/text';
import { displayDate, displayMonth } from '../util/dates';
import { AccountBook, countArg } from './shared';

const AXES = ['category', 'account', 'need'] as const;

const SEVERITY_MARK: Record<FinanceSignal['severity'], string> = { high: '!', medium: '!', info: '•' };

/** A signal as one or two lines, coloured by how pressing it is. */
export function signalLines(out: Output, signal: FinanceSignal, indent = ''): string[] {
  const c = out.colors;
  const colour = signal.severity === 'high' ? c.red : signal.severity === 'medium' ? c.yellow : c.cyan;
  return [`${indent}${colour(SEVERITY_MARK[signal.severity])} ${c.bold(singleLine(signal.title))}`, `${indent}  ${singleLine(signal.detail)}`];
}

/** The headline of safe-to-spend: the amount, and until when. */
export function safeToSpendLine(out: Output, s: SafeToSpend): string {
  const until = s.next_income
    ? `until ${displayDate(s.next_income.date, out.locale)}, when ${singleLine(s.next_income.description)} comes in`
    : `for the next 30 days (to ${displayDate(s.until, out.locale)})`;
  return `${out.signed(out.money(s.amount, s.currency), s.amount)} ${until}`;
}

export function registerInsights(program: Command, app: App): void {
  const insights = program
    .command('insights')
    .alias('insight')
    .description('Where your money goes and where it is heading: cash flow, spending, forecast, signals');

  insights
    .command('cash-flow')
    .description('Income, spending, what was left and the savings rate, month by month')
    .option('-m, --months <n>', 'Months, ending this one (default 12)', countArg('--months'))
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(insightsCashFlow, { query: opts.months ? { months: opts.months } : {} });
      app.out.emit(data, {
        records: (d) => d.months,
        human: (d) => {
          const out = app.out;
          const cur = d.currency;
          out.line(
            out.table(d.months, [
              { header: 'MONTH', get: (m) => displayMonth(m.month, out.locale) },
              { header: `INCOME (${cur})`, get: (m) => out.amount(m.income, cur), align: 'right' },
              { header: 'SPENDING', get: (m) => out.amount(m.expenses, cur), align: 'right' },
              { header: 'LEFT OVER', get: (m) => out.amount(m.net, cur), align: 'right', style: (t, m) => out.signed(t, m.net) },
              { header: 'SAVED', get: (m) => (m.savings_rate === null ? '—' : out.percent(m.savings_rate)), align: 'right' },
            ]),
          );
        },
      });
    });

  insights
    .command('spending')
    .description('Where the money went, largest first')
    .option('-m, --months <n>', 'Months, ending this one (default 3)', countArg('--months'))
    .addOption(new Option('--by <axis>', 'Group by').choices(AXES).default('category' as const))
    .action(async (opts) => {
      const api = await app.api();
      const [data, book] = await Promise.all([
        api.call(insightsSpending, { query: { by: opts.by, ...(opts.months ? { months: opts.months } : {}) } }),
        opts.by === 'account' ? AccountBook.load(api) : Promise.resolve(undefined),
      ]);
      app.out.emit(data, {
        records: (d) => d.lines,
        human: (d) => {
          const out = app.out;
          if (!d.lines.length) return out.note('No spending in that period.');
          const cur = d.currency;
          const first = d.months[0];
          const last = d.months.at(-1);
          out.line(out.colors.dim(`By ${d.by}, ${displayMonth(first, out.locale)} to ${displayMonth(last, out.locale)}, in ${cur}`));
          out.line(
            out.table(d.lines, [
              { header: d.by.toUpperCase(), get: (l) => (book ? book.label(l.key) : l.key), shrink: true },
              { header: 'TOTAL', get: (l) => out.amount(l.total, cur), align: 'right' },
              { header: 'SHARE', get: (l) => (l.share === null ? '—' : out.percent(l.share)), align: 'right' },
            ]),
          );
        },
      });
    });

  insights
    .command('net-worth')
    .description('What you own less what you owe, at the end of each month')
    .option('-m, --months <n>', 'Month ends to show (default 24)', countArg('--months'))
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(insightsNetWorth, { query: opts.months ? { months: opts.months } : {} });
      app.out.emit(data, {
        records: (d) => d.points,
        human: (d) => {
          const out = app.out;
          const cur = d.currency;
          out.line(
            out.table(d.points, [
              { header: 'MONTH', get: (p) => displayMonth(p.month, out.locale) },
              { header: `ASSETS (${cur})`, get: (p) => out.amount(p.assets, cur), align: 'right' },
              { header: 'LIABILITIES', get: (p) => out.amount(p.liabilities, cur), align: 'right' },
              { header: 'NET WORTH', get: (p) => out.amount(p.net_worth, cur), align: 'right', style: (t, p) => out.signed(t, p.net_worth) },
            ]),
          );
        },
      });
    });

  insights
    .command('recurring')
    .description('Payments that keep coming back, and whether you track them as subscriptions')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(insightsRecurring);
      app.out.emit(data, {
        records: (d) => d.items,
        human: (d) => {
          const out = app.out;
          if (!d.items.length) return out.note('No recurring payments found yet.');
          out.line(
            out.table(d.items, [
              { header: 'PAYEE', get: (r) => r.payee, shrink: true },
              { header: 'EVERY', get: (r) => r.cadence.replace(/ly$/, '').replace('dai', 'day') },
              { header: 'TYPICAL', get: (r) => `${r.varies ? '~' : ''}${out.money(r.typical_amount, r.currency)}`, align: 'right' },
              { header: 'NEXT', get: (r) => displayDate(r.next_expected, out.locale) },
              { header: 'TRACKED', get: (r) => (r.tracked ? 'yes' : 'no'), style: (t, r) => (r.tracked ? t : out.colors.yellow(t)) },
            ]),
          );
          const untracked = d.items.filter((r) => !r.tracked).length;
          if (untracked) {
            out.note(`${untracked} not tracked: add one with \`salli subscriptions add\` to be told when it is missed or its price changes.`);
          }
        },
      });
    });

  insights
    .command('forecast')
    .description('Where your cash is heading: the lowest point, and what moves it')
    .option('-d, --days <n>', 'How many days ahead (default 60)', countArg('--days'))
    .option('--flows <n>', 'How many upcoming flows to list', countArg('--flows'), 10)
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(insightsForecast, { query: opts.days ? { days: opts.days } : {} });
      app.out.emit(data, {
        records: (d) => d.flows,
        human: (d) => {
          const out = app.out;
          const c = out.colors;
          const cur = d.currency;
          out.line(`Cash today ${out.money(d.today, cur)}; on ${displayDate(d.end, out.locale)} ${out.money(d.end_balance, cur)}.`);
          const low = `Lowest: ${out.money(d.lowest, cur)} on ${displayDate(d.lowest_date, out.locale)}`;
          out.line(isNegativeAmount(d.lowest) ? c.red(low) : low);
          if (d.accounts.length) {
            out.line();
            out.line(
              out.table(d.accounts, [
                { header: 'ACCOUNT', get: (a) => a.name, shrink: true },
                { header: 'TODAY', get: (a) => out.money(a.today, a.currency), align: 'right' },
                { header: 'LOWEST', get: (a) => out.money(a.lowest, a.currency), align: 'right', style: (t, a) => out.signed(t, a.lowest) },
                { header: 'ON', get: (a) => displayDate(a.lowest_date, out.locale) },
                { header: 'AT THE END', get: (a) => out.money(a.end, a.currency), align: 'right' },
              ]),
            );
          }
          const upcoming = d.flows.slice(0, opts.flows);
          if (upcoming.length) {
            out.line();
            out.line(out.heading('Coming up'));
            out.line(
              out.table(upcoming, [
                { header: 'DATE', get: (f) => displayDate(f.date, out.locale) },
                { header: 'WHAT', get: (f) => f.description + (f.source === 'subscription' ? ' (declared)' : ''), shrink: true },
                { header: 'AMOUNT', get: (f) => out.money(f.amount, f.currency), align: 'right', style: (t, f) => out.signed(t, f.amount) },
              ]),
            );
          }
          for (const note of d.notes ?? []) out.note(singleLine(note));
        },
      });
    });

  insights
    .command('safe-to-spend')
    .description('What could go out today without your cash running out before payday')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(insightsSafeToSpend);
      app.out.emit(data, {
        records: (d) => d.committed,
        human: (d) => {
          const out = app.out;
          out.line(`${out.heading('Safe to spend')} ${safeToSpendLine(out, d)}`);
          out.line(out.colors.dim(`Cash today ${out.money(d.cash_today, d.currency)}; ${plural(d.committed.length, 'payment')} expected before then.`));
          if (d.committed.length) {
            out.line(
              out.table(d.committed, [
                { header: 'DATE', get: (f) => displayDate(f.date, out.locale) },
                { header: 'WHAT', get: (f) => f.description, shrink: true },
                { header: 'AMOUNT', get: (f) => out.money(f.amount, f.currency), align: 'right' },
              ]),
            );
          }
          for (const note of d.notes) out.note(singleLine(note));
        },
      });
    });

  insights
    .command('signals')
    .description('What in your finances needs your attention now')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(insightsSignals);
      app.out.emit(data, {
        records: (d) => d.signals,
        human: (d) => {
          if (!d.signals.length) return app.out.success('Nothing needs your attention.');
          for (const signal of d.signals) app.out.line(signalLines(app.out, signal).join('\n'));
        },
      });
    });
}
