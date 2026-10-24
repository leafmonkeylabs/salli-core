/**
 * Financial independence (score, projections, assumptions), goals and the
 * monthly briefing. What a purchase does is a scenario: `salli whatif`,
 * `salli compare`.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  advisorBriefingPrepare,
  advisorBriefingResume,
  advisorDailyBriefingGet,
  advisorDailyBriefingSet,
  advisorReportsLatest,
  advisorReportsList,
  advisorRun,
  fiAssumptions,
  fiAssumptionsSet,
  fiProjections,
  fiScoreGet,
  fiScoreHistory,
  fiScoreRecompute,
  fiSurplus,
  goalsAllocationsList,
  goalsAllocationsSet,
  goalsCreate,
  goalsDelete,
  goalsList,
  goalsUpdate,
  type AdvisoryReport,
  type BriefingPrepared,
  type FiAssumptions,
  type FiAssumptionsUpdate,
  type FiScore,
  type Goal,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, displayMonth, parseDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { AccountBook, amountArg, confirmAction, countArg, rateArg } from './shared';

/** A field from the server, as one line of safe text. */
const str = (v: unknown): string => (typeof v === 'string' ? singleLine(v) : v === null || v === undefined ? '' : String(v));

// ── Planning assumptions ─────────────────────────────────────────────────────
//
// FI figures are in real terms (today's money). Where you have set no figure,
// a neutral placeholder stands in, and every command that shows a figure built
// on one says so.

/** The assumptions you can set, by the name you type, and the API's name. */
const ASSUMPTIONS = {
  'real-return': { key: 'real_return', label: 'Real return' },
  'nominal-return': { key: 'nominal_return', label: 'Nominal return' },
  inflation: { key: 'inflation', label: 'Inflation' },
  swr: { key: 'safe_withdrawal_rate', label: 'Safe withdrawal rate' },
  'surplus-invested': { key: 'surplus_invested', label: 'Surplus invested' },
} as const;
type AssumptionName = keyof typeof ASSUMPTIONS;
const ASSUMPTION_NAMES = Object.keys(ASSUMPTIONS) as AssumptionName[];

function assumptionName(value: string): AssumptionName {
  const name = value.trim().toLowerCase().replace(/_/g, '-');
  const known = name === 'safe-withdrawal-rate' ? 'swr' : name;
  if (!(ASSUMPTION_NAMES as string[]).includes(known)) {
    throw new UsageError(`Unknown assumption "${value}".`, `They are: ${ASSUMPTION_NAMES.join(', ')}.`);
  }
  return known as AssumptionName;
}

const PLACEHOLDER_LABELS: Record<string, string> = {
  real_return: 'real return',
  safe_withdrawal_rate: 'safe withdrawal rate',
  surplus_invested: 'share of your monthly surplus invested',
};

/** Says, on stderr, when figures rest on placeholders, and how to set your own. */
function assumptionsNote(app: App, assumptions: FiAssumptions | null | undefined): void {
  if (!assumptions || assumptions.status !== 'placeholder') return;
  const labels = assumptions.placeholders.map((p) => `the ${PLACEHOLDER_LABELS[p] ?? p}`);
  const names = labels.length > 1 ? `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}` : (labels[0] ?? '');
  app.out.note(
    `Using placeholder assumptions for ${names}: round figures, not forecasts. Set yours with \`salli fi assumptions set real-return 5% --source <where it comes from>\` (and swr, and surplus-invested).`,
  );
}

// ── FI score and the rest of `salli fi` ──────────────────────────────────────

