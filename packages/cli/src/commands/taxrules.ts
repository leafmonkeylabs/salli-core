/**
 * salli tax schema, and salli tax rules …: your own tax rule sets
 * (docs/taxrules.md). You, or an AI agent, write the rules; Salli's engine
 * validates them against their worked examples and computes with them.
 *
 * Everything here is open to an agent but one command: `activate`, which
 * makes a version the rules Salli computes your tax with. It shows what is
 * being activated (the diff, the source behind each changed figure, every
 * worked example, who wrote it and why) and asks you to type the version
 * number. It has no --yes, and refuses outright when it can't ask a person:
 * stdin or stdout isn't a terminal, or the output is meant for a program
 * (--json, --output). An agent running commands can't answer a prompt, so it
 * can't activate. The server also refuses (403) any sign-in that doesn't hold
 * tax:activate; this explains why when it does.
 *
 * The CLI never computes a figure: every amount shown is the server's, as
 * the decimal string it sent.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  SalliApiError,
  taxRuleSetsCreate,
  taxRuleSetsDiff,
  taxRuleSetsGet,
  taxRuleSetsImport,
  taxRuleSetsList,
  taxRuleSetsVersionsActivate,
  taxRuleSetsVersionsCreate,
  taxRuleSetsVersionsEvaluate,
  taxRuleSetsVersionsExport,
  taxRuleSetsVersionsGet,
  taxRuleSetsVersionsPropose,
  taxRuleSetsVersionsValidate,
  taxSchema,
  toJsonText,
  type JsonValue,
  type SalliClient,
  type TaxRuleChange,
  type TaxRuleDiff,
  type TaxRuleEvaluation,
  type TaxRuleExampleResult,
  type TaxRuleProblem,
  type TaxRuleSet,
  type TaxRuleSetVersion,
  type TaxRuleSetVersionSummary,
  type TaxRuleValidation,
} from '@leafmonkeylabs/salli-sdk';
import { readFile, stat } from 'node:fs/promises';
import type { App } from '../app';
import { firstPartyClientId } from '../auth/login';
import { CliError, ExitCode, NotFoundError, UsageError } from '../errors';
import { sanitize, singleLine, truncate } from '../output/text';
import { displayDate, displayRange } from '../util/dates';
import { parseWholeNumber } from '../util/numbers';
import { writeOutput } from '../util/files';
import { TAX_ACTIVATE } from '../util/permissions';
import { resolveById } from '../util/resolve';
import { readAllStdin } from '../util/stdin';
import { collect } from './shared';

/** The most a rule-set document may be (the server refuses more). */
const MAX_DOCUMENT_BYTES = 1024 * 1024;

type Status = TaxRuleSetVersionSummary['status'];

// ── finding rule sets and versions ───────────────────────────────────────────

/** The rule set `query` names: its id (or a unique start of it), or its name ("XA 2031"). */
export function resolveRuleSet(sets: readonly TaxRuleSet[], query: string): TaxRuleSet {
  const wanted = query.trim().toLowerCase();
  const byName = sets.filter((s) => s.name.toLowerCase() === wanted);
  if (byName.length === 1 && byName[0]) return byName[0];
  try {
    return resolveById(sets, query, 'rule set');
  } catch (error) {
    if (error instanceof NotFoundError) {
      throw new NotFoundError(`No tax rule set "${query}".`, 'See `salli tax rules list` for ids and names.');
    }
    throw error;
  }
}

/**
 * The version `query` names in a set: its number (`3` or `v3`), or its id
 * (or a unique start; an id can begin with digits only, so a number no
 * version has is tried as one).
 */
export function resolveVersion(set: TaxRuleSet, query: string): TaxRuleSetVersionSummary {
  const number = /^(v)?(\d+)$/i.exec(query.trim());
  if (number) {
    const wanted = parseWholeNumber(number[2]);
    const found = set.versions.find((v) => v.version === wanted);
    if (found) return found;
    const byId = number[1] ? [] : set.versions.filter((v) => v.id.startsWith(query.trim()));
    if (byId.length === 1 && byId[0]) return byId[0];
    throw new NotFoundError(`${set.name} has no version ${number[2]}.`, `It has ${versionRange(set)}.`);
  }
  return resolveById(set.versions, query, 'version');
}

function versionRange(set: TaxRuleSet): string {
  const numbers = set.versions.map((v) => v.version);
  if (numbers.length === 0) return 'no versions';
  return numbers.length === 1 ? 'version 1' : `versions ${numbers[0]} to ${numbers[numbers.length - 1]}`;
}

