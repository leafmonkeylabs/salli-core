/**
 * Budgets, debts, investments, subscriptions and insurance: thin wrappers
 * over the API, each with a table for people and the API's JSON for
 * scripts.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  budgetsCreate,
  budgetsDelete,
  budgetsGet,
  budgetsList,
  budgetsSummary,
  budgetsUpdate,
  debtsCreate,
  debtsDelete,
  debtsGet,
  debtsList,
  debtsPayoffPlan,
  debtsUpdate,
  holdingsCreate,
  holdingsDelete,
  holdingsGet,
  holdingsList,
  holdingsUpdate,
  insurancePoliciesCreate,
  insurancePoliciesDelete,
  insurancePoliciesGet,
  insurancePoliciesList,
  insurancePoliciesUpdate,
  insuranceReport,
  insuranceTargetsDelete,
  insuranceTargetsList,
  insuranceTargetsSet,
  portfolioSummary,
  subscriptionsCreate,
  subscriptionsDelete,
  subscriptionsGet,
  subscriptionsList,
  subscriptionsReport,
  subscriptionsReports,
  subscriptionsUpdate,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { plural, singleLine } from '../output/text';
import { displayDate, displayRange, monthPeriod, parseDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { renderRecord } from './records';
import { AccountBook, accountAmountArg, amountArg, collect, confirmAction, countArg, rateArg, wireAmount } from './shared';

type Row = Record<string, unknown> & { id: string };
/** A field from the server, as one line of safe text. */
const str = (v: unknown): string => (typeof v === 'string' ? singleLine(v) : v === null || v === undefined ? '' : String(v));

async function listOf(api: SalliClient, fn: Parameters<SalliClient['call']>[0], key: string, query: Record<string, unknown> = {}): Promise<Row[]> {
  const data = (await api.call(fn, { query } as never)) as Record<string, unknown>;
  return (Array.isArray(data[key]) ? data[key] : []) as Row[];
}

function changes<T extends Record<string, unknown>>(values: T): Partial<T> {
  return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined)) as Partial<T>;
}

function requireChanges(body: Record<string, unknown>, flags: string): void {
  if (Object.keys(body).length === 0) throw new UsageError('Nothing to change.', `Pass one or more of ${flags}.`);
}

// ── Budgets ──────────────────────────────────────────────────────────────────

