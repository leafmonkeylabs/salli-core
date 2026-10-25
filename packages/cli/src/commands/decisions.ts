/**
 * salli principles list | add | edit | archive | check | figures
 * salli decisions list | show | record | note | reviews | review | export
 *
 * Principles are your own rules of thumb (salli.principle/1): a label and a
 * check over Salli's decision figures, like `emergency_months >= 6`. Salli
 * says which options keep or break them; it never ranks options.
 *
 * The decision journal keeps how you decided (salli.decision/1): the
 * options as Salli ran them, your principles' checks, what you chose and
 * your reasons in your own words. Entries can't be edited or deleted; notes
 * and reviews append. On the review date, Salli compares what you chose
 * projected with what happened. Every figure is the server's; the CLI does
 * no arithmetic on money.
 */
import { type Command } from '@commander-js/extra-typings';
import {
  decisionsExport,
  decisionsExportMarkdown,
  decisionsGet,
  decisionsList,
  decisionsMarkdown,
  decisionsNotesAdd,
  decisionsRecord,
  decisionsReview,
  decisionsReviewsDue,
  principlesArchive,
  principlesCheck,
  principlesCreate,
  principlesFigures,
  principlesList,
  principlesUpdate,
  type Decision,
  type DecisionSummary,
  type DueReview,
  type Principle,
  type PrinciplesCheck,
  type ReviewComparison,
  toJsonText,
  type SalliClient,
  type Scenario,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import type { Output } from '../output/output';
import { plural, singleLine } from '../output/text';
import { displayDate, displayMonth, parseDate } from '../util/dates';
import { textOf, writeOutput } from '../util/files';
import { resolveById } from '../util/resolve';
import { readScenario } from './scenarios';
import { AccountBook, collect, confirmAction } from './shared';

const STATUS: Record<string, string> = { keeps: 'keeps', breaks: 'breaks', unknown: 'can’t tell' };
const DECISION_STATUS: Record<string, string> = {
  awaiting_review: 'awaiting review',
  review_due: 'review due',
  reviewed: 'reviewed',
};
const FIGURE_NAMES: Record<string, string> = {
  cash: 'Cash',
  investments: 'Investments',
  owed: 'Owed',
  net_worth: 'Net worth',
};
const KEY_FIGURES: Array<[string, string]> = [
  ['lowest_cash', 'Lowest cash, next 12 months'],
  ['emergency_months', 'Emergency months at the low'],
  ['net_worth_5y', 'Net worth in 5 years (today’s money)'],
  ['net_worth_10y', 'Net worth in 10 years (today’s money)'],
  ['total_interest', 'Interest on debts'],
  ['debt_free_months', 'Months to debt-free'],
  ['fi_months', 'Months to FI'],
];

async function resolvePrinciple(api: SalliClient, query: string): Promise<Principle> {
  return resolveById((await api.call(principlesList, { query: { include_archived: true } })).principles, query, 'principle');
}

async function resolveDecision(api: SalliClient, query: string): Promise<DecisionSummary> {
  return resolveById((await api.call(decisionsList)).decisions, query, 'decision');
}

function statusStyle(out: Output, status: string): (text: string) => string {
  const c = out.colors;
  if (status === 'breaks') return c.red;
  if (status === 'keeps') return c.green;
  return c.yellow;
}

/** A figure's value as recorded: an amount, months, a rate, a count, or none. */
function figureText(out: Output, value: unknown, currency: string, name: string): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number') return String(value);
  if (name.includes('rate')) return out.percent(value, 2);
  if (name.includes('months')) return out.decimal(value);
  return out.amount(value, currency);
}

// ── Principles ────────────────────────────────────────────────────────────────