function scoreView(app: App, s: FiScore): void {
  const out = app.out;
  const cur = s.currency;
  out.line(`${out.heading(`FI score ${s.overall_score}`)} ${out.colors.dim(`(grade ${singleLine(s.grade)})`)}`);
  out.line(
    out.details([
      ['Monthly income', out.money(s.monthly_income, cur)],
      ['Monthly spending', out.money(s.monthly_expenses, cur)],
      ['Monthly surplus', out.signed(out.money(s.monthly_surplus, cur), s.monthly_surplus)],
      ['Savings rate', out.percent(s.savings_rate)],
      ['FI number', out.money(s.fi_number, cur)],
      ['Net worth', out.money(s.net_worth, cur)],
      ['Progress to FI', out.percent(s.progress_to_fi)],
      ['Emergency fund', `${out.decimal(s.emergency_fund_months, 1)} months`],
      ['FI by', s.projected_fi_month ? displayMonth(s.projected_fi_month, out.locale) : 'not yet in reach'],
    ]),
  );
  if (s.components.length) {
    out.line();
    out.line(
      out.table(s.components, [
        { header: 'PART', get: (c) => c.label },
        { header: 'SCORE', get: (c) => c.score, align: 'right' },
        { header: 'WEIGHT', get: (c) => out.percent(c.weight, 0), align: 'right' },
        { header: 'WHY', get: (c) => c.detail, shrink: true },
      ]),
    );
  }
}