function registerBudgets(program: Command, app: App): void {
  const budgets = program.command('budgets').alias('budget').description('Spending limits per category, against what you actually spent');

  const resolveBudget = async (api: SalliClient, query: string): Promise<Row> =>
    resolveById(await listOf(api, budgetsList, 'budgets'), query, 'budget');

  const periodOf = (opts: { month?: string; from?: string; to?: string }, required: boolean): { period_start?: string; period_end?: string } => {
    const now = app.runtime.now();
    if (opts.month) {
      if (opts.from || opts.to) throw new UsageError('Pass --month, or --from and --to, not both.');
      const p = monthPeriod(opts.month, now);
      return { period_start: p.from, period_end: p.to };
    }
    if (required && (!opts.from || !opts.to)) throw new UsageError('A budget needs --month, or --from and --to.');
    return changes({
      period_start: opts.from ? parseDate(opts.from, now, '--from') : undefined,
      period_end: opts.to ? parseDate(opts.to, now, '--to') : undefined,
    });
  };

  const linesOf = async (api: SalliClient, values: readonly string[]) => {
    const book = await AccountBook.load(api);
    return values.map((value) => {
      const { account, amount } = accountAmountArg(value, '--line');
      return { account_id: book.resolve(account).id, limit_amount: wireAmount(amount) };
    });
  };

  budgets
    .command('list')
    .alias('ls')
    .description('List budgets')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(budgetsList);
      app.out.emit(data, {
        records: (d) => (d as { budgets: Row[] }).budgets,
        human: (d) => {
          const rows = (d as { budgets: Row[] }).budgets;
          if (!rows.length) return app.out.note('No budgets yet. Add one with `salli budgets add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (b) => b.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'PERIOD', get: (b) => displayRange(b.period_start, b.period_end, app.out.locale) },
              { header: 'CATEGORIES', get: (b) => (Array.isArray(b.lines) ? b.lines.length : 0), align: 'right' },
              { header: 'CURRENCY', get: (b) => str(b.currency) },
            ]),
          );
        },
      });
    });

  budgets
    .command('show')
    .argument('<budget>', 'Budget id (or its start)')
    .description('Show a budget’s limits')
    .action(async (query) => {
      const api = await app.api();
      const budget = await resolveBudget(api, query);
      const [data, book] = await Promise.all([api.call(budgetsGet, { path: { budget_id: budget.id } }), AccountBook.load(api)]);
      const b = data as Row & { lines?: Array<{ account_id: string; limit_amount: string }> };
      app.out.emit(data, {
        records: () => b.lines ?? [],
        human: () => {
          app.out.line(app.out.heading(`Budget ${displayRange(b.period_start, b.period_end, app.out.locale)}`));
          app.out.line(
            app.out.table(b.lines ?? [], [
              { header: 'CATEGORY', get: (l) => book.label(l.account_id), shrink: true },
              { header: `LIMIT (${str(b.currency)})`, get: (l) => app.out.amount(l.limit_amount, b.currency), align: 'right' },
            ]),
          );
        },
      });
    });

  budgets
    .command('summary')
    .argument('<budget>', 'Budget id (or its start)')
    .description('Limits against actual spending for the budget’s period')
    .action(async (query) => {
      const api = await app.api();
      const budget = await resolveBudget(api, query);
      const data = (await api.call(budgetsSummary, { path: { budget_id: budget.id } })) as Row & {
        lines: Array<{ category: string; limit_amount: string; actual_amount: string; variance: string }>;
      };
      app.out.emit(data, {
        records: (d) => d.lines,
        human: (d) => {
          const out = app.out;
          const cur = d.currency;
          out.line(out.heading(`Budget ${displayRange(d.period_start, d.period_end, out.locale)}`));
          const total = { category: 'Total', limit_amount: str(d.total_limit), actual_amount: str(d.total_actual), variance: str(d.total_variance) };
          out.line(
            out.table([...d.lines, total], [
              { header: 'CATEGORY', get: (l) => l.category, shrink: true, style: (t, l) => (l === total ? out.colors.bold(t) : t) },
              { header: 'LIMIT', get: (l) => out.amount(l.limit_amount, cur), align: 'right' },
              { header: 'SPENT', get: (l) => out.amount(l.actual_amount, cur), align: 'right' },
              { header: 'LEFT', get: (l) => out.amount(l.variance, cur), align: 'right', style: (t, l) => out.signed(t, l.variance) },
            ]),
          );
          out.note(`Amounts in ${str(cur)}. Negative “left” means over the limit.`);
        },
      });
    });

  budgets
    .command('add')
    .description('Add a budget: limits per expense account for a period')
    .option('--month <yyyy-mm>', 'The period: a calendar month')
    .option('--from <date>', 'Or: the first day')
    .option('--to <date>', 'and the last day')
    .requiredOption('--line <account:limit>', 'A category and its limit, e.g. groceries:400 (repeatable)', collect)
    .action(async (opts) => {
      const api = await app.api();
      const period = periodOf(opts, true);
      const created = await api.call(budgetsCreate, {
        body: { period_start: period.period_start as string, period_end: period.period_end as string, lines: await linesOf(api, opts.line) },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added a budget for ${displayRange(period.period_start, period.period_end, app.out.locale)}.`);
    });

  budgets
    .command('update')
    .argument('<budget>', 'Budget id (or its start)')
    .description('Change a budget’s period, or replace its limits')
    .option('--month <yyyy-mm>', 'New period: a calendar month')
    .option('--from <date>', 'New first day')
    .option('--to <date>', 'New last day')
    .option('--line <account:limit>', 'Replaces all limits (repeatable)', collect)
    .action(async (query, opts) => {
      const api = await app.api();
      const budget = await resolveBudget(api, query);
      const body = { ...periodOf(opts, false), ...(opts.line ? { lines: await linesOf(api, opts.line) } : {}) };
      requireChanges(body, '--month, --from, --to or --line');
      const result = await api.call(budgetsUpdate, { path: { budget_id: budget.id }, body });
      app.out.done(result as Record<string, unknown>, 'Budget updated.');
    });

  budgets
    .command('delete')
    .argument('<budget>', 'Budget id (or its start)')
    .description('Delete a budget')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const budget = await resolveBudget(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the budget for ${displayRange(budget.period_start, budget.period_end, app.out.locale)}?`))) return;
      await api.call(budgetsDelete, { path: { budget_id: budget.id } });
      app.out.done({ id: budget.id, deleted: true }, 'Budget deleted.');
    });
}

// ── Debts ────────────────────────────────────────────────────────────────────