export function showCheck(app: App, data: PrinciplesCheck): void {
  const out = app.out;
  if (!data.principles.length) {
    out.note('You have no principles yet. Add one with `salli principles add`.');
    return;
  }
  const columns = [{ label: 'Baseline', results: data.baseline.results }, ...data.options.map((o) => ({ label: o.label, results: o.results }))];
  type Row = { label: string; check: string; statuses: string[] };
  const rows: Row[] = data.principles.map((p, i) => ({
    label: p.label,
    check: p.check,
    statuses: columns.map((c) => c.results[i]?.status ?? 'unknown'),
  }));
  out.line(out.heading('Your principles') + ` ${out.colors.dim(`as of ${displayDate(data.as_of, out.locale)}, in ${data.currency}`)}`);
  out.line();
  out.line(
    out.table(rows, [
      { header: 'PRINCIPLE', get: (r) => singleLine(r.label), shrink: true },
      ...columns.map((c, i) => ({
        header: singleLine(c.label).toUpperCase(),
        get: (r: Row) => STATUS[r.statuses[i] ?? 'unknown'] ?? '',
        style: (t: string, r: Row) => statusStyle(out, r.statuses[i] ?? 'unknown')(t),
      })),
    ]),
  );
  const why: string[] = [];
  columns.forEach((c) => {
    for (const r of c.results) {
      if (r.status !== 'keeps') why.push(`${singleLine(c.label)}, ${singleLine(r.label)}: ${singleLine(r.reason)}`);
    }
  });
  if (why.length) {
    out.line();
    for (const line of why) out.line(`  ${line}`);
  }
  out.note('Salli doesn’t rank options: which principle matters most is yours to weigh.');
}

export function registerPrinciples(program: Command, app: App): void {
  const principles = program
    .command('principles')
    .alias('principle')
    .description('Experimental: Your own rules of thumb, checked against your options (never a ranking)')
    .addHelpText(
      'after',
      `
A principle is a label and a check over Salli's figures (\`salli principles
figures\` lists them, with their units): true or false, written like
  emergency_months >= 6
  max_debt_rate_while_investing <= 0.07
  account_lowest >= 2000            (with --account checking)
  not any_account_below_zero and fi_months_gained >= 0

Examples:
  $ salli principles add "Six months of essentials in cash" --check "emergency_months >= 6"
  $ salli principles add "Checking above 2,000" --check "account_lowest >= 2000" --account checking
  $ salli principles check cash.json instalments.json`,
    );

  principles
    .command('list')
    .alias('ls')
    .description('Your principles in use (--all: archived ones too)')
    .option('--all', 'Include archived principles')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(principlesList, { query: { include_archived: opts.all === true } });
      app.out.emit(data, {
        records: (d) => d.principles,
        human: (d) => {
          if (!d.principles.length) return app.out.note('No principles yet. Add one with `salli principles add`.');
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.principles, [
              { header: 'ID', get: (p) => p.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'PRINCIPLE', get: (p) => singleLine(p.label), shrink: true, style: (t, p) => (p.status === 'archived' ? c.dim(t) : t) },
              { header: 'CHECK', get: (p) => singleLine(p.check), shrink: true },
              { header: 'VERSION', get: (p) => p.version, align: 'right' },
              ...(opts.all ? [{ header: 'STATUS', get: (p: Principle) => p.status }] : []),
            ]),
          );
        },
      });
    });

  principles
    .command('add')
    .argument('<label>', 'What the principle is, in your words')
    .description('Keep a principle (its check is validated first)')
    .requiredOption('--check <expression>', 'True or false over the figures: "emergency_months >= 6"')
    .option('--account <account>', 'The cash account account_lowest reads (code, name or id)')
    .option('--note <text>', 'Why it matters to you')
    .action(async (label, opts) => {
      const api = await app.api();
      const account = opts.account ? (await AccountBook.load(api)).resolve(opts.account).id : undefined;
      const added = await api.call(principlesCreate, {
        body: { label, check: opts.check, ...(account ? { account } : {}), ...(opts.note ? { note: opts.note } : {}) },
      });
      if (app.out.machine) app.out.emit(added, { human: () => undefined });
      else app.out.success(`Kept the principle “${singleLine(added.label)}” ${app.out.errColors.dim(added.id)}`);
    });

  principles
    .command('edit')
    .argument('<principle>', 'Principle id (or its start)')
    .description('Change a principle in use (its version counts up; recorded decisions keep the old one)')
    .option('--label <label>', 'A new label')
    .option('--check <expression>', 'A new check')
    .option('--account <account>', 'A new account for account_lowest')
    .option('--no-account', 'Remove its account')
    .option('--note <text>', 'A new note ("" removes it)')
    .action(async (query, opts) => {
      const api = await app.api();
      const found = await resolvePrinciple(api, query);
      const body: Record<string, string | null> = {};
      if (opts.label !== undefined) body.label = opts.label;
      if (opts.check !== undefined) body.check = opts.check;
      if (typeof opts.account === 'string') body.account = (await AccountBook.load(api)).resolve(opts.account).id;
      else if (opts.account === false) body.account = null;
      if (opts.note !== undefined) body.note = opts.note || null;
      if (!Object.keys(body).length) throw new UsageError('Nothing to change.', 'Pass --label, --check, --account, --no-account or --note.');
      const edited = await api.call(principlesUpdate, { path: { principle_id: found.id }, body });
      app.out.done(edited, `Updated “${singleLine(edited.label)}” (version ${edited.version}).`);
    });

  principles
    .command('archive')
    .argument('<principle>', 'Principle id (or its start)')
    .description('Stop checking against a principle (it is kept, archived)')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const found = await resolvePrinciple(api, query);
      if (!(await confirmAction(app, opts.yes, `Archive “${singleLine(found.label)}”?`))) return;
      const archived = await api.call(principlesArchive, { path: { principle_id: found.id } });
      app.out.done(archived, `Archived “${singleLine(archived.label)}”. It stays in your records.`);
    });

  principles
    .command('check')
    .argument('[files...]', 'Up to five scenario documents ("-" reads one from stdin); none checks your baseline')
    .description('Which principles your baseline and each option keep or break')
    .action(async (files) => {
      if (files.length > 5) throw new UsageError(`Check at most 5 options (got ${files.length}).`);
      const options: Record<string, unknown>[] = [];
      for (const file of files) {
        const doc = await readScenario(app, file);
        if (doc.label === undefined || doc.label === null) doc.label = file === '-' ? 'stdin' : file.replace(/^.*\//, '').replace(/\.[^.]*$/, '');
        options.push(doc);
      }
      const api = await app.api();
      const data = await api.call(principlesCheck, { body: { options: options as unknown as Scenario[] } });
      app.out.emit(data, { records: (d) => d.options, human: (d) => showCheck(app, d) });
    });

  principles
    .command('figures')
    .description('The figures a check may read, with their units')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(principlesFigures);
      app.out.emit(data, {
        records: (d) => d.figures,
        human: (d) => {
          app.out.line(
            app.out.table(d.figures, [
              { header: 'FIGURE', get: (f) => f.name },
              { header: 'UNIT', get: (f) => f.unit, shrink: true },
              { header: 'MONEY', get: (f) => (f.terms === 'real' ? 'today’s' : f.terms === 'nominal' ? 'each day’s own' : '') },
              { header: 'WHAT IT IS', get: (f) => f.description, shrink: true },
            ]),
          );
        },
      });
    });
}

