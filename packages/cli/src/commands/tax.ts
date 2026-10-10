/**
 * salli tax …: your tax, computed by Salli's engine from the rule set you
 * activated (docs/taxrules.md), each line explained, and returns prepared
 * from the forms in your rules for you to review. Salli knows no country's
 * tax law: without active rules there is nothing to compute, and every
 * command says how to add some (`salli tax rules`).
 *
 * The CLI never computes a figure: every amount shown is the server's, as the
 * decimal string it sent.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  taxCompute,
  taxCurrentYear,
  taxExplain,
  taxLatest,
  taxReturnsGet,
  taxReturnsPrepare,
  taxReturnsResume,
  type SalliClient,
  type TaxComputation,
  type TaxLineExplanation,
  type TaxReturnDraft,
  type TaxReturnResumed,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, NotFoundError, UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, displayRange } from '../util/dates';
import { collect } from './shared';
import { answersArg, registerTaxRules } from './taxrules';

/** A field from the server, as one line of safe text. */
const str = (v: string | null | undefined): string => (v ? singleLine(v) : '');

/** Which rules: --country, --region and --year, as query parameters. */
function where(opts: { country?: string; region?: string; year?: string }): Record<string, string> {
  return {
    ...(opts.country ? { country: opts.country } : {}),
    ...(opts.region ? { region: opts.region } : {}),
    ...(opts.year ? { year: opts.year } : {}),
  };
}

function place(t: { country: string; region?: string | null; year: string }): string {
  return `${t.country}${t.region ? ` ${singleLine(t.region)}` : ''} ${singleLine(t.year)}`;
}

// ── showing a computation ────────────────────────────────────────────────────

function renderLines(app: App, lines: TaxComputation['lines'], cur: string): void {
  const out = app.out;
  const c = out.colors;
  out.line(
    out.table(lines, [
      { header: 'LINE', get: (l) => l.label + (l.refundable === true ? ' (refundable)' : ''), shrink: true },
      { header: 'KEY', get: (l) => l.key, style: (s) => c.dim(s) },
      { header: `AMOUNT (${cur})`, get: (l) => out.amount(l.amount, cur), align: 'right', style: (s, l) => out.signed(s, l.amount) },
      { header: 'FROM', get: (l) => l.expr, shrink: true, style: (s) => c.dim(s) },
    ]),
  );
}

function renderOwed(app: App, t: { net: string; tax_payable: string; refund_due: string; currency: string }): void {
  const out = app.out;
  const m = (amount: string): string => out.money(amount, t.currency);
  out.line(
    out.details([
      ['Net', m(t.net)],
      ['Payable', m(t.tax_payable), out.colors.bold],
      ['Refund', m(t.refund_due), out.colors.green],
    ]),
  );
}

export function taxView(app: App, t: TaxComputation): void {
  const out = app.out;
  const c = out.colors;
  const cur = t.currency;
  const when = t.created_at ? ` · computed ${displayDate(t.created_at, out.locale)}` : '';
  out.line(
    `${out.heading(`Tax ${place(t)}`)} ` +
      c.dim(`${displayRange(t.period_start, t.period_end, out.locale)} · ${cur}${when} · not tax advice`),
  );
  out.line(c.dim(`Computed from your rules, version ${t.version} (${t.content_hash.slice(0, 12)}).`));
  out.line();
  if (t.roles.length) {
    out.line(
      out.table(t.roles, [
        { header: 'FROM YOUR LEDGER', get: (r) => r.label, shrink: true },
        { header: 'ROLE', get: (r) => r.key, style: (s) => c.dim(s) },
        { header: `TOTAL (${cur})`, get: (r) => out.amount(r.total, cur), align: 'right' },
        { header: 'POSTINGS', get: (r) => r.postings, align: 'right' },
      ]),
    );
    out.line();
  }
  renderLines(app, t.lines, cur);
  out.line();
  renderOwed(app, t);
  for (const warning of t.warnings) out.warn(singleLine(warning));
  out.note(singleLine(t.provenance));
}

