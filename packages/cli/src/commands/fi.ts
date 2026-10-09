/**
 * Financial independence (score, projections, purchases, strategy), goals
 * and the wealth advisor.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  advisorDailyBriefingGet,
  advisorDailyBriefingSet,
  advisorRecommendationsApply,
  advisorRecommendationsDismiss,
  advisorReportsLatest,
  advisorReportsList,
  advisorRun,
  fiProjections,
  fiScoreGet,
  fiScoreHistory,
  fiScoreRecompute,
  fiSimulatePurchase,
  fiStrategyGenerate,
  fiStrategyGet,
  fiStrategyHistory,
  fiSurplus,
  goalsAllocationsList,
  goalsAllocationsSet,
  goalsCreate,
  goalsDelete,
  goalsList,
  goalsUpdate,
  parseEventData,
  SalliApiError,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import type { FiScore } from '../api-types';
import { CliError, UsageError } from '../errors';
import { plural, singleLine } from '../output/text';
import { displayDate, parseDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { AccountBook, amountArg, confirmAction, countArg, rateArg } from './shared';

type Row = Record<string, unknown> & { id: string };
/** A field from the server, as one line of safe text. */
const str = (v: unknown): string => (typeof v === 'string' ? singleLine(v) : v === null || v === undefined ? '' : String(v));

// ── FI score and the rest of `salli fi` ──────────────────────────────────────

function scoreView(app: App, s: FiScore): void {
  const out = app.out;
  const cur = s.currency;
  out.line(`${out.heading(`FI score ${s.overall_score}`)} ${out.colors.dim(`(grade ${s.grade})`)}`);
  out.line(
    out.details([
      ['Monthly income', out.money(s.monthly_income, cur)],
      ['Monthly spending', out.money(s.monthly_expenses, cur)],
      ['Monthly surplus', out.signed(out.money(s.monthly_surplus, cur), s.monthly_surplus)],
      ['Savings rate', out.percent(s.savings_rate)],
      ['FI number', out.money(s.fi_number, cur)],
      ['Net worth', out.money(s.net_worth, cur)],
      ['Progress to FI', out.percent(s.progress_to_fi)],
      ['Emergency fund', `${s.emergency_fund_months} months`],
      ['FI by', s.projected_fi_date ? displayDate(s.projected_fi_date, out.locale) : 'not yet in reach'],
    ]),
  );
  if (s.components?.length) {
    out.line();
    out.line(
      out.table(s.components, [
        { header: 'PART', get: (c) => c.label ?? '' },
        { header: 'SCORE', get: (c) => c.score ?? '', align: 'right' },
        { header: 'WEIGHT', get: (c) => out.percent(c.weight, 0), align: 'right' },
        { header: 'WHY', get: (c) => c.detail ?? '', shrink: true },
      ]),
    );
  }
}

function strategyView(app: App, s: Record<string, unknown>): void {
  const out = app.out;
  out.line(`${out.heading('FIRE strategy')} ${out.colors.dim(`v${str(s.version)}${s.fire_style ? ` · ${str(s.fire_style)}` : ''}`)}`);
  out.line(
    out.details([
      ['Safe withdrawal', s.swr === undefined ? undefined : out.percent(s.swr, 2)],
      ['Returns', [s.return_conservative, s.return_base, s.return_growth].every((r) => r !== undefined) ? `${out.percent(s.return_conservative, 1)} / ${out.percent(s.return_base, 1)} / ${out.percent(s.return_growth, 1)} (conservative / base / growth)` : undefined],
      ['Target spending', s.target_monthly_expenses === undefined || s.target_monthly_expenses === null ? undefined : `${str(s.target_monthly_expenses)} a month`],
      ['Target age', str(s.target_age) || undefined],
    ]),
  );
  const buckets = Array.isArray(s.buckets) ? (s.buckets as Array<Record<string, unknown>>) : [];
  if (buckets.length) {
    out.line();
    out.line(
      out.table(buckets, [
        { header: 'BUCKET', get: (b) => str(b.name) },
        { header: 'TARGET', get: (b) => str(b.target_pct), align: 'right' },
        { header: 'WHAT FOR', get: (b) => str(b.description), shrink: true },
      ]),
    );
  }
  if (typeof s.ai_rationale === 'string' && s.ai_rationale) {
    out.line();
    out.line(out.colors.dim(singleLine(s.ai_rationale)));
  }
}