// ── Decisions ─────────────────────────────────────────────────────────────────

function showComparison(out: Output, c: ReviewComparison): void {
  out.line(out.heading(`What ${singleLine(c.option)} projected for ${displayDate(c.at, out.locale)}, and what happened`));
  type Row = { label: string; projected: string; actual: string; difference: string };
  const rows: Row[] = c.figures.map((f) => ({
    label: FIGURE_NAMES[f.figure] ?? f.figure,
    projected: out.amount(f.projected, c.currency),
    actual: out.amount(f.actual, c.currency),
    difference: out.amount(f.difference, c.currency),
  }));
  const s = c.spending;
  if (s.months.length && s.projected && s.actual && s.difference) {
    const first = s.months[0] ?? '';
    const last = s.months.at(-1) ?? '';
    rows.push({
      label: `Spending a month (${displayMonth(first, out.locale)}${first === last ? '' : ` to ${displayMonth(last, out.locale)}`})`,
      projected: out.amount(s.projected, c.currency),
      actual: out.amount(s.actual, c.currency),
      difference: out.amount(s.difference, c.currency),
    });
  }
  out.line(
    out.table(rows, [
      { header: '', get: (r) => r.label, shrink: true },
      { header: 'PROJECTED', get: (r) => r.projected, align: 'right' },
      { header: 'ACTUAL', get: (r) => r.actual, align: 'right' },
      { header: 'DIFFERENCE', get: (r) => r.difference, align: 'right' },
    ]),
  );
  out.note(`In ${c.currency}, each day’s own money. A difference is what happened; why is yours to say.`);
  for (const note of c.notes) out.note(singleLine(note));
}