function registerDebts(program: Command, app: App): void {
  const debts = program.command('debts').alias('debt').description('Your debts, and the fastest way to pay them off');
  const resolveDebt = async (api: SalliClient, query: string): Promise<Row> =>
    resolveById(await listOf(api, debtsList, 'debts', { active_only: false }), query, 'debt');
  const debtTable = (rows: Row[]): string =>
    app.out.table(rows, [
      { header: 'ID', get: (d) => d.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
      { header: 'NAME', get: (d) => str(d.name), shrink: true, style: (t, d) => (d.is_active === false ? app.out.colors.dim(t) : t) },
      { header: 'BALANCE', get: (d) => app.out.money(d.principal, d.currency), align: 'right' },
      { header: 'APR', get: (d) => app.out.percent(d.apr, 2), align: 'right' },
      { header: 'MINIMUM', get: (d) => app.out.money(d.minimum_payment, d.currency), align: 'right' },
      { header: '', get: (d) => (d.is_active === false ? 'paid off' : ''), style: (t) => app.out.colors.dim(t) },
    ]);

  debts
    .command('list')
    .alias('ls')
    .description('List debts')
    .option('--all', 'Include paid-off (inactive) debts')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(debtsList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => (d as { debts: Row[] }).debts,
        human: (d) => {
          const rows = (d as { debts: Row[] }).debts;
          if (!rows.length) return app.out.note('No debts. Add one with `salli debts add`.');
          app.out.line(debtTable(rows));
        },
      });
    });

  debts
    .command('show')
    .argument('<debt>', 'Debt id (or its start)')
    .description('Show a debt')
    .action(async (query) => {
      const api = await app.api();
      const debt = await resolveDebt(api, query);
      const data = (await api.call(debtsGet, { path: { debt_id: debt.id } })) as Row;
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['principal', 'minimum_payment'], ratios: ['apr'] })) });
    });

  debts
    .command('add')
    .argument('<name>', 'e.g. "Credit card"')
    .description('Add a debt')
    .requiredOption('--balance <amount>', 'What you owe now')
    .requiredOption('--apr <rate>', 'Annual rate: 0.18 or 18%')
    .requiredOption('--minimum <amount>', 'The minimum monthly payment')
    .action(async (name, opts) => {
      const api = await app.api();
      const created = await api.call(debtsCreate, {
        body: {
          name,
          principal: wireAmount(amountArg(opts.balance, '--balance')),
          apr: wireAmount(rateArg(opts.apr, '--apr')),
          minimum_payment: wireAmount(amountArg(opts.minimum, '--minimum')),
        },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added the debt “${name}”.`);
    });

  debts
    .command('update')
    .argument('<debt>', 'Debt id (or its start)')
    .description('Change a debt')
    .option('--name <name>', 'New name')
    .option('--balance <amount>', 'New balance')
    .option('--apr <rate>', 'New annual rate: 0.18 or 18%')
    .option('--minimum <amount>', 'New minimum payment')
    .option('--paid-off', 'Mark it paid off (inactive)')
    .option('--active', 'Mark it active again')
    .action(async (query, opts) => {
      const api = await app.api();
      const debt = await resolveDebt(api, query);
      const body = changes({
        name: opts.name,
        principal: opts.balance ? wireAmount(amountArg(opts.balance, '--balance')) : undefined,
        apr: opts.apr ? wireAmount(rateArg(opts.apr, '--apr')) : undefined,
        minimum_payment: opts.minimum ? wireAmount(amountArg(opts.minimum, '--minimum')) : undefined,
        is_active: opts.paidOff ? false : opts.active ? true : undefined,
      });
      requireChanges(body, '--name, --balance, --apr, --minimum, --paid-off or --active');
      const result = await api.call(debtsUpdate, { path: { debt_id: debt.id }, body });
      app.out.done(result as Record<string, unknown>, `Updated “${str(debt.name)}”.`);
    });

  debts
    .command('delete')
    .argument('<debt>', 'Debt id (or its start)')
    .description('Delete a debt')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const debt = await resolveDebt(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the debt “${str(debt.name)}”?`))) return;
      await api.call(debtsDelete, { path: { debt_id: debt.id } });
      app.out.done({ id: debt.id, deleted: true }, `Deleted “${str(debt.name)}”.`);
    });

  debts
    .command('payoff-plan')
    .alias('plan')
    .description('How long paying off your debts takes, and what it costs')
    .addOption(new Option('--strategy <strategy>', 'avalanche: highest rate first; snowball: smallest balance first').choices(['avalanche', 'snowball']).default('avalanche'))
    .option('--extra <amount>', 'Paid on top of the minimums each month', '0')
    .option('--months <n>', 'Months of the schedule to show', countArg('--months'), 12)
    .action(async (opts) => {
      const api = await app.api();
      const plan = (await api.call(debtsPayoffPlan, {
        query: { strategy: opts.strategy, extra_monthly_payment: wireAmount(amountArg(opts.extra, '--extra')) },
      })) as {
        strategy: string;
        currency: string;
        months_to_payoff: number | null;
        total_interest_paid: string;
        schedule: Array<{ month: number; debt_name: string; payment: string; principal_paid: string; interest_paid: string; remaining_balance: string }>;
      };
      app.out.emit(plan, {
        records: (p) => p.schedule,
        human: (p) => {
          const out = app.out;
          out.line(
            out.details([
              ['Strategy', p.strategy],
              ['Debt-free in', p.months_to_payoff === null ? 'not within the planning horizon' : plural(p.months_to_payoff, 'month')],
              ['Interest paid', out.money(p.total_interest_paid, p.currency)],
            ]),
          );
          if (!p.schedule.length) return;
          out.line();
          const shown = p.schedule.filter((e) => e.month <= opts.months);
          out.line(
            out.table(shown, [
              { header: 'MONTH', get: (e) => e.month, align: 'right' },
              { header: 'DEBT', get: (e) => e.debt_name, shrink: true },
              { header: 'PAYMENT', get: (e) => out.amount(e.payment, p.currency), align: 'right' },
              { header: 'PRINCIPAL', get: (e) => out.amount(e.principal_paid, p.currency), align: 'right' },
              { header: 'INTEREST', get: (e) => out.amount(e.interest_paid, p.currency), align: 'right' },
              { header: 'LEFT', get: (e) => out.amount(e.remaining_balance, p.currency), align: 'right' },
            ]),
          );
          if (shown.length < p.schedule.length) out.note(`First ${opts.months} months shown (--months for more). Amounts in ${p.currency}.`);
        },
      });
    });
}

