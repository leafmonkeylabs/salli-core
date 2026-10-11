/**
 * salli baseline
 *
 * Your money as of a day: the one model Salli computes FI, insights, the
 * forecast and the debt plan from, with the definitions behind it (the
 * months averaged, the exchange rates and their source, each account's role,
 * the assumptions and which are placeholders). Every figure is the server's.
 */
import type { Command } from '@commander-js/extra-typings';
import { baselineGet, type Baseline } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { plural, singleLine } from '../output/text';
import { displayDate, displayMonth, parseDate } from '../util/dates';
import { countArg } from './shared';

const ROLES: Record<Baseline['balances'][number]['role'], string> = {
  cash: 'cash',
  investment: 'investment',
  other_asset: 'other asset',
  liability: 'liability',
};

const PLACEHOLDERS: Record<Baseline['placeholders'][number], string> = {
  real_return: 'the real return',
  safe_withdrawal_rate: 'the safe withdrawal rate',
  surplus_invested: 'the share of your monthly surplus invested (all of it)',
  inflation: 'inflation (none set: nominal amounts keep their real value)',
};

/** The monthly timeline's point a whole number of years on: points are the
 * as-of date, then each month's end from the as-of month's. */
function yearsOn(points: Baseline['monthly']['points'], years: number): Baseline['monthly']['points'][number] | undefined {
  return points[years * 12 + 1];
}

