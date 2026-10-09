/**
 * salli rules list | add | show | update | delete | test | suggest
 *
 * Rules book imported transactions that look a certain way before any model
 * is asked: "when the description contains uber, it goes to Transport". They
 * are tried lowest priority number first, and the first that matches decides.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  rulesCreate,
  rulesDelete,
  rulesGet,
  rulesList,
  rulesSuggestions,
  rulesTest,
  rulesUpdate,
  type CategorizationRule,
  type RuleActions,
  type RuleCondition,
  type RuleDraft,
  type RuleUpdate,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { UsageError } from '../errors';
import { plural, singleLine } from '../output/text';
import { displayDate } from '../util/dates';
import { resolveById } from '../util/resolve';
import { AccountBook, amountArg, collect, confirmAction, countArg, currencyArg } from './shared';

const FIELDS = ['description', 'amount', 'direction', 'currency'] as const;
const OPERATORS = [
  'contains',
  'not_contains',
  'equals',
  'starts_with',
  'ends_with',
  'matches',
  'gt',
  'gte',
  'lt',
  'lte',
  'between',
] as const;
const NEEDS = ['essential', 'discretionary', 'savings'] as const;

const IF_HELP = 'A condition: FIELD OPERATOR VALUE, e.g. "description contains uber" (repeatable)';

const CONDITION_HELP = `
A condition is FIELD OPERATOR VALUE:
  description  contains, not_contains, equals, starts_with, ends_with, matches (a pattern)
  amount       equals, gt, gte, lt, lte, or between LOW HIGH
  direction    equals in | out
  currency     equals USD`;

const isOneOf = <T extends string>(values: readonly T[], value: string): value is T => (values as readonly string[]).includes(value);

/**
 * Splits a condition into words as a shell would: quotes group words, and a
 * backslash escapes a quote, a space or another backslash (and is kept
 * before anything else, so a pattern like \d+ needs no quoting).
 */
export function splitWords(text: string): string[] {
  const words: string[] = [];
  let word = '';
  let inWord = false;
  let quote: string | undefined;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text.charAt(i);
    const next = text.charAt(i + 1);
    if (quote) {
      if (ch === quote) quote = undefined;
      else if (ch === '\\' && quote === '"' && (next === '"' || next === '\\')) {
        word += next;
        i += 1;
      } else word += ch;
    } else if (ch === '"' || ch === "'") {
      quote = ch;
      inWord = true;
    } else if (ch === '\\' && next && /[\s"'\\]/.test(next)) {
      word += next;
      inWord = true;
      i += 1;
    } else if (/\s/.test(ch)) {
      if (inWord) words.push(word);
      word = '';
      inWord = false;
    } else {
      word += ch;
      inWord = true;
    }
  }
  if (quote) throw new UsageError(`A quote is not closed in "${text}".`);
  if (inWord) words.push(word);
  return words;
}

/** `--if "amount between 10 50"` as the API's condition. */
export function parseCondition(text: string): RuleCondition {
  const [rawField = '', rawOperator = '', ...rest] = splitWords(text);
  if (!rawField || !rawOperator || rest.length === 0) {
    throw new UsageError(`Not a condition: "${text}".`, 'Write FIELD OPERATOR VALUE, e.g. --if "description contains uber".');
  }
  const field = rawField.toLowerCase();
  if (!isOneOf(FIELDS, field)) throw new UsageError(`Unknown field "${rawField}" in "${text}".`, `Fields: ${FIELDS.join(', ')}`);
  const operator = rawOperator.toLowerCase();
  if (!isOneOf(OPERATORS, operator)) {
    throw new UsageError(`Unknown operator "${rawOperator}" in "${text}".`, `Operators: ${OPERATORS.join(', ')}`);
  }
  // The rest is the text, spaces and all: --if "description contains uber eats".
  if (field === 'description') return { field, operator, value: rest.join(' ') };
  const amount = (value: string): string => amountArg(value, 'An amount in --if');
  if (field === 'amount' && operator === 'between') {
    const [low, high] = rest;
    if (rest.length !== 2 || !low || !high) throw new UsageError(`"between" takes two amounts, e.g. --if "amount between 10 50" (got "${text}").`);
    return { field, operator, value: amount(low), value2: amount(high) };
  }
  const [value = ''] = rest;
  if (rest.length !== 1) throw new UsageError(`Too many words in "${text}".`, `Quote a value with spaces: --if "${field} ${operator} 'a b'".`);
  if (field === 'amount') return { field, operator, value: amount(value) };
  if (field === 'currency') return { field, operator, value: currencyArg(value) };
  return { field, operator, value: value.toLowerCase() };
}