function explanationView(app: App, e: TaxLineExplanation): void {
  const out = app.out;
  const c = out.colors;
  const cur = e.currency;
  const line = e.line;
  out.line(`${out.heading(`${singleLine(line.label)} (${line.key})`)} ${c.dim(`${place(e)} · rules v${e.version}`)}`);
  out.line(
    out.details([
      ['Amount', out.money(line.amount, cur), c.bold],
      ['From', singleLine(line.expr)],
      line.block !== null && line.block !== undefined && ['Block', `${line.block} (${singleLine(line.path)})`],
      line.source && ['Source', `${singleLine(line.source.title)} ${c.dim(singleLine(line.source.url))}`],
      line.refundable !== null && line.refundable !== undefined && ['Refundable', line.refundable ? 'yes' : 'no'],
    ]),
  );
  if (e.inputs.length) {
    out.line();
    out.line(
      out.table(e.inputs, [
        { header: 'FROM YOUR LEDGER', get: (r) => r.label, shrink: true },
        { header: 'ROLE', get: (r) => r.key, style: (s) => c.dim(s) },
        { header: `TOTAL (${cur})`, get: (r) => out.amount(r.total, cur), align: 'right' },
      ]),
    );
  }
  if (e.answers.length) {
    out.line();
    out.line(
      out.table(e.answers, [
        { header: 'YOUR ANSWER TO', get: (a) => a.label, shrink: true },
        { header: 'ANSWER', get: (a) => `${String(a.value)}${a.default ? ' (default)' : ''}` },
      ]),
    );
  }
  if (e.lines.length) {
    out.line();
    out.line(
      out.table(e.lines, [
        { header: 'USES LINE', get: (l) => l.label, shrink: true },
        { header: 'KEY', get: (l) => l.key, style: (s) => c.dim(s) },
        { header: `AMOUNT (${cur})`, get: (l) => out.amount(l.amount, cur), align: 'right' },
      ]),
    );
  }
  for (const table of e.tables) {
    out.line();
    out.line(`${out.heading(`Band table ${table.key}`)}${table.source ? ` ${c.dim(singleLine(table.source.title))}` : ''}`);
    out.line(
      out.table(table.bands, [
        { header: `UP TO (${cur})`, get: (b) => (b.upto === null || b.upto === undefined ? 'the rest' : out.amount(b.upto, cur)), align: 'right' },
        { header: 'RATE', get: (b) => b.rate, align: 'right' },
      ]),
    );
  }
  if (e.used_by.length) out.note(`Used by: ${e.used_by.map(singleLine).join(', ')}.`);
  out.note(singleLine(e.provenance));
}

// ── returns ──────────────────────────────────────────────────────────────────

function fieldValue(value: string | boolean): string {
  return typeof value === 'boolean' ? (value ? 'yes' : 'no') : value;
}

function renderDraft(app: App, d: TaxReturnDraft, title: string): void {
  const out = app.out;
  const c = out.colors;
  out.line(`${out.heading(`${title}: ${place(d)}`)} ${c.dim(`rules v${d.version} · ${d.currency} · not tax advice`)}`);
  for (const form of d.forms) {
    out.line();
    out.line(out.heading(singleLine(form.label)));
    out.line(
      out.table(form.fields, [
        { header: 'FIELD', get: (f) => f.id, style: (s) => c.dim(s) },
        { header: 'LABEL', get: (f) => f.label, shrink: true },
        { header: 'VALUE', get: (f) => fieldValue(f.value), align: 'right' },
      ]),
    );
    if (form.instructions) out.line(singleLine(form.instructions));
    if (form.url) out.line(c.dim(singleLine(form.url)));
  }
  out.line();
  renderOwed(app, d);
  for (const warning of d.warnings) out.warn(singleLine(warning));
  out.note(singleLine(d.note));
}

type Decision = 'approve' | 'edit' | 'reject';

async function decide(app: App, opts: { approve?: boolean; edit?: boolean; reject?: boolean }): Promise<Decision> {
  const given = (['approve', 'edit', 'reject'] as const).filter((d) => opts[d]);
  if (given.length > 1) throw new UsageError('Choose one of --approve, --edit and --reject.');
  if (given[0]) return given[0];
  if (!app.prompter.interactive || app.out.machine) {
    throw new UsageError('Say what to do with the draft: --approve, --edit (with --answer) or --reject.');
  }
  return app.prompter.select<Decision>({
    message: 'This return:',
    options: [
      { value: 'approve', label: 'Approve it', hint: 'the worksheet, ready to file yourself' },
      { value: 'edit', label: 'Edit', hint: 'compute again: new answers, or after fixing your ledger' },
      { value: 'reject', label: 'Reject it' },
    ],
  });
}