export function registerBaseline(program: Command, app: App): void {
  program
    .command('baseline')
    .description('Your money as of a day, and the definitions every figure uses')
    .option('--as-of <date>', 'The day to see it as of (YYYY-MM-DD; default today)')
    .option('--years <n>', 'How far the monthly timeline runs (1 to 50, default 30)', countArg('--years'))
    .option('--daily', 'Include every day of the cash timeline (with --json)')
    .addHelpText(
      'after',
      `
Income and spending are netted per calendar month and averaged over the full
months observed (at most twelve). Balances in other currencies are valued at
the published rate for the as-of date. The monthly timeline is in today's
money: the share of each month's surplus you invest goes into your
investments, which grow at your real return; the rest stays in cash, which
earns nothing; debts follow their schedules, and their payments join the
surplus once each is paid off.

Examples:
  $ salli baseline
  $ salli baseline --as-of 2026-06-30 --years 20
  $ salli baseline --json`,
    )
    .action(async (opts) => {
      const api = await app.api();
      const asOf = opts.asOf ? parseDate(opts.asOf, app.runtime.now(), '--as-of') : undefined;
      const data = await api.call(baselineGet, {
        query: {
          ...(asOf ? { as_of: asOf } : {}),
          ...(opts.years ? { horizon_years: opts.years } : {}),
          daily: Boolean(opts.daily),
        },
      });
      app.out.emit(data, {
        records: (d) => d.monthly.points,
        human: (d) => {
          const out = app.out;
          const c = out.colors;
          const cur = d.currency;
          const f = d.flows;
          out.line(out.heading(`Baseline as of ${displayDate(d.as_of, out.locale)}`) + ` ${c.dim(`in ${cur}`)}`);
          out.line();

          const months = d.months_observed;
          out.line(
            out.details([
              [
                'Averaged over',
                months.length
                  ? `${plural(months.length, 'full month')}, ${displayMonth(months[0], out.locale)} to ${displayMonth(months[months.length - 1], out.locale)}`
                  : 'no full month yet',
              ],
              ['Income', `${out.money(f.monthly_income, cur)} a month`],
              ['Spending', `${out.money(f.monthly_expenses, cur)} a month`],
              ['Left over', out.signed(`${out.money(f.monthly_surplus, cur)} a month`, f.monthly_surplus)],
              ['Saved', f.savings_rate === null ? '—' : out.percent(f.savings_rate)],
              f.essential_monthly === null ? false : ['Essential', `${out.money(f.essential_monthly, cur)} a month`],
            ]),
          );
          out.line();

          out.line(
            out.table(d.balances, [
              { header: 'ACCOUNT', get: (b) => `${b.code} ${b.name}`, shrink: true },
              { header: 'ROLE', get: (b) => ROLES[b.role] + (b.in_cash && b.role !== 'cash' ? ' (cash)' : '') },
              { header: 'BALANCE', get: (b) => (b.amount === null ? '—' : out.money(b.amount, b.currency)), align: 'right' },
              { header: `VALUE (${cur})`, get: (b) => (b.value === null ? '—' : out.amount(b.value, cur)), align: 'right' },
            ]),
          );
          for (const r of d.rates) {
            out.note(
              r.rate === null
                ? `No published ${r.currency} rate for ${displayDate(d.as_of, out.locale)}: those balances are left out of the totals.`
                : `${r.currency} at ${r.rate} ${cur}, published by ${singleLine(r.source ?? 'an unnamed source')} for ${displayDate(r.as_of ?? d.as_of, out.locale)}.`,
            );
          }
          const t = d.totals;
          out.line();
          out.line(
            out.details([
              ['Cash', out.money(t.cash, cur)],
              ['Investments', out.money(t.investments, cur)],
              ['Other assets', out.money(t.other_assets, cur)],
              ['Debts', out.money(t.debts, cur)],
              ['Other liabilities', out.money(t.other_liabilities, cur)],
              ['Net worth', out.signed(out.money(t.net_worth, cur), t.net_worth)],
            ]),
          );

          if (d.debts.length) {
            out.line();
            out.line(
              out.table(d.debts, [
                { header: 'DEBT', get: (x) => x.name, shrink: true },
                { header: 'OWES', get: (x) => out.amount(x.balance, cur), align: 'right' },
                { header: 'FROM', get: (x) => (x.source === 'account' ? 'its account' : 'declared') },
                { header: 'RATE', get: (x) => out.percent(x.apr, 2), align: 'right' },
                { header: 'PAID OFF', get: (x) => (x.paid_off ? displayMonth(x.paid_off, out.locale) : 'not within the horizon') },
              ]),
            );
          }

          const cash = d.cash;
          out.line();
          out.line(
            out.details([
              ['Cash today', out.money(cash.today, cur)],
              ['Lowest ahead', `${out.signed(out.money(cash.lowest, cur), cash.lowest)} on ${displayDate(cash.lowest_date, out.locale)}`],
              [`By ${displayDate(cash.end, out.locale)}`, out.money(cash.month_ends[cash.month_ends.length - 1]?.cash ?? cash.today, cur)],
            ]),
          );

          const points = d.monthly.points;
          const marks = [1, 5, 10, 20, d.monthly.horizon_years]
            .filter((y, i, all) => y <= d.monthly.horizon_years && all.indexOf(y) === i)
            .map((y) => ({ years: y, point: yearsOn(points, y) }))
            .filter((m): m is { years: number; point: Baseline['monthly']['points'][number] } => m.point !== undefined);
          if (marks.length) {
            out.line();
            out.line(
              out.table(marks, [
                { header: 'IN', get: (m) => plural(m.years, 'year') },
                { header: 'MONTH', get: (m) => displayMonth(m.point.month, out.locale) },
                { header: `NET WORTH (${cur})`, get: (m) => out.amount(m.point.net_worth, cur), align: 'right' },
                { header: 'CASH', get: (m) => out.amount(m.point.cash, cur), align: 'right' },
                { header: 'INVESTMENTS', get: (m) => out.amount(m.point.investments, cur), align: 'right' },
                { header: 'DEBTS', get: (m) => out.amount(m.point.debts, cur), align: 'right' },
              ]),
            );
            out.note(
              `In today's money. ${out.percent(d.monthly.surplus_invested, 0)} of each month's surplus invested, at ${out.percent(d.monthly.real_return, 2)} a year after inflation.`,
            );
          }

          if (d.placeholders.length) {
            out.note(
              `Placeholders: ${d.placeholders.map((p) => PLACEHOLDERS[p]).join('; ')}. Set yours with \`salli fi assumptions set\`.`,
            );
          }
          for (const n of d.notes) out.note(singleLine(n));
        },
      });
    });
}