function describeCondition(c: RuleCondition): string {
  const value = c.field === 'description' ? `“${c.value}”` : c.value;
  return `${c.field} ${c.operator.replace(/_/g, ' ')} ${value}${c.value2 ? ` and ${c.value2}` : ''}`;
}

function describeActions(actions: RuleActions, book: AccountBook): string {
  const parts: string[] = [];
  if (actions.account_id) parts.push(`book to ${book.label(actions.account_id)}`);
  if (actions.category) parts.push(`category ${actions.category}`);
  if (actions.need) parts.push(`need ${actions.need}`);
  if (actions.description) parts.push(`rename to “${actions.description}”`);
  return parts.join(', ') || 'nothing';
}

/** "when description contains “uber” → book to 5100 Transport". */
function describeRule(rule: Pick<RuleDraft, 'conditions' | 'actions' | 'match_all'>, book: AccountBook): string {
  const when = rule.conditions.map(describeCondition).join(rule.match_all === false ? ' or ' : ' and ');
  return singleLine(`when ${when} → ${describeActions(rule.actions, book)}`);
}

const shellQuote = (text: string): string => (/^[\w@%+=:,./-]+$/.test(text) ? text : `'${text.replace(/'/g, `'\\''`)}'`);
/** A word of a condition, quoted for `splitWords` when it needs to be. */
const conditionWord = (word: string): string => (/^[^\s"'\\]+$/.test(word) ? word : `"${word.replace(/["\\]/g, '\\$&')}"`);

/** The `salli rules add` command that would add a suggestion. */
function addCommand(rule: RuleDraft, book: AccountBook): string {
  const words = ['salli', 'rules', 'add', shellQuote(rule.name)];
  for (const c of rule.conditions) {
    const condition = [c.field, c.operator, c.value, ...(c.value2 ? [c.value2] : [])].map(conditionWord).join(' ');
    words.push('--if', shellQuote(condition));
  }
  if (rule.actions.account_id) words.push('--account', shellQuote(book.get(rule.actions.account_id)?.code ?? rule.actions.account_id));
  if (rule.actions.category) words.push('--category', shellQuote(rule.actions.category));
  if (rule.actions.need) words.push('--need', rule.actions.need);
  if (rule.actions.description) words.push('--rename', shellQuote(rule.actions.description));
  if (rule.match_all === false) words.push('--any');
  return singleLine(words.join(' '));
}

interface ActionFlags {
  account?: string;
  category?: string;
  need?: string;
  rename?: string;
}

async function actionsFrom(api: SalliClient, flags: ActionFlags): Promise<RuleActions> {
  const actions: RuleActions = {};
  if (flags.account) actions.account_id = (await AccountBook.load(api)).resolve(flags.account).id;
  if (flags.category) actions.category = flags.category.trim();
  if (flags.need && isOneOf(NEEDS, flags.need)) actions.need = flags.need;
  if (flags.rename) actions.description = flags.rename;
  return actions;
}

async function resolveRule(api: SalliClient, query: string): Promise<CategorizationRule> {
  return resolveById(await api.call(rulesList), query, 'rule');
}

const needOption = (description: string) => new Option('--need <need>', description).choices(NEEDS);