function newest(set: TaxRuleSet): TaxRuleSetVersionSummary {
  const last = set.versions[set.versions.length - 1];
  if (!last) throw new NotFoundError(`${set.name} has no versions.`);
  return last;
}

/** The version a command acts on: the one --version names, else the newest. */
function chosen(app: App, set: TaxRuleSet, query: string | undefined): TaxRuleSetVersionSummary {
  if (query !== undefined) return resolveVersion(set, query);
  const version = newest(set);
  if (set.versions.length > 1) app.out.note(`Version ${version.version}, the newest (choose another with --version).`);
  return version;
}

async function loadSet(api: SalliClient, query: string): Promise<TaxRuleSet> {
  return resolveRuleSet(await api.call(taxRuleSetsList), query);
}

function versionPath(set: TaxRuleSet, version: TaxRuleSetVersionSummary): { rule_set_id: string; version_id: string } {
  return { rule_set_id: set.id, version_id: version.id };
}

/** A rule-set file's text, or stdin's for "-". Sent as text, so the server reads it strictly. */
async function readDocument(app: App, path: string): Promise<string> {
  if (path === '-') return readAllStdin(app.runtime.stdin);
  let info;
  try {
    info = await stat(path);
  } catch {
    throw new UsageError(`No such file: ${path}`);
  }
  if (!info.isFile()) throw new UsageError(`Not a file: ${path}`);
  if (info.size > MAX_DOCUMENT_BYTES) throw new UsageError(`${path} is larger than a rule set may be (1 MiB).`);
  return readFile(path, 'utf8');
}

function noteArg(value: string): string {
  const note = value.trim();
  if (!note) throw new UsageError('--note is empty.');
  return note;
}

/** `key=value` answers to a rule set's questions: true/false, or text (a decimal, a choice). */
export function answersArg(values: readonly string[]): Record<string, string | boolean> {
  const answers: Record<string, string | boolean> = {};
  for (const value of values) {
    const at = value.indexOf('=');
    const key = at > 0 ? value.slice(0, at).trim() : '';
    const answer = at > 0 ? value.slice(at + 1).trim() : '';
    if (!key || !answer) throw new UsageError(`--answer takes KEY=VALUE, e.g. --answer filing_status=joint (got "${value}").`);
    answers[key] = answer === 'true' ? true : answer === 'false' ? false : answer;
  }
  return answers;
}

// ── showing them ─────────────────────────────────────────────────────────────

function statusStyle(app: App, status: Status): (text: string) => string {
  const c = app.out.colors;
  const styles: Record<Status, (s: string) => string> = {
    active: c.green,
    proposed: c.yellow,
    validated: c.cyan,
    draft: (s) => s,
    invalid: c.red,
    superseded: c.dim,
  };
  return styles[status];
}

function statusText(app: App, status: Status): string {
  return statusStyle(app, status)(status);
}

/** "you (Salli CLI)" or "an agent (Claude)". */
function authorText(version: TaxRuleSetVersionSummary): string {
  const name = version.author_name ? ` (${singleLine(version.author_name)})` : '';
  return version.author_kind === 'agent' ? `an agent${name}` : `you${name}`;
}

function hashText(hash: string | null | undefined): string {
  return hash ? hash.slice(0, 12) : '—';
}

/** A changed value, as the document has it: decimals as their text, anything else as compact JSON. */
function valueText(value: JsonValue | undefined): string {
  if (value === undefined || value === null) return '—';
  if (typeof value === 'string') return truncate(singleLine(value), 70);
  const record = typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
  if (typeof record?.url === 'string') {
    // A source: what it is and where.
    const title = typeof record.title === 'string' ? `${singleLine(record.title)} — ` : '';
    return `${title}${singleLine(record.url)}`;
  }
  return truncate(singleLine(JSON.stringify(value)), 70);
}

/** "Budget Statement 2031 — https://…", for the source a change cites. */
function sourceText(diff: TaxRuleDiff, id: string | null): string | undefined {
  if (!id) return undefined;
  const source = diff.sources[id];
  if (!source) return `source "${singleLine(id)}" (not declared in this version)`;
  const title = typeof source.title === 'string' ? singleLine(source.title) : singleLine(id);
  const url = typeof source.url === 'string' ? singleLine(source.url) : undefined;
  const retrieved = typeof source.retrieved === 'string' ? `, retrieved ${singleLine(source.retrieved)}` : '';
  return url ? `${title} — ${url}${retrieved}` : `${title}${retrieved}`;
}