// ── Investments ──────────────────────────────────────────────────────────────

function registerPortfolio(program: Command, app: App): void {
  program
    .command('portfolio')
    .description('Your investments: value, gain, allocation and rebalancing (holdings: `salli holdings`)')
    .option('--target <class:fraction>', 'A target allocation, e.g. equity:0.6 (repeatable) for rebalancing alerts', collect)
    .action(async (opts) => {
      for (const t of opts.target ?? []) {
        const [cls, fraction] = t.split(':');
        if (!cls || !fraction) throw new UsageError(`--target takes ASSET_CLASS:FRACTION, e.g. equity:0.6 (got "${t}").`);
        rateArg(fraction, '--target');
      }
      const api = await app.api();
      const s = (await api.call(portfolioSummary, { query: { target: opts.target ?? [] } })) as {
        currency: string;
        total_value: string;
        total_cost_basis: string;
        total_gain: string;
        total_gain_pct: string;
        allocation: Array<{ asset_class: string; current_value: string; pct_of_portfolio: string }>;
        alerts: Array<{ asset_class: string; current_pct: string; target_pct: string; drift_pct: string }>;
      };
      app.out.emit(s, {
        records: (d) => d.allocation,
        human: (d) => {
          const out = app.out;
          out.line(
            out.details([
              ['Value', out.money(d.total_value, d.currency)],
              ['Invested', out.money(d.total_cost_basis, d.currency)],
              ['Gain', `${out.signed(out.money(d.total_gain, d.currency), d.total_gain)} (${out.percent(d.total_gain_pct, 2)})`],
            ]),
          );
          if (d.allocation.length) {
            out.line();
            out.line(
              out.table(d.allocation, [
                { header: 'ASSET CLASS', get: (a) => a.asset_class },
                { header: `VALUE (${d.currency})`, get: (a) => out.amount(a.current_value, d.currency), align: 'right' },
                { header: 'SHARE', get: (a) => out.percent(a.pct_of_portfolio), align: 'right' },
              ]),
            );
          }
          if (d.alerts.length) {
            out.line();
            out.line(out.heading('Rebalancing'));
            out.line(
              out.table(d.alerts, [
                { header: 'ASSET CLASS', get: (a) => a.asset_class },
                { header: 'NOW', get: (a) => out.percent(a.current_pct), align: 'right' },
                { header: 'TARGET', get: (a) => out.percent(a.target_pct), align: 'right' },
                { header: 'DRIFT', get: (a) => out.percent(a.drift_pct, 1), align: 'right', style: (t) => out.colors.yellow(t) },
              ]),
            );
          }
        },
      });
    });

  const holdings = program.command('holdings').alias('holding').description('Investment holdings you track (values as you last entered them)');
  const resolveHolding = async (api: SalliClient, query: string): Promise<Row> =>
    resolveById(await listOf(api, holdingsList, 'holdings', { active_only: false }), query, 'holding');

  holdings
    .command('list')
    .alias('ls')
    .description('List holdings')
    .option('--all', 'Include sold (inactive) holdings')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(holdingsList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => (d as { holdings: Row[] }).holdings,
        human: (d) => {
          const rows = (d as { holdings: Row[] }).holdings;
          if (!rows.length) return app.out.note('No holdings yet. Add one with `salli holdings add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (h) => h.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'SYMBOL', get: (h) => str(h.symbol) },
              { header: 'NAME', get: (h) => str(h.name), shrink: true },
              { header: 'CLASS', get: (h) => str(h.asset_class) },
              { header: 'INVESTED', get: (h) => app.out.money(h.cost_basis, h.currency), align: 'right' },
              { header: 'VALUE', get: (h) => app.out.money(h.current_value, h.currency), align: 'right' },
            ]),
          );
        },
      });
    });

  holdings
    .command('show')
    .argument('<holding>', 'Holding id (or its start)')
    .description('Show a holding')
    .action(async (query) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const data = (await api.call(holdingsGet, { path: { holding_id: holding.id } })) as Row;
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['cost_basis', 'current_value'] })) });
    });

  holdings
    .command('add')
    .argument('<symbol>', 'Ticker or short name, e.g. VOO')
    .description('Add a holding')
    .requiredOption('--name <name>', 'Display name')
    .requiredOption('--class <asset-class>', 'equity, bond, cash, crypto, property…')
    .requiredOption('--invested <amount>', 'Total amount invested (cost basis)')
    .requiredOption('--value <amount>', 'What it is worth now')
    .action(async (symbol, opts) => {
      const api = await app.api();
      const created = await api.call(holdingsCreate, {
        body: {
          symbol,
          name: opts.name,
          asset_class: opts.class,
          cost_basis: wireAmount(amountArg(opts.invested, '--invested')),
          current_value: wireAmount(amountArg(opts.value, '--value')),
        },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added ${symbol}.`);
    });

  holdings
    .command('update')
    .argument('<holding>', 'Holding id (or its start)')
    .description('Change a holding (e.g. its current value)')
    .option('--symbol <symbol>', 'New symbol')
    .option('--name <name>', 'New name')
    .option('--class <asset-class>', 'New asset class')
    .option('--invested <amount>', 'New cost basis')
    .option('--value <amount>', 'New current value')
    .option('--sold', 'Mark it sold (inactive)')
    .option('--active', 'Mark it active again')
    .action(async (query, opts) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const body = changes({
        symbol: opts.symbol,
        name: opts.name,
        asset_class: opts.class,
        cost_basis: opts.invested ? wireAmount(amountArg(opts.invested, '--invested')) : undefined,
        current_value: opts.value ? wireAmount(amountArg(opts.value, '--value')) : undefined,
        is_active: opts.sold ? false : opts.active ? true : undefined,
      });
      requireChanges(body, '--symbol, --name, --class, --invested, --value, --sold or --active');
      const result = await api.call(holdingsUpdate, { path: { holding_id: holding.id }, body });
      app.out.done(result as Record<string, unknown>, `Updated ${str(holding.symbol)}.`);
    });

  holdings
    .command('delete')
    .argument('<holding>', 'Holding id (or its start)')
    .description('Delete a holding')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete ${str(holding.symbol)}?`))) return;
      await api.call(holdingsDelete, { path: { holding_id: holding.id } });
      app.out.done({ id: holding.id, deleted: true }, `Deleted ${str(holding.symbol)}.`);
    });
}

