/**
 * salli whatif | salli compare
 *
 * The decision lab's scenarios: the baseline plus changes, run by the server
 * (POST /v1/scenarios/run) or compared side by side (POST
 * /v1/scenarios/compare). Every figure is the server's, as baseline,
 * scenario and change; the CLI builds the scenario document from flags or
 * reads it from a file, and never does arithmetic on money. Salli never
 * ranks options, and neither does this command.
 */
import { readFile, stat, writeFile } from 'node:fs/promises';
import { basename, extname } from 'node:path';
import type { Command } from '@commander-js/extra-typings';
import {
  debtsList,
  insightsRecurring,
  scenariosCompare,
  scenariosRun,
  type ExtraDebtPaymentChange,
  type Scenario,
  type ScenarioComparison,
  type ScenarioRun,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { NotFoundError, UsageError } from '../errors';
import type { Output } from '../output/output';
import { plural, singleLine } from '../output/text';
import { displayDate, displayMonth, isoDate, parseDate } from '../util/dates';
import { readAllStdin } from '../util/stdin';
import { resolveById } from '../util/resolve';
import { AccountBook, amountArg, collect, countArg, rateArg } from './shared';

type Change = NonNullable<Scenario['changes']>[number];
type AmountFigure = ScenarioRun['cash']['lowest'];
type MonthFigure = ScenarioRun['fi']['fi_month'];

/** The most a scenario file may be (the server reads far less). */
const MAX_SCENARIO_BYTES = 256 * 1024;

const CADENCES: Record<string, 'weekly' | 'monthly' | 'quarterly' | 'yearly'> = {
  week: 'weekly',
  weekly: 'weekly',
  month: 'monthly',
  monthly: 'monthly',
  quarter: 'quarterly',
  quarterly: 'quarterly',
  year: 'yearly',
  yearly: 'yearly',
  annual: 'yearly',
  annually: 'yearly',
};

const UNIT: Record<string, string> = { weekly: 'week', monthly: 'month', quarterly: 'quarter', yearly: 'year' };

// ── Reading the flags ─────────────────────────────────────────────────────────

/** `VALUE@DATE` split at its last @ when what follows is a date, else the whole value. */
export function splitAt(value: string, now: Date, flag: string): { head: string; date: string | undefined } {
  const at = value.lastIndexOf('@');
  if (at <= 0) return { head: value.trim(), date: undefined };
  const tail = value.slice(at + 1).trim();
  if (!/^(\d{4}-\d{2}-\d{2}|today|tomorrow)$/i.test(tail)) return { head: value.trim(), date: undefined };
  return { head: value.slice(0, at).trim(), date: parseDate(tail, now, flag) };
}

/** A positive amount someone typed (no sign). */
function priceArg(text: string, flag: string): string {
  const amount = amountArg(text, flag);
  if (amount.startsWith('-') || /^0*(\.0*)?$/.test(amount)) {
    throw new UsageError(`${flag} takes an amount above zero, like 2400 (got "${text}").`);
  }
  return amount;
}

/** `AMOUNT/CADENCE`: a signed amount and how often. */
export function amountPerArg(text: string, flag: string): { amount: string; cadence: 'weekly' | 'monthly' | 'quarterly' | 'yearly' } {
  const slash = text.lastIndexOf('/');
  if (slash <= 0) throw new UsageError(`${flag} takes AMOUNT/PERIOD, like -450/month (got "${text}").`);
  const cadence = CADENCES[text.slice(slash + 1).trim().toLowerCase()];
  if (!cadence) throw new UsageError(`${flag}: the period is week, month, quarter or year (got "${text.slice(slash + 1)}").`);
  return { amount: amountArg(text.slice(0, slash), flag), cadence };
}

/** `--buy 2400[@2026-11-01]`: money out once. */
export function buyArg(value: string, day: string, now: Date, account?: string): Change {
  const { head, date } = splitAt(value, now, '--buy');
  const price = priceArg(head, '--buy');
  return { type: 'one_off', date: date ?? day, amount: `-${price}`, ...(account ? { account } : {}), label: `Buy ${price}` };
}

/** `--loan 18000@6.9%x48[@2026-12-01]`: borrowed, repaid monthly over the term. */
export function loanArg(value: string, day: string, now: Date, account?: string): Change {
  const { head, date } = splitAt(value, now, '--loan');
  const match = /^([^@]+)@([^xX]+)[xX](\d+)$/.exec(head);
  if (!match) throw new UsageError(`--loan takes AMOUNT@RATExMONTHS, like 18000@6.9%x48 (got "${value}").`);
  const [, principalText = '', rateText = '', monthsText = ''] = match;
  const principal = priceArg(principalText, '--loan');
  const rate = rateArg(rateText, '--loan');
  const months = countArg('--loan')(monthsText);
  return {
    type: 'loan',
    principal,
    annual_rate: rate,
    term_months: months,
    start: date ?? day,
    ...(account ? { into: account } : {}),
    label: `Loan of ${principal}`,
  };
}

/** `--recurring -450/month[@2027-01-01]`: the same amount again and again. */
export function recurringArg(value: string, day: string, now: Date, account?: string): Change {
  const { head, date } = splitAt(value, now, '--recurring');
  const { amount, cadence } = amountPerArg(head, '--recurring');
  return {
    type: 'recurring',
    amount,
    cadence,
    start: date ?? day,
    ...(account ? { account } : {}),
    label: `${amount} a ${UNIT[cadence]}`,
  };
}

/** `--income +600/month[@2027-01-01]`: monthly net income changes. */
export function incomeArg(value: string, day: string, now: Date): Change {
  const { head, date } = splitAt(value, now, '--income');
  const { amount, cadence } = amountPerArg(head, '--income');
  if (cadence !== 'monthly') throw new UsageError(`--income is a change a month, like +600/month (got "${value}").`);
  return { type: 'income_change', monthly_net: amount, from: date ?? day, label: `Income ${amount.startsWith('-') ? amount : `+${amount}`} a month` };
}

/** `--extra-payment DEBT:200/month[@2026-11-01]`: on top of a debt's minimum. */
export function extraArg(value: string, day: string, now: Date): { debt: string; change: Omit<ExtraDebtPaymentChange, 'debt'> } {
  const { head, date } = splitAt(value, now, '--extra-payment');
  const colon = head.lastIndexOf(':');
  if (colon <= 0) throw new UsageError(`--extra-payment takes DEBT:AMOUNT/month, like "car loan:200/month" (got "${value}").`);
  const per = head.slice(colon + 1);
  const amountText = per.includes('/') ? per : `${per}/month`;
  const { amount, cadence } = amountPerArg(amountText, '--extra-payment');
  if (cadence !== 'monthly' || amount.startsWith('-')) {
    throw new UsageError(`--extra-payment is an amount above zero a month, like 200/month (got "${value}").`);
  }
  return { debt: head.slice(0, colon).trim(), change: { type: 'extra_debt_payment', monthly: amount, from: date ?? day } };
}

/** `--invest 5000[@2026-12-15]`: cash into your investments. */
export function investArg(value: string, day: string, now: Date, account?: string): Change {
  const { head, date } = splitAt(value, now, '--invest');
  const amount = priceArg(head, '--invest');
  return { type: 'invest', amount, date: date ?? day, ...(account ? { from: account } : {}), label: `Invest ${amount}` };
}

/** Reads a scenario document: a file, or stdin for "-". */
export async function readScenario(app: App, path: string): Promise<Record<string, unknown>> {
  let text: string;
  if (path === '-') {
    text = await readAllStdin(app.runtime.stdin);
  } else {
    let info;
    try {
      info = await stat(path);
    } catch {
      throw new UsageError(`No such file: ${path}`);
    }
    if (!info.isFile()) throw new UsageError(`Not a file: ${path}`);
    if (info.size > MAX_SCENARIO_BYTES) throw new UsageError(`${path} is larger than a scenario may be (256 KiB).`);
    text = await readFile(path, 'utf8');
  }
  let doc: unknown;
  try {
    doc = JSON.parse(text);
  } catch {
    throw new UsageError(`${path === '-' ? 'stdin' : path} is not JSON.`, 'A scenario is a JSON document: see `salli whatif --help`.');
  }
  if (typeof doc !== 'object' || doc === null || Array.isArray(doc)) {
    throw new UsageError(`${path === '-' ? 'stdin' : path} is not a scenario: a JSON object with "schema": "salli.scenario/1".`);
  }
  return doc as Record<string, unknown>;
}

// ── Showing a result ──────────────────────────────────────────────────────────

/** A change with its sign: "+120.00", "-2,400.00", "0.00". */
function change(out: Output, delta: string | null | undefined, currency: string): string {
  if (delta === null || delta === undefined) return '—';
  const text = out.amount(delta, currency);
  return /^-/.test(delta) || /^0*(\.0*)?$/.test(delta.replace(/^-/, '')) ? text : `+${text}`;
}

function months(delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return '—';
  if (delta === 0) return 'same month';
  return `${plural(Math.abs(delta), 'month')} ${delta > 0 ? 'later' : 'sooner'}`;
}

function month(out: Output, value: string | null | undefined): string {
  return value ? displayMonth(value, out.locale) : 'not within 50 years';
}

interface FigureRow {
  label: string;
  baseline: string;
  scenario: string;
  change: string;
}

function amountRow(out: Output, label: string, f: AmountFigure, currency: string): FigureRow {
  return {
    label,
    baseline: f.baseline === null ? '—' : out.amount(f.baseline, currency),
    scenario: f.scenario === null ? '—' : out.amount(f.scenario, currency),
    change: change(out, f.delta, currency),
  };
}

function monthRow(out: Output, label: string, f: MonthFigure): FigureRow {
  return { label, baseline: month(out, f.baseline), scenario: month(out, f.scenario), change: months(f.delta_months) };
}

function figureTable(out: Output, rows: FigureRow[]): string {
  return out.table(rows, [
    { header: '', get: (r) => r.label, shrink: true },
    { header: 'BASELINE', get: (r) => r.baseline, align: 'right' },
    { header: 'SCENARIO', get: (r) => r.scenario, align: 'right' },
    { header: 'CHANGE', get: (r) => r.change, align: 'right' },
  ]);
}

function describeChange(out: Output, run: ScenarioRun, index: number): string {
  const doc = run.scenario.changes?.[index];
  const applied = run.changes[index];
  const cur = run.currency;
  if (!doc) return '';
  const on = (day: string) => displayDate(day, out.locale);
  switch (doc.type) {
    case 'one_off':
      return `${out.money(doc.amount, cur)} on ${on(doc.date)}`;
    case 'recurring':
      return `${out.money(doc.amount, cur)} a ${UNIT[doc.cadence]} from ${on(doc.start)}${doc.end ? ` to ${on(doc.end)}` : ''}`;
    case 'income_change':
      return `${out.money(doc.monthly_net, cur)} a month from ${on(doc.from)}${doc.to ? ` to ${on(doc.to)}` : ''}`;
    case 'loan':
      return `${out.money(doc.principal, cur)} at ${out.percent(doc.annual_rate, 2)} over ${plural(doc.term_months, 'month')}: ${out.money(applied?.payment, cur)} a month from ${month(out, applied?.first_payment)}`;
    case 'extra_debt_payment':
      return `${out.money(doc.monthly, cur)} a month from ${on(doc.from)}${doc.to ? ` to ${on(doc.to)}` : ''}`;
    case 'invest':
      return `${out.money(doc.amount, cur)} on ${on(doc.date)}`;
    case 'set_aside':
      return `${out.money(doc.monthly, cur)} a month kept in cash from ${on(doc.from)}${doc.to ? ` to ${on(doc.to)}` : ''}`;
    case 'stop_recurring': {
      const stopped = applied?.stopped.map((s) => `${singleLine(s.payee)} (${out.money(s.amount, s.currency)} ${s.cadence})`).join(', ');
      return `from ${on(doc.from)}${stopped ? `: ${stopped}` : ''}`;
    }
  }
}

function notesFor(app: App, run: ScenarioRun): void {
  const out = app.out;
  if (run.is_stale) {
    out.warn(`Your ledger's newest entry is from ${displayDate(run.data_as_of, out.locale)}: bring it up to date before deciding on these figures.`);
  }
  if (run.placeholders.length) {
    const names: Record<string, string> = {
      real_return: 'the real return',
      safe_withdrawal_rate: 'the safe withdrawal rate',
      surplus_invested: 'the share of your monthly surplus invested (all of it)',
      inflation: 'inflation (none set: nominal amounts keep their real value)',
    };
    out.note(`Placeholders: ${run.placeholders.map((p) => names[p] ?? p).join('; ')}. Set yours with \`salli fi assumptions set\`.`);
  }
  for (const note of run.notes) out.note(singleLine(note));
}

export function showRun(app: App, run: ScenarioRun): void {
  const out = app.out;
  const cur = run.currency;
  const c = out.colors;
  out.line(
    out.heading(`What if${run.label ? `: ${singleLine(run.label)}` : ''}`) +
      ` ${c.dim(`as of ${displayDate(run.as_of, out.locale)}, in ${cur}`)}`,
  );
  if (run.changes.length) {
    out.line();
    out.line(
      out.table(run.changes, [
        { header: '#', get: (ch) => ch.index + 1, align: 'right' },
        { header: 'CHANGE', get: (ch) => singleLine(ch.label), shrink: true },
        { header: 'WHAT', get: (ch) => describeChange(out, run, ch.index), shrink: true },
      ]),
    );
  }

  const cash = run.cash;
  const rows: FigureRow[] = [
    amountRow(out, 'Lowest cash', cash.lowest, cur),
    {
      label: 'Lowest on',
      baseline: displayDate(cash.lowest_date.baseline, out.locale),
      scenario: displayDate(cash.lowest_date.scenario, out.locale),
      change: cash.lowest_date.delta_days ? `${plural(Math.abs(cash.lowest_date.delta_days), 'day')} ${cash.lowest_date.delta_days > 0 ? 'later' : 'sooner'}` : 'same day',
    },
    amountRow(out, `Cash by ${displayDate(cash.end, out.locale)}`, cash.at_end, cur),
    amountRow(out, `Safe to spend until ${displayDate(cash.safe_until, out.locale)}`, cash.safe_to_spend, cur),
    ...cash.accounts.map((a) => amountRow(out, `${singleLine(a.name)} at its lowest`, a.lowest, a.currency)),
  ];
  const r = run.resilience;
  if (r.basis) {
    rows.push({
      label: `Emergency fund at the low (months of ${r.basis === 'essential' ? 'essential ' : ''}spending)`,
      baseline: out.decimal(r.lowest.baseline),
      scenario: out.decimal(r.lowest.scenario),
      change: r.lowest.delta === null ? '—' : /^-/.test(r.lowest.delta) ? out.decimal(r.lowest.delta) : `+${out.decimal(r.lowest.delta)}`,
    });
  }
  out.line();
  out.line(figureTable(out, rows));
  const below = cash.below_zero.scenario.filter((id) => !cash.below_zero.baseline.includes(id));
  for (const id of below) {
    const account = cash.accounts.find((a) => a.account_id === id);
    if (account) {
      out.warn(
        `${singleLine(account.name)} goes below zero: ${out.money(account.lowest.scenario, account.currency)} on ${displayDate(account.lowest_date.scenario, out.locale)}.`,
      );
    }
  }

  if (run.monthly.length) {
    out.line();
    out.line(
      out.table(run.monthly, [
        { header: 'IN', get: (p) => plural(p.years, 'year') },
        { header: 'MONTH', get: (p) => displayMonth(p.month, out.locale) },
        { header: `NET WORTH (${cur})`, get: (p) => out.amount(p.net_worth.scenario, cur), align: 'right' },
        { header: 'CHANGE', get: (p) => change(out, p.net_worth.delta, cur), align: 'right' },
        { header: 'CASH', get: (p) => change(out, p.cash.delta, cur), align: 'right' },
        { header: 'INVESTMENTS', get: (p) => change(out, p.investments.delta, cur), align: 'right' },
        { header: 'DEBTS', get: (p) => change(out, p.debts.delta, cur), align: 'right' },
      ]),
    );
    out.note('In today’s money. CASH, INVESTMENTS and DEBTS are the changes against the baseline.');
  }

  const debts = run.debts;
  const longRows: FigureRow[] = [
    ...debts.items.map((d) =>
      d.source === 'scenario'
        ? { ...monthRow(out, `${singleLine(d.name)} (new) paid off`, d.paid_off), baseline: '—', change: '—' }
        : monthRow(out, `${singleLine(d.name)} paid off`, d.paid_off),
    ),
    amountRow(out, 'Interest on debts', debts.total_interest, cur),
    monthRow(out, 'Debt-free', debts.debt_free),
    amountRow(out, 'FI number', run.fi.fi_number, cur),
    monthRow(out, 'Financially independent', run.fi.fi_month),
  ];
  out.line();
  out.line(figureTable(out, longRows));

  if (run.break_evens.length) {
    out.line();
    out.line(out.heading('Break-evens'));
    for (const b of run.break_evens) out.line(`  ${singleLine(b.says)}`);
  }
  notesFor(app, run);
}

// ── Comparing ─────────────────────────────────────────────────────────────────

const FIGURE_NAMES: Record<string, string> = {
  'cash.lowest': 'lowest cash',
  'cash.at_end': 'cash in a year',
  'cash.safe_to_spend': 'safe to spend',
  'resilience.lowest': 'emergency months at the low',
  'debts.total_interest': 'interest',
  'debts.debt_free': 'debt-free',
  'fi.fi_number': 'FI number',
  'fi.fi_month': 'FI',
};

function figureName(figure: string): string {
  const known = FIGURE_NAMES[figure];
  if (known) return known;
  const match = /^monthly\.(\d+)y\.(\w+)$/.exec(figure);
  if (!match) return figure;
  const [, years = '', what = ''] = match;
  // eslint-disable-next-line no-restricted-syntax -- not money: a number of years
  return `${what.replace('_', ' ')} in ${plural(Number(years), 'year')}`;
}

type Delta = ScenarioComparison['trade'][number]['gains'][number];

function deltaText(out: Output, d: Delta, currency: string): string {
  if (d.unit === 'month') {
    // eslint-disable-next-line no-restricted-syntax -- not money: a number of months
    const n = typeof d.delta === 'number' ? d.delta : d.delta === null ? null : Number(d.delta);
    return `${figureName(d.figure)} ${n === null ? `${month(out, d.this)} against ${month(out, d.other)}` : months(n)}`;
  }
  const value = typeof d.delta === 'string' ? d.delta : null;
  const shown = d.unit === 'months_of_spending' ? (value === null ? '—' : `${/^-/.test(value) ? '' : '+'}${out.decimal(value)}`) : change(out, value, currency);
  return `${figureName(d.figure)} ${shown}`;
}

export function showComparison(app: App, data: ScenarioComparison): void {
  const out = app.out;
  const cur = data.currency;
  const c = out.colors;
  const options = data.options;
  out.line(
    out.heading(`Comparing ${plural(options.length, 'option')}`) +
      ` ${c.dim(`as of ${displayDate(data.as_of, out.locale)}, in ${cur}, over ${plural(data.horizon_years, 'year')}`)}`,
  );

  type Row = { label: string; baseline: string; values: string[] };
  const first = options[0];
  if (!first) return;
  const rows: Row[] = [
    { label: 'Lowest cash', baseline: out.amount(first.cash.lowest.baseline, cur), values: options.map((o) => out.amount(o.cash.lowest.scenario, cur)) },
    { label: 'Lowest on', baseline: displayDate(first.cash.lowest_date.baseline, out.locale), values: options.map((o) => displayDate(o.cash.lowest_date.scenario, out.locale)) },
    { label: `Cash by ${displayDate(first.cash.end, out.locale)}`, baseline: out.amount(first.cash.at_end.baseline, cur), values: options.map((o) => out.amount(o.cash.at_end.scenario, cur)) },
    { label: 'Safe to spend', baseline: out.amount(first.cash.safe_to_spend.baseline, cur), values: options.map((o) => out.amount(o.cash.safe_to_spend.scenario, cur)) },
    ...(first.resilience.basis
      ? [{ label: 'Emergency months at the low', baseline: out.decimal(first.resilience.lowest.baseline), values: options.map((o) => out.decimal(o.resilience.lowest.scenario)) }]
      : []),
    ...first.monthly.map((p, i) => ({
      label: `Net worth in ${plural(p.years, 'year')}`,
      baseline: out.amount(p.net_worth.baseline, cur),
      values: options.map((o) => out.amount(o.monthly[i]?.net_worth.scenario, cur)),
    })),
    { label: 'Interest on debts', baseline: out.amount(first.debts.total_interest.baseline, cur), values: options.map((o) => out.amount(o.debts.total_interest.scenario, cur)) },
    { label: 'Debt-free', baseline: month(out, first.debts.debt_free.baseline), values: options.map((o) => month(out, o.debts.debt_free.scenario)) },
    { label: 'FI number', baseline: out.amount(first.fi.fi_number.baseline, cur), values: options.map((o) => out.amount(o.fi.fi_number.scenario, cur)) },
    { label: 'Financially independent', baseline: month(out, first.fi.fi_month.baseline), values: options.map((o) => month(out, o.fi.fi_month.scenario)) },
  ];
  out.line();
  out.line(
    out.table(rows, [
      { header: '', get: (r) => r.label, shrink: true },
      { header: 'BASELINE', get: (r) => r.baseline, align: 'right' },
      ...data.labels.map((label, i) => ({ header: singleLine(label).toUpperCase(), get: (r: Row) => r.values[i] ?? '—', align: 'right' as const })),
    ]),
  );

  out.line();
  out.line(out.heading('The trade'));
  for (const t of data.trade) {
    const a = data.labels.indexOf(t.option);
    const b = data.labels.indexOf(t.against);
    if (a > b) continue; // each pair once: the other way round is the same, mirrored
    out.line(`  ${singleLine(t.option)} against ${singleLine(t.against)}`);
    out.line(`    ahead on:  ${t.gains.length ? t.gains.map((d) => deltaText(out, d, cur)).join('; ') : 'nothing'}`);
    out.line(`    behind on: ${t.gives_up.length ? t.gives_up.map((d) => deltaText(out, d, cur)).join('; ') : 'nothing'}`);
  }

  const s = data.sensitivity;
  out.line();
  out.line(
    out.table(s.options, [
      { header: `AT ${data.horizon_years} YEARS`, get: (o) => singleLine(o.option), shrink: true },
      { header: `CONSERVATIVE (${out.percent(s.real_returns.conservative, 2)})`, get: (o) => `${out.amount(o.conservative.net_worth.scenario, cur)}  ${month(out, o.conservative.fi_month.scenario)}`, align: 'right' },
      { header: `BASE (${out.percent(s.real_returns.base, 2)})`, get: (o) => `${out.amount(o.base.net_worth.scenario, cur)}  ${month(out, o.base.fi_month.scenario)}`, align: 'right' },
      { header: `GROWTH (${out.percent(s.real_returns.growth, 2)})`, get: (o) => `${out.amount(o.growth.net_worth.scenario, cur)}  ${month(out, o.growth.fi_month.scenario)}`, align: 'right' },
    ]),
  );
  out.note('Net worth at the horizon and the FI month under each real return, in today’s money. Cash earns nothing, so only these move.');

  if (data.break_evens.length) {
    out.line();
    out.line(out.heading('Break-evens'));
    for (const b of data.break_evens) out.line(`  ${singleLine(b.says)}`);
  }
  out.note('Salli doesn’t rank options: what matters most is yours to weigh.');
  notesFor(app, first);
}

// ── The commands ──────────────────────────────────────────────────────────────

export function registerScenarios(program: Command, app: App): void {
  program
    .command('whatif')
    .alias('what-if')
    .description('What a change would do: every figure against your baseline (stores nothing)')
    .option('--buy <amount[@date]>', 'Buy something: money out once (repeatable)', collect)
    .option('--loan <amount@ratexmonths[@date]>', 'Borrow, repaid monthly: 18000@6.9%x48 (repeatable)', collect)
    .option('--recurring <amount/period[@date]>', 'The same amount again and again: -450/month, +80/week (repeatable)', collect)
    .option('--income <amount/month[@date]>', 'Your monthly net income changes: +600/month (repeatable)', collect)
    .option('--extra-payment <debt:amount/month[@date]>', 'Pay more on a debt each month: "car loan:200/month" (repeatable)', collect)
    .option('--invest <amount[@date]>', 'Move cash into your investments (repeatable)', collect)
    .option('--cancel <recurring[@date]>', 'Stop a recurring payment, by its key or payee (repeatable)', collect)
    .option('--account <account>', 'The cash account the changes move (default: your cash total)')
    .option('--years <n>', 'How far the monthly figures run (1 to 50, default 20)', countArg('--years'))
    .option('--as-of <date>', 'The day your baseline is as of (default today)')
    .option('--label <text>', 'What to call this scenario')
    .option('--file <path>', 'Run a scenario document instead of flags ("-" reads stdin)')
    .option('--save <path>', 'Also write the scenario the flags make, to reuse with `salli compare`')
    .addHelpText(
      'after',
      `
Dates default to the as-of date (today). Amounts are in your base currency,
as you would write them: 2400, 1234.50. A rate is 6.9% or 0.069.

The scenario is a document (salli.scenario/1): --save writes the one the
flags make, and --file runs one you wrote. Every figure is the server's,
under your baseline and under the scenario, with the change. Nothing is
stored.

Examples:
  $ salli whatif --buy 2400@2026-11-01
  $ salli whatif --loan 18000@6.9%x48 --buy 18000 --label "Car on finance"
  $ salli whatif --recurring -450/month@2027-01-01 --income +600/month@2027-01-01
  $ salli whatif --extra-payment "student loan:200/month" --years 10
  $ salli whatif --invest 5000 --account savings --save invest.json
  $ salli whatif --cancel streamflix
  $ salli whatif --file scenario.json --json`,
    )
    .action(async (options) => {
      const opts = {
        ...options,
        buy: options.buy ?? [],
        loan: options.loan ?? [],
        recurring: options.recurring ?? [],
        income: options.income ?? [],
        extraPayment: options.extraPayment ?? [],
        invest: options.invest ?? [],
        cancel: options.cancel ?? [],
      };
      const flagged =
        opts.buy.length + opts.loan.length + opts.recurring.length + opts.income.length + opts.extraPayment.length + opts.invest.length + opts.cancel.length;
      if (opts.file && flagged) throw new UsageError('Give changes as flags or as --file, not both.');
      if (opts.file && opts.save) throw new UsageError('--save writes the scenario the flags make; with --file you have it already.');
      const now = app.runtime.now();
      const asOf = opts.asOf ? parseDate(opts.asOf, now, '--as-of') : undefined;
      const api = await app.api();

      let doc: Record<string, unknown>;
      if (opts.file) {
        doc = await readScenario(app, opts.file);
        if (opts.years) doc.horizon_years = opts.years;
        if (asOf) doc.as_of = asOf;
        if (opts.label) doc.label = opts.label;
      } else {
        if (!flagged) {
          throw new UsageError('Say what changes: --buy, --loan, --recurring, --income, --extra-payment, --invest or --cancel.', 'Or run a scenario document with --file. See `salli whatif --help`.');
        }
        const day = asOf ?? isoDate(now);
        const account = opts.account ? (await AccountBook.load(api)).resolve(opts.account).id : undefined;
        const changes: Change[] = [
          ...opts.buy.map((v) => buyArg(v, day, now, account)),
          ...opts.loan.map((v) => loanArg(v, day, now, account)),
          ...opts.recurring.map((v) => recurringArg(v, day, now, account)),
          ...opts.income.map((v) => incomeArg(v, day, now)),
          ...opts.invest.map((v) => investArg(v, day, now, account)),
        ];
        if (opts.extraPayment.length) {
          const debts = (await api.call(debtsList, { query: { active_only: true } })).debts;
          for (const value of opts.extraPayment) {
            const { debt, change: extra } = extraArg(value, day, now);
            const lower = debt.toLowerCase();
            const found = debts.find((d) => d.name.toLowerCase() === lower) ?? resolveById(debts, debt, 'debt');
            changes.push({ ...extra, debt: found.id, label: `Extra on ${found.name}` });
          }
        }
        if (opts.cancel.length) {
          const recurring = (await api.call(insightsRecurring)).items;
          for (const value of opts.cancel) {
            const { head, date } = splitAt(value, now, '--cancel');
            const lower = head.toLowerCase();
            const found = recurring.find((r) => r.key === head) ?? recurring.find((r) => r.payee.toLowerCase() === lower);
            if (!found) {
              throw new NotFoundError(`No recurring payment "${head}".`, '`salli insights recurring` lists them, with their keys.');
            }
            changes.push({ type: 'stop_recurring', key: found.key, from: date ?? day, label: `Cancel ${found.payee}` });
          }
        }
        doc = {
          schema: 'salli.scenario/1',
          ...(opts.label ? { label: opts.label } : {}),
          ...(asOf ? { as_of: asOf } : {}),
          ...(opts.years ? { horizon_years: opts.years } : {}),
          changes,
        };
        if (opts.save) {
          await writeFile(opts.save, `${JSON.stringify(doc, null, 2)}\n`, 'utf8');
          app.out.note(`Saved the scenario to ${opts.save}.`);
        }
      }
      const run = await api.call(scenariosRun, { body: doc as unknown as Scenario });
      app.out.emit(run, { records: (d) => d.monthly, human: (d) => showRun(app, d) });
    });

  program
    .command('compare')
    .argument('<files...>', 'Two to five scenario documents ("-" reads one from stdin)')
    .description('Options side by side: the trade between them, sensitivity and break-evens (never a ranking)')
    .addHelpText(
      'after',
      `
Each file is a scenario (salli.scenario/1): write one, or make one with
\`salli whatif ... --save <file>\`. An option without a label is named after
its file. The options share one as-of date and one horizon.

Salli reports what each option gains and gives up against the others, the
same options under the conservative and growth real returns, and where the
answer changes (the break-evens). It never says which is best.

Examples:
  $ salli whatif --buy 2400 --save cash.json
  $ salli whatif --buy 2400 --loan 2400@6.9%x12 --label Instalments --save instalments.json
  $ salli compare cash.json instalments.json
  $ salli compare invest.json pay-down.json --json`,
    )
    .action(async (files) => {
      if (files.length < 2 || files.length > 5) throw new UsageError(`Compare 2 to 5 scenarios (got ${files.length}).`);
      if (files.filter((f) => f === '-').length > 1) throw new UsageError('Only one scenario can come from stdin.');
      const options: Record<string, unknown>[] = [];
      for (const file of files) {
        const doc = await readScenario(app, file);
        if (doc.label === undefined || doc.label === null) doc.label = file === '-' ? 'stdin' : basename(file, extname(file));
        options.push(doc);
      }
      const api = await app.api();
      const data = await api.call(scenariosCompare, { body: { options: options as unknown as Scenario[] } });
      app.out.emit(data, { records: (d) => d.options, human: (d) => showComparison(app, d) });
    });
}