function renderProblems(app: App, heading: string, problems: readonly TaxRuleProblem[], mark: string): void {
  if (!problems.length) return;
  const out = app.out;
  out.line(out.heading(`${heading} (${problems.length})`));
  for (const p of problems) {
    out.line(`  ${mark} ${out.colors.bold(singleLine(p.path))}  ${singleLine(p.message)}`);
    if (p.snippet) {
      for (const line of sanitize(p.snippet).split('\n')) out.line(`      ${out.colors.dim(line)}`);
    }
  }
  out.line();
}

function renderExamples(app: App, examples: readonly TaxRuleExampleResult[]): void {
  const out = app.out;
  const c = out.colors;
  if (!examples.length) {
    out.line(`${c.yellow('!')} No worked examples. Add the authority's own, so Salli can check these rules against them.`);
    return;
  }
  const passed = examples.filter((e) => e.passed).length;
  out.line(out.heading(`Worked examples (${passed} of ${examples.length} pass)`));
  for (const example of examples) {
    out.line(`  ${example.passed ? c.green('✓') : c.red('✗')} ${singleLine(example.name)}`);
    if (example.error) out.line(`      ${c.red(singleLine(example.error))}`);
    for (const m of example.mismatches) {
      out.line(`      ${c.bold(singleLine(m.key))}: expected ${singleLine(m.expected)}, got ${c.red(singleLine(m.got))}`);
      out.line(`        ${c.dim(`from ${singleLine(m.expr)}`)}`);
    }
  }
}

/** A validation report: problems, warnings, then every worked example. */
function renderValidation(app: App, validation: TaxRuleValidation): void {
  const out = app.out;
  const c = out.colors;
  if (validation.ok) out.line(`${c.green('✓')} Valid: it compiles, and every worked example passes.`);
  else if (validation.errors.length) out.line(`${c.red('✗')} Invalid: it doesn't compile (problems below).`);
  else out.line(`${c.yellow('!')} Not ready: it compiles, but its worked examples are missing or don't all pass.`);
  out.line(c.dim(`Validated ${displayDate(validation.validated_at, out.locale)}${validation.content_hash ? ` · hash ${hashText(validation.content_hash)}` : ''}`));
  out.line();
  renderProblems(app, 'Problems', validation.errors, c.red('✗'));
  renderProblems(app, 'Warnings', validation.warnings, c.yellow('!'));
  renderExamples(app, validation.examples);
}

function renderVersionDetails(app: App, set: TaxRuleSet, v: TaxRuleSetVersionSummary): void {
  const out = app.out;
  out.line(out.heading(`${set.name}, version ${v.version}`));
  out.line(
    out.details([
      ['Status', statusText(app, v.status)],
      ['Author', authorText(v)],
      ['Note', v.change_note ? singleLine(v.change_note) : undefined],
      ['Hash', v.content_hash ?? undefined],
      ['Created', displayDate(v.created_at, out.locale)],
      ['Proposed', v.proposed_at ? displayDate(v.proposed_at, out.locale) : undefined],
      ['Activated', v.activated_at ? displayDate(v.activated_at, out.locale) : undefined],
      ['Superseded', v.superseded_at ? displayDate(v.superseded_at, out.locale) : undefined],
      ['Id', v.id],
    ]),
  );
  out.line();
}

/** What a stored version's report means next, for people. */
function nextStep(app: App, set: TaxRuleSet, v: TaxRuleSetVersion): void {
  const id = set.id.slice(0, 8);
  if (v.validation.ok) {
    app.out.note(
      `Next: propose it for review (\`salli tax rules propose ${id} --version ${v.version}\`), ` +
        `or review and activate it yourself (\`salli tax rules activate ${id} --version ${v.version}\`).`,
    );
  } else {
    app.out.note(`Fix what is listed, then add it as a new version: \`salli tax rules version ${id} <file> --note "…"\`.`);
  }
}

/** A version just stored (create, version, import): what it is, then its report. */
function emitStored(app: App, set: TaxRuleSet | undefined, v: TaxRuleSetVersion, what: string): void {
  app.out.emit(v, {
    human: (d) => {
      const name = set?.name ?? 'the rule set';
      app.out.success(`${what} ${name}, version ${d.version}: ${d.status}.`);
      renderValidation(app, d.validation);
      if (set) nextStep(app, set, d);
    },
  });
}

