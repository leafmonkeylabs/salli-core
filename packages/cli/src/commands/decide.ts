/**
 * salli decide <template> | salli decide --list
 *
 * A common decision (afford it, debt or invest, a windfall, a big change,
 * borrowing, an emergency fund) as a few questions: `salli decide` asks
 * them, Salli builds the options from your answers and runs every one on
 * your baseline (POST /v1/decisions/start), and you see the comparison and
 * your principles' checks. Then, if you want, it records what you chose
 * and why, asking first: an entry can't be edited or deleted.
 *
 * For scripts: --answers <file.json> and --set id=value answer without
 * asking, and --record with --chosen, --reasons, --review-on and --yes
 * records. The server checks every answer and computes every figure; the
 * CLI only reads what you type into the API's formats.
 */
import { readFile } from 'node:fs/promises';
import type { Command } from '@commander-js/extra-typings';
import {
  debtsList,
  decisionsRecord,
  decisionsStart,
  decisionsTemplatesGet,
  decisionsTemplatesList,
  type DecisionStart,
  type DecisionTemplate,
  type PrinciplesCheck,
  type SalliClient,
  type Scenario,
  type TemplateQuestion,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { plural, singleLine } from '../output/text';
import { displayDate, displayMonth, parseDate } from '../util/dates';
import { parseWholeNumber } from '../util/numbers';
import { resolveById } from '../util/resolve';
import { showCheck } from './decisions';
import { showComparison } from './scenarios';
import { AccountBook, amountArg, collect, confirmAction, rateArg } from './shared';

type Answers = Record<string, unknown>;
interface Debt {
  id: string;
  name: string;
}

/** What the person's own debts and accounts are called, to name and find them. */
class Names {
  private constructor(
    readonly debts: Debt[],
    readonly book: AccountBook,
  ) {}

  static async load(api: SalliClient, template: DecisionTemplate): Promise<Names> {
    const types = new Set(template.questions.map((q) => q.type));
    const debts = types.has('debt') || types.has('splits') ? (await api.call(debtsList, { query: { active_only: true } })).debts : [];
    const book = types.has('account') ? await AccountBook.load(api) : new AccountBook([]);
    return new Names(
      debts.map((d) => ({ id: d.id, name: d.name })),
      book,
    );
  }

  debt(query: string): string {
    const lower = query.trim().toLowerCase();
    return (this.debts.find((d) => d.name.toLowerCase() === lower) ?? resolveById(this.debts, query.trim(), 'debt')).id;
  }

  account(query: string): string {
    return this.book.resolve(query).id;
  }
}

// ── Reading answers ───────────────────────────────────────────────────────────

/** One answer typed as text, in the form the API takes; a usage error otherwise. */
function fromText(app: App, q: TemplateQuestion, text: string, names: Names): unknown {
  const flag = `--set ${q.id}`;
  const value = text.trim();
  switch (q.type) {
    case 'amount':
    case 'signed_amount':
      return amountArg(value, flag);
    case 'number':
      return amountArg(value, flag);
    case 'rate':
      return rateArg(value, flag);
    case 'months':
    case 'years': {
      const n = parseWholeNumber(value);
      if (n === undefined) throw new UsageError(`${flag} is a whole number (got "${text}").`);
      return n;
    }
    case 'date':
      return parseDate(value, app.runtime.now(), flag);
    case 'choice': {
      const found = q.choices.find((c) => c.value === value || c.label.toLowerCase() === value.toLowerCase());
      if (!found) throw new UsageError(`${flag} is one of: ${q.choices.map((c) => c.value).join(', ')} (got "${text}").`);
      return found.value;
    }
    case 'debt':
      return names.debt(value);
    case 'account':
      return names.account(value);
    case 'text':
      return value;
    case 'amounts':
      return value
        .split(',')
        .map((v) => v.trim())
        .filter(Boolean)
        .map((v) => amountArg(v, flag));
    case 'loans':
    case 'splits':
      throw new UsageError(`${q.id} is a list: give it in --answers <file.json>, or answer it when asked.`);
  }
}

/** `id=value` pairs, read by each question's type. */
function setAnswers(app: App, template: DecisionTemplate, pairs: string[], names: Names): Answers {
  const out: Answers = {};
  for (const pair of pairs) {
    const at = pair.indexOf('=');
    if (at <= 0) throw new UsageError(`--set takes ID=VALUE, like --set price=2400 (got "${pair}").`);
    const id = pair.slice(0, at).trim();
    const q = template.questions.find((x) => x.id === id);
    if (!q) throw new UsageError(`${template.id} has no question "${id}".`, `Its questions: ${template.questions.map((x) => x.id).join(', ')}.`);
    out[id] = fromText(app, q, pair.slice(at + 1), names);
  }
  return out;
}

async function readAnswers(path: string): Promise<Answers> {
  let doc: unknown;
  try {
    doc = JSON.parse(await readFile(path, 'utf8'));
  } catch {
    throw new UsageError(`${path} is not a JSON file of answers.`, 'Answers are an object by question id: see `salli decide <template> --questions`.');
  }
  if (typeof doc !== 'object' || doc === null || Array.isArray(doc)) throw new UsageError(`${path} is not an object of answers by question id.`);
  return doc as Answers;
}

/** Whether a question is asked, given the answers so far (or, unanswered, their defaults). */
function applies(q: TemplateQuestion, answers: Answers, template: DecisionTemplate): boolean {
  if (!q.when) return true;
  const value = answers[q.when.question] ?? template.questions.find((x) => x.id === q.when?.question)?.default?.value;
  if (value === undefined || value === null) return false;
  return q.when.equals === null || value === q.when.equals;
}

/** The ids a question takes, as the answers' schema lists them (your own debts or cash accounts). */
function allowed(template: DecisionTemplate, id: string): string[] | undefined {
  const properties = template.answers_schema.properties as Record<string, { enum?: string[] }> | undefined;
  return properties?.[id]?.enum;
}

// ── Asking ────────────────────────────────────────────────────────────────────

function shown(q: TemplateQuestion): string {
  const value = q.default?.value;
  return value === undefined ? '' : String(value);
}

async function askText(app: App, q: TemplateQuestion, names: Names, initial: string, optional: boolean): Promise<unknown> {
  for (;;) {
    const text = await app.prompter.text({
      message: q.prompt,
      placeholder: optional ? 'leave it empty to skip' : q.help,
      initialValue: initial,
      validate: (v) => (v.trim() || optional || initial ? undefined : 'This one needs an answer.'),
    });
    if (!text.trim()) return initial ? fromText(app, q, initial, names) : undefined;
    try {
      return fromText(app, q, text, names);
    } catch (error) {
      if (!(error instanceof UsageError)) throw error;
      app.out.warn(error.message.replace(`--set ${q.id} `, `${q.id} `));
    }
  }
}

async function askLoans(app: App, q: TemplateQuestion): Promise<unknown[]> {
  const loans: unknown[] = [];
  const most = q.max_items ?? 4;
  while (loans.length < most) {
    app.out.note(`Loan ${loans.length + 1}:`);
    const rate = await app.prompter.text({ message: 'Its yearly rate (6.9% or 0.069)?', validate: (v) => (v.trim() ? undefined : 'A rate, like 6.9%.') });
    const term = await app.prompter.text({ message: 'Over how many months?', validate: (v) => (parseWholeNumber(v.trim()) ? undefined : 'A whole number of months.') });
    const label = await app.prompter.text({ message: 'What to call it (optional)?', placeholder: 'leave it empty for “rate over months”' });
    loans.push({ annual_rate: rateArg(rate, 'rate'), term_months: parseWholeNumber(term.trim()), ...(label.trim() ? { label: label.trim() } : {}) });
    if (loans.length >= most || !(await app.prompter.confirm({ message: 'Compare another loan?', initialValue: false }))) break;
  }
  return loans;
}

async function askSplits(app: App, q: TemplateQuestion, names: Names): Promise<unknown[]> {
  const splits: unknown[] = [];
  const least = q.min_items ?? 2;
  const most = q.max_items ?? 5;
  while (splits.length < most) {
    app.out.note(`Way ${splits.length + 1} of sharing it out (what you don't put to work stays in cash):`);
    const label = await app.prompter.text({ message: 'What to call it?', validate: (v) => (v.trim() ? undefined : 'A few words, like “Car first”.') });
    const debts: { debt: string; amount: string }[] = [];
    for (const debt of names.debts) {
      const amount = await app.prompter.text({ message: `How much onto ${debt.name}?`, placeholder: 'leave it empty for none' });
      if (amount.trim()) debts.push({ debt: debt.id, amount: amountArg(amount, 'amount') });
    }
    const invest = await app.prompter.text({ message: 'How much invested?', placeholder: 'leave it empty for none' });
    splits.push({ label: label.trim(), debts, ...(invest.trim() ? { invest: amountArg(invest, 'invest') } : {}) });
    if (splits.length < least) continue;
    if (splits.length >= most || !(await app.prompter.confirm({ message: 'Another way of sharing it out?', initialValue: false }))) break;
  }
  return splits;
}

async function ask(app: App, template: DecisionTemplate, given: Answers, names: Names): Promise<Answers> {
  const answers: Answers = { ...given };
  app.out.line(app.out.heading(template.title) + ` ${app.out.colors.dim(template.summary)}`);
  for (const q of template.questions) {
    if (q.id in answers || !applies(q, answers, template)) continue;
    const optional = !q.required || q.default !== null;
    if (q.help && q.type !== 'loans' && q.type !== 'splits') app.out.note(q.help + (q.default ? ` (Default: ${q.default.note}.)` : ''));
    let value: unknown;
    if (q.type === 'choice') {
      value = await app.prompter.select({
        message: q.prompt,
        options: q.choices.map((c) => ({ value: c.value, label: c.label })),
        ...(q.default ? { initialValue: String(q.default.value) } : {}),
      });
    } else if (q.type === 'debt' && names.debts.length) {
      value = await app.prompter.select({
        message: q.prompt,
        options: names.debts.map((d) => ({ value: d.id, label: d.name })),
        ...(q.default ? { initialValue: String(q.default.value) } : {}),
      });
    } else if (q.type === 'account') {
      const ids = allowed(template, q.id) ?? [];
      const cash = names.book.accounts.filter((a) => ids.includes(a.id));
      value = await app.prompter.select<string | undefined>({
        message: q.prompt,
        options: [{ value: undefined, label: 'My cash as a whole' }, ...cash.map((a) => ({ value: a.id, label: singleLine(a.name) }))],
        initialValue: undefined,
      });
    } else if (q.type === 'loans') {
      app.out.note(q.help);
      value = await askLoans(app, q);
    } else if (q.type === 'splits') {
      app.out.note(q.help);
      value = await askSplits(app, q, names);
    } else {
      value = await askText(app, q, names, shown(q), optional);
    }
    if (value !== undefined) answers[q.id] = value;
  }
  return answers;
}

// ── Showing ───────────────────────────────────────────────────────────────────

function showStart(app: App, data: DecisionStart): void {
  const out = app.out;
  out.line(out.heading(singleLine(data.question)) + ` ${out.colors.dim(`${data.template.title}, as of ${displayDate(data.as_of, out.locale)}, in ${data.currency}`)}`);
  out.line();
  out.line(
    out.table(data.options, [
      { header: 'OPTION', get: (o) => singleLine(o.label) },
      { header: 'WHAT IT IS', get: (o) => singleLine(o.describes), shrink: true },
    ]),
  );
  const defaulted = data.answers.filter((a) => a.source !== 'given');
  if (defaulted.length) {
    out.note(`Not answered, so: ${defaulted.map((a) => `${a.id} ${typeof a.value === 'object' ? JSON.stringify(a.value) : String(a.value)} (${a.note ?? a.source})`).join('; ')}.`);
  }
  out.line();
  showComparison(app, data.comparison);
  if (data.cover) {
    const c = data.cover;
    out.line();
    out.line(
      out.heading(`Cash covering ${out.decimal(c.target_months)} months of ${c.basis === 'essential' ? 'essential ' : ''}spending`) +
        ` ${out.colors.dim(`${out.amount(c.target, data.currency)} in today’s money; ${out.decimal(c.now)} months now`)}`,
    );
    const rows = [{ label: 'Baseline', month: c.baseline.month, months: c.baseline.months }, ...c.options.map((o) => ({ label: o.option, month: o.month, months: o.months }))];
    out.line(
      out.table(rows, [
        { header: '', get: (r) => singleLine(r.label), shrink: true },
        { header: 'REACHED BY', get: (r) => (r.month ? displayMonth(r.month, out.locale) : 'not within 50 years'), align: 'right' },
        { header: 'MONTHS', get: (r) => (r.months === null ? '—' : String(r.months)), align: 'right' },
      ]),
    );
  }
  const check: PrinciplesCheck = {
    as_of: data.as_of,
    currency: data.currency,
    principles: data.principles.principles,
    baseline: data.principles.baseline,
    options: data.principles.options,
    placeholders: data.placeholders,
    data_as_of: data.data_as_of,
  };
  out.line();
  showCheck(app, check);
  for (const note of data.notes) out.note(singleLine(note));
}

// ── Recording ─────────────────────────────────────────────────────────────────

interface RecordOptions {
  record?: boolean;
  chosen?: string;
  reasons?: string;
  reviewOn?: string;
  question?: string;
  yes?: boolean;
}

async function record(app: App, api: SalliClient, data: DecisionStart, opts: RecordOptions): Promise<unknown> {
  const prompter = app.prompter;
  const interactive = prompter.interactive && !app.out.machine;
  if (!opts.record) {
    if (!interactive) return undefined;
    if (!(await prompter.confirm({ message: 'Record what you choose in your decision journal?', initialValue: false }))) return undefined;
  }
  const labels = data.record.labels;
  let chosen = opts.chosen;
  if (chosen === undefined) {
    if (!interactive) throw new UsageError('To record, say which option you chose.', `Pass --chosen with one of: ${labels.join(', ')}.`);
    chosen = await prompter.select({ message: 'Which did you choose?', options: labels.map((l) => ({ value: l, label: l })) });
  } else if (!labels.includes(chosen)) {
    throw new UsageError(`--chosen is one of the options: ${labels.join(', ')} (got "${chosen}").`);
  }
  const reasons =
    opts.reasons ??
    (interactive
      ? await prompter.text({ message: 'Why? In your own words.', validate: (v) => (v.trim() ? undefined : 'Write a few words, in your own terms.') })
      : undefined);
  if (!reasons) throw new UsageError('To record, give your reasons.', 'Pass --reasons "…", in your own words.');
  const reviewText =
    opts.reviewOn ??
    (interactive
      ? await prompter.text({
          message: 'When do you want to look back on it?',
          placeholder: `a date from ${data.record.earliest_review} on`,
          validate: (v) => (v.trim() ? undefined : 'A date, like 2027-04-11.'),
        })
      : undefined);
  if (!reviewText) throw new UsageError('To record, say when to look back.', 'Pass --review-on YYYY-MM-DD.');
  const reviewOn = parseDate(reviewText, app.runtime.now(), '--review-on');
  const question =
    opts.question ?? (interactive ? await prompter.text({ message: 'The question, in your words:', initialValue: data.record.question }) : data.record.question);
  const ok = await confirmAction(app, opts.yes, `Record “${singleLine(question || data.record.question)}”, chose “${singleLine(chosen)}”? Entries can't be edited or deleted afterwards`);
  if (!ok) return undefined;
  const recorded = await api.call(decisionsRecord, {
    body: {
      question: question || data.record.question,
      options: data.record.options as Scenario[],
      chosen,
      reasons,
      review_on: reviewOn,
    },
  });
  if (!app.out.machine) {
    app.out.success(`Recorded “${singleLine(recorded.entry.question)}” ${app.out.errColors.dim(recorded.id)}`);
    app.out.note(`Salli will remind you to review it on ${displayDate(recorded.entry.review_on, app.out.locale)}.`);
  }
  return recorded;
}

// ── The command ───────────────────────────────────────────────────────────────

export function registerDecide(program: Command, app: App): void {
  program
    .command('decide')
    .argument('[template]', 'A template: afford-it, debt-or-invest, windfall, big-change, borrow, emergency-fund')
    .description('Work through a common decision: Salli builds and compares the options (never ranks them)')
    .option('--list', 'List the templates')
    .option('--questions', 'Show the template’s questions and your defaults, and stop')
    .option('--answers <file>', 'Answers as a JSON object by question id (for scripts)')
    .option('--set <id=value>', 'Answer one question (repeatable): --set price=2400', collect)
    .option('--as-of <date>', 'The day your baseline is as of (default today)')
    .option('--record', 'Record the decision afterwards (with --chosen, --reasons, --review-on)')
    .option('--chosen <label>', 'The label of the option you chose')
    .option('--reasons <text>', 'Your reasons, in your own words')
    .option('--review-on <date>', 'When to look back (from the end of this month)')
    .option('--question <text>', 'The question, in your words (default: the template’s)')
    .option('-y, --yes', 'Do not ask before recording')
    .addHelpText(
      'after',
      `
In a terminal, it asks each question, with your own defaults where there
are honest ones (your only debt, what it owes, your principles' cash
target, the date). Salli builds the options, runs each on your baseline and
shows the comparison, the sensitivity, the break-evens and your
principles' checks. Then it offers to record what you choose, and why.

Examples:
  $ salli decide --list
  $ salli decide afford-it
  $ salli decide afford-it --set price=2400 --set instalment_months=12 --set instalment_rate=6.9%
  $ salli decide emergency-fund --set target_months=6 --set set_aside=200,500 --json
  $ salli decide windfall --answers windfall.json
  $ salli decide debt-or-invest --answers a.json --record --chosen "Invest it" \\
      --reasons "I'd rather grow it." --review-on 2027-10-31 --yes`,
    )
    .action(async (id, opts) => {
      const api = await app.api();
      if (opts.list || !id) {
        if (!opts.list) throw new UsageError('Say which template.', 'See them with `salli decide --list`.');
        const data = await api.call(decisionsTemplatesList);
        app.out.emit(data, {
          records: (d) => d.templates,
          human: (d) => {
            app.out.line(
              app.out.table(d.templates, [
                { header: 'TEMPLATE', get: (t) => t.id },
                { header: 'FOR', get: (t) => t.summary, shrink: true },
              ]),
            );
            app.out.note('Conveniences, not advice: each builds the options you describe, and Salli compares them.');
          },
        });
        return;
      }
      const template = await api.call(decisionsTemplatesGet, { path: { template_id: id } });
      if (opts.questions) {
        app.out.emit(template, {
          records: (t) => t.questions,
          human: (t) => {
            app.out.line(app.out.heading(t.title) + ` ${app.out.colors.dim(t.summary)}`);
            app.out.line(
              app.out.table(t.questions, [
                { header: 'ID', get: (q) => q.id },
                { header: 'TYPE', get: (q) => q.type },
                { header: 'QUESTION', get: (q) => q.prompt, shrink: true },
                { header: 'DEFAULT', get: (q) => (q.default ? `${String(q.default.value)} (${q.default.note})` : q.required ? 'needed' : ''), shrink: true },
              ]),
            );
          },
        });
        return;
      }
      const names = await Names.load(api, template);
      let answers: Answers = opts.answers ? await readAnswers(opts.answers) : {};
      answers = { ...answers, ...setAnswers(app, template, opts.set ?? [], names) };
      const scripted = opts.answers !== undefined || (opts.set ?? []).length > 0;
      if (app.prompter.interactive && !app.out.machine && !scripted) answers = await ask(app, template, answers, names);
      const asOf = opts.asOf ? parseDate(opts.asOf, app.runtime.now(), '--as-of') : undefined;
      const data = await api.call(decisionsStart, { body: { template: template.id, answers, ...(asOf ? { as_of: asOf } : {}) } });
      if (!app.out.machine) showStart(app, data);
      const recorded = await record(app, api, data, opts);
      if (app.out.machine) {
        app.out.emit(recorded ? { ...data, recorded } : data, { records: (d) => d.options, human: () => undefined });
      } else if (!recorded) {
        app.out.note(`Nothing is recorded. ${plural(data.options.length, 'option')} weighed; the choice is yours.`);
      }
    });
}
