/**
 * Budgets, debts, investments, subscriptions and insurance: thin wrappers
 * over the API, each with a table for people and the API's JSON for
 * scripts.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  budgetsCreate,
  budgetsCurrent,
  budgetsDelete,
  budgetsMonthlyGet,
  budgetsMonthlySet,
  budgetsTrend,
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
  insuranceNeeds,
  insuranceReport,
  insuranceTargetsDelete,
  insuranceTargetsList,
  insuranceTargetsSet,
  ipsAdopt,
  ipsDrift,
  ipsGet,
  ipsRiskProfile,
  ipsVersions,
  portfolioSummary,
  subscriptionsCreate,
  subscriptionsDelete,
  subscriptionsGet,
  subscriptionsList,
  subscriptionsReport,
  subscriptionsReports,
  subscriptionsUpdate,
  type Budget,
  type BudgetSummaryLine,
  type Debt,
  type Holding,
  type InsurancePolicy,
  type PolicyTargetIn,
  type InvestorRiskProfile,
  type SalliClient,
  type Subscription,
  type SubscriptionReport,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { plural, singleLine } from '../output/text';
import { displayDate, displayMonth, displayRange, monthPeriod, parseDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { registerInvestments, resolveHolding } from './investments';
import { renderRecord } from './records';
import { AccountBook, accountAmountArg, amountArg, collect, confirmAction, countArg, currencyArg, rateArg } from './shared';

/** A field from the server, as one line of safe text. */
const str = (v: string | null | undefined): string => (v ? singleLine(v) : '');

function changes<T extends Record<string, unknown>>(values: T): Partial<T> {
  return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined)) as Partial<T>;
}

function requireChanges(body: Record<string, unknown>, flags: string): void {
  if (Object.keys(body).length === 0) throw new UsageError('Nothing to change.', `Pass one or more of ${flags}.`);
}

// ── Budgets ──────────────────────────────────────────────────────────────────