/** The changes a diff lists: figures first, each with the source it cites. */
function renderChanges(app: App, diff: TaxRuleDiff): void {
  const out = app.out;
  const c = out.colors;
  if (!diff.from) {
    out.line(`${out.heading('First version')}: no version is active yet, so all of it is new.`);
    out.line();
    return;
  }
  if (!diff.changes.length) {
    out.line(`No changes from version ${diff.from.version}.`);
    out.line();
    return;
  }
  const mark = (change: TaxRuleChange): string =>
    change.kind === 'added' ? c.green('+') : change.kind === 'removed' ? c.red('-') : c.yellow('~');
  const line = (change: TaxRuleChange): void => {
    const path = c.bold(singleLine(change.path));
    const values =
      change.kind === 'added'
        ? `added: ${valueText(change.after)}`
        : change.kind === 'removed'
          ? `removed (was ${valueText(change.before)})`
          : `${valueText(change.before)} → ${c.bold(valueText(change.after))}`;
    out.line(`  ${mark(change)} ${path}  ${values}`);
    const source = sourceText(diff, change.source);
    if (source) out.line(`      ${c.dim('source:')} ${source}`);
    else if (change.figure) out.line(`      ${c.yellow('no source cited for this figure')}`);
  };
  const figures = diff.changes.filter((ch) => ch.figure);
  const others = diff.changes.filter((ch) => !ch.figure);
  if (figures.length) {
    out.line(out.heading(`Changed figures (${figures.length})`));
    figures.forEach(line);
    out.line();
  }
  if (others.length) {
    out.line(out.heading(`Other changes (${others.length})`));
    others.forEach(line);
    out.line();
  }
}

function renderDiff(app: App, set: TaxRuleSet, diff: TaxRuleDiff): void {
  const out = app.out;
  const from = diff.from ? `version ${diff.from.version} (${diff.from.status})` : 'nothing active';
  out.line(out.heading(`${set.name}: ${from} → version ${diff.to.version} (${diff.to.status})`));
  out.line();
  renderChanges(app, diff);
  renderExamples(app, diff.examples);
}

function renderEvaluation(app: App, e: TaxRuleEvaluation): void {
  const out = app.out;
  const c = out.colors;
  const cur = e.currency;
  const where = e.region ? `${e.country} ${singleLine(e.region)}` : e.country;
  out.line(
    `${out.heading(`${where} ${singleLine(e.year)}, version ${e.version.version}`)} ` +
      c.dim(`${displayRange(e.period_start, e.period_end, out.locale)} · ${cur} · not tax advice`),
  );
  if (!e.validated) out.line(`${c.yellow('!')} These rules haven't passed their worked examples: treat the figures as a draft.`);
  out.line();
  if (e.roles.length) {
    out.line(
      out.table(e.roles, [
        { header: 'FROM YOUR LEDGER', get: (r) => r.label, shrink: true },
        { header: 'ROLE', get: (r) => r.key, style: (s) => c.dim(s) },
        { header: `TOTAL (${cur})`, get: (r) => out.amount(r.total, cur), align: 'right' },
        { header: 'POSTINGS', get: (r) => r.postings, align: 'right' },
      ]),
    );
    out.line();
  }
  if (e.rates.length) {
    out.line(c.dim(`Converted from ${e.base_currency} at ${e.rates.length} published rate${e.rates.length === 1 ? '' : 's'} (see --json).`));
    out.line();
  }
  out.line(
    out.table(e.lines, [
      { header: 'LINE', get: (l) => l.key, style: (s) => c.dim(s) },
      { header: 'LABEL', get: (l) => l.label + (l.refundable === true ? ' (refundable)' : ''), shrink: true },
      { header: `AMOUNT (${cur})`, get: (l) => out.amount(l.amount, cur), align: 'right', style: (s, l) => out.signed(s, l.amount) },
      { header: 'FROM', get: (l) => l.expr, shrink: true, style: (s) => c.dim(s) },
    ]),
  );
  out.line();
  const m = (amount: string): string => out.money(amount, cur);
  out.line(
    out.details([
      ['Net', `${m(e.net)}  ${c.dim(`(${singleLine(e.net_expr)})`)}`],
      ['Payable', m(e.tax_payable), c.bold],
      ['Refund', m(e.refund_due), c.green],
    ]),
  );
  for (const warning of e.warnings) out.warn(singleLine(warning));
  out.note(singleLine(e.provenance));
}

// ── activation ───────────────────────────────────────────────────────────────

/**
 * Refuses unless a person is at a terminal to read the review and type the
 * version number. Checked before anything else, signing in included.
 */
function refuseUnlessAPersonIsHere(app: App): void {
  const { stdin, stdout } = app.runtime;
  const why = app.out.machine
    ? `the output is for a program (--${app.out.format === 'json' ? 'json' : `output ${app.out.format}`})`
    : stdin.isTTY !== true
      ? 'stdin is not a terminal'
      : stdout.isTTY !== true
        ? 'stdout is not a terminal'
        : !app.prompter.interactive
          ? 'there is no terminal to ask in'
          : undefined;
  if (!why) return;
  throw new CliError(`Activating tax rules needs a person at a terminal, and ${why}.`, {
    exitCode: ExitCode.USAGE,
    kind: 'needs-a-person',
    hint:
      'Run `salli tax rules activate <set>` yourself, in your own terminal: it shows the changes, their sources and the worked ' +
      'examples, and asks you to type the version number. There is no --yes. An AI agent can draft, validate and propose ' +
      'rules, never activate them.',
  });
}