function registerFi(program: Command, app: App): void {
  const fi = program.command('fi').description('Financial independence: your score, projections and assumptions');

  fi.command('score')
    .description('Your FI score and the figures behind it')
    .option('--recompute', 'Compute it afresh from the ledger')
    .action(async (opts) => {
      const api = await app.api();
      const score = await (opts.recompute ? api.call(fiScoreRecompute) : api.call(fiScoreGet));
      app.out.emit(score, {
        records: (s) => s.components,
        human: (s) => {
          scoreView(app, s);
          assumptionsNote(app, s.assumptions);
        },
      });
    });

  const assumptions = fi
    .command('assumptions')
    .description('The planning assumptions behind your FI figures (in real terms): which apply, where each came from, and setting your own');

  assumptions
    .command('show', { isDefault: true })
    .description('Which assumptions apply, where each came from, and which are placeholders')
    .action(async () => {
      const api = await app.api();
      const report = await api.call(fiAssumptions);
      app.out.emit(report, {
        human: (r) => {
          const out = app.out;
          const a = r.applied;
          const rows = ASSUMPTION_NAMES.map((name) => ({ name, ...ASSUMPTIONS[name], applied: a[ASSUMPTIONS[name].key] }));
          const from = (origin: string): string => (origin === 'user' ? 'you' : 'placeholder');
          out.line(`${out.heading('FI assumptions')} ${out.colors.dim('real terms: after inflation, in today’s money')}`);
          out.line(
            out.table(rows, [
              { header: 'ASSUMPTION', get: (n) => n.label },
              { header: 'APPLIED', get: (n) => (n.applied ? out.percent(n.applied.value, 2) : 'not set'), align: 'right' },
              { header: 'FROM', get: (n) => (n.applied ? from(n.applied.origin) : ''), style: (t) => (t === 'placeholder' ? out.colors.yellow(t) : t) },
              { header: 'SOURCE', get: (n) => (n.applied ? singleLine(n.applied.source) : ''), shrink: true },
            ]),
          );
          out.line(
            out.colors.dim(
              `Scenarios (real): ${out.percent(a.real_returns.conservative, 1)} / ${out.percent(a.real_returns.base, 1)} / ${out.percent(a.real_returns.growth, 1)} (conservative / base / growth)`,
            ),
          );
          out.note(singleLine(a.message));
          if (a.status === 'placeholder') {
            out.note('Set your own with `salli fi assumptions set <name> <rate> --source <where it comes from>`.');
          }
        },
      });
    });

  assumptions
    .command('set')
    .argument('<name>', `Which: ${ASSUMPTION_NAMES.join(', ')}`)
    .argument('<rate>', 'A yearly rate: 0.03 or 3%; for surplus-invested, the share you invest: 0.8 or 80%')
    .option('--source <source>', 'Where the figure comes from: a URL, or a publication and its date')
    .option('--note <note>', 'Anything else worth keeping with it')
    .description('Set one of your own planning assumptions, with its source')
    .action(async (nameText, rateText, opts) => {
      const name = assumptionName(nameText);
      const { key, label } = ASSUMPTIONS[name];
      const value = rateArg(rateText, '<rate>');
      const body: FiAssumptionsUpdate = { [key]: { value, source: opts.source ?? null, note: opts.note ?? null } };
      const api = await app.api();
      const report = await api.call(fiAssumptionsSet, { body });
      app.out.emit(report, {
        human: (r) => {
          app.out.success(`${label} set to ${app.out.percent(value, 2)}${opts.source ? ` (source: ${singleLine(opts.source)})` : ''}.`);
          if (!opts.source) app.out.warn('No source given: add one with --source, so you can check the figure later.');
          app.out.note(singleLine(r.applied.message));
        },
      });
    });

  assumptions
    .command('clear')
    .argument('<names...>', `Which: ${ASSUMPTION_NAMES.join(', ')}`)
    .description('Clear your own figures: a placeholder stands in again')
    .action(async (names) => {
      const keys = names.map((n) => ASSUMPTIONS[assumptionName(n)].key);
      const body: FiAssumptionsUpdate = Object.fromEntries(keys.map((k) => [k, null]));
      const api = await app.api();
      const report = await api.call(fiAssumptionsSet, { body });
      app.out.emit(report, {
        human: (r) => {
          app.out.success(`Cleared: ${names.join(', ')}.`);
          app.out.note(singleLine(r.applied.message));
        },
      });
    });

  fi.command('history')
    .description('How your FI score has moved')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(fiScoreHistory);
      app.out.emit(data, {
        records: (d) => d.history,
        human: (d) => {
          if (!d.history.length) return app.out.note('No history yet.');
          app.out.line(
            app.out.table(d.history, [
              { header: 'DATE', get: (h) => displayDate(h.created_at, app.out.locale) },
              { header: 'SCORE', get: (h) => h.score, align: 'right' },
              { header: `NET WORTH (${d.currency})`, get: (h) => (h.net_worth === null ? '' : app.out.amount(h.net_worth, d.currency)), align: 'right' },
            ]),
          );
        },
      });
    });

  fi.command('projections')
    .description('Your investments projected forward, and the month you reach FI in each scenario')
    .action(async () => {
      const api = await app.api();
      const p = await api.call(fiProjections);
      app.out.emit(p, {
        records: (d) => d.points ?? [],
        human: (d) => {
          const out = app.out;
          const currency = d.currency ?? '';
          const points = d.points ?? [];
          const by = (date: { month: string | null } | undefined): string => (date?.month ? displayMonth(date.month, out.locale) : 'not in reach');
          const future = d.terms === 'real_and_nominal';
          out.line(
            out.details([
              ['FI number', out.money(d.fi_number, currency)],
              ['Invested now', out.money(d.current_portfolio, currency)],
              d.fi_by
                ? ['FI by', `${by(d.fi_by.conservative)} / ${by(d.fi_by.base)} / ${by(d.fi_by.growth)} (conservative / base / growth)`]
                : false,
            ]),
          );
          if (points.length) {
            out.line();
            out.line(
              out.table(points, [
                { header: 'YEAR', get: (pt) => pt.year, align: 'right' },
                { header: 'CONSERVATIVE', get: (pt) => out.amount(pt.conservative, currency), align: 'right' },
                { header: 'BASE', get: (pt) => out.amount(pt.base, currency), align: 'right' },
                { header: 'GROWTH', get: (pt) => out.amount(pt.growth, currency), align: 'right' },
                ...(future
                  ? [
                      { header: 'BASE (THEN)', get: (pt: (typeof points)[number]) => (pt.nominal ? out.amount(pt.nominal.base, currency) : ''), align: 'right' as const },
                      { header: 'FI NUMBER (THEN)', get: (pt: (typeof points)[number]) => (pt.nominal ? out.amount(pt.nominal.fi_number, currency) : ''), align: 'right' as const },
                    ]
                  : []),
              ]),
            );
          }
          out.note(
            future
              ? `Amounts in ${singleLine(currency)}, in today’s money; the THEN columns are in each year’s own money, at your inflation of ${out.percent(d.inflation, 2)}.`
              : `Amounts in ${singleLine(currency)}, in today’s money. Set your inflation to see them in future money too: salli fi assumptions set inflation 3% --source <where it comes from>.`,
          );
          assumptionsNote(app, d.assumptions);
        },
      });
    });

  fi.command('surplus')
    .description('Where money comes from and goes, averaged over the last 12 months')
    .action(async () => {
      const api = await app.api();
      const s = await api.call(fiSurplus);
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
}

// ── Goals ────────────────────────────────────────────────────────────────────

function registerGoals(program: Command, app: App): void {
  const goals = program.command('goals').alias('goal').description('Savings goals, funded by money earmarked in real accounts');
  const resolveGoal = async (api: SalliClient, query: string): Promise<Goal> => resolveById((await api.call(goalsList)).goals, query, 'goal');

  goals
    .command('list')
    .alias('ls')
    .description('List goals and their progress')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(goalsList);
      app.out.emit(data, {
        records: (d) => d.goals,
        human: (d) => {
          if (!d.goals.length) return app.out.note('No goals yet. Add one with `salli goals add`.');
          const out = app.out;
          out.line(
            out.table(d.goals, [
              { header: 'ID', get: (g) => g.id.slice(0, 8), style: (t) => out.colors.dim(t) },
              { header: 'NAME', get: (g) => g.name, shrink: true },
              { header: 'TARGET', get: (g) => out.money(g.target_amount, g.currency), align: 'right' },
              { header: 'FUNDED', get: (g) => out.amount(g.current_amount, g.currency), align: 'right' },
              { header: 'PROGRESS', get: (g) => out.percent(g.progress, 0), align: 'right' },
              { header: 'BY', get: (g) => displayDate(g.target_date, out.locale) },
              {
                header: '',
                get: (g) => (/^0*(\.0*)?$/.test(g.shortfall) ? '' : `short ${out.amount(g.shortfall, g.currency)}`),
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
      app.out.done(result, `Updated “${str(goal.name)}”.`);
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
        api.call(goalsAllocationsList, { path: { goal_id: goal.id } }),
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
        result,
        /^0*(\.0*)?$/.test(amount)
          ? `Cleared ${account.name} from “${str(goal.name)}”.`
          : `Earmarked ${app.out.money(amount, account.currency)} of ${account.name} for “${str(goal.name)}”.`,
      );
    });
}

// ── Advisor ──────────────────────────────────────────────────────────────────

/** A briefing's summary and notes, then Salli's signals, as it was written. */
function notesView(app: App, b: { summary?: string | null; notes?: { topic: string; text: string }[] | null; signals?: { title?: string | null }[] | null }): void {
  const out = app.out;
  if (b.summary) out.line(singleLine(b.summary));
  for (const note of b.notes ?? []) out.line(`${out.colors.dim(note.topic.padEnd(12))} ${singleLine(note.text)}`);
  const signals = (b.signals ?? []).filter((s) => s.title);
  if (signals.length) {
    out.line();
    out.line(out.heading('Signals'));
    for (const s of signals) out.line(`- ${singleLine(str(s.title))}`);
  }
  out.note('The AI’s words; every figure in them is Salli’s. Not advice.');
}

function reportView(app: App, report: AdvisoryReport): void {
  const out = app.out;
  out.line(`${out.heading('Briefing')} ${out.colors.dim(`${displayDate(report.created_at, out.locale)} · ${str(report.id).slice(0, 8)}`)}`);
  notesView(app, report);
}

function registerAdvisor(program: Command, app: App): void {
  const advisor = program.command('advisor').description('The monthly briefing: your figures and signals, described by the AI (not advice)');

  advisor
    .command('run')
    .description('Write a briefing now (an AI call)')
    .action(async () => {
      const api = await app.api();
      const spinner = app.prompter.spinner();
      spinner.start('Writing your briefing');
      let report: AdvisoryReport;
      try {
        report = await api.call(advisorRun, { timeoutMs: 5 * 60_000 });
      } finally {
        spinner.stop();
      }
      app.out.emit(report, { records: (r) => r.notes ?? [], human: (r) => reportView(app, r) });
    });

  advisor
    .command('latest')
    .description('Show the most recent briefing')
    .action(async () => {
      const api = await app.api();
      const report = await api.call(advisorReportsLatest);
      // An empty object means there is none yet.
      if (!report.id) {
        throw new CliError('No briefing yet.', { exitCode: 4, kind: 'not-found', hint: 'Write one with `salli advisor run`.' });
      }
      app.out.emit(report, { records: (r) => r.notes ?? [], human: (r) => reportView(app, r) });
    });

  advisor
    .command('reports')
    .description('List past briefings')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(advisorReportsList);
      app.out.emit(data, {
        records: (d) => d.reports,
        human: (d) => {
          if (!d.reports.length) return app.out.note('No briefings yet. Write one with `salli advisor run`.');
          app.out.line(
            app.out.table(d.reports, [
              { header: 'ID', get: (r) => str(r.id).slice(0, 8), style: (t) => app.out.colors.dim(t) },
              { header: 'DATE', get: (r) => displayDate(r.created_at, app.out.locale) },
              { header: 'TRIGGER', get: (r) => str(r.trigger) },
              { header: 'SUMMARY', get: (r) => singleLine(str(r.summary)), shrink: true },
            ]),
          );
        },
      });
    });

  advisor
    .command('daily-briefing')
    .description('Show, or switch on or off, the daily briefing')
    .option('--on', 'Write a briefing for you every day')
    .option('--off', 'Stop the daily run')
    .action(async (opts) => {
      if (opts.on && opts.off) throw new UsageError('Pass --on or --off, not both.');
      const api = await app.api();
      if (opts.on || opts.off) await api.call(advisorDailyBriefingSet, { body: { enabled: !!opts.on } });
      const state = await api.call(advisorDailyBriefingGet);
      app.out.emit(state, { human: (s) => app.out.line(`Daily briefing: ${s.enabled ? 'on' : 'off'}`) });
    });

  advisor
    .command('briefing')
    .description('The monthly briefing: the AI drafts it, you approve it before it is saved')
    .addOption(new Option('--decision <decision>', 'Decide without being asked (for scripts)').choices(['approve', 'reject']))
    .option('--thread <id>', 'Decide on a draft prepared earlier, without drafting again (needs --decision)')
    .action(async (opts) => {
      if (opts.thread && !opts.decision) throw new UsageError('--thread decides on an earlier draft: pass --decision too.');
      const api = await app.api();
      let thread = opts.thread;
      if (!thread) {
        const spinner = app.prompter.spinner();
        spinner.start('Drafting your briefing');
        let prepared: BriefingPrepared;
        try {
          prepared = await api.call(advisorBriefingPrepare, { body: {}, timeoutMs: 5 * 60_000 });
        } finally {
          spinner.stop();
        }
        if (prepared.error) throw new CliError(`The briefing could not be drafted: ${singleLine(prepared.error)}`);
        // Without a decision, a script gets the draft and its thread to decide
        // on later; a person is shown it and asked.
        if (!opts.decision && (app.out.machine || !app.prompter.interactive)) {
          app.out.emit(prepared, {
            records: (p) => p.briefing.notes,
            human: (p) => {
              briefingView(app, p);
              app.out.note(`Save it with: salli advisor briefing --thread ${p.thread_id} --decision approve`);
            },
          });
          return;
        }
        if (!app.out.machine) briefingView(app, prepared);
        thread = prepared.thread_id;
      }
      const decision =
        opts.decision ??
        (await app.prompter.select({
          message: 'Save this briefing?',
          options: [
            { value: 'approve', label: 'Save it' },
            { value: 'reject', label: 'Discard it' },
          ],
        }));
      const result = await api.call(advisorBriefingResume, { body: { thread_id: thread, decision } });
      if (decision === 'approve' && !result.report.id) {
        throw new CliError(`The briefing was not saved: ${singleLine(result.error || 'unknown reason')}`);
      }
      app.out.done(
        result,
        result.report.id ? `Saved briefing ${str(result.report.id).slice(0, 8)}: see it with salli advisor latest.` : 'Discarded the briefing.',
      );
    });
}

function briefingView(app: App, prepared: BriefingPrepared): void {
  app.out.line(app.out.heading('Monthly briefing'));
  notesView(app, prepared.briefing);
}

export function registerPlanningAhead(program: Command, app: App): void {
  registerFi(program, app);
  registerGoals(program, app);
  registerAdvisor(program, app);
}