function registerBudgets(program: Command, app: App): void {
  const budgets = program.command('budgets').alias('budget').description('Spending limits per category, against what you actually spent');

  const resolveBudget = async (api: SalliClient, query: string): Promise<Budget> =>
    resolveById((await api.call(budgetsList)).budgets, query, 'budget');

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
      return { account_id: book.resolve(account).id, limit_amount: amount };
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
        records: (d) => d.budgets,
        human: (d) => {
          const rows = d.budgets;
          if (!rows.length) return app.out.note('No budgets yet. Add one with `salli budgets add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (b) => b.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'PERIOD', get: (b) => displayRange(b.period_start, b.period_end, app.out.locale) },
              { header: 'CATEGORIES', get: (b) => b.lines.length, align: 'right' },
              { header: 'CURRENCY', get: (b) => b.currency },
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
      const [b, book] = await Promise.all([api.call(budgetsGet, { path: { budget_id: budget.id } }), AccountBook.load(api)]);
      app.out.emit(b, {
        records: () => b.lines,
        human: () => {
          app.out.line(app.out.heading(`Budget ${displayRange(b.period_start, b.period_end, app.out.locale)}`));
          app.out.line(
            app.out.table(b.lines, [
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
      const data = await api.call(budgetsSummary, { path: { budget_id: budget.id } });
      app.out.emit(data, {
        records: (d) => d.lines,
        human: (d) => {
          const out = app.out;
          const cur = d.currency;
          out.line(out.heading(`Budget ${displayRange(d.period_start, d.period_end, out.locale)}`));
          const total: BudgetSummaryLine = {
            account_id: '',
            category: 'Total',
            limit_amount: d.total_limit,
            actual_amount: d.total_actual,
            variance: d.total_variance,
          };
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
    .command('monthly')
    .description('Show the monthly budget, or replace it with --line')
    .option('--line <account:limit>', 'A category and its monthly limit, e.g. groceries:400 (repeatable; replaces all)', collect)
    .option('--rollover <account>', 'This line’s unspent amount carries to the next month (repeatable)', collect)
    .option('--clear', 'Remove every line')
    .action(async (opts) => {
      const api = await app.api();
      let data;
      if (opts.clear || opts.line) {
        const book = await AccountBook.load(api);
        const rolling = new Set((opts.rollover ?? []).map((q) => book.resolve(q).id));
        const lines = opts.clear ? [] : (await linesOf(api, opts.line ?? [])).map((l) => ({ ...l, rollover: rolling.has(l.account_id) }));
        data = await api.call(budgetsMonthlySet, { body: { lines } });
      } else {
        if (opts.rollover) throw new UsageError('--rollover goes with --line.');
        data = await api.call(budgetsMonthlyGet);
      }
      const book = await AccountBook.load(api);
      app.out.emit(data, {
        records: (d) => d.lines,
        human: (d) => {
          if (!d.lines.length) return app.out.note('No monthly budget. Set one with `salli budgets monthly --line groceries:400`.');
          app.out.line(
            app.out.table(d.lines, [
              { header: 'CATEGORY', get: (l) => book.name(l.account_id), shrink: true },
              { header: 'LIMIT', get: (l) => app.out.amount(l.limit_amount, d.currency), align: 'right' },
              { header: 'ROLLOVER', get: (l) => (l.rollover ? 'yes' : '') },
              { header: 'SINCE', get: (l) => l.since },
            ]),
          );
        },
      });
    });

  budgets
    .command('current')
    .alias('now')
    .description('This month: each line’s limit, spent, left and pace')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(budgetsCurrent);
      app.out.emit(data, {
        records: (d) => d.lines,
        human: (d) => {
          const out = app.out;
          if (!d.lines.length) return out.note('No monthly budget. Set one with `salli budgets monthly --line groceries:400`.');
          out.line(out.heading(`Budget ${d.month}`));
          out.line(
            out.table(d.lines, [
              { header: 'CATEGORY', get: (l) => l.category, shrink: true },
              { header: 'AVAILABLE', get: (l) => out.amount(l.available, d.currency), align: 'right' },
              { header: 'SPENT', get: (l) => out.amount(l.spent, d.currency), align: 'right' },
              { header: 'LEFT', get: (l) => out.amount(l.left, d.currency), align: 'right', style: (t, l) => out.signed(t, l.left) },
              { header: 'PACE', get: (l) => l.pace },
            ]),
          );
          out.note(`Amounts in ${str(d.currency)}. Pace compares spending with the share of the month gone.`);
        },
      });
    });

  budgets
    .command('trend')
    .description('Spending per category, month by month')
    .option('--months <n>', 'How many months, this one last (default 6)', countArg('--months'))
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(budgetsTrend, { query: opts.months !== undefined ? { months: opts.months } : {} });
      app.out.emit(data, {
        records: (d) => d.categories,
        human: (d) => {
          const out = app.out;
          if (!d.categories.length) return out.note('No spending in these months.');
          out.line(
            out.table(d.categories, [
              { header: 'CATEGORY', get: (c) => c.category, shrink: true },
              ...d.months.map((m, i) => ({ header: m, get: (c: (typeof d.categories)[number]) => out.amount(c.spent[i] ?? '0', d.currency), align: 'right' as const })),
            ]),
          );
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
      app.out.done(result, 'Budget updated.');
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
  const resolveDebt = async (api: SalliClient, query: string): Promise<Debt> =>
    resolveById((await api.call(debtsList, { query: { active_only: false } })).debts, query, 'debt');
  const debtTable = (rows: readonly Debt[]): string =>
    app.out.table(rows, [
      { header: 'ID', get: (d) => d.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
      { header: 'NAME', get: (d) => d.name, shrink: true, style: (t, d) => (d.is_active ? t : app.out.colors.dim(t)) },
      { header: 'BALANCE', get: (d) => app.out.money(d.principal, d.currency), align: 'right' },
      { header: 'APR', get: (d) => app.out.percent(d.apr, 2), align: 'right' },
      { header: 'MINIMUM', get: (d) => app.out.money(d.minimum_payment, d.currency), align: 'right' },
      // A linked debt's balance in planning is its account's, not the one declared here.
      ...(rows.some((d) => d.account_id)
        ? [{ header: 'ACCOUNT', get: (d: Debt) => (d.account_id ? d.account_id.slice(0, 8) : ''), style: (t: string) => app.out.colors.dim(t) }]
        : []),
      { header: '', get: (d) => (d.is_active ? '' : 'paid off'), style: (t) => app.out.colors.dim(t) },
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
        records: (d) => d.debts,
        human: (d) => {
          const rows = d.debts;
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
      const data = await api.call(debtsGet, { path: { debt_id: debt.id } });
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['principal', 'minimum_payment'], ratios: ['apr'] })) });
    });

  debts
    .command('add')
    .argument('<name>', 'e.g. "Credit card"')
    .description('Add a debt')
    .requiredOption('--balance <amount>', 'What you owe now')
    .requiredOption('--apr <rate>', 'Annual rate: 0.18 or 18%')
    .requiredOption('--minimum <amount>', 'The minimum monthly payment')
    .option('--account <account>', 'The liability account that holds it in your ledger (code, name or id), so it is counted once')
    .action(async (name, opts) => {
      const api = await app.api();
      const account = opts.account ? (await AccountBook.load(api)).resolve(opts.account) : undefined;
      const created = await api.call(debtsCreate, {
        body: {
          name,
          principal: amountArg(opts.balance, '--balance'),
          apr: rateArg(opts.apr, '--apr'),
          minimum_payment: amountArg(opts.minimum, '--minimum'),
          ...(account ? { account_id: account.id } : {}),
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
    .option('--account <account>', 'Link it to the liability account that holds it (code, name or id)')
    .option('--no-account', 'Unlink it from its account (it then counts as declared)')
    .action(async (query, opts) => {
      const api = await app.api();
      const debt = await resolveDebt(api, query);
      const account = typeof opts.account === 'string' ? (await AccountBook.load(api)).resolve(opts.account) : undefined;
      const body = changes({
        name: opts.name,
        principal: opts.balance ? amountArg(opts.balance, '--balance') : undefined,
        apr: opts.apr ? rateArg(opts.apr, '--apr') : undefined,
        minimum_payment: opts.minimum ? amountArg(opts.minimum, '--minimum') : undefined,
        is_active: opts.paidOff ? false : opts.active ? true : undefined,
        account_id: account ? account.id : opts.account === false ? null : undefined,
      });
      requireChanges(body, '--name, --balance, --apr, --minimum, --paid-off, --active, --account or --no-account');
      const result = await api.call(debtsUpdate, { path: { debt_id: debt.id }, body });
      app.out.done(result, `Updated “${str(debt.name)}”.`);
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
      const plan = await api.call(debtsPayoffPlan, {
        query: { strategy: opts.strategy, extra_monthly_payment: amountArg(opts.extra, '--extra') },
      });
      app.out.emit(plan, {
        records: (p) => p.schedule,
        human: (p) => {
          const out = app.out;
          out.line(
            out.details([
              ['Strategy', p.strategy],
              [
                'Debt-free',
                p.months_to_payoff === null || !p.debt_free_month
                  ? 'not within the planning horizon'
                  : `after ${displayMonth(p.debt_free_month, out.locale)} (${plural(p.months_to_payoff, 'month')})`,
              ],
              ['Interest paid', out.money(p.total_interest_paid, p.currency)],
            ]),
          );
          // A linked debt starts from its ledger account's balance, not the one declared.
          const fromAccounts = p.debts.filter((d) => d.source === 'account');
          if (fromAccounts.length) {
            out.note(`From your ledger: ${fromAccounts.map((d) => `${singleLine(d.name)} ${out.money(d.balance, p.currency)}`).join(', ')}.`);
          }
          if (!p.schedule.length) return;
          out.line();
          const shown = p.schedule.filter((e) => e.month <= opts.months);
          out.line(
            out.table(shown, [
              { header: 'MONTH', get: (e) => displayMonth(e.period, out.locale) },
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
  const portfolio = program
    .command('portfolio')
    .description('Your investments: value and allocation, transactions, lots, prices and performance (holdings: `salli holdings`)');
  portfolio
    .command('summary', { isDefault: true })
    .description('Value, gain, allocation and rebalancing')
    .option('--target <class:fraction>', 'A target allocation, e.g. equity:0.6 (repeatable) for rebalancing alerts', collect)
    .action(async (opts) => {
      for (const t of opts.target ?? []) {
        const [cls, fraction] = t.split(':');
        if (!cls || !fraction) throw new UsageError(`--target takes ASSET_CLASS:FRACTION, e.g. equity:0.6 (got "${t}").`);
        rateArg(fraction, '--target');
      }
      const api = await app.api();
      const s = await api.call(portfolioSummary, { query: { target: opts.target ?? [] } });
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
          if (d.costs.weighted_expense_ratio !== null) {
            out.line();
            out.line(
              out.details([
                ['Expense ratio', `${out.percent(d.costs.weighted_expense_ratio, 2)} weighted, on ${out.money(d.costs.value_covered, d.currency)}`],
                ['Yearly cost', out.money(d.costs.yearly_cost, d.currency)],
              ]),
            );
            if (d.costs.without_ratio.length) out.note(`No expense ratio for ${singleLine(d.costs.without_ratio.join(', '))}.`);
          }
          if (d.alerts.length) {
            out.line();
            out.line(out.heading(d.target_source === 'policy' ? 'Rebalancing (your investment policy)' : 'Rebalancing'));
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

  registerInvestments(portfolio, app);
  registerPolicy(program, app);

  const holdings = program.command('holdings').alias('holding').description('Investment holdings you track (values as you last entered them)');

  holdings
    .command('list')
    .alias('ls')
    .description('List holdings')
    .option('--all', 'Include sold (inactive) holdings')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(holdingsList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => d.holdings,
        human: (d) => {
          const rows = d.holdings;
          if (!rows.length) return app.out.note('No holdings yet. Add one with `salli holdings add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (h) => h.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'SYMBOL', get: (h) => h.symbol },
              { header: 'NAME', get: (h) => h.name, shrink: true },
              { header: 'CLASS', get: (h) => h.asset_class },
              { header: 'QUANTITY', get: (h) => h.quantity ?? '', align: 'right' },
              { header: 'INVESTED', get: (h) => app.out.money(h.cost_basis, h.currency), align: 'right' },
              { header: 'VALUE', get: (h) => app.out.money(h.current_value, h.currency), align: 'right' },
              // A linked holding sits in an investment account of the ledger, which stays the one source of balances.
              ...(rows.some((h) => h.account_id)
                ? [{ header: 'ACCOUNT', get: (h: Holding) => (h.account_id ? h.account_id.slice(0, 8) : ''), style: (t: string) => app.out.colors.dim(t) }]
                : []),
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
      const data = await api.call(holdingsGet, { path: { holding_id: holding.id } });
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['cost_basis', 'current_value'] })) });
    });

  holdings
    .command('add')
    .argument('<symbol>', 'Ticker or short name, e.g. VOO')
    .description('Add a holding: declare what it cost and is worth, or record its transactions after')
    .requiredOption('--name <name>', 'Display name')
    .requiredOption('--class <asset-class>', 'equity, bond, cash, crypto, property…')
    .option('--currency <code>', 'What it trades in (default: your base currency)')
    .option('--invested <amount>', 'Declared: total amount invested (cost basis)')
    .option('--value <amount>', 'Declared: what it is worth now')
    .option('--account <account>', 'The investment account that holds it in your ledger (code, name or id)')
    .addOption(new Option('--cost-method <method>', 'How its sales are costed (default: your tax rules’, else fifo)').choices(['fifo', 'average'] as const))
    .option('--expense-ratio <fraction>', 'Its yearly running cost, e.g. 0.002 or 0.2%')
    .option('--allocation <class:share,…>', 'A fund’s look-through, e.g. equity.international:0.6,fixed_income:0.4 (adds up to 1)')
    .action(async (symbol, opts) => {
      const api = await app.api();
      const account = opts.account ? (await AccountBook.load(api)).resolve(opts.account) : undefined;
      const created = await api.call(holdingsCreate, {
        body: {
          symbol,
          name: opts.name,
          asset_class: opts.class,
          ...(opts.currency ? { currency: currencyArg(opts.currency) } : {}),
          ...(opts.invested ? { cost_basis: amountArg(opts.invested, '--invested') } : {}),
          ...(opts.value ? { current_value: amountArg(opts.value, '--value') } : {}),
          ...(account ? { account_id: account.id } : {}),
          ...(opts.costMethod ? { cost_method: opts.costMethod } : {}),
          ...(opts.expenseRatio ? { expense_ratio: rateArg(opts.expenseRatio, '--expense-ratio') } : {}),
          ...(opts.allocation ? { allocation: allocationArg(opts.allocation) } : {}),
        },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else {
        app.out.success(`Added ${symbol}.`);
        if (!opts.invested && !opts.value) app.out.note(`Record what you bought: salli portfolio transactions add ${symbol} buy --quantity … --price …`);
      }
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
    .option('--account <account>', 'Link it to the investment account that holds it in your ledger (code, name or id)')
    .option('--no-account', 'Unlink it from its account (a what-if can then invest into it, but not sell it)')
    .addOption(new Option('--cost-method <method>', 'How its sales are costed; default: back to your tax rules’, else fifo').choices(['fifo', 'average', 'default'] as const))
    .option('--expense-ratio <fraction>', 'Its yearly running cost, e.g. 0.002 or 0.2%; none clears it')
    .option('--allocation <class:share,…>', 'A fund’s look-through, e.g. equity:0.6,fixed_income:0.4; none clears it')
    .action(async (query, opts) => {
      const api = await app.api();
      const holding = await resolveHolding(api, query);
      const account = typeof opts.account === 'string' ? (await AccountBook.load(api)).resolve(opts.account) : undefined;
      const body = changes({
        symbol: opts.symbol,
        name: opts.name,
        asset_class: opts.class,
        cost_basis: opts.invested ? amountArg(opts.invested, '--invested') : undefined,
        current_value: opts.value ? amountArg(opts.value, '--value') : undefined,
        is_active: opts.sold ? false : opts.active ? true : undefined,
        account_id: account ? account.id : opts.account === false ? null : undefined,
        cost_method: opts.costMethod === 'default' ? null : opts.costMethod,
        expense_ratio: opts.expenseRatio === undefined ? undefined : opts.expenseRatio === 'none' ? null : rateArg(opts.expenseRatio, '--expense-ratio'),
        allocation: opts.allocation === undefined ? undefined : opts.allocation === 'none' ? null : allocationArg(opts.allocation),
      });
      requireChanges(body, '--symbol, --name, --class, --invested, --value, --sold, --active, --account, --no-account, --cost-method, --expense-ratio or --allocation');
      const result = await api.call(holdingsUpdate, { path: { holding_id: holding.id }, body });
      app.out.done(result, `Updated ${str(holding.symbol)}.`);
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
  const resolveSub = async (api: SalliClient, query: string): Promise<Subscription> =>
    resolveById((await api.call(subscriptionsList, { query: { active_only: false } })).subscriptions, query, 'subscription');

  subs
    .command('list')
    .alias('ls')
    .description('List subscriptions')
    .option('--all', 'Include cancelled (inactive) ones')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(subscriptionsList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => d.subscriptions,
        human: (d) => {
          const rows = d.subscriptions;
          if (!rows.length) return app.out.note('No subscriptions yet. Add one with `salli subscriptions add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'NAME', get: (s) => s.name, shrink: true },
              { header: 'AMOUNT', get: (s) => app.out.money(s.amount, s.currency), align: 'right' },
              { header: 'EVERY', get: (s) => s.frequency.replace(/ly$/, '').replace('dai', 'day') },
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
      const data = await api.call(subscriptionsGet, { path: { subscription_id: sub.id } });
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
          amount: amountArg(opts.amount, '--amount'),
          frequency: opts.frequency,
          next_due_date: parseDate(opts.next, app.runtime.now(), '--next'),
          ...(account ? { account_id: account } : {}),
          ...(opts.graceDays !== undefined ? { grace_days: opts.graceDays } : {}),
          ...(opts.tolerance ? { amount_tolerance_pct: rateArg(opts.tolerance, '--tolerance') } : {}),
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
        amount: opts.amount ? amountArg(opts.amount, '--amount') : undefined,
        frequency: opts.frequency,
        next_due_date: opts.next ? parseDate(opts.next, app.runtime.now(), '--next') : undefined,
        account_id: opts.account ? (await AccountBook.load(api)).resolve(opts.account).id : undefined,
        grace_days: opts.graceDays,
        amount_tolerance_pct: opts.tolerance ? rateArg(opts.tolerance, '--tolerance') : undefined,
        is_active: opts.cancelled ? false : opts.active ? true : undefined,
      });
      requireChanges(body, '--name, --amount, --frequency, --next, --account, --grace-days, --tolerance, --cancelled or --active');
      const result = await api.call(subscriptionsUpdate, { path: { subscription_id: sub.id }, body });
      app.out.done(result, `Updated “${str(sub.name)}”.`);
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
      const data = query
        ? await api.call(subscriptionsReport, { path: { subscription_id: (await resolveSub(api, query)).id } })
        : await api.call(subscriptionsReports);
      const reports: SubscriptionReport[] = 'reports' in data ? data.reports : [data];
      app.out.emit(data, {
        records: () => reports,
        human: () => {
          const c = app.out.colors;
          if (!reports.length) return app.out.note('No subscriptions to check.');
          for (const r of reports) {
            app.out.line(`${app.out.heading(r.name)} ${c.dim(singleLine(r.subscription_id.slice(0, 8)))}`);
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
  const resolvePolicy = async (api: SalliClient, query: string): Promise<InsurancePolicy> =>
    resolveById((await api.call(insurancePoliciesList, { query: { active_only: false } })).policies, query, 'policy');

  policies
    .command('list')
    .alias('ls')
    .description('List policies')
    .option('--all', 'Include lapsed (inactive) policies')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(insurancePoliciesList, { query: { active_only: !opts.all } });
      app.out.emit(data, {
        records: (d) => d.policies,
        human: (d) => {
          const rows = d.policies;
          if (!rows.length) return app.out.note('No policies yet. Add one with `salli insurance policies add`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'ID', get: (p) => p.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'NAME', get: (p) => p.name, shrink: true },
              { header: 'TYPE', get: (p) => p.policy_type },
              { header: 'PROVIDER', get: (p) => p.provider, shrink: true },
              { header: 'COVER', get: (p) => app.out.money(p.coverage_amount, p.currency), align: 'right' },
              { header: 'PREMIUM', get: (p) => `${app.out.money(p.premium_amount, p.currency)} ${p.premium_frequency}`, align: 'right' },
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
      const data = await api.call(insurancePoliciesGet, { path: { policy_id: policy.id } });
      app.out.emit(data, { human: (d) => app.out.line(renderRecord(app, d, { money: ['coverage_amount', 'premium_amount'] })) });
    });

  policies
    .command('add')
    .argument('<name>', 'e.g. "Life cover"')
    .description('Add a policy')
    .requiredOption('--type <type>', 'life, health, income_protection (cover: the monthly benefit), motor, property, liability, other')
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
          coverage_amount: amountArg(opts.cover, '--cover'),
          premium_amount: amountArg(opts.premium, '--premium'),
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
        coverage_amount: opts.cover ? amountArg(opts.cover, '--cover') : undefined,
        premium_amount: opts.premium ? amountArg(opts.premium, '--premium') : undefined,
        premium_frequency: opts.frequency,
        expiry_date: opts.expires ? parseDate(opts.expires, app.runtime.now(), '--expires') : undefined,
        is_active: opts.lapsed ? false : opts.active ? true : undefined,
      });
      requireChanges(body, '--name, --type, --provider, --cover, --premium, --frequency, --expires, --lapsed or --active');
      const result = await api.call(insurancePoliciesUpdate, { path: { policy_id: policy.id }, body });
      app.out.done(result, `Updated “${str(policy.name)}”.`);
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

  const targets = insurance.command('targets').alias('target').description('Experimental: How much cover you want, per type');

  targets
    .command('list')
    .alias('ls')
    .description('List cover targets')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(insuranceTargetsList);
      app.out.emit(data, {
        records: (d) => d.targets,
        human: (d) => {
          const rows = d.targets;
          if (!rows.length) return app.out.note('No targets yet. Set one with `salli insurance targets set life --amount 500000`.');
          app.out.line(
            app.out.table(rows, [
              { header: 'TYPE', get: (t) => t.policy_type },
              { header: 'TARGET', get: (t) => app.out.money(t.target_amount, t.currency), align: 'right' },
            ]),
          );
        },
      });
    });

  targets
    .command('set')
    .argument('<type>', 'life, health, income_protection (cover: the monthly benefit), motor, property, liability, other')
    .requiredOption('--amount <amount>', 'The cover you want in total for this type')
    .description('Set the cover you want for a type')
    .action(async (type, opts) => {
      const api = await app.api();
      const result = await api.call(insuranceTargetsSet, {
        body: { policy_type: type, target_amount: amountArg(opts.amount, '--amount') },
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
    .command('needs')
    .description('Experimental: Life cover and income protection, as figures from your money (never a product)')
    .option('--years <n>', 'Years of income to replace', '10')
    .option('--benefit-years <n>', 'Years a disability benefit would pay (else to your planning age)')
    .option('--sick-pay <amount>', 'What your employer would pay while you are off sick, in all')
    .action(async (opts) => {
      const api = await app.api();
      const r = await api.call(insuranceNeeds, {
        query: {
          replacement_years: countArg('--years')(opts.years),
          ...(opts.benefitYears === undefined ? {} : { benefit_years: countArg('--benefit-years')(opts.benefitYears) }),
          ...(opts.sickPay === undefined ? {} : { sick_pay: amountArg(opts.sickPay, '--sick-pay') }),
        },
      });
      app.out.emit(r, {
        human: (d) => {
          const m = (v: string): string => app.out.money(v, d.currency);
          app.out.line(
            app.out.details([
              [`Income for ${d.replacement_years} years`, m(d.income_replacement)],
              ['+ Debts', m(d.debts)],
              ['+ Goals still to fund', m(d.goals)],
              ['− Cash, savings, investments', m(d.assets)],
              ['Life cover need', m(d.life_cover_need)],
              ['Life cover held', m(d.life_cover_held)],
              ['Gap', m(d.life_cover_gap)],
              ['Income protection, a month', m(d.income_protection_monthly)],
              ['Liability cover need (net worth)', m(d.liability_cover_need)],
              ['Liability cover held', m(d.liability_cover_held)],
              ['Liability gap', m(d.liability_cover_gap)],
              [`Disability cover need (${d.protection_months} months, less sick pay)`, m(d.protection_need)],
              ['Disability cover held', m(d.protection_held)],
              ['Disability gap', m(d.protection_gap)],
            ]),
          );
        },
      });
    });

  insurance
    .command('report')
    .description('Cover against your targets, missing types, and policies expiring soon')
    .action(async () => {
      const api = await app.api();
      const r = await api.call(insuranceReport);
      app.out.emit(r, {
        records: (d) => d.lines,
        human: (d) => {
          const out = app.out;
          if (d.lines.length) {
            out.line(
              out.table(d.lines, [
                { header: 'TYPE', get: (l) => l.policy_type },
                { header: 'TARGET', get: (l) => `${out.amount(l.target_amount, d.currency)}${l.basis === 'needs' ? ' (needs)' : ''}`, align: 'right' },
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

function riskRows(app: App, r: InvestorRiskProfile): Array<readonly [string, string]> {
  const out = app.out;
  const c = r.capacity;
  return [
    ['Tolerance', r.tolerance.category ? `${r.tolerance.category} (${r.tolerance.score ?? '—'})` : 'not answered (`salli onboarding risk`)'],
    ['Capacity', `${c.category} (${c.score})${c.missing.length ? `, without ${c.missing.join(', ')}` : ''}`],
    ['Need', r.need.category ? `${r.need.category}: ${r.need.required_return === null ? 'beyond 20%' : `${out.percent(r.need.required_return, 2)} a year after inflation`}${r.need.above_profile ? ', above the profile' : ''}` : 'no horizon (`salli ips set --horizon`)'],
    ['Profile', `${r.profile}: equity up to ${out.percent(r.equity_max)}`],
    ['Method', str(r.method.says)],
  ];
}

// ── Investment policy ────────────────────────────────────────────────────────

/** `CLASS:SHARE,…`, a holding's look-through. */
function allocationArg(value: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const pair of value.split(',')) {
    const [cls, share] = pair.split(':');
    if (!cls || !share) throw new UsageError(`--allocation takes CLASS:SHARE,… e.g. equity:0.6,fixed_income:0.4 (got "${value}").`);
    out[cls.trim()] = rateArg(share, '--allocation');
  }
  return out;
}

/** `CLASS:FRACTION[:BAND]`, for `salli ips set --target`. */
function policyTarget(value: string): PolicyTargetIn {
  const [cls, target, band] = value.split(':');
  if (!cls || !target) throw new UsageError(`--target takes ASSET_CLASS:FRACTION[:BAND], e.g. equity:0.6:0.05 (got "${value}").`);
  return { asset_class: cls as PolicyTargetIn['asset_class'], target: rateArg(target, '--target'), ...(band ? { band: rateArg(band, '--target') } : {}) };
}

function registerPolicy(program: Command, app: App): void {
  const ips = program.command('ips').description('Experimental: Your investment policy statement: targets with bands, rebalancing rule, horizon, review date; drift against it');

  ips
    .command('show', { isDefault: true })
    .description('The policy in force')
    .action(async () => {
      const api = await app.api();
      const p = await api.call(ipsGet);
      app.out.emit(p, {
        human: (d) => {
          const out = app.out;
          out.line(`${out.heading(`Investment policy, version ${d.version}`)} ${out.colors.dim(displayDate(d.created_at.slice(0, 10), out.locale))}`);
          out.line(
            out.table(d.content.targets, [
              { header: 'ASSET CLASS', get: (t) => t.asset_class },
              { header: 'TARGET', get: (t) => out.percent(t.target), align: 'right' },
              { header: 'BAND ±', get: (t) => out.percent(t.band), align: 'right' },
            ]),
          );
          const r = d.content.rebalancing;
          out.line(
            out.details([
              ['Rebalancing', r.rule === 'bands' ? 'when a class leaves its band' : `${r.rule === 'both' ? 'when a class leaves its band, or ' : ''}every ${r.every_months ?? '?'} months`],
              ['Horizon', d.content.horizon_years === null ? '—' : `${d.content.horizon_years} years`],
              ['Objectives', str(d.content.objectives) || '—'],
              ['Constraints', str(d.content.constraints) || '—'],
              ['Review on', d.content.review_on ? displayDate(d.content.review_on, out.locale) : '—'],
            ]),
          );
        },
      });
    });

  ips
    .command('history')
    .description('Every version, oldest first')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(ipsVersions);
      app.out.emit(data, {
        records: (d) => d.versions,
        human: (d) => {
          if (!d.versions.length) return app.out.note('No investment policy yet: `salli ips set`.');
          app.out.line(
            app.out.table(d.versions, [
              { header: 'VERSION', get: (v) => String(v.version), align: 'right' },
              { header: 'ADOPTED', get: (v) => displayDate(v.created_at.slice(0, 10), app.out.locale) },
              { header: 'TARGETS', get: (v) => v.content.targets.map((t) => `${t.asset_class} ${app.out.percent(t.target)}`).join(', '), shrink: true },
            ]),
          );
        },
      });
    });

  ips
    .command('set')
    .description('Adopt a new version (earlier ones are kept)')
    .requiredOption('--target <class:fraction[:band]>', 'A target share and its band, e.g. equity:0.6:0.05 (repeatable; they add up to 1)', collect)
    .addOption(new Option('--rebalance <rule>', 'When to rebalance').choices(['bands', 'calendar', 'both'] as const).default('bands' as const))
    .option('--every-months <n>', 'For a calendar rule: how often')
    .option('--horizon <years>', 'Years until the money is needed')
    .option('--objectives <text>', 'What the money is for, in your words')
    .option('--constraints <text>', 'Limits you set yourself')
    .option('--review-on <date>', 'When to look at the policy again (YYYY-MM-DD)')
    .option('--override-reason <text>', 'Why the equity target may sit above your risk profile’s band (needed then; stored with the version)')
    .action(async (opts) => {
      const api = await app.api();
      const now = app.runtime.now();
      const stored = await api.call(ipsAdopt, {
        body: {
          targets: (opts.target ?? []).map(policyTarget),
          rebalancing: { rule: opts.rebalance, ...(opts.everyMonths ? { every_months: countArg('--every-months')(opts.everyMonths) } : {}) },
          ...(opts.horizon ? { horizon_years: countArg('--horizon')(opts.horizon) } : {}),
          ...(opts.objectives ? { objectives: opts.objectives } : {}),
          ...(opts.constraints ? { constraints: opts.constraints } : {}),
          ...(opts.reviewOn ? { review_on: parseDate(opts.reviewOn, now, '--review-on') } : {}),
          ...(opts.overrideReason ? { override_reason: opts.overrideReason } : {}),
        },
      });
      app.out.done(stored, `Adopted version ${stored.version} of your investment policy.`);
    });

  ips
    .command('drift')
    .description('The portfolio against the policy, with your risk profile beside it')
    .action(async () => {
      const api = await app.api();
      const d = await api.call(ipsDrift);
      app.out.emit(d, {
        records: (r) => r.classes,
        human: (r) => {
          const out = app.out;
          out.line(
            out.table(r.classes, [
              { header: 'ASSET CLASS', get: (c) => `${c.asset_class}${c.in_policy ? '' : ' (not in policy)'}` },
              { header: 'NOW', get: (c) => out.percent(c.current_pct), align: 'right' },
              { header: 'TARGET', get: (c) => `${out.percent(c.target_pct)} ±${out.percent(c.band)}`, align: 'right' },
              { header: 'DRIFT', get: (c) => out.percent(c.drift_pct, 1), align: 'right', style: (t, c) => (c.outside_band ? out.colors.yellow(t) : t) },
              { header: `TO TARGET (${r.currency})`, get: (c) => out.amount(c.to_target, r.currency), align: 'right' },
            ]),
          );
          if (r.rebalance_due) out.line('Your policy’s rebalancing rule says it is time to rebalance.');
          if (r.review_due) out.line('Your policy’s review date has come.');
          out.line();
          out.line(out.details(riskRows(app, r.risk_profile)));
          if (r.equity_check.above_profile) {
            out.line(`${out.colors.yellow('!')} The policy’s equity target (${out.percent(r.equity_check.equity_target)}) is above your ${r.equity_check.profile} profile’s ${out.percent(r.equity_check.profile_equity_max)}${r.equity_check.override_reason ? `, by your override: ${singleLine(r.equity_check.override_reason)}` : ''}.`);
          }
          for (const sale of r.tax_aware_sales) {
            out.line();
            out.line(`${out.heading(`To bring ${sale.asset_class} to target`)}: ${out.money(sale.to_sell, r.currency)} of lots, realising ${out.money(sale.realised_gain, r.currency)} (losses first; figures, not advice)`);
            out.line(
              out.table(sale.lots, [
                { header: 'HOLDING', get: (l) => singleLine(l.symbol) },
                { header: 'LOT', get: (l) => displayDate(l.opened_on, out.locale) },
                { header: 'HELD', get: (l) => l.holding_period ?? '—' },
                { header: 'UNITS', get: (l) => l.quantity, align: 'right' },
                { header: 'PROCEEDS', get: (l) => out.amount(l.proceeds, r.currency), align: 'right' },
                { header: 'GAIN', get: (l) => out.amount(l.realised_gain, r.currency), align: 'right' },
              ]),
            );
          }
          for (const note of r.notes) out.note(singleLine(note));
        },
      });
    });

  ips
    .command('risk')
    .description('Risk tolerance, risk capacity from your figures, and the profile (the lower)')
    .action(async () => {
      const api = await app.api();
      const r = await api.call(ipsRiskProfile);
      app.out.emit(r, { human: (d) => app.out.line(app.out.details(riskRows(app, d))) });
    });
}

export function registerPlanning(program: Command, app: App): void {
  registerBudgets(program, app);
  registerDebts(program, app);
  registerPortfolio(program, app);
  registerSubscriptions(program, app);
  registerInsurance(program, app);
}