async function editAnswers(app: App, given: Record<string, string | boolean>): Promise<Record<string, string | boolean>> {
  if (Object.keys(given).length || !app.prompter.interactive || app.out.machine) return given;
  const text = await app.prompter.text({
    message: 'Answers to change (key=value, comma-separated), or nothing to compute again from your ledger',
    placeholder: 'filing_status=joint',
  });
  return answersArg(
    text
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

async function review(
  app: App,
  api: SalliClient,
  thread: string,
  opts: { approve?: boolean; edit?: boolean; reject?: boolean; answer?: string[] },
): Promise<void> {
  const pending = await api.call(taxReturnsGet, { path: { thread_id: thread } });
  if (!pending.waiting || !pending.draft) {
    throw new NotFoundError(`No return of yours is waiting for review on thread ${singleLine(thread)}.`, 'Prepare one with `salli tax return prepare`.');
  }
  if (!app.out.machine) renderDraft(app, pending.draft, 'Draft return');
  let answers = answersArg(opts.answer ?? []);
  for (;;) {
    const decision = await decide(app, opts);
    if (decision === 'edit') answers = await editAnswers(app, answers);
    const resumed: TaxReturnResumed = await api.call(taxReturnsResume, {
      body: { thread_id: thread, decision, answers: decision === 'edit' ? answers : {} },
    });
    if (resumed.draft) {
      // Edited: computed again, and waiting for review again.
      if (app.out.machine || !app.prompter.interactive || opts.edit) {
        app.out.emit(resumed, { human: (r) => r.draft && renderDraft(app, r.draft, 'New draft return') });
        if (!app.out.machine) app.out.note(`Review it: \`salli tax return review ${singleLine(thread)}\`.`);
        return;
      }
      app.out.line();
      renderDraft(app, resumed.draft, 'New draft return');
      answers = {};
      continue;
    }
    if (resumed.worksheet) {
      app.out.emit(resumed, {
        human: (r) => {
          if (!r.worksheet) return;
          app.out.line();
          renderDraft(app, r.worksheet, 'Ready to file');
          app.out.success('Approved. File it with your tax authority, as each form says; Salli files nothing.');
        },
      });
      return;
    }
    if (decision === 'reject') {
      app.out.done({ ...resumed }, 'Rejected: nothing was approved.');
      return;
    }
    throw new CliError(str(resumed.error) || 'The return could not be resumed.', { kind: 'return' });
  }
}

// ── the commands ─────────────────────────────────────────────────────────────

export function registerTax(program: Command, app: App): void {
  const tax = program
    .command('tax')
    .description('Your tax, from the tax rules you (or your agent) wrote and you activated')
    .addHelpText(
      'after',
      `
Salli knows no country's tax law. It computes your tax only from your own active
rules: add them with \`salli tax rules create|import\`, or ask your AI agent (its
research_tax_rules prompt drafts them), then review and activate them yourself.

Examples:
  $ salli tax year
  $ salli tax compute --answer filing_status=single
  $ salli tax explain income_tax
  $ salli tax return prepare
  $ salli tax return review <thread>`,
    );

  tax
    .command('year')
    .description('The tax year you are in today: the year of your active rules that covers it')
    .option('--country <code>', 'The country of the rules (default: your tax residency)')
    .option('--region <name>', 'The region, for rules set per region')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(taxCurrentYear, { query: where(opts) });
      app.out.emit(data, {
        human: (d) => {
          const out = app.out;
          if (!d.country) {
            out.warn('Salli does not know where you are taxed.');
            out.note('Set it with `salli profile set --tax-residency <country>`, or name one with --country.');
            return;
          }
          const from = d.country_source === 'tax_residency' ? 'your tax residency' : 'as given';
          out.line(
            out.details([
              ['Country', `${d.country} (${from})`],
              [
                'Tax year',
                d.year
                  ? `${singleLine(d.year)}${d.region ? ` ${singleLine(d.region)}` : ''} (${displayRange(d.start, d.end, out.locale)}), your rules v${d.version}`
                  : 'none: no active rules of yours cover today',
              ],
              ['Computes', d.latest_year ? `${singleLine(d.latest_year)} when no year is named` : 'nothing yet'],
            ]),
          );
          if (!d.latest_year) out.note('Add your rules with `salli tax rules create <file>` (or ask your agent), then activate them.');
        },
      });
    });

  tax
    .command('compute')
    .description('Compute your tax with your active rules, from your ledger, and store it')
    .option('--year <year>', 'The tax year, as your rules name it (default: your current tax year)')
    .option('--country <code>', 'The country of the rules to use (default: your tax residency)')
    .option('--region <name>', 'The region, for rules set per region')
    .option('--answer <key=value>', 'Answer one of your rules’ questions (repeatable)', collect)
    .action(async (opts) => {
      const answers = answersArg(opts.answer ?? []);
      const api = await app.api();
      const t = await api.call(taxCompute, { query: where(opts), body: { answers } });
      app.out.emit(t, { records: (d) => d.lines, human: (d) => taxView(app, d) });
    });

  tax
    .command('latest')
    .description('The last computation stored for a year')
    .option('--year <year>', 'The tax year, as your rules name it (default: your current tax year)')
    .option('--country <code>', 'The country of the rules to use (default: your tax residency)')
    .option('--region <name>', 'The region, for rules set per region')
    .action(async (opts) => {
      const api = await app.api();
      const data = await api.call(taxLatest, { query: where(opts) });
      if (!data.result && !app.out.machine) {
        throw new CliError('No stored computation for that year.', { exitCode: 4, kind: 'not-found', hint: 'Run `salli tax compute`.' });
      }
      app.out.emit(data, { human: (d) => d.result && taxView(app, d.result) });
    });

  tax
    .command('explain')
    .argument('<line>', 'A line’s key, as `salli tax compute` lists it')
    .description('Where one line of your tax came from: what it used, and its source')
    .option('--year <year>', 'The tax year, as your rules name it (default: your current tax year)')
    .option('--country <code>', 'The country of the rules to use (default: your tax residency)')
    .option('--region <name>', 'The region, for rules set per region')
    .option('--answer <key=value>', 'Answer one of your rules’ questions (repeatable)', collect)
    .action(async (line, opts) => {
      const answers = answersArg(opts.answer ?? []);
      const api = await app.api();
      const e = await api.call(taxExplain, { query: where(opts), body: { line_key: line, answers } });
      app.out.emit(e, { human: (d) => explanationView(app, d) });
    });

  const ret = tax.command('return').description('Prepare a return from the forms in your rules, and review it');

  ret
    .command('prepare')
    .description('Compute your tax and fill in your rules’ return forms, for you to review')
    .option('--year <year>', 'The tax year, as your rules name it (default: your current tax year)')
    .option('--country <code>', 'The country of the rules to use (default: your tax residency)')
    .option('--region <name>', 'The region, for rules set per region')
    .option('--answer <key=value>', 'Answer one of your rules’ questions (repeatable)', collect)
    .option('--thread <id>', 'Name the review thread (default: a new one)')
    .action(async (opts) => {
      const answers = answersArg(opts.answer ?? []);
      const api = await app.api();
      const prepared = await api.call(taxReturnsPrepare, {
        body: {
          answers,
          ...(opts.year ? { year: opts.year } : {}),
          ...(opts.country ? { country: opts.country } : {}),
          ...(opts.region ? { region: opts.region } : {}),
          ...(opts.thread ? { thread_id: opts.thread } : {}),
        },
      });
      if (prepared.error && !app.out.machine) {
        throw new CliError(singleLine(prepared.error), { kind: 'return' });
      }
      app.out.emit(prepared, {
        human: (p) => {
          if (!p.draft) return;
          renderDraft(app, p.draft, 'Draft return');
          app.out.note(`Review it: \`salli tax return review ${singleLine(p.thread_id)}\`.`);
        },
      });
    });

  ret
    .command('review')
    .argument('<thread>', 'The thread `salli tax return prepare` named')
    .description('Show a prepared return, then approve, edit (compute again) or reject it')
    .addOption(new Option('--approve', 'Approve it: the worksheet, ready to file').conflicts(['edit', 'reject']))
    .addOption(new Option('--edit', 'Compute it again (with --answer, or after fixing your ledger)').conflicts(['reject']))
    .addOption(new Option('--reject', 'Reject it'))
    .option('--answer <key=value>', 'With --edit: an answer to change (repeatable)', collect)
    .action(async (thread, opts) => {
      const api = await app.api();
      await review(app, api, thread, opts);
    });

  registerTaxRules(tax, app);
}