function registerFi(program: Command, app: App): void {
  const fi = program.command('fi').description('Financial independence: your score, projections, and what a purchase costs you');

  fi.command('score')
    .description('Your FI score and the figures behind it')
    .option('--recompute', 'Compute it afresh from the ledger')
    .action(async (opts) => {
      const api = await app.api();
      const score = (await (opts.recompute ? api.call(fiScoreRecompute) : api.call(fiScoreGet))) as FiScore;
      app.out.emit(score, { records: (s) => s.components ?? [], human: (s) => scoreView(app, s) });
    });

  fi.command('history')
    .description('How your FI score has moved')
    .action(async () => {
      const api = await app.api();
      const data = (await api.call(fiScoreHistory)) as { history: Array<Record<string, unknown>> };
      app.out.emit(data, {
        records: (d) => d.history,
        human: (d) => {
          if (!d.history.length) return app.out.note('No history yet.');
          app.out.line(
            app.out.table(d.history, [
              { header: 'DATE', get: (h) => displayDate(h.created_at, app.out.locale) },
              { header: 'SCORE', get: (h) => str(h.overall_score ?? h.score), align: 'right' },
              { header: 'NET WORTH', get: (h) => app.out.money(h.net_worth, h.currency ?? ''), align: 'right' },
            ]),
          );
        },
      });
    });

  fi.command('projections')
    .description('Your investments projected forward, and the year you reach FI in each scenario')
    .action(async () => {
      const api = await app.api();
      const p = (await api.call(fiProjections)) as {
        currency: string;
        fi_number: string;
        current_portfolio: string;
        fire_year_conservative: number | null;
        fire_year_base: number | null;
        fire_year_growth: number | null;
        points: Array<{ year: number; conservative: string; base: string; growth: string }>;
      };
      app.out.emit(p, {
        records: (d) => d.points,
        human: (d) => {
          const out = app.out;
          const years = (n: number | null): string => (n === null ? 'not in reach' : plural(n, 'year'));
          out.line(
            out.details([
              ['FI number', out.money(d.fi_number, d.currency)],
              ['Invested now', out.money(d.current_portfolio, d.currency)],
              ['FI in', `${years(d.fire_year_conservative)} / ${years(d.fire_year_base)} / ${years(d.fire_year_growth)} (conservative / base / growth)`],
            ]),
          );
          out.line();
          out.line(
            out.table(d.points, [
              { header: 'YEAR', get: (pt) => pt.year, align: 'right' },
              { header: 'CONSERVATIVE', get: (pt) => out.amount(pt.conservative, d.currency), align: 'right' },
              { header: 'BASE', get: (pt) => out.amount(pt.base, d.currency), align: 'right' },
              { header: 'GROWTH', get: (pt) => out.amount(pt.growth, d.currency), align: 'right' },
            ]),
          );
          out.note(`Amounts in ${d.currency}, in today’s money.`);
        },
      });
    });

  fi.command('surplus')
    .description('Where money comes from and goes, averaged over the last 12 months')
    .action(async () => {
      const api = await app.api();
      const s = (await api.call(fiSurplus)) as {
        currency: string;
        income_by_source: Record<string, string>;
        expense_by_category: Record<string, string>;
        gross_monthly_income: string;
        gross_monthly_expenses: string;
        monthly_surplus: string;
        savings_rate: string;
      };
      app.out.emit(s, {
        human: (d) => {
          const out = app.out;
          out.line(
            out.details([
              ['Monthly income', out.money(d.gross_monthly_income, d.currency)],
              ['Monthly spending', out.money(d.gross_monthly_expenses, d.currency)],
              ['Monthly surplus', out.signed(out.money(d.monthly_surplus, d.currency), d.monthly_surplus)],
              ['Savings rate', out.percent(d.savings_rate)],
            ]),
          );
          const section = (title: string, items: Record<string, string>): void => {
            const rows = Object.entries(items).map(([name, amount]) => ({ name, amount }));
            if (!rows.length) return;
            out.line();
            out.line(
              out.table(rows, [
                { header: title, get: (r) => r.name, shrink: true },
                { header: `A MONTH (${d.currency})`, get: (r) => out.amount(r.amount, d.currency), align: 'right' },
              ]),
            );
          };
          section('INCOME', d.income_by_source);
          section('SPENDING', d.expense_by_category);
        },
      });
    });

  fi.command('simulate-purchase')
    .alias('afford')
    .argument('<amount>', 'The price')
    .description('What a purchase costs you in months of freedom: cash against instalments')
    .option('--months <n>', 'Pay in instalments over this many months', countArg('--months'))
    .option('--rate <rate>', 'The instalments’ annual interest: 0.18 or 18%', '0')
    .action(async (amountText, opts) => {
      const api = await app.api();
      const impact = (await api.call(fiSimulatePurchase, {
        body: {
          amount: amountArg(amountText),
          ...(opts.months !== undefined ? { term_months: opts.months } : {}),
          annual_interest_rate: rateArg(opts.rate, '--rate'),
        },
      })) as {
        amount: string;
        currency: string;
        baseline_months_to_fi: number | null;
        payable_from_liquid: boolean;
        options: Array<{ key: string; label: string; total_cost: string; interest_cost: string; monthly_payment: string | null; months_delay: number | null; exceeds_monthly_surplus: boolean }>;
        cheapest_option_key: string | null;
        is_stale: boolean;
        data_as_of: string | null;
      };
      app.out.emit(impact, {
        records: (d) => d.options,
        human: (d) => {
          const out = app.out;
          out.line(out.heading(`Buying something for ${out.money(d.amount, d.currency)}`));
          out.line(
            out.table(d.options, [
              { header: 'HOW', get: (o) => o.label + (o.key === d.cheapest_option_key ? ' (cheapest)' : '') },
              { header: 'COSTS', get: (o) => out.amount(o.total_cost, d.currency), align: 'right' },
              { header: 'INTEREST', get: (o) => out.amount(o.interest_cost, d.currency), align: 'right' },
              { header: 'A MONTH', get: (o) => (o.monthly_payment ? out.amount(o.monthly_payment, d.currency) : ''), align: 'right' },
              {
                header: 'DELAYS FI BY',
                get: (o) => (o.months_delay === null ? 'unknown' : plural(o.months_delay, 'month')),
                align: 'right',
                style: (t, o) => (o.exceeds_monthly_surplus ? out.colors.red(t) : t),
              },
            ]),
          );
          out.note(`Amounts in ${d.currency}.`);
          if (!d.payable_from_liquid) out.warn('Paying cash would use more than your liquid savings.');
          if (d.is_stale) out.warn(`Your ledger’s latest entry is from ${displayDate(d.data_as_of, out.locale)}: add recent entries for a truer answer.`);
        },
      });
    });

  const strategy = fi.command('strategy').description('Your FIRE strategy (drafted by the AI, all figures from the engine)');

  strategy
    .command('show', { isDefault: true })
    .description('Show your current strategy')
    .action(async () => {
      const api = await app.api();
      let data: Record<string, unknown>;
      try {
        data = (await api.call(fiStrategyGet)) as Record<string, unknown>;
      } catch (error) {
        if (error instanceof SalliApiError && error.status === 404) {
          throw new CliError('You have no FIRE strategy yet.', { exitCode: 4, kind: 'not-found', hint: 'Create one with `salli fi strategy generate`.' });
        }
        throw error;
      }
      app.out.emit(data, { human: (d) => strategyView(app, d) });
    });

  strategy
    .command('history')
    .description('Earlier versions of your strategy')
    .action(async () => {
      const api = await app.api();
      const data = (await api.call(fiStrategyHistory)) as { history: Array<Record<string, unknown>> };
      app.out.emit(data, {
        records: (d) => d.history,
        human: (d) => {
          if (!d.history.length) return app.out.note('No strategies yet.');
          app.out.line(
            app.out.table(d.history, [
              { header: 'VERSION', get: (h) => str(h.version), align: 'right' },
              { header: 'STYLE', get: (h) => str(h.fire_style) },
              { header: 'CREATED', get: (h) => displayDate(h.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  strategy
    .command('generate')
    .description('Draft a new strategy with the AI (streams its progress)')
    .action(async () => {
      const api = await app.api();
      const spinner = app.prompter.spinner();
      spinner.start('Drafting your strategy');
      let result: Record<string, unknown> | undefined;
      const events: unknown[] = [];
      try {
        for await (const message of api.events(fiStrategyGenerate, { signal: app.runtime.signal })) {
          const event = parseEventData(message) as { type?: string; message?: string; strategy?: Record<string, unknown> } | undefined;
          if (!event) continue;
          events.push(event);
          if (app.out.format === 'ndjson') app.out.line(message.data);
          if (event.type === 'status' && event.message) spinner.message(event.message);
          if (event.type === 'error') throw new CliError(`The strategy could not be drafted: ${event.message ?? 'unknown error'}`);
          if (event.type === 'done') result = event.strategy;
        }
      } finally {
        spinner.stop();
      }
      if (app.out.format === 'ndjson') return;
      if (!result) throw new CliError('The server finished without a strategy.');
      app.out.emit(result, { human: (d) => strategyView(app, d) });
    });
}

// ── Goals ────────────────────────────────────────────────────────────────────

function registerGoals(program: Command, app: App): void {
  const goals = program.command('goals').alias('goal').description('Savings goals, funded by money earmarked in real accounts');
  const resolveGoal = async (api: SalliClient, query: string): Promise<Row> => {
    const data = (await api.call(goalsList)) as { goals: Row[] };
    return resolveById(data.goals, query, 'goal');
  };

  goals
    .command('list')
    .alias('ls')
    .description('List goals and their progress')
    .action(async () => {
      const api = await app.api();
      const data = (await api.call(goalsList)) as { goals: Row[] };
      app.out.emit(data, {
        records: (d) => d.goals,
        human: (d) => {
          if (!d.goals.length) return app.out.note('No goals yet. Add one with `salli goals add`.');
          const out = app.out;
          out.line(
            out.table(d.goals, [
              { header: 'ID', get: (g) => g.id.slice(0, 8), style: (t) => out.colors.dim(t) },
              { header: 'NAME', get: (g) => str(g.name), shrink: true },
              { header: 'TARGET', get: (g) => out.money(g.target_amount, g.currency), align: 'right' },
              { header: 'FUNDED', get: (g) => out.amount(g.current_amount, g.currency), align: 'right' },
              { header: 'PROGRESS', get: (g) => out.percent(g.progress, 0), align: 'right' },
              { header: 'BY', get: (g) => displayDate(g.target_date, out.locale) },
              {
                header: '',
                get: (g) => (typeof g.shortfall === 'string' && !/^0*(\.0*)?$/.test(g.shortfall) ? `short ${out.amount(g.shortfall, g.currency)}` : ''),
                style: (t) => out.colors.yellow(t),
              },
            ]),
          );
        },
      });
    });

  goals
    .command('add')
    .argument('<name>', 'e.g. "Emergency fund"')
    .description('Add a goal')
    .option('--target <amount>', 'How much it needs')
    .option('--by <date>', 'When (YYYY-MM-DD)')
    .option('--kind <kind>', 'emergency_fund, home, retirement, custom…', 'custom')
    .option('--priority <n>', '1 (high) to 3 (low): who is funded first when an account backs several goals', countArg('--priority'), 2)
    .action(async (name, opts) => {
      const api = await app.api();
      const created = await api.call(goalsCreate, {
        body: {
          name,
          kind: opts.kind,
          priority: opts.priority,
          ...(opts.target ? { target_amount: amountArg(opts.target, '--target') } : {}),
          ...(opts.by ? { target_date: parseDate(opts.by, app.runtime.now(), '--by') } : {}),
        },
      });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added the goal “${name}”. Back it with money: salli goals allocate "${name}" <account> <amount>`);
    });

  goals
    .command('update')
    .argument('<goal>', 'Goal id (or its start)')
    .description('Change a goal')
    .option('--name <name>', 'New name')
    .option('--target <amount>', 'New target')
    .option('--by <date>', 'New date')
    .option('--kind <kind>', 'New kind')
    .option('--priority <n>', 'New priority', countArg('--priority'))
    .option('--archive', 'Archive it (inactive)')
    .option('--active', 'Make it active again')
    .action(async (query, opts) => {
      const api = await app.api();
      const goal = await resolveGoal(api, query);
      const body = Object.fromEntries(
        Object.entries({
          name: opts.name,
          kind: opts.kind,
          priority: opts.priority,
          target_amount: opts.target ? amountArg(opts.target, '--target') : undefined,
          target_date: opts.by ? parseDate(opts.by, app.runtime.now(), '--by') : undefined,
          is_active: opts.archive ? false : opts.active ? true : undefined,
        }).filter(([, v]) => v !== undefined),
      );
      if (!Object.keys(body).length) throw new UsageError('Nothing to change.', 'Pass --name, --target, --by, --kind, --priority, --archive or --active.');
      const result = await api.call(goalsUpdate, { path: { goal_id: goal.id }, body });
      app.out.done(result as Record<string, unknown>, `Updated “${str(goal.name)}”.`);
    });

  goals
    .command('delete')
    .argument('<goal>', 'Goal id (or its start)')
    .description('Delete a goal')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const goal = await resolveGoal(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the goal “${str(goal.name)}”?`))) return;
      await api.call(goalsDelete, { path: { goal_id: goal.id } });
      app.out.done({ id: goal.id, deleted: true }, `Deleted “${str(goal.name)}”.`);
    });

  goals
    .command('allocations')
    .argument('<goal>', 'Goal id (or its start)')
    .description('Which accounts back a goal, and how much of each')
    .action(async (query) => {
      const api = await app.api();
      const goal = await resolveGoal(api, query);
      const [data, book] = await Promise.all([
        api.call(goalsAllocationsList, { path: { goal_id: goal.id } }) as Promise<{ allocations: Array<{ account_id: string; allocated_amount: string; currency: string }> }>,
        AccountBook.load(api),
      ]);
      app.out.emit(data, {
        records: (d) => d.allocations,
        human: (d) => {
          if (!d.allocations.length) return app.out.note(`Nothing earmarked for “${str(goal.name)}” yet: salli goals allocate`);
          app.out.line(
            app.out.table(d.allocations, [
              { header: 'ACCOUNT', get: (a) => book.label(a.account_id), shrink: true },
              { header: 'EARMARKED', get: (a) => app.out.money(a.allocated_amount, a.currency), align: 'right' },
            ]),
          );
        },
      });
    });

  goals
    .command('allocate')
    .argument('<goal>', 'Goal id (or its start)')
    .argument('<account>', 'Account (code, name or id)')
    .argument('<amount>', 'How much of the account is for this goal; 0 clears it')
    .description('Earmark part of an account for a goal')
    .action(async (query, accountQuery, amountText) => {
      const api = await app.api();
      const [goal, book] = await Promise.all([resolveGoal(api, query), AccountBook.load(api)]);
      const account = book.resolve(accountQuery);
      const amount = amountArg(amountText);
      const result = await api.call(goalsAllocationsSet, { path: { goal_id: goal.id }, body: { account_id: account.id, allocated_amount: amount } });
      app.out.done(
        result as Record<string, unknown>,
        /^0*(\.0*)?$/.test(amount)
          ? `Cleared ${account.name} from “${str(goal.name)}”.`
          : `Earmarked ${app.out.money(amount, account.currency)} of ${account.name} for “${str(goal.name)}”.`,
      );
    });
}

// ── Advisor ──────────────────────────────────────────────────────────────────

function reportView(app: App, report: Record<string, unknown>): void {
  const out = app.out;
  out.line(`${out.heading('Advisor report')} ${out.colors.dim(`${displayDate(report.created_at, out.locale)} · ${str(report.id).slice(0, 8)}`)}`);
  if (report.summary) out.line(singleLine(str(report.summary)));
  if (report.fire_tier_assessment) out.line(out.colors.dim(singleLine(str(report.fire_tier_assessment))));
  const recs = Array.isArray(report.recommendations) ? (report.recommendations as Row[]) : [];
  if (recs.length) {
    out.line();
    out.line(
      out.table(recs, [
        { header: 'ID', get: (r) => str(r.id).slice(0, 8), style: (t) => out.colors.dim(t) },
        { header: 'RECOMMENDATION', get: (r) => str(r.title), shrink: true },
        { header: 'AREA', get: (r) => str(r.category) },
        { header: 'STATUS', get: (r) => str(r.status) },
      ]),
    );
  }
}

function registerAdvisor(program: Command, app: App): void {
  const advisor = program.command('advisor').description('The wealth advisor: a review of your finances, with recommendations');

  advisor
    .command('run')
    .description('Run the advisor now (an AI call)')
    .action(async () => {
      const api = await app.api();
      const spinner = app.prompter.spinner();
      spinner.start('Reviewing your finances');
      let report: Record<string, unknown>;
      try {
        report = (await api.call(advisorRun, { timeoutMs: 5 * 60_000 })) as Record<string, unknown>;
      } finally {
        spinner.stop();
      }
      app.out.emit(report, { records: (r) => (r.recommendations as unknown[]) ?? [], human: (r) => reportView(app, r) });
    });

  advisor
    .command('latest')
    .description('Show the most recent report')
    .action(async () => {
      const api = await app.api();
      const report = (await api.call(advisorReportsLatest)) as Record<string, unknown>;
      if (!report || Object.keys(report).length === 0) {
        throw new CliError('No advisor report yet.', { exitCode: 4, kind: 'not-found', hint: 'Run one with `salli advisor run`.' });
      }
      app.out.emit(report, { records: (r) => (r.recommendations as unknown[]) ?? [], human: (r) => reportView(app, r) });
    });

  advisor
    .command('reports')
    .description('List past reports')
    .action(async () => {
      const api = await app.api();
      const data = (await api.call(advisorReportsList)) as { reports: Row[] };
      app.out.emit(data, {
        records: (d) => d.reports,
        human: (d) => {
          if (!d.reports.length) return app.out.note('No reports yet. Run one with `salli advisor run`.');
          app.out.line(
            app.out.table(d.reports, [
              { header: 'ID', get: (r) => r.id.slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'DATE', get: (r) => displayDate(r.created_at, app.out.locale) },
              { header: 'TRIGGER', get: (r) => str(r.trigger) },
              { header: 'RECOMMENDATIONS', get: (r) => (Array.isArray(r.recommendations) ? r.recommendations.length : 0), align: 'right' },
            ]),
          );
        },
      });
    });

  for (const [name, fn, verb] of [
    ['apply', advisorRecommendationsApply, 'Applied'],
    ['dismiss', advisorRecommendationsDismiss, 'Dismissed'],
  ] as const) {
    advisor
      .command(name)
      .argument('<recommendation>', 'Recommendation id (or its start), from `salli advisor latest`')
      .option('--report <id>', 'The report it is in (default: the latest)')
      .description(`${verb === 'Applied' ? 'Apply' : 'Dismiss'} a recommendation`)
      .action(async (recQuery, opts) => {
        const api = await app.api();
        const reports = ((await api.call(advisorReportsList)) as { reports: Row[] }).reports;
        const report = opts.report ? resolveById(reports, opts.report, 'report') : reports[0];
        if (!report) throw new CliError('No advisor report yet.', { exitCode: 4, kind: 'not-found' });
        const recs = (Array.isArray(report.recommendations) ? report.recommendations : []) as Row[];
        const rec = resolveById(recs, recQuery, 'recommendation');
        const result = await api.call(fn, { path: { report_id: report.id, rec_id: rec.id } });
        app.out.done(result as Record<string, unknown>, `${verb} “${str(rec.title)}”.`);
      });
  }

  advisor
    .command('daily-briefing')
    .description('Show, or switch on or off, the daily advisor run')
    .option('--on', 'Run the advisor for you every day')
    .option('--off', 'Stop the daily run')
    .action(async (opts) => {
      if (opts.on && opts.off) throw new UsageError('Pass --on or --off, not both.');
      const api = await app.api();
      if (opts.on || opts.off) await api.call(advisorDailyBriefingSet, { body: { enabled: !!opts.on } });
      const state = (await api.call(advisorDailyBriefingGet)) as { enabled: boolean };
      app.out.emit(state, { human: (s) => app.out.line(`Daily briefing: ${s.enabled ? 'on' : 'off'}`) });
    });
}

export function registerPlanningAhead(program: Command, app: App): void {
  registerFi(program, app);
  registerGoals(program, app);
  registerAdvisor(program, app);
}

