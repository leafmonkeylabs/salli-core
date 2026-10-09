/**
 * salli ledger trial-balance | income-statement, and salli tags list
 */
import { Option, type Command } from '@commander-js/extra-typings';
import { compareAmounts, ledgerIncomeStatement, ledgerTrialBalance, tagsList } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import type { IncomeStatement, TagList, TrialBalance } from '../api-types';
import { UsageError } from '../errors';
import { displayWidth, padEnd, padStart, singleLine } from '../output/text';
import { displayRange, isoDate, monthPeriod, parseDate } from '../util/dates';
import { AccountBook } from './shared';

export function registerLedger(program: Command, app: App): void {
  const ledger = program.command('ledger').description('Ledger reports: trial balance and income statement');

  ledger
    .command('trial-balance')
    .alias('tb')
    .description('Every account’s balance; debits and credits net to zero')
    .option('--from <date>', 'From this date (YYYY-MM-DD)')
    .option('--to <date>', 'Up to this date')
    .action(async (opts) => {
      const now = app.runtime.now();
      const api = await app.api();
      const [tb, book] = await Promise.all([
        api.call(ledgerTrialBalance, {
          query: {
            ...(opts.from ? { from_date: parseDate(opts.from, now, '--from') } : {}),
            ...(opts.to ? { to_date: parseDate(opts.to, now, '--to') } : {}),
          },
        }) as Promise<TrialBalance>,
        AccountBook.load(api),
      ]);
      const rows = Object.entries(tb.balances)
        .map(([id, balance]) => ({ account_id: id, code: book.get(id)?.code ?? '', name: book.name(id), balance }))
        .sort((a, b) => a.code.localeCompare(b.code));
      app.out.emit(tb, {
        records: () => rows.map((r) => ({ ...r, currency: tb.currency })),
        human: () => {
          if (rows.length === 0) {
            app.out.note('No entries yet.');
            return;
          }
          const c = app.out.colors;
          const table = app.out.table([...rows, { account_id: '', code: '', name: 'Net', balance: tb.net }], [
            { header: 'CODE', get: (r) => r.code },
            { header: 'ACCOUNT', get: (r) => r.name, shrink: true, style: (t, r) => (r.account_id ? t : c.bold(t)) },
            {
              header: `BALANCE (${tb.currency})`,
              get: (r) => app.out.amount(r.balance, tb.currency),
              align: 'right',
              style: (t, r) => (r.account_id ? t : c.bold(t)),
            },
          ]);
          app.out.line(table);
          app.out.note('Debit balances are positive, credit balances negative.');
        },
      });
    });

  ledger
    .command('income-statement')
    .alias('pl')
    .description('Income and expenses for a period, and what was left (default: this month)')
    .option('--month <yyyy-mm>', 'A calendar month')
    .option('--from <date>', 'From this date')
    .option('--to <date>', 'Up to this date (default: today)')
    .action(async (opts) => {
      const now = app.runtime.now();
      if (opts.month && (opts.from || opts.to)) throw new UsageError('Pass --month, or --from/--to, not both.');
      const period = opts.month
        ? monthPeriod(opts.month, now, app.out.locale)
        : opts.from
          ? { from: parseDate(opts.from, now, '--from'), to: opts.to ? parseDate(opts.to, now, '--to') : isoDate(now) }
          : monthPeriod(undefined, now, app.out.locale);
      const api = await app.api();
      const statement = (await api.call(ledgerIncomeStatement, {
        query: { from_date: period.from, to_date: period.to },
      })) as IncomeStatement;
      const lines = [
        ...Object.entries(statement.income).map(([name, amount]) => ({ kind: 'income', name, amount })),
        ...Object.entries(statement.expenses).map(([name, amount]) => ({ kind: 'expense', name, amount })),
      ];
      app.out.emit(statement, {
        records: () => lines.map((l) => ({ ...l, currency: statement.currency })),
        human: () => {
          const out = app.out;
          const c = out.colors;
          const cur = statement.currency;
          out.line(
            `${out.heading('Income statement')} ${c.dim(`· ${displayRange(statement.from_date, statement.to_date, out.locale)} · ${cur}`)}`,
          );
          const byAmount = (items: Record<string, string>) => Object.entries(items).sort(([, a], [, b]) => compareAmounts(b, a));
          const income = byAmount(statement.income).map(([name, amount]) => [singleLine(name), out.amount(amount, cur)] as const);
          const expenses = byAmount(statement.expenses).map(([name, amount]) => [singleLine(name), out.amount(amount, cur)] as const);
          const net = out.amount(statement.net_income, cur);
          const nameWidth = Math.max(12, ...[...income, ...expenses].map(([name]) => displayWidth(name) + 2));
          const amountWidth = Math.max(displayWidth(net), ...[...income, ...expenses].map(([, amount]) => displayWidth(amount)));
          const lines: string[] = [];
          const section = (title: string, items: ReadonlyArray<readonly [string, string]>): void => {
            lines.push(c.bold(title));
            if (items.length === 0) lines.push(c.dim('  none'));
            for (const [name, amount] of items) lines.push(`  ${padEnd(name, nameWidth - 2)}  ${padStart(amount, amountWidth)}`);
          };
          section('Income', income);
          section('Expenses', expenses);
          lines.push('');
          lines.push(`${c.bold(padEnd('Net income', nameWidth))}  ${c.bold(out.signed(padStart(net, amountWidth), statement.net_income))}`);
          out.line(lines.join('\n'));
        },
      });
    });

  program
    .command('tags')
    .description('Tags you can put on postings (categories and needs)')
    .command('list', { isDefault: true })
    .description('List tags')
    .addOption(new Option('--kind <kind>', 'Only one axis').choices(['category', 'need']))
    .action(async (opts) => {
      const api = await app.api();
      const data = (await api.call(tagsList, { query: opts.kind ? { kind: opts.kind as 'category' | 'need' } : {} })) as TagList;
      app.out.emit(data, {
        records: (d) => d.tags,
        human: (d) => {
          if (d.tags.length === 0) {
            app.out.note('No tags yet. Tag a posting with `salli entries tag`.');
            return;
          }
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.tags, [
              { header: 'AXIS', get: (t) => t.kind },
              { header: 'SLUG', get: (t) => t.slug },
              { header: 'NAME', get: (t) => t.name, shrink: true },
              { header: '', get: (t) => (t.is_system ? 'built-in' : ''), style: (t) => c.dim(t) },
            ]),
          );
        },
      });
    });
}