/** The version activate defaults to: the newest proposed one. */
function newestProposed(set: TaxRuleSet): TaxRuleSetVersionSummary {
  const proposed = set.versions.filter((v) => v.status === 'proposed');
  const last = proposed[proposed.length - 1];
  if (!last) {
    throw new NotFoundError(
      `${set.name} has no proposed version to review.`,
      `Propose one (\`salli tax rules propose ${set.id.slice(0, 8)}\`), or name one with --version.`,
    );
  }
  return last;
}

/** The review: what activating changes, the evidence for it, and who wrote it. */
function renderReview(app: App, set: TaxRuleSet, v: TaxRuleSetVersionSummary, diff: TaxRuleDiff): void {
  const out = app.out;
  const c = out.colors;
  out.line(out.heading(`Activate ${set.name}, version ${v.version}?`));
  out.line(
    diff.from
      ? `Salli would compute your ${set.name} tax with version ${v.version} instead of version ${diff.from.version}` +
          (diff.from.activated_at ? ` (active since ${displayDate(diff.from.activated_at, out.locale)}).` : '.')
      : `Salli would compute your ${set.name} tax with version ${v.version}. It is the first version you activate.`,
  );
  out.line();
  out.line(
    out.details([
      ['Written by', authorText(v)],
      ['Why', v.change_note ? singleLine(v.change_note) : c.dim('no note given')],
      ['Status', statusText(app, v.status)],
      ['Proposed', v.proposed_at ? displayDate(v.proposed_at, out.locale) : undefined],
      ['Hash', hashText(v.content_hash)],
    ]),
  );
  out.line();
  if (diff.from) out.line(c.dim(`Against version ${diff.from.version}, the active one:`));
  renderChanges(app, diff);
  renderExamples(app, diff.examples);
  out.line();
  out.line(c.dim('Salli computes with rules you or your agent entered; it does not vouch for them. Check each changed figure against its source.'));
}

/** Why the server refused to activate (403), and what would work. */
async function explainForbidden(app: App, error: SalliApiError): Promise<CliError> {
  const ctx = await app.context();
  const auth = await app.auth(ctx);
  let why: string;
  let hint: string;
  if (auth.source === 'env' || auth.credentials?.kind === 'token') {
    why = 'This personal access token was made without tax:activate';
    hint =
      'Sign in yourself with `salli login`, or make a token that may, from your own sign-in: `salli tokens create <name> --allow tax:activate`. ' +
      'Tokens are what scripts and agents are given, so they can’t activate unless you say so.';
  } else {
    let own: string | undefined;
    try {
      own = firstPartyClientId(await app.client(ctx.server, undefined, 10_000).meta());
    } catch {
      own = undefined;
    }
    const registered = auth.credentials?.kind === 'oauth' && auth.credentials.client_id !== own;
    why = registered
      ? 'This sign-in is a client salli registered for itself, which the server treats like any other application'
      : 'This sign-in is an agent’s or another application’s, not your own';
    hint = registered && own
      ? 'Sign in again with `salli login`: it signs in as the server’s own CLI client, which may activate.'
      : 'Activate in the Salli app, or sign in yourself with `salli login`, or use a token made with `salli tokens create <name> --allow tax:activate`.';
  }
  return new CliError(`Not activated. ${why}, so it doesn't hold ${TAX_ACTIVATE}.`, {
    exitCode: ExitCode.REFUSED,
    kind: 'forbidden',
    hint,
    cause: error,
  });
}

// ── the commands ─────────────────────────────────────────────────────────────