export function registerRules(program: Command, app: App): void {
  const rules = program
    .command('rules')
    .alias('rule')
    .description('Rules that book transactions that look a certain way, before any AI is asked')
    .addHelpText(
      'after',
      `
Rules are tried lowest priority number first; the first that matches decides.
${CONDITION_HELP}

Examples:
  $ salli rules test --if "description contains uber" --account transport
  $ salli rules add "Uber rides" --if "description contains uber" --account transport
  $ salli rules add "Small coffees" --if "description contains coffee" --if "amount lt 10" --category coffee
  $ salli rules suggest`,
    );

  rules
    .command('list')
    .alias('ls')
    .description('Your rules, in the order they are tried')
    .action(async () => {
      const api = await app.api();
      const [list, book] = await Promise.all([api.call(rulesList), AccountBook.load(api)]);
      app.out.emit(list, {
        human: (d) => {
          if (!d.length) return app.out.note('No rules yet. Add one with `salli rules add`, or see `salli rules suggest`.');
          const c = app.out.colors;
          app.out.line(
            app.out.table(d, [
              { header: 'ID', get: (r) => r.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'PRIORITY', get: (r) => r.priority ?? 100, align: 'right' },
              { header: 'NAME', get: (r) => r.name, shrink: true, style: (t, r) => (r.enabled === false ? c.dim(t) : t) },
              { header: 'RULE', get: (r) => describeRule(r, book), shrink: true },
              { header: 'ON', get: (r) => (r.enabled === false ? 'no' : 'yes') },
              { header: 'HITS', get: (r) => r.hits, align: 'right' },
            ]),
          );
        },
      });
    });

  rules
    .command('show')
    .argument('<rule>', 'Rule id (or its start)')
    .description('One rule in full')
    .action(async (query) => {
      const api = await app.api();
      const found = await resolveRule(api, query);
      const [rule, book] = await Promise.all([api.call(rulesGet, { path: { rule_id: found.id } }), AccountBook.load(api)]);
      app.out.emit(rule, {
        records: (r) => r.conditions,
        human: (r) => {
          const out = app.out;
          out.line(out.heading(r.name));
          out.line(
            out.details([
              ['When', r.conditions.map(describeCondition).join(r.match_all === false ? ' or ' : ' and ')],
              ['Then', describeActions(r.actions, book)],
              ['Priority', String(r.priority ?? 100)],
              ['On', r.enabled === false ? 'no' : 'yes', r.enabled === false ? out.colors.yellow : undefined],
              ['Hits', r.hits ? `${r.hits}${r.last_hit_at ? `, last on ${displayDate(r.last_hit_at, out.locale)}` : ''}` : 'none yet'],
              ['Created', displayDate(r.created_at, out.locale)],
              ['ID', r.id, out.colors.dim],
            ]),
          );
        },
      });
    });

  rules
    .command('add')
    .argument('<name>', 'What the rule is, e.g. "Uber rides"')
    .description('Add a rule (see what it would do first with `salli rules test`)')
    .requiredOption('--if <condition>', IF_HELP, collect)
    .option('--account <account>', 'Book the other side to this account (code, name or id)')
    .option('--category <slug>', 'Tag it with this category')
    .addOption(needOption('Tag it with this need'))
    .option('--rename <description>', 'Replace the bank’s description with this')
    .option('--priority <n>', 'Lower runs first (default 100)', countArg('--priority'))
    .option('--any', 'Match when any condition holds (default: all of them)')
    .addHelpText('after', CONDITION_HELP)
    .action(async (name, opts) => {
      const conditions = opts.if.map(parseCondition);
      if (!opts.account && !opts.category && !opts.need && !opts.rename) {
        throw new UsageError('A rule needs something to do.', 'Pass --account, --category, --need or --rename.');
      }
      const api = await app.api();
      const body: RuleDraft = {
        name,
        conditions,
        actions: await actionsFrom(api, opts),
        match_all: !opts.any,
        ...(opts.priority !== undefined ? { priority: opts.priority } : {}),
      };
      const created = await api.call(rulesCreate, { body });
      if (app.out.machine) app.out.emit(created, { human: () => undefined });
      else app.out.success(`Added the rule “${singleLine(name)}” ${app.out.errColors.dim(created.id)}`);
    });

  rules
    .command('update')
    .argument('<rule>', 'Rule id (or its start)')
    .description('Change a rule')
    .option('--name <name>', 'New name')
    .option('--if <condition>', `${IF_HELP}; replaces all of them`, collect)
    .option('--account <account>', 'Book to this account instead')
    .option('--category <slug>', 'Tag with this category instead')
    .addOption(needOption('Tag with this need instead'))
    .option('--rename <description>', 'Replace the description with this instead')
    .option('--priority <n>', 'New priority (lower runs first)', countArg('--priority'))
    .option('--any', 'Match when any condition holds')
    .option('--all', 'Match only when every condition holds')
    .option('--enabled', 'Turn it on')
    .option('--disabled', 'Turn it off (it stays, but decides nothing)')
    .action(async (query, opts) => {
      if (opts.any && opts.all) throw new UsageError('Pass --any or --all, not both.');
      if (opts.enabled && opts.disabled) throw new UsageError('Pass --enabled or --disabled, not both.');
      const conditions = opts.if?.map(parseCondition);
      const api = await app.api();
      const rule = await resolveRule(api, query);
      const body: RuleUpdate = {};
      if (opts.name !== undefined) body.name = opts.name;
      if (conditions) body.conditions = conditions;
      if (opts.priority !== undefined) body.priority = opts.priority;
      if (opts.any || opts.all) body.match_all = opts.all === true;
      if (opts.enabled || opts.disabled) body.enabled = opts.enabled === true;
      const changed = await actionsFrom(api, opts);
      // The API replaces the actions whole, so the ones not changed are sent as they are.
      if (Object.keys(changed).length) body.actions = { ...rule.actions, ...changed };
      if (!Object.keys(body).length) {
        throw new UsageError('Nothing to change.', 'Pass --name, --if, --account, --category, --need, --rename, --priority, --any, --all, --enabled or --disabled.');
      }
      const result = await api.call(rulesUpdate, { path: { rule_id: rule.id }, body });
      app.out.done(result, `Updated the rule “${singleLine(body.name ?? rule.name)}”.`);
    });

  rules
    .command('delete')
    .argument('<rule>', 'Rule id (or its start)')
    .description('Delete a rule (what it already booked stays booked)')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, opts) => {
      const api = await app.api();
      const rule = await resolveRule(api, query);
      if (!(await confirmAction(app, opts.yes, `Delete the rule “${singleLine(rule.name)}”?`))) return;
      await api.call(rulesDelete, { path: { rule_id: rule.id } });
      app.out.done({ id: rule.id, deleted: true }, `Deleted the rule “${singleLine(rule.name)}”.`);
    });

  rules
    .command('test')
    .description('What a rule would match among what you have already booked')
    .requiredOption('--if <condition>', IF_HELP, collect)
    .option('--account <account>', 'The account it would book to: says how many already went there')
    .option('--any', 'Match when any condition holds (default: all of them)')
    .addHelpText('after', CONDITION_HELP)
    .action(async (opts) => {
      const conditions = opts.if.map(parseCondition);
      const api = await app.api();
      const book = await AccountBook.load(api);
      const account = opts.account ? book.resolve(opts.account) : undefined;
      const result = await api.call(rulesTest, {
        body: {
          name: 'test',
          conditions,
          match_all: !opts.any,
          // A rule must do something; a test that names no account only renames.
          actions: account ? { account_id: account.id } : { description: '(test)' },
        },
      });
      app.out.emit(result, {
        records: (r) => r.matches,
        human: (r) => {
          const out = app.out;
          const c = out.colors;
          out.line(
            `Matches ${plural(r.total, 'booked transaction')}` +
              (account ? `; ${r.agreeing} of them already went to ${book.label(account.id)}` : '') +
              '.',
          );
          if (!r.matches.length) return;
          out.line();
          out.line(
            out.table(r.matches, [
              { header: 'DATE', get: (m) => displayDate(m.entry_date, out.locale) },
              { header: 'DESCRIPTION', get: (m) => m.description, shrink: true },
              { header: 'AMOUNT', get: (m) => `${out.money(m.amount, m.currency)} ${m.direction}`, align: 'right' },
              {
                header: 'BOOKED TO',
                get: (m) => book.label(m.account_id),
                shrink: true,
                style: (t, m) => (account && m.account_id !== account.id ? c.yellow(t) : t),
              },
              { header: 'ENTRY', get: (m) => m.entry_id.slice(0, 8), style: (t) => c.dim(t) },
            ]),
          );
          if (r.matches.length < r.total) out.note(`Showing ${r.matches.length} of ${r.total}.`);
        },
      });
    });

  rules
    .command('suggest')
    .description('Rules your own bookkeeping implies (nothing is added until you add it)')
    .action(async () => {
      const api = await app.api();
      const [found, book] = await Promise.all([api.call(rulesSuggestions), AccountBook.load(api)]);
      app.out.emit(found, {
        human: (d) => {
          const out = app.out;
          if (!d.length) return out.note('Nothing to suggest yet: book a few more transactions by hand.');
          for (const [i, s] of d.entries()) {
            if (i) out.line();
            const example = s.examples[0];
            out.line(
              `${out.colors.bold(singleLine(s.name))}  ${describeRule(s, book)}` +
                out.colors.dim(`  (${s.agreement} of ${s.support} agree${example ? `, e.g. “${singleLine(example)}”` : ''})`),
            );
            out.line(out.colors.dim(`  ${addCommand(s, book)}`));
          }
        },
      });
    });
}