function showDecision(app: App, d: Decision): void {
  const out = app.out;
  const c = out.colors;
  const e = d.entry;
  out.line(out.heading(singleLine(e.question)));
  out.line(
    out.details([
      ['Chosen', e.chosen],
      ['Recorded', `${displayDate(e.recorded_at.slice(0, 10), out.locale)}, as of ${displayDate(e.as_of, out.locale)}${e.recorded_via.channel === 'mcp' ? ` by ${e.recorded_via.client ?? 'an agent'}, confirmed by you` : ''}`],
      ['Review on', `${displayDate(e.review_on, out.locale)} (${DECISION_STATUS[d.status] ?? d.status})`],
      ['Hash', `${d.hash} ${d.verified ? '(unchanged)' : '(DOES NOT MATCH)'}`, d.verified ? c.dim : c.red],
      ['ID', d.id, c.dim],
    ]),
  );
  out.line();
  out.line(c.bold('Your reasons'));
  for (const line of e.reasons.split('\n')) out.line(`  ${singleLine(line)}`);
  if (e.agent_summary) {
    out.line();
    out.line(c.bold(`The agent’s summary${e.agent_summary.agent ? ` (${singleLine(e.agent_summary.agent)})` : ''}`) + c.dim(' written by the agent, not you'));
    for (const line of e.agent_summary.text.split('\n')) out.line(`  ${singleLine(line)}`);
  }
  type Row = { label: string; baseline: string; values: string[] };
  const rows: Row[] = KEY_FIGURES.map(([name, label]) => ({
    label,
    baseline: figureText(out, e.baseline.figures[name], e.currency, name),
    values: e.options.map((o) => figureText(out, o.figures[name], e.currency, name)),
  }));
  out.line();
  out.line(
    out.table(rows, [
      { header: '', get: (r) => r.label, shrink: true },
      { header: 'BASELINE', get: (r) => r.baseline, align: 'right' },
      ...e.options.map((o, i) => ({
        header: `${singleLine(o.label).toUpperCase()}${o.label === e.chosen ? ' (CHOSEN)' : ''}`,
        get: (r: Row) => r.values[i] ?? '—',
        align: 'right' as const,
      })),
    ]),
  );
  if (e.principles.length) {
    type PRow = { label: string; statuses: string[] };
    const prow: PRow[] = e.principles.map((p, i) => ({
      label: p.label,
      statuses: [e.baseline.principles[i]?.status ?? 'unknown', ...e.options.map((o) => o.principles[i]?.status ?? 'unknown')],
    }));
    out.line();
    out.line(
      out.table(prow, [
        { header: 'PRINCIPLE', get: (r) => singleLine(r.label), shrink: true },
        ...['Baseline', ...e.options.map((o) => o.label)].map((label, i) => ({
          header: singleLine(label).toUpperCase(),
          get: (r: PRow) => STATUS[r.statuses[i] ?? 'unknown'] ?? '',
          style: (t: string, r: PRow) => statusStyle(out, r.statuses[i] ?? 'unknown')(t),
        })),
      ]),
    );
  }
  if (d.notes.length) {
    out.line();
    out.line(c.bold('Notes'));
    for (const n of d.notes) {
      out.line(`  ${displayDate(n.note.at.slice(0, 10), out.locale)}${n.note.author === 'agent' ? ' (agent)' : ''}: ${singleLine(n.note.text)}`);
    }
  }
  for (const r of d.reviews) {
    out.line();
    showComparison(out, r.review.comparison);
    out.line(c.bold('Your reflection'));
    for (const line of r.review.reflection.split('\n')) out.line(`  ${singleLine(line)}`);
  }
  if (e.basis.placeholders.length) out.note(`Placeholders the figures rested on: ${e.basis.placeholders.join(', ')}.`);
}

function showDue(app: App, due: DueReview): void {
  const out = app.out;
  out.line(out.heading(singleLine(due.question)) + ` ${out.colors.dim(`chose ${singleLine(due.chosen)}; review due ${displayDate(due.review_on, out.locale)}`)}`);
  out.line(`  Your reasons then: ${singleLine(due.reasons)}`);
  out.line();
  showComparison(out, due.comparison);
}

