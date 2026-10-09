/**
 * salli status: your finances on one screen.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  compareAmounts,
  fiScoreGet,
  isAbortError,
  ledgerIncomeStatement,
  remindersList,
  reportsBalanceSheet,
  SalliApiError,
  SalliNetworkError,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { problemFor } from '../errors';
import { displayWidth, padEnd, padStart, singleLine, truncate } from '../output/text';
import { displayDate, displayRange, isoDate, monthPeriod, monthToDate } from '../util/dates';

/** "budget_overspend" → "Budget overspend". */
export function humanize(kind: string): string {
  const text = singleLine(kind.replace(/_/g, ' '));
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function fatal(error: unknown): boolean {
  return (
    error instanceof SalliNetworkError ||
    isAbortError(error) ||
    (error instanceof SalliApiError && (error.status === 401 || error.status === 403))
  );
}

export function registerStatus(program: Command, app: App): void {
  program
    .command('status')
    .description('Your finances on one screen: net worth, this month, FI score, what is due')
    .option('--month <yyyy-mm>', 'Show this month instead of the current one (to date)')
    .action(async (opts) => {
      const api = await app.api();
      const ctx = await app.context();
      const now = app.runtime.now();
      const period = opts.month ? monthPeriod(opts.month, now, app.out.locale) : monthToDate(now, app.out.locale);

      const settled = await Promise.allSettled([
        api.call(reportsBalanceSheet),
        api.call(ledgerIncomeStatement, { query: { from_date: period.from, to_date: period.to } }),
        api.call(fiScoreGet),
        api.call(remindersList, { query: { status: 'pending' } }),
      ]);
      const failure = settled.find((s): s is PromiseRejectedResult => s.status === 'rejected' && fatal(s.reason));
      if (failure) throw failure.reason;

      const unavailable: Record<string, unknown> = {};
      const value = <T>(settledResult: PromiseSettledResult<T>, name: string): T | null => {
        if (settledResult.status === 'fulfilled') return settledResult.value;
        unavailable[name] = problemFor(settledResult.reason);
        return null;
      };
      const balanceSheet = value(settled[0], 'balance_sheet');
      const income = value(settled[1], 'income_statement');
      const fi = value(settled[2], 'fi_score');
      const reminders = value(settled[3], 'reminders');

      const result = {
        context: ctx.name,
        server: ctx.server,
        period: { from: period.from, to: period.to },
        balance_sheet: balanceSheet,
        income_statement: income,
        fi_score: fi,
        reminders,
        ...(Object.keys(unavailable).length ? { unavailable } : {}),
      };

      app.out.emit(result, {
        human: () => {
          const out = app.out;
          const c = out.colors;
          const lines: string[] = [];
          const label = (text: string, indent = 0): string => padEnd(`${' '.repeat(indent)}${text}`, 16);
          // Amounts of a block share a currency: the code once, the numbers right-aligned.
          const block = (currency: string, rows: Array<[string, string, number, boolean?]>): void => {
            const shown = rows.map(([text, amount, indent, strong]) => [text, out.amount(amount, currency), indent, strong, amount] as const);
            const width = Math.max(...shown.map(([, amount]) => displayWidth(amount)));
            for (const [text, amount, indent, strong, raw] of shown) {
              const value = out.signed(`${currency} ${padStart(amount, width)}`, raw);
              lines.push(`${label(strong ? c.bold(text) : text, indent)}${strong ? c.bold(value) : value}`);
            }
          };

          lines.push(c.dim(`Salli · ${ctx.name} · ${ctx.server}`), '');

          if (balanceSheet) {
            block(balanceSheet.currency, [
              ['Net worth', balanceSheet.net_worth, 0, true],
              ['Assets', balanceSheet.total_assets, 2],
              ['Liabilities', balanceSheet.total_liabilities, 2],
            ]);
          } else {
            lines.push(`${label('Net worth')}${c.dim('unavailable')}`);
          }
          lines.push('');

          const toDate = period.to === isoDate(now);
          lines.push(c.bold(`${period.label}${toDate ? ' so far' : ''}`) + c.dim(` (${displayRange(period.from, period.to, out.locale)})`));
          if (income && income.lines.length) {
            const cur = income.currency;
            block(cur, [
              ['Income', income.total_income, 2],
              ['Spending', income.total_expenses, 2],
              ['Net income', income.net_income, 2, true],
            ]);
            const spending = income.lines.filter((l) => l.type === 'expense').sort((a, b) => compareAmounts(b.amount, a.amount));
            if (spending.length) {
              const room = Number.isFinite(out.width) ? out.width - 16 : Number.POSITIVE_INFINITY;
              const top = spending.slice(0, 3).map((l) => `${singleLine(l.name)} ${out.amount(l.amount, cur)}`);
              const text = top.join(' · ') + (spending.length > 3 ? ` · +${spending.length - 3} more` : '');
              lines.push(`${label('Most on', 2)}${truncate(text, room)}`);
            }
          } else if (income) {
            lines.push(`  ${c.dim('Nothing recorded yet this month.')}`);
          } else {
            lines.push(`  ${c.dim('unavailable')}`);
          }
          lines.push('');

          if (fi) {
            const progress = out.percent(fi.progress_to_fi);
            lines.push(`${label(c.bold('FI score'))}${singleLine(fi.overall_score)} (${singleLine(fi.grade)}) · ${progress} of the way to financial independence`);
            lines.push(`${label('Savings rate', 2)}${out.percent(fi.savings_rate)} of income`);
            if (fi.projected_fi_date) lines.push(`${label('FI by', 2)}${displayDate(fi.projected_fi_date, out.locale)}`);
            lines.push('');
          }

          const pending = (reminders?.reminders ?? [])
            .filter((r) => r.status === 'pending')
            .sort((a, b) => a.due_date.localeCompare(b.due_date));
          lines.push(c.bold('Coming up'));
          if (pending.length === 0) lines.push(`  ${c.dim(reminders ? 'Nothing due.' : 'unavailable')}`);
          const today = isoDate(now);
          for (const r of pending.slice(0, 5)) {
            const overdue = r.due_date < today;
            const when = displayDate(r.due_date, out.locale).padEnd(12);
            const flag = r.severity === 'critical' ? c.red('!') : r.severity === 'warning' ? c.yellow('!') : ' ';
            const note = overdue ? c.red('overdue') : r.severity ? c.dim(r.severity) : '';
            lines.push(`${flag} ${overdue ? c.red(when) : when}  ${singleLine(humanize(r.kind)).padEnd(28)}${note}`.trimEnd());
          }
          if (pending.length > 5) lines.push(c.dim(`  +${pending.length - 5} more: salli reminders list`));

          out.line(lines.join('\n'));
          for (const [name] of Object.entries(unavailable)) out.note(`(${name.replace('_', ' ')} unavailable)`);
        },
      });
    });
}