export function registerTaxRules(tax: Command, app: App): void {
  tax
    .command('schema')
    .description('The JSON Schema a tax rule set is written against')
    .option('-o, --out <file>', 'Write it to this file (default: stdout)')
    .action(async (opts) => {
      const api = await app.api();
      const schema = await api.call(taxSchema);
      await writeOutput(app, `${toJsonText(schema)}\n`, opts.out, { schema: 'salli.tax/1' }, 'the JSON Schema');
    });

  const rules = tax
    .command('rules')
    .alias('rule-sets')
    .description('Your own tax rule sets: write, check, review and activate them')
    .addHelpText(
      'after',
      `
A rule set is a JSON document (salli.tax/1, see \`salli tax schema\`) saying how
one jurisdiction taxes one year, citing its sources, with the authority's own
worked examples. Each change is a new version; nothing stored ever changes.

  draft → validated → proposed → active → superseded   (or invalid)

Anyone signed in, an AI agent included, can create, validate, propose and
evaluate. Only you activate, here, at a terminal: \`activate\` shows the diff,
each changed figure's source and every worked example, and asks you to type
the version number. It has no --yes and won't run for a program.

<set> is a rule set's id (or its start) or name ("XA 2031"); --version is a
number (3) or a version id. Without --version, commands use the newest.

Examples:
  $ salli tax schema -o salli-tax.schema.json
  $ salli tax rules create xa-2031.json --note "From the 2031 Act"
  $ salli tax rules validate "XA 2031"
  $ salli tax rules diff "XA 2031"
  $ salli tax rules evaluate "XA 2031" --answer filing_status=joint
  $ salli tax rules activate "XA 2031"`,
    );

  rules
    .command('list')
    .alias('ls')
    .description('Your rule sets, with their active and newest versions')
    .action(async () => {
      const api = await app.api();
      const sets = await api.call(taxRuleSetsList);
      app.out.emit(sets, {
        human: (d) => {
          if (!d.length) {
            app.out.note('No rule sets. Write one against `salli tax schema`, then `salli tax rules create <file>`.');
            return;
          }
          const c = app.out.colors;
          const active = (s: TaxRuleSet): string => {
            const v = s.versions.find((x) => x.id === s.active_version_id);
            return v ? `v${v.version}` : '—';
          };
          app.out.line(
            app.out.table(d, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'RULE SET', get: (s) => s.name, shrink: true },
              { header: 'ACTIVE', get: active },
              { header: 'NEWEST', get: (s) => (s.versions.length ? `v${newest(s).version} ${newest(s).status}` : '—') },
              { header: 'VERSIONS', get: (s) => s.versions.length, align: 'right' },
              { header: 'UPDATED', get: (s) => displayDate(s.updated_at, app.out.locale) },
            ]),
          );
          const waiting = d.filter((s) => s.versions.some((v) => v.status === 'proposed'));
          for (const s of waiting) {
            app.out.note(`${singleLine(s.name)} has a version proposed for your review: \`salli tax rules activate ${s.id.slice(0, 8)}\`.`);
          }
        },
      });
    });

  rules
    .command('show')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('A rule set’s versions, or one version’s details and validation report')
    .option('--version <n|id>', 'Show this version (its details and report)')
    .action(async (query, opts) => {
      const api = await app.api();
      const set = await loadSet(api, query);
      if (opts.version !== undefined) {
        const summary = resolveVersion(set, opts.version);
        const version = await api.call(taxRuleSetsVersionsGet, { path: versionPath(set, summary) });
        app.out.emit(version, {
          human: (v) => {
            renderVersionDetails(app, set, v);
            renderValidation(app, v.validation);
          },
        });
        return;
      }
      const full = await api.call(taxRuleSetsGet, { path: { rule_set_id: set.id } });
      app.out.emit(full, {
        records: (s) => s.versions,
        human: (s) => {
          const out = app.out;
          const c = out.colors;
          const active = s.versions.find((v) => v.id === s.active_version_id);
          out.line(`${out.heading(s.name)} ${c.dim(s.id)}`);
          out.line(
            out.details([
              ['Active', active ? `version ${active.version}${active.activated_at ? `, since ${displayDate(active.activated_at, out.locale)}` : ''}` : 'none yet'],
            ]),
          );
          out.line();
          if (!s.versions.length) return out.note('No versions.');
          out.line(
            out.table(s.versions, [
              { header: 'VERSION', get: (v) => v.version, align: 'right' },
              { header: 'STATUS', get: (v) => v.status, style: (t, v) => statusStyle(app, v.status)(t) },
              { header: 'AUTHOR', get: (v) => authorText(v) },
              { header: 'NOTE', get: (v) => (v.change_note ? v.change_note : '—'), shrink: true },
              { header: 'HASH', get: (v) => hashText(v.content_hash), style: (t) => c.dim(t) },
              { header: 'CREATED', get: (v) => displayDate(v.created_at, out.locale) },
            ]),
          );
          const proposed = s.versions.filter((v) => v.status === 'proposed').at(-1);
          if (proposed) {
            out.note(`Version ${proposed.version} awaits your review: \`salli tax rules activate ${s.id.slice(0, 8)}\` (at your terminal).`);
          }
        },
      });
    });

  rules
    .command('create')
    .argument('<file>', 'The rule set’s JSON ("-" reads stdin)')
    .description('A new rule set from a document, as its version 1')
    .option('--note <text>', 'Where the rules come from, for the history', noteArg)
    .action(async (file, opts) => {
      const document = await readDocument(app, file);
      const api = await app.api();
      const created = await api.call(taxRuleSetsCreate, { body: { document, ...(opts.note ? { note: opts.note } : {}) } });
      const set = (await api.call(taxRuleSetsList)).find((s) => s.id === created.rule_set_id);
      emitStored(app, set, created, 'Created');
    });

  rules
    .command('version')
    .argument('<set>', 'Rule set id (or its start) or name')
    .argument('<file>', 'The new version’s JSON ("-" reads stdin)')
    .description('Add a version: an edit never changes one already stored')
    .option('--note <text>', 'What changed and why', noteArg)
    .action(async (query, file, opts) => {
      const document = await readDocument(app, file);
      const api = await app.api();
      const set = await loadSet(api, query);
      const created = await api.call(taxRuleSetsVersionsCreate, {
        path: { rule_set_id: set.id },
        body: { document, ...(opts.note ? { note: opts.note } : {}) },
      });
      emitStored(app, set, created, 'Added to');
    });

  rules
    .command('import')
    .argument('<source>', 'A rule-set file, or an https:// URL the server fetches')
    .description('Import a rule set (it lands as a draft, never further)')
    .option('--note <text>', 'Where it came from', noteArg)
    .action(async (source, opts) => {
      const isUrl = /^[a-z][a-z0-9+.-]*:\/\//i.test(source);
      if (isUrl && !/^https:\/\//i.test(source)) throw new UsageError('Only https:// URLs can be imported.');
      const body = isUrl
        ? { url: source, ...(opts.note ? { note: opts.note } : {}) }
        : { document: await readDocument(app, source), ...(opts.note ? { note: opts.note } : {}) };
      const api = await app.api();
      const imported = await api.call(taxRuleSetsImport, { body });
      const set = (await api.call(taxRuleSetsList)).find((s) => s.id === imported.rule_set_id);
      emitStored(app, set, imported, 'Imported into');
    });

  rules
    .command('export')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('A version as a file: canonical JSON, whose SHA-256 is its content hash')
    .option('--version <n|id>', 'The version (default: the newest)')
    .option('-o, --out <file>', 'Write it to this file (default: stdout)')
    .action(async (query, opts) => {
      const api = await app.api();
      const set = await loadSet(api, query);
      const version = chosen(app, set, opts.version);
      const exported = await api.call(taxRuleSetsVersionsExport, { path: versionPath(set, version) });
      if (opts.out === undefined || opts.out === '-') {
        if (app.out.machine) app.out.emit(exported, { human: () => undefined });
        else {
          // Exactly the text, so a pipe gets the bytes the hash is of.
          app.out.write(exported.text);
          if (app.runtime.stdout.isTTY) app.out.line();
          app.out.note(`Suggested file name: ${singleLine(exported.filename)}`);
        }
        return;
      }
      await writeOutput(
        app,
        exported.text,
        opts.out,
        { rule_set_id: set.id, version: version.version, content_hash: exported.content_hash, canonical: exported.canonical },
        `${set.name} version ${version.version}${exported.content_hash ? ` (sha256 ${hashText(exported.content_hash)}…)` : ''}`,
      );
    });

  rules
    .command('validate')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('Check a version again: its problems, warnings and every worked example')
    .option('--version <n|id>', 'The version (default: the newest)')
    .addHelpText('after', '\nExits 1 when the version is not valid, so a script (or an agent) can loop until it is.')
    .action(async (query, opts) => {
      const api = await app.api();
      const set = await loadSet(api, query);
      const version = chosen(app, set, opts.version);
      const checked = await api.call(taxRuleSetsVersionsValidate, { path: versionPath(set, version) });
      app.out.emit(checked, {
        records: (v) => v.validation.examples,
        human: (v) => {
          app.out.line(`${app.out.heading(`${set.name}, version ${v.version}`)} ${app.out.colors.dim(v.status)}`);
          renderValidation(app, v.validation);
        },
      });
      if (!checked.validation.ok) {
        throw new CliError(`Version ${checked.version} is not valid.`, { exitCode: ExitCode.ERROR, kind: 'invalid-rule-set', quiet: true });
      }
    });

  rules
    .command('propose')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('Ask for the version to be reviewed and activated (it must be valid)')
    .option('--version <n|id>', 'The version (default: the newest)')
    .action(async (query, opts) => {
      const api = await app.api();
      const set = await loadSet(api, query);
      const version = chosen(app, set, opts.version);
      const proposed = await api.call(taxRuleSetsVersionsPropose, { path: versionPath(set, version) });
      app.out.emit(proposed, {
        human: (v) => {
          app.out.success(`Proposed ${set.name}, version ${v.version}, for review.`);
          app.out.note(
            `To activate it, review it and confirm yourself, at your own terminal: \`salli tax rules activate ${set.id.slice(0, 8)}\`.`,
          );
        },
      });
    });

  rules
    .command('diff')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('What changed between two versions, with the source behind each change')
    .option('--from <n|id>', 'Compare from this version (default: the active one)')
    .option('--to <n|id>', 'Compare to this version (default: the newest)')
    .action(async (query, opts) => {
      const api = await app.api();
      const set = await loadSet(api, query);
      const to = opts.to !== undefined ? resolveVersion(set, opts.to) : newest(set);
      const from = opts.from !== undefined ? resolveVersion(set, opts.from) : undefined;
      const diff = await api.call(taxRuleSetsDiff, {
        path: { rule_set_id: set.id },
        query: { to: to.id, ...(from ? { from: from.id } : {}) },
      });
      app.out.emit(diff, { records: (d) => d.changes, human: (d) => renderDiff(app, set, d) });
    });

  rules
    .command('evaluate')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('Apply a version to your ledger, line by line (nothing is stored)')
    .option('--version <n|id>', 'The version (default: the newest)')
    .option('--answer <key=value>', 'Answer one of its questions (repeatable)', collect)
    .option('--year <label>', 'Refuse unless the rules are for this year')
    .action(async (query, opts) => {
      const answers = answersArg(opts.answer ?? []);
      const api = await app.api();
      const set = await loadSet(api, query);
      const version = chosen(app, set, opts.version);
      const evaluation = await api.call(taxRuleSetsVersionsEvaluate, {
        path: versionPath(set, version),
        body: { answers, ...(opts.year ? { year: opts.year } : {}) },
      });
      app.out.emit(evaluation, { records: (e) => e.lines, human: (e) => renderEvaluation(app, e) });
    });

  rules
    .command('activate')
    .argument('<set>', 'Rule set id (or its start) or name')
    .description('Review a version and make it the rules Salli computes with (you, at a terminal)')
    .option('--version <n|id>', 'The version (default: the newest proposed one)')
    .addHelpText(
      'after',
      `
Shows the changes against the active version with the source of each changed
figure, every worked example, who wrote the version and why, then asks you to
type its number. There is no --yes, and it refuses to run when stdin or stdout
isn't a terminal, or with --json or --output: an AI agent can't activate.`,
    )
    .action(async (query, opts) => {
      refuseUnlessAPersonIsHere(app);
      const api = await app.api();
      const set = await loadSet(api, query);
      const version = opts.version !== undefined ? resolveVersion(set, opts.version) : newestProposed(set);
      if (version.status === 'active') {
        app.out.success(`${set.name}, version ${version.version}, is already active.`);
        return;
      }
      if (version.status === 'superseded') {
        throw new CliError(`${set.name}, version ${version.version}, was superseded and can't be activated again.`, {
          exitCode: ExitCode.USAGE,
          kind: 'rule-set-state',
          hint: 'To use these rules again, export it and add the export as a new version.',
        });
      }
      const diff = await api.call(taxRuleSetsDiff, { path: { rule_set_id: set.id }, query: { to: version.id } });
      renderReview(app, set, version, diff);
      if (!diff.validation_ok) {
        throw new CliError(`Version ${version.version} can't be activated: it doesn't pass validation.`, {
          exitCode: ExitCode.ERROR,
          kind: 'invalid-rule-set',
          hint: `See \`salli tax rules validate ${set.id.slice(0, 8)} --version ${version.version}\`.`,
        });
      }
      app.out.line();
      const typed = await app.prompter.text({
        message: `Type ${version.version} to activate version ${version.version} of ${set.name}, or anything else to cancel`,
      });
      if (typed.trim() !== String(version.version)) {
        throw new CliError(`Not activated: you typed “${truncate(singleLine(typed), 20)}”, not ${version.version}.`, {
          exitCode: ExitCode.ERROR,
          kind: 'not-confirmed',
        });
      }
      let activated: TaxRuleSetVersion;
      try {
        activated = await api.call(taxRuleSetsVersionsActivate, { path: versionPath(set, version) });
      } catch (error) {
        if (error instanceof SalliApiError && error.status === 403) throw await explainForbidden(app, error);
        throw error;
      }
      app.out.success(`${set.name}, version ${activated.version}, is active: Salli computes your ${set.name} tax with it.`);
    });
}