export function registerDecisions(program: Command, app: App): void {
  const decisions = program
    .command('decisions')
    .alias('decision')
    .description('Experimental: Your decision journal: what you chose and why, and how it turned out')
    .addHelpText(
      'after',
      `
An entry records the options as Salli ran them, your principles' checks,
what you chose and your reasons in your own words. It can't be edited or
deleted: add notes, and review it from its review date on.

Examples:
  $ salli whatif --buy 2400 --label "Pay cash" --save cash.json
  $ salli decisions record --question "Laptop: cash or wait?" --option cash.json --option wait.json \\
      --chosen "Pay cash" --reasons "The old one is dying." --review-on 2027-04-11
  $ salli decisions reviews
  $ salli decisions export --format markdown -o journal.md`,
    );

  decisions
    .command('list')
    .alias('ls')
    .description('Your decisions, newest first')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(decisionsList);
      app.out.emit(data, {
        records: (d) => d.decisions,
        human: (d) => {
          if (!d.decisions.length) return app.out.note('No decisions recorded yet. See `salli decisions record --help`.');
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.decisions, [
              { header: 'ID', get: (x) => x.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'RECORDED', get: (x) => displayDate(x.recorded_at.slice(0, 10), app.out.locale) },
              { header: 'QUESTION', get: (x) => singleLine(x.question), shrink: true },
              { header: 'CHOSEN', get: (x) => singleLine(x.chosen), shrink: true },
              { header: 'REVIEW', get: (x) => displayDate(x.review_on, app.out.locale) },
              { header: 'STATUS', get: (x) => DECISION_STATUS[x.status] ?? x.status, style: (t, x) => (x.status === 'review_due' ? c.yellow(t) : t) },
            ]),
          );
        },
      });
    });

  decisions
    .command('show')
    .argument('<decision>', 'Decision id (or its start)')
    .description('One decision as recorded, with its notes and reviews')
    .action(async (query) => {
      const api = await app.api();
      const found = await resolveDecision(api, query);
      const decision = await api.call(decisionsGet, { path: { decision_id: found.id } });
      app.out.emit(decision, { records: (d) => d.entry.options, human: (d) => showDecision(app, d) });
    });

  decisions
    .command('record')
    .description('Record a decision you made: Salli runs each option and keeps it, with your reasons')
    .requiredOption('--question <text>', 'What you were deciding')
    .requiredOption('--option <file>', 'A scenario you weighed, with its label (repeatable, 1 to 5)', collect)
    .requiredOption('--chosen <label>', 'The label of the option you chose')
    .requiredOption('--reasons <text>', 'Your reasons, in your own words')
    .requiredOption('--review-on <date>', 'When to look back (from the end of this month)')
    .option('--agent-summary <text>', 'Your agent’s summary, recorded as the agent’s')
    .option('--agent <name>', 'The agent that wrote the summary')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (opts) => {
      const files = opts.option ?? [];
      if (files.length > 5) throw new UsageError(`A decision records at most 5 options (got ${files.length}).`);
      const options: Record<string, unknown>[] = [];
      for (const file of files) {
        const doc = await readScenario(app, file);
        if (doc.label === undefined || doc.label === null) doc.label = file === '-' ? 'stdin' : file.replace(/^.*\//, '').replace(/\.[^.]*$/, '');
        options.push(doc);
      }
      const reviewOn = parseDate(opts.reviewOn, app.runtime.now(), '--review-on');
      const ok = await confirmAction(
        app,
        opts.yes,
        `Record “${singleLine(opts.question)}”, chose “${singleLine(opts.chosen)}”? Entries can't be edited or deleted afterwards`,
      );
      if (!ok) return;
      const api = await app.api();
      const recorded = await api.call(decisionsRecord, {
        body: {
          question: opts.question,
          options: options as unknown as Scenario[],
          chosen: opts.chosen,
          reasons: opts.reasons,
          review_on: reviewOn,
          ...(opts.agentSummary ? { agent_summary: opts.agentSummary } : {}),
          ...(opts.agent ? { agent: opts.agent } : {}),
        },
      });
      if (app.out.machine) app.out.emit(recorded, { human: () => undefined });
      else {
        app.out.success(`Recorded “${singleLine(recorded.entry.question)}” ${app.out.errColors.dim(recorded.id)}`);
        app.out.note(`Salli will remind you to review it on ${displayDate(recorded.entry.review_on, app.out.locale)}. Hash ${recorded.hash}.`);
      }
    });

  decisions
    .command('note')
    .argument('<decision>', 'Decision id (or its start)')
    .argument('<text>', 'The note')
    .description('Add a note to a decision (the entry itself never changes)')
    .action(async (query, text) => {
      const api = await app.api();
      const found = await resolveDecision(api, query);
      const note = await api.call(decisionsNotesAdd, { path: { decision_id: found.id }, body: { text } });
      app.out.done(note, `Noted on “${singleLine(found.question)}”.`);
    });

  decisions
    .command('reviews')
    .description('Decisions due for review, each with what was projected and what happened')
    .action(async () => {
      const api = await app.api();
      const data = await api.call(decisionsReviewsDue);
      app.out.emit(data, {
        records: (d) => d.reviews,
        human: (d) => {
          if (!d.reviews.length) return app.out.note('No decisions are due for review.');
          d.reviews.forEach((due, i) => {
            if (i) app.out.line();
            showDue(app, due);
          });
          app.out.note(`${plural(d.reviews.length, 'decision')} to look back on: \`salli decisions review <id>\` adds your reflection.`);
        },
      });
    });

  decisions
    .command('review')
    .argument('<decision>', 'Decision id (or its start)')
    .description('Review a decision from its review date: Salli’s comparison, and your reflection')
    .option('--reflection <text>', 'What you make of how it turned out, in your words')
    .option('--as-of <date>', 'The day the review is as of (default today)')
    .action(async (query, opts) => {
      const api = await app.api();
      const found = await resolveDecision(api, query);
      let reflection = opts.reflection;
      if (reflection === undefined) {
        if (!app.prompter.interactive) throw new UsageError('A review needs your reflection.', 'Pass --reflection "…".');
        const due = (await api.call(decisionsReviewsDue)).reviews.find((r) => r.id === found.id);
        if (due && !app.out.machine) {
          showDue(app, due);
          app.out.line();
        }
        reflection = await app.prompter.text({
          message: 'What do you make of how it turned out?',
          validate: (v) => (v.trim() ? undefined : 'Write a few words, in your own terms.'),
        });
      }
      const asOf = opts.asOf ? parseDate(opts.asOf, app.runtime.now(), '--as-of') : undefined;
      const reviewed = await api.call(decisionsReview, {
        path: { decision_id: found.id },
        body: { reflection, ...(asOf ? { as_of: asOf } : {}) },
      });
      app.out.emit(reviewed, {
        human: (r) => {
          showComparison(app.out, r.review.comparison);
          app.out.success(`Reviewed “${singleLine(found.question)}”. The entry itself is unchanged.`);
        },
      });
    });

  decisions
    .command('export')
    .argument('[decision]', 'One decision (id or its start); default: the whole journal')
    .description('The journal as Markdown to read, or JSON with every document and hash')
    .option('--format <format>', 'markdown or json', 'markdown')
    .option('-o, --out <file>', 'Write it to this file (default: stdout)')
    .action(async (query, opts) => {
      if (opts.format !== 'markdown' && opts.format !== 'json') throw new UsageError(`--format is markdown or json (got "${opts.format}").`);
      const api = await app.api();
      const id = query ? (await resolveDecision(api, query)).id : undefined;
      let text: string;
      if (opts.format === 'markdown') {
        text = textOf(
          id
            ? await api.call(decisionsMarkdown, { path: { decision_id: id }, parseAs: 'text' })
            : await api.call(decisionsExportMarkdown, { parseAs: 'text' }),
        );
      } else {
        const data = id ? await api.call(decisionsGet, { path: { decision_id: id } }) : await api.call(decisionsExport);
        text = `${toJsonText(data)}\n`;
      }
      await writeOutput(app, text, opts.out, { format: opts.format }, `your decision journal as ${opts.format === 'json' ? 'JSON' : 'Markdown'}`, { private: true });
    });
}
