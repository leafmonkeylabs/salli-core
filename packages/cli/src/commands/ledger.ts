/**
 * salli ledger trial-balance | income-statement | unrealised-fx | revalue | lock | unlock |
 * close-year | retained-earnings | verify, and salli tags list
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  compareAmounts,
  ledgerCloseYear,
  ledgerIncomeStatement,
  ledgerLockDateSet,
  ledgerFxRevaluationPost,
  ledgerRetainedEarningsSet,
  ledgerTrialBalance,
  ledgerUnrealisedFx,
  ledgerVerify,
  tagsList,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { displayWidth, padEnd, padStart, singleLine } from '../output/text';
import { displayDate, displayRange, isoDate, monthPeriod, parseDate } from '../util/dates';
import { AccountBook } from './shared';

export function registerLedger(program: Command, app: App): void {
  const ledger = program.command('ledger').description('Ledger reports, and closing the books up to a day');

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
        }),
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
      const statement = await api.call(ledgerIncomeStatement, {
        query: { from_date: period.from, to_date: period.to },
      });
      const { lines } = statement;
      app.out.emit(statement, {
        records: () => lines.map((l) => ({ ...l, currency: statement.currency })),
        human: () => {
          const out = app.out;
          const c = out.colors;
          const cur = statement.currency;
          out.line(
            `${out.heading('Income statement')} ${c.dim(`· ${displayRange(statement.from_date, statement.to_date, out.locale)} · ${cur}`)}`,
          );
          const rows = (type: 'income' | 'expense') =>
            lines
              .filter((l) => l.type === type)
              .sort((a, b) => compareAmounts(b.amount, a.amount))
              .map((l) => [singleLine(`${l.code} ${l.name}`) + (l.is_active ? '' : ' (closed)'), out.amount(l.amount, cur)] as const);
          const income = rows('income');
          const expenses = rows('expense');
          const totalIncome = out.amount(statement.total_income, cur);
          const totalExpenses = out.amount(statement.total_expenses, cur);
          const net = out.amount(statement.net_income, cur);
          const named = [...income, ...expenses];
          const nameWidth = Math.max('Total expenses'.length + 2, ...named.map(([name]) => displayWidth(name) + 2));
          const amountWidth = Math.max(...[totalIncome, totalExpenses, net, ...named.map(([, amount]) => amount)].map((a) => displayWidth(a)));
          const text: string[] = [];
          const section = (title: string, items: ReadonlyArray<readonly [string, string]>, total: string): void => {
            text.push(c.bold(title));
            if (items.length === 0) text.push(c.dim('  none'));
            for (const [name, amount] of items) text.push(`  ${padEnd(name, nameWidth - 2)}  ${padStart(amount, amountWidth)}`);
            text.push(`  ${padEnd(`Total ${title.toLowerCase()}`, nameWidth - 2)}  ${padStart(total, amountWidth)}`);
            text.push('');
          };
          section('Income', income, totalIncome);
          section('Expenses', expenses, totalExpenses);
          text.push(`${c.bold(padEnd('Net income', nameWidth))}  ${c.bold(out.signed(padStart(net, amountWidth), statement.net_income))}`);
          out.line(text.join('\n'));
        },
      });
    });

  ledger
    .command('unrealised-fx')
    .description('Foreign-currency accounts revalued at a day’s rate against what they cost: computed, not posted')
    .option('--as-of <date>', 'The day (default: today)', 'today')
    .action(async (opts) => {
      const api = await app.api();
      const fx = await api.call(ledgerUnrealisedFx, { query: { as_of: parseDate(opts.asOf, app.runtime.now(), '--as-of') } });
      app.out.emit(fx, {
        records: (d) => d.lines.map((l) => ({ ...l, currency: d.currency })),
        human: (d) => {
          const out = app.out;
          if (d.lines.length)
            out.line(
              out.table(d.lines, [
                { header: 'ACCOUNT', get: (l) => singleLine(`${l.code} ${l.name}`), shrink: true },
                { header: 'BALANCE', get: (l) => out.amount(l.balance, l.account_currency), align: 'right' },
                { header: `COST (${d.currency})`, get: (l) => out.amount(l.cost, d.currency), align: 'right' },
                { header: `VALUE (${d.currency})`, get: (l) => out.amount(l.value, d.currency), align: 'right' },
                { header: 'GAIN', get: (l) => out.amount(l.gain, d.currency), align: 'right' },
              ]),
            );
          out.line(`Unrealised ${out.amount(d.total, d.currency)} · posted ${out.amount(d.posted, d.currency)} · not posted ${out.amount(d.unposted, d.currency)}`);
          for (const note of d.notes) out.warn(note);
        },
      });
    });

  ledger
    .command('revalue')
    .argument('<date>', 'A month’s last day, before today')
    .description('Post the unrealised exchange gain or loss not yet booked, at a period’s end')
    .action(async (date) => {
      const api = await app.api();
      const posted = await api.call(ledgerFxRevaluationPost, { body: { as_of: parseDate(date, app.runtime.now(), '<date>') } });
      app.out.emit(posted, {
        human: (d) => (d.entry_id ? app.out.success(`Posted the revaluation (entry ${d.entry_id.slice(0, 8)}).`) : app.out.note('Nothing left to post.')),
      });
    });

  ledger
    .command('lock')
    .argument('<date>', 'The last day to close (YYYY-MM-DD), before today')
    .description('Close the books up to and including a day: nothing on or before it is posted, reversed, changed or retagged')
    .action(async (date) => {
      const api = await app.api();
      const lock = await api.call(ledgerLockDateSet, { body: { lock_date: parseDate(date, app.runtime.now(), '<date>') } });
      app.out.emit(lock, { human: () => app.out.success(`The books are closed up to and including ${displayDate(lock.lock_date, app.out.locale)}.`) });
    });

  ledger
    .command('unlock')
    .description('Open every closed day again (your own sign-in only)')
    .action(async () => {
      const api = await app.api();
      const lock = await api.call(ledgerLockDateSet, { body: { lock_date: null } });
      app.out.emit(lock, { human: () => app.out.success('The books are open: no day is closed.') });
    });

  ledger
    .command('close-year')
    .argument('<date>', 'The last day of the year to close (YYYY-MM-DD)')
    .description('Move the year’s income and expenses to retained earnings, in one entry on that day')
    .action(async (date) => {
      const api = await app.api();
      const closed = await api.call(ledgerCloseYear, { body: { period_end: parseDate(date, app.runtime.now(), '<date>') } });
      app.out.emit(closed, {
        human: (d) =>
          app.out.success(
            `Closed to ${displayDate(d.period_end, app.out.locale)}: ${app.out.amount(d.earnings, d.currency)} ${d.currency} moved to retained earnings.`,
          ),
      });
    });

  ledger
    .command('retained-earnings')
    .argument('<account>', 'An equity account (code or id)')
    .description('Say which equity account a year-end close moves earnings to')
    .action(async (account) => {
      const api = await app.api();
      const book = await AccountBook.load(api);
      const { id } = book.resolve(account);
      await api.call(ledgerRetainedEarningsSet, { body: { account_id: id } });
      app.out.done({ account_id: id }, `${singleLine(book.name(id))} now holds retained earnings.`);
    });

  ledger
    .command('verify')
    .description('Check every entry is as it was posted (the ledger’s hash chain)')
    .action(async () => {
      const api = await app.api();
      const check = await api.call(ledgerVerify, {});
      app.out.emit(check, {
        human: (d) => {
          if (d.ok) {
            app.out.success(`All ${d.checked} entries are as they were posted.`);
            return;
          }
          const b = d.first_break;
          const why = { missing: 'an entry before it is missing', link: 'it does not follow the entry before it', content: 'it changed after it was posted' };
          app.out.warn(b ? `The chain breaks at entry ${b.seq} (${b.entry_id.slice(0, 8)}): ${why[b.reason]}.` : 'The chain breaks.');
          app.out.note(`${d.checked} entries before it check out.`);
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
      const data = await api.call(tagsList, { query: opts.kind ? { kind: opts.kind as 'category' | 'need' } : {} });
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