// ── Subscriptions ────────────────────────────────────────────────────────────

const FREQUENCIES = ['weekly', 'monthly', 'quarterly', 'yearly'] as const;

function registerSubscriptions(program: Command, app: App): void {
  const subs = program.command('subscriptions').alias('subscription').description('Recurring charges, and alerts when one is missed or changes price');
  const resolveSub = async (api: SalliClient, query: string): Promise<Row> =>
    resolveById(await listOf(api, subscriptionsList, 'subscriptions', { active_only: false }), query, 'subscription');

  subs
    .command('list')
    .alias('ls')
    .description('List subscriptions')
    .option('--all', 'Include cancelled (inactive) ones')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(subscriptionsList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => (d as { subscriptions: Row[] }).subscriptions,
        human: (d) => {
          const rows = (d as { subscriptions: Row[] }).subscriptions;
          if (!rows.length) return app.out.note('No subscriptions yet. Add one with `salli subscriptions add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'NAME', get: (s) => str(s.name), shrink: true },
              { header: 'AMOUNT', get: (s) => app.out.money(s.amount, s.currency), align: 'right' },
              { header: 'EVERY', get: (s) => str(s.frequency).replace(/ly$/, '').replace('dai', 'day') },
              { header: 'NEXT', get: (s) => displayDate(s.next_due_date, app.out.locale) },
            ]),
          );
        },
      });
    });

  subs
    .command('show')
    .argument('<subscription>', 'Subscription id (or its start)')
    .description('Show a subscription')
    .action(async (query) => {
      const api = await app.api();
      const sub = await resolveSub(api, query);
      const data = (await api.call(subscriptionsGet, { path: { subscription_id: sub.id } })) as Row;
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['amount'], ratios: ['amount_tolerance_pct'] })) });
    });

  subs
    .command('add')
    .argument('<name>', 'e.g. Netflix')
    .description('Add a subscription')
    .requiredOption('--amount <amount>', 'The expected charge')
    .addOption(new Option('--frequency <frequency>', 'How often').choices(FREQUENCIES).makeOptionMandatory())
    .requiredOption('--next <date>', 'The next charge date (YYYY-MM-DD)')
    .option('--account <account>', 'Only match charges to this expense account')
    .option('--grace-days <n>', 'Days late before it counts as missed', countArg('--grace-days'))
    .option('--tolerance <rate>', 'Price change to allow before alerting: 0.05 or 5%')
    .action(async (name, opts) => {
      const api = await app.api();
      const account = opts.account ? (await AccountBook.load(api)).resolve(opts.account).id : undefined;
      const created = await api.call(subscriptionsCreate, {
        body: {
          name,
          amount: wireAmount(amountArg(opts.amount, '--amount')),
          frequency: opts.frequency as string,
          next_due_date: parseDate(opts.next, app.runtime.now(), '--next'),
          ...(account ? { account_id: account } : {}),
          ...(opts.graceDays !== undefined ? { grace_days: opts.graceDays } : {}),
          ...(opts.tolerance ? { amount_tolerance_pct: wireAmount(rateArg(opts.tolerance, '--tolerance')) } : {}),
        },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added the subscription “${name}”.`);
    });

  subs
    .command('update')
    .argument('<subscription>', 'Subscription id (or its start)')
    .description('Change a subscription')
    .option('--name <name>', 'New name')
    .option('--amount <amount>', 'New amount')
    .addOption(new Option('--frequency <frequency>', 'New frequency').choices(FREQUENCIES))
    .option('--next <date>', 'New next charge date')
    .option('--account <account>', 'New expense account')
    .option('--grace-days <n>', 'New grace period', countArg('--grace-days'))
    .option('--tolerance <rate>', 'New price tolerance: 0.05 or 5%')
    .option('--cancelled', 'Mark it cancelled (inactive)')
    .option('--active', 'Mark it active again')
    .action(async (query, opts) => {
      const api = await app.api();
      const sub = await resolveSub(api, query);
      const body = changes({
        name: opts.name,
        amount: opts.amount ? wireAmount(amountArg(opts.amount, '--amount')) : undefined,
        frequency: opts.frequency as string | undefined,
        next_due_date: opts.next ? parseDate(opts.next, app.runtime.now(), '--next') : undefined,
        account_id: opts.account ? (await AccountBook.load(api)).resolve(opts.account).id : undefined,
        grace_days: opts.graceDays,
        amount_tolerance_pct: opts.tolerance ? wireAmount(rateArg(opts.tolerance, '--tolerance')) : undefined,
        is_active: opts.cancelled ? false : opts.active ? true : undefined,
      });
      requireChanges(body, '--name, --amount, --frequency, --next, --account, --grace-days, --tolerance, --cancelled or --active');
      const result = await api.call(subscriptionsUpdate, { path: { subscription_id: sub.id }, body });
      app.out.done(result as Record<string, unknown>, `Updated “${str(sub.name)}”.`);
    });

  subs
    .command('delete')
    .argument('<subscription>', 'Subscription id (or its start)')
    .description('Delete a subscription')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const sub = await resolveSub(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the subscription “${str(sub.name)}”?`))) return;
      await api.call(subscriptionsDelete, { path: { subscription_id: sub.id } });
      app.out.done({ id: sub.id, deleted: true }, `Deleted “${str(sub.name)}”.`);
    });

  subs
    .command('report')
    .argument('[subscription]', 'One subscription (default: all)')
    .description('Missed charges and price changes')
    .action(async (query) => {
      const api = await app.api();
      type Report = { subscription_id: string; name: string; currency: string; alerts: Array<{ kind: string; message: string }>; matches: Array<{ entry_date: string; amount: string }> };
      const data = query
        ? await api.call(subscriptionsReport, { path: { subscription_id: (await resolveSub(api, query)).id } })
        : await api.call(subscriptionsReports);
      const reports: Report[] = query ? [data as Report] : ((data as { reports: Report[] }).reports ?? []);
      app.out.emit(data, {
        records: () => reports,
        human: () => {
          const c = app.out.colors;
          if (!reports.length) return app.out.note('No subscriptions to check.');
          for (const r of reports) {
            app.out.line(`${app.out.heading(r.name)} ${c.dim(r.subscription_id.slice(0, 8))}`);
            if (!r.alerts.length) app.out.line(`  ${c.green('✓')} charged as expected`);
            for (const a of r.alerts) app.out.line(`  ${a.kind === 'missed_charge' ? c.red('!') : c.yellow('!')} ${singleLine(a.message)}`);
            const last = r.matches.at(-1);
            if (last) app.out.line(c.dim(`  last charge ${app.out.money(last.amount, r.currency)} on ${displayDate(last.entry_date, app.out.locale)}`));
          }
        },
      });
    });
}

// ── Insurance ────────────────────────────────────────────────────────────────

function registerInsurance(program: Command, app: App): void {
  const insurance = program.command('insurance').description('Insurance policies, the cover you want, and the gaps');
  const policies = insurance.command('policies').alias('policy').description('Your policies');
  const resolvePolicy = async (api: SalliClient, query: string): Promise<Row> =>
    resolveById(await listOf(api, insurancePoliciesList, 'policies', { active_only: false }), query, 'policy');

  policies
    .command('list')
    .alias('ls')
    .description('List policies')
    .option('--all', 'Include lapsed (inactive) policies')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(insurancePoliciesList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => (d as { policies: Row[] }).policies,
        human: (d) => {
          const rows = (d as { policies: Row[] }).policies;
          if (!rows.length) return app.out.note('No policies yet. Add one with `salli insurance policies add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (p) => p.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'NAME', get: (p) => str(p.name), shrink: true },
              { header: 'TYPE', get: (p) => str(p.policy_type) },
              { header: 'PROVIDER', get: (p) => str(p.provider), shrink: true },
              { header: 'COVER', get: (p) => app.out.money(p.coverage_amount, p.currency), align: 'right' },
              { header: 'PREMIUM', get: (p) => `${app.out.money(p.premium_amount, p.currency)} ${str(p.premium_frequency)}`, align: 'right' },
              { header: 'EXPIRES', get: (p) => displayDate(p.expiry_date, app.out.locale) },
            ]),
          );
        },
      });
    });

  policies
    .command('show')
    .argument('<policy>', 'Policy id (or its start)')
    .description('Show a policy')
    .action(async (query) => {
      const api = await app.api();
      const policy = await resolvePolicy(api, query);
      const data = (await api.call(insurancePoliciesGet, { path: { policy_id: policy.id } })) as Row;
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['coverage_amount', 'premium_amount'] })) });
    });

  policies
    .command('add')
    .argument('<name>', 'e.g. "Life cover"')
    .description('Add a policy')
    .requiredOption('--type <type>', 'life, health, motor, property, other')
    .requiredOption('--provider <provider>', 'The insurer')
    .requiredOption('--cover <amount>', 'Coverage amount')
    .requiredOption('--premium <amount>', 'Premium amount')
    .addOption(new Option('--frequency <frequency>', 'How often the premium is paid').choices(['monthly', 'quarterly', 'yearly']).default('monthly'))
    .requiredOption('--expires <date>', 'Expiry date (YYYY-MM-DD)')
    .action(async (name, opts) => {
      const api = await app.api();
      const created = await api.call(insurancePoliciesCreate, {
        body: {
          name,
          policy_type: opts.type,
          provider: opts.provider,
          coverage_amount: wireAmount(amountArg(opts.cover, '--cover')),
          premium_amount: wireAmount(amountArg(opts.premium, '--premium')),
          premium_frequency: opts.frequency,
          expiry_date: parseDate(opts.expires, app.runtime.now(), '--expires'),
        },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added the policy “${name}”.`);
    });

  policies
    .command('update')
    .argument('<policy>', 'Policy id (or its start)')
    .description('Change a policy')
    .option('--name <name>', 'New name')
    .option('--type <type>', 'New type')
    .option('--provider <provider>', 'New insurer')
    .option('--cover <amount>', 'New coverage amount')
    .option('--premium <amount>', 'New premium')
    .addOption(new Option('--frequency <frequency>', 'New premium frequency').choices(['monthly', 'quarterly', 'yearly']))
    .option('--expires <date>', 'New expiry date')
    .option('--lapsed', 'Mark it lapsed (inactive)')
    .option('--active', 'Mark it active again')
    .action(async (query, opts) => {
      const api = await app.api();
      const policy = await resolvePolicy(api, query);
      const body = changes({
        name: opts.name,
        policy_type: opts.type,
        provider: opts.provider,
        coverage_amount: opts.cover ? wireAmount(amountArg(opts.cover, '--cover')) : undefined,
        premium_amount: opts.premium ? wireAmount(amountArg(opts.premium, '--premium')) : undefined,
        premium_frequency: opts.frequency as string | undefined,
        expiry_date: opts.expires ? parseDate(opts.expires, app.runtime.now(), '--expires') : undefined,
        is_active: opts.lapsed ? false : opts.active ? true : undefined,
      });
      requireChanges(body, '--name, --type, --provider, --cover, --premium, --frequency, --expires, --lapsed or --active');
      const result = await api.call(insurancePoliciesUpdate, { path: { policy_id: policy.id }, body });
      app.out.done(result as Record<string, unknown>, `Updated “${str(policy.name)}”.`);
    });

  policies
    .command('delete')
    .argument('<policy>', 'Policy id (or its start)')
    .description('Delete a policy')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const policy = await resolvePolicy(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the policy “${str(policy.name)}”?`))) return;
      await api.call(insurancePoliciesDelete, { path: { policy_id: policy.id } });
      app.out.done({ id: policy.id, deleted: true }, `Deleted “${str(policy.name)}”.`);
    });

  const targets = insurance.command('targets').alias('target').description('How much cover you want, per type');

  targets
    .command('list')
    .alias('ls')
    .description('List cover targets')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(insuranceTargetsList);
      app.out.emit(data, {
        records: (d) => (d as { targets: Row[] }).targets,
        human: (d) => {
          const rows = (d as { targets: Row[] }).targets;
          if (!rows.length) return app.out.note('No targets yet. Set one with `salli insurance targets set life --amount 500000`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'TYPE', get: (t) => str(t.policy_type) },
              { header: 'TARGET', get: (t) => app.out.money(t.target_amount, t.currency), align: 'right' },
            ]),
          );
        },
      });
    });

  targets
    .command('set')
    .argument('<type>', 'life, health, motor, property, other')
    .requiredOption('--amount <amount>', 'The cover you want in total for this type')
    .description('Set the cover you want for a type')
    .action(async (type, opts) => {
      const api = await app.api();
      const result = await api.call(insuranceTargetsSet, {
        body: { policy_type: type, target_amount: wireAmount(amountArg(opts.amount, '--amount')) },
      });
      if (app.out.machine) app.out.emit(result, { human: () => undefined });
      else app.out.success(`Target for ${type} cover set.`);
    });

  targets
    .command('delete')
    .argument('<type>', 'The policy type')
    .description('Remove the target for a type')
    .action(async (type) => {
      const api = await app.api();
      await api.call(insuranceTargetsDelete, { path: { policy_type: type } });
      app.out.done({ policy_type: type, deleted: true }, `Removed the ${type} target.`);
    });

  insurance
    .command('report')
    .description('Cover against your targets, missing types, and policies expiring soon')
    .action(async () => {
      const api = await app.api();
      const r = (await api.call(insuranceReport)) as {
        currency: string;
        lines: Array<{ policy_type: string; target_amount: string; actual_coverage: string; gap: string }>;
        missing_types: string[];
        expiring_soon: Array<{ policy_name: string; policy_type: string; expiry_date: string; days_until_expiry: number }>;
      };
      app.out.emit(r, {
        records: (d) => d.lines,
        human: (d) => {
          const out = app.out;
          if (d.lines.length) {
            out.line(
              out.table(d.lines, [
                { header: 'TYPE', get: (l) => l.policy_type },
                { header: 'TARGET', get: (l) => out.amount(l.target_amount, d.currency), align: 'right' },
                { header: 'COVERED', get: (l) => out.amount(l.actual_coverage, d.currency), align: 'right' },
                {
                  header: 'GAP',
                  get: (l) => out.amount(l.gap, d.currency),
                  align: 'right',
                  style: (t, l) => (/^0*(\.0*)?$/.test(l.gap) || l.gap.startsWith('-') ? out.colors.green(t) : out.colors.red(t)),
                },
              ]),
            );
            out.note(`Amounts in ${d.currency}.`);
          } else out.note('No cover targets yet: `salli insurance targets set`.');
          if (d.missing_types.length) out.line(`${out.colors.red('!')} No cover at all for: ${singleLine(d.missing_types.join(', '))}`);
          for (const e of d.expiring_soon) {
            out.line(`${out.colors.yellow('!')} ${singleLine(`${e.policy_name} (${e.policy_type})`)} expires ${displayDate(e.expiry_date, out.locale)}, in ${e.days_until_expiry} days`);
          }
        },
      });
    });
}

export function registerPlanning(program: Command, app: App): void {
  registerBudgets(program, app);
  registerDebts(program, app);
  registerPortfolio(program, app);
  registerSubscriptions(program, app);
  registerInsurance(program, app);
}
