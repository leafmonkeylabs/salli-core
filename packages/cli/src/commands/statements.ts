/**
 * salli import <file>, and salli statements list | pending | post | discard | categorize
 *
 * A statement is read on the server (CSV, OFX/QFX, QIF, camt.053, MT940,
 * PDF or Excel). Each transaction gets the other side from a rule or the
 * classifier and a duplicate check, and nothing reaches the ledger until it
 * is approved. The statement's own account (`--account`) is the money side
 * of every transaction; in review you choose where the money came from or
 * went, and that choice is sent to the server before posting.
 */
import { Option, type Command } from '@commander-js/extra-typings';
import {
  statementsCategorize,
  statementsDiscard,
  statementsList,
  statementsPending,
  statementsPost,
  statementsUpload,
  type BankStatement,
  type PostedStatementTransactions,
  type SalliClient,
  type StatementTransaction,
  type StatementUpload,
  type TransactionChoice,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { NotFoundError, UsageError } from '../errors';
import { plural, singleLine } from '../output/text';
import { displayDate, displayRange } from '../util/dates';
import { readUpload } from '../util/files';
import { resolveById } from '../util/resolve';
import { AccountBook, confirmAction, currencyArg, limitArg } from './shared';

type Transaction = StatementTransaction;

const MAX_BYTES = 10 * 1024 * 1024;
const NEEDS = ['essential', 'discretionary', 'savings'] as const;
const DATE_ORDERS = ['DMY', 'MDY', 'YMD'] as const;
/** The most choices one categorize request takes. */
const CHOICES_PER_REQUEST = 500;

/** Repeats an earlier import: never posted, never waits in review. */
const isDuplicate = (t: Transaction): boolean => t.dedup_status === 'exact_duplicate';
/** Already decided: posted or discarded. */
const isSettled = (t: Transaction): boolean => t.dedup_status === 'posted' || t.dedup_status === 'discarded';

/** The account the money moved in: the statement's own, or what the classifier said. */
const moneySide = (t: Transaction): string | null =>
  t.account_id ?? (t.credit_flag ? t.debit_account_id : t.credit_account_id);
/** Where the money came from (in) or went (out): what review chooses. */
const otherSide = (t: Transaction): string | null => (t.credit_flag ? t.credit_account_id : t.debit_account_id);

const isComplete = (t: Transaction): boolean => !!t.debit_account_id && !!t.credit_account_id;

/** Waiting for review, not a possible duplicate, and complete: safe to post unreviewed. */
const isClean = (t: Transaction): boolean =>
  !isDuplicate(t) && !isSettled(t) && t.dedup_status !== 'fuzzy_match' && isComplete(t);

const shownDescription = (t: Transaction): string => t.description_override || t.description;

function transactionTable(app: App, book: AccountBook, list: readonly Transaction[]): string {
  const c = app.out.colors;
  return app.out.table(list, [
    { header: 'DATE', get: (t) => displayDate(t.date, app.out.locale) },
    { header: 'DESCRIPTION', get: (t) => shownDescription(t), shrink: true },
    { header: 'AMOUNT', get: (t) => `${app.out.money(t.amount, t.currency)} ${t.credit_flag ? 'in' : 'out'}`, align: 'right' },
    { header: 'FROM', get: (t) => book.name(t.credit_account_id), shrink: true },
    { header: 'TO', get: (t) => book.name(t.debit_account_id), shrink: true },
    { header: 'SURE', get: (t) => (t.rule_id ? 'rule' : app.out.percent(t.confidence, 0)), align: 'right' },
    {
      header: 'CHECK',
      get: (t) =>
        isDuplicate(t)
          ? 'already imported'
          : t.dedup_status === 'fuzzy_match'
            ? 'maybe a duplicate'
            : isSettled(t)
              ? t.dedup_status
              : !isComplete(t)
                ? 'needs an account'
                : '',
      style: (s) => c.yellow(s),
    },
    { header: 'ID', get: (t) => t.id.slice(0, 8), style: (s) => c.dim(s) },
  ]);
}

/** Sends the accounts chosen in review: the other side of each transaction. */
async function categorize(api: SalliClient, choices: readonly TransactionChoice[]): Promise<string[]> {
  const updated: string[] = [];
  for (let i = 0; i < choices.length; i += CHOICES_PER_REQUEST) {
    const result = await api.call(statementsCategorize, { body: { choices: choices.slice(i, i + CHOICES_PER_REQUEST) } });
    updated.push(...result.updated);
  }
  return updated;
}

interface Decision {
  approved: Transaction[];
  /** The other side chosen in review, by transaction. */
  chosen: Map<Transaction, string>;
  discarded: Transaction[];
  skipped: Transaction[];
}

async function review(app: App, book: AccountBook, transactions: Transaction[]): Promise<Decision> {
  const out = app.out;
  const c = out.errColors;
  const decision: Decision = { approved: [], chosen: new Map(), discarded: [], skipped: [] };
  let approveRest = false;

  for (const [i, t] of transactions.entries()) {
    const position = c.dim(`[${i + 1}/${transactions.length}]`);
    if (isDuplicate(t) || isSettled(t)) {
      const why = isDuplicate(t) ? 'imported before, skipped' : `${t.dedup_status}, skipped`;
      out.info(`${position} ${displayDate(t.date, out.locale)} ${singleLine(shownDescription(t))} ${c.dim(`— ${why}`)}`);
      decision.skipped.push(t);
      continue;
    }
    if (approveRest) {
      if (isClean(t)) decision.approved.push(t);
      else decision.skipped.push(t);
      continue;
    }
    const money = moneySide(t);
    for (;;) {
      const other = decision.chosen.get(t) ?? otherSide(t);
      const [from, to] = t.credit_flag ? [other, money] : [money, other];
      out.info('');
      out.info(`${position} ${c.bold(displayDate(t.date, out.locale))}  ${c.bold(singleLine(shownDescription(t)))}`);
      if (t.description_override) out.info(c.dim(`      as the bank wrote it: ${singleLine(t.description)}`));
      out.info(
        `      ${out.money(t.amount, t.currency)} ${t.credit_flag ? 'in' : 'out'} · from ${book.name(from)} to ${book.name(to)}` +
          c.dim(` · ${decision.chosen.has(t) ? 'your choice' : t.rule_id ? 'by a rule' : `${out.percent(t.confidence, 0)} sure`}`),
      );
      if (t.dedup_status === 'fuzzy_match') out.warn('      This looks like something already in your ledger.');
      const complete = !!money && !!other;
      const choice = await app.prompter.select<string>({
        message: complete ? 'Post this one?' : 'It needs an account first',
        options: [
          ...(complete ? [{ value: 'approve', label: 'Approve' }] : []),
          ...(money ? [{ value: 'change', label: t.credit_flag ? 'Change where it came from' : 'Change where it went' }] : []),
          { value: 'skip', label: 'Skip (leave it pending)' },
          { value: 'discard', label: 'Discard (never post it)' },
          { value: 'rest', label: 'Approve this and every remaining clear one' },
          { value: 'stop', label: 'Stop reviewing (post what is approved so far)' },
        ],
        initialValue: complete ? 'approve' : money ? 'change' : 'skip',
      });
      if (choice === 'change') {
        const account = await app.prompter.search({
          message: t.credit_flag ? 'Where did it come from?' : 'Where did it go?',
          options: book.accounts
            .filter((a) => a.is_active && a.id !== money)
            .map((a) => ({ value: a.id, label: `${a.code} ${a.name}`, hint: a.type })),
          placeholder: 'Type to search',
        });
        decision.chosen.set(t, account);
        continue;
      }
      if (choice === 'approve') decision.approved.push(t);
      else if (choice === 'skip') decision.skipped.push(t);
      else if (choice === 'discard') decision.discarded.push(t);
      else if (choice === 'rest') {
        if (complete) decision.approved.push(t);
        else decision.skipped.push(t);
        approveRest = true;
      } else if (choice === 'stop') {
        decision.skipped.push(...transactions.slice(i));
        return decision;
      }
      if (!money && choice !== 'discard') {
        out.note('      This statement names no account: import it with --account to choose where its money went.');
      }
      break;
    }
  }
  return decision;
}

/** Statements, newest first. */
async function statementsOf(api: SalliClient): Promise<BankStatement[]> {
  return (await api.call(statementsList, { query: { limit: 200 } })).statements;
}

async function resolveStatement(api: SalliClient, query: string): Promise<BankStatement> {
  return resolveById(await statementsOf(api), query, 'statement');
}

/** Pending transactions: one statement's, or every statement's. */
async function pendingOf(api: SalliClient, statementId?: string): Promise<Transaction[]> {
  const ids = statementId ? [statementId] : (await statementsOf(api)).map((s) => s.id);
  const pending: Transaction[] = [];
  for (const id of ids) pending.push(...(await api.call(statementsPending, { path: { statement_id: id } })).transactions);
  return pending;
}

export function registerStatements(program: Command, app: App): void {
  program
    .command('import')
    .argument('<file>', 'A bank statement: CSV, OFX/QFX, QIF, camt.053, MT940, PDF or Excel')
    .description('Import a bank statement: review each transaction, then post the ones you approve')
    .option('--account <account>', 'The bank, cash or card account the statement is for (code, name or id)')
    .option('--currency <code>', 'The statement’s currency, for a file that names none')
    .option('--bank <name>', 'The bank, as a hint for reading the file')
    .addOption(new Option('--date-order <order>', 'How to read dates the file leaves ambiguous (01/02/2026)').choices(DATE_ORDERS))
    .option('--source-account <name>', 'For a file holding several accounts: which of the file’s accounts to import')
    .option('--replaces <statement>', 'An earlier import of this statement, imported again on purpose (its id)')
    .option('-y, --yes', 'Approve every transaction that is complete and not a possible duplicate, without asking')
    .option('--allow-possible-duplicates', 'With --yes, approve possible duplicates too')
    .addHelpText(
      'after',
      `
With --account, that account is the money side of every transaction, and
review chooses only where the money came from or went. Transactions imported
before are skipped. With --yes, possible duplicates (unless
--allow-possible-duplicates) and transactions without an account stay pending
for you to review later (salli statements pending).

Examples:
  $ salli import ~/Downloads/september.ofx --account checking
  $ salli import statement.csv --account "credit card" --date-order DMY --yes
  $ salli import september.csv --account checking --replaces 3fa85f64`,
    )
    .action(async (file, opts) => {
      const upload = await readUpload(file, MAX_BYTES);
      const api = await app.api();
      const book = await AccountBook.load(api);
      const account = opts.account ? book.resolve(opts.account) : undefined;
      const replaces = opts.replaces ? (await resolveStatement(api, opts.replaces)).id : undefined;
      const spinner = app.prompter.spinner();
      spinner.start(`Reading ${upload.name}`);
      let parsed: StatementUpload;
      try {
        parsed = await api.call(statementsUpload, {
          body: { file: upload },
          query: {
            ...(opts.bank ? { bank: opts.bank } : {}),
            ...(opts.currency ? { currency: currencyArg(opts.currency) } : {}),
            ...(account ? { account_id: account.id } : {}),
            ...(opts.sourceAccount ? { source_account: opts.sourceAccount } : {}),
            ...(replaces ? { replaces } : {}),
            ...(opts.dateOrder ? { date_order: opts.dateOrder } : {}),
          },
          timeoutMs: 5 * 60_000,
        });
      } finally {
        spinner.stop();
      }
      const out = app.out;
      const transactions = parsed.transactions;
      const period = parsed.period_start ? ` for ${displayRange(parsed.period_start, parsed.period_end, out.locale)}` : '';
      const into = account ? ` into ${singleLine(`${account.code} ${account.name}`)}` : '';
      out.info(`Read ${plural(transactions.length, 'transaction')} from ${singleLine(parsed.bank || upload.name)}${period}${into}.`);
      for (const problem of parsed.errors) out.warn(singleLine(String(problem)));
      if (!account && transactions.some((t) => !t.account_id)) {
        out.note('No --account: the classifier guessed both sides. Name the statement’s account to choose only where money went.');
      }

      let decision: Decision;
      if (opts.yes) {
        const approve = (t: Transaction): boolean =>
          isClean(t) || (opts.allowPossibleDuplicates === true && t.dedup_status === 'fuzzy_match' && isComplete(t));
        decision = { approved: transactions.filter(approve), chosen: new Map(), discarded: [], skipped: transactions.filter((t) => !approve(t)) };
      } else if (app.prompter.interactive) {
        decision = await review(app, book, transactions);
      } else {
        // No one to ask: leave everything pending, say how to finish.
        out.emit(parsed, {
          records: (u) => u.transactions,
          human: (u) => out.line(transactionTable(app, book, u.transactions)),
        });
        out.note(
          `Nothing posted. Review in a terminal with \`salli statements pending\`, or post with \`salli statements post ${parsed.statement_id.slice(0, 8)} --all --yes\`.`,
        );
        return;
      }

      // A choice for a transaction left pending is kept too, for when it is posted later.
      const choices: TransactionChoice[] = [...decision.chosen]
        .filter(([t]) => !decision.discarded.includes(t))
        .map(([t, account_id]) => ({ transaction_id: t.id, account_id }));
      const categorized = choices.length ? await categorize(api, choices) : [];
      const posted: PostedStatementTransactions = decision.approved.length
        ? await api.call(statementsPost, {
            path: { statement_id: parsed.statement_id },
            body: { approved_ids: decision.approved.map((t) => t.id) },
            timeoutMs: 120_000,
          })
        : { posted: 0, entry_ids: [] };
      const discarded = decision.discarded.length
        ? (
            await api.call(statementsDiscard, {
              path: { statement_id: parsed.statement_id },
              body: { ids: decision.discarded.map((t) => t.id) },
            })
          ).discarded
        : 0;
      out.emit(
        { upload: parsed, categorized, posted, discarded, skipped: decision.skipped.map((t) => t.id) },
        {
          human: () => {
            const duplicates = decision.skipped.filter(isDuplicate).length;
            const pending = decision.skipped.filter((t) => !isDuplicate(t) && !isSettled(t)).length;
            out.success(
              `Posted ${posted.posted} of ${transactions.length}` +
                (discarded ? `; ${discarded} discarded` : '') +
                (duplicates ? `; ${duplicates} imported before` : '') +
                (pending ? `; ${pending} left pending (salli statements pending)` : '') +
                '.',
            );
          },
        },
      );
    });

  const statements = program.command('statements').alias('statement').description('Imported bank statements and their pending transactions');

  statements
    .command('list')
    .alias('ls')
    .description('Statements you have imported, newest first')
    .option('--limit <n>', 'At most this many', limitArg)
    .action(async (opts) => {
      const api = await app.api();
      const [data, book] = await Promise.all([api.call(statementsList, { query: opts.limit ? { limit: opts.limit } : {} }), AccountBook.load(api)]);
      app.out.emit(data, {
        records: (d) => d.statements,
        human: (d) => {
          if (d.statements.length === 0) {
            app.out.note('No statements yet. Import one with `salli import <file>`.');
            return;
          }
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.statements, [
              { header: 'ID', get: (s) => s.id.slice(0, 8), style: (t) => c.dim(t) },
              { header: 'ACCOUNT', get: (s) => (s.account_id ? book.label(s.account_id) : ''), shrink: true },
              { header: 'BANK', get: (s) => s.bank ?? '', shrink: true },
              { header: 'PERIOD', get: (s) => (s.period_start ? displayRange(s.period_start, s.period_end, app.out.locale) : '') },
              { header: 'STATUS', get: (s) => s.status },
              { header: 'IMPORTED', get: (s) => displayDate(s.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  statements
    .command('pending')
    .argument('[statement]', 'A statement id (or its start); default: every statement')
    .description('Transactions read from statements but not posted or discarded yet')
    .action(async (query) => {
      const api = await app.api();
      const statement = query ? await resolveStatement(api, query) : undefined;
      const [transactions, book] = await Promise.all([pendingOf(api, statement?.id), AccountBook.load(api)]);
      app.out.emit(statement ? { statement_id: statement.id, transactions } : { transactions }, {
        records: (d) => d.transactions,
        human: () => {
          if (transactions.length === 0) {
            app.out.note('Nothing pending.');
            return;
          }
          app.out.line(transactionTable(app, book, transactions));
        },
      });
    });

  statements
    .command('post')
    .argument('<statement>', 'Statement id (or its start)')
    .argument('[transactions...]', 'Transaction ids (or their starts) to post')
    .description('Post pending transactions to the ledger')
    .option('--all', 'Every pending transaction that is complete and not a possible duplicate')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, ids, opts) => {
      if (!opts.all && ids.length === 0) throw new UsageError('Name the transactions to post, or pass --all.');
      if (opts.all && ids.length > 0) throw new UsageError('Pass transaction ids, or --all, not both.');
      const api = await app.api();
      const statement = await resolveStatement(api, query);
      const transactions = await pendingOf(api, statement.id);
      const chosen = opts.all ? transactions.filter(isClean) : ids.map((id) => resolveById(transactions, id, 'pending transaction'));
      if (chosen.length === 0) {
        app.out.note('Nothing to post.');
        return;
      }
      if (opts.all && !(await confirmAction(app, opts.yes, `Post ${plural(chosen.length, 'transaction')} to your ledger?`))) return;
      const result = await api.call(statementsPost, {
        path: { statement_id: statement.id },
        body: { approved_ids: chosen.map((t) => t.id) },
        timeoutMs: 120_000,
      });
      if (app.out.machine) app.out.emit(result, { human: () => undefined });
      else {
        app.out.success(`Posted ${plural(result.posted, 'transaction')}.`);
        if (result.posted < chosen.length) app.out.note(`${chosen.length - result.posted} were not posted: duplicates, or missing an account.`);
      }
    });

  statements
    .command('discard')
    .argument('<statement>', 'Statement id (or its start)')
    .argument('[transactions...]', 'Transaction ids (or their starts); default: every pending one')
    .description('Discard pending transactions: they are never posted and leave review')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (query, ids, opts) => {
      const api = await app.api();
      const statement = await resolveStatement(api, query);
      let chosen: string[] | undefined;
      if (ids.length) {
        const transactions = await pendingOf(api, statement.id);
        chosen = ids.map((id) => resolveById(transactions, id, 'pending transaction').id);
      } else if (!(await confirmAction(app, opts.yes, `Discard every pending transaction of statement ${statement.id.slice(0, 8)}?`))) {
        return;
      }
      const result = await api.call(statementsDiscard, { path: { statement_id: statement.id }, body: chosen ? { ids: chosen } : {} });
      app.out.done({ statement_id: statement.id, ...result }, `Discarded ${plural(result.discarded, 'transaction')}.`);
    });

  statements
    .command('categorize')
    .argument('<transaction>', 'A pending transaction id (or its start)')
    .argument('<account>', 'Where the money came from or went (code, name or id)')
    .description('Choose where a pending transaction goes before posting it')
    .option('--category <slug>', 'Tag it with this category')
    .addOption(new Option('--need <need>', 'Tag it with this need').choices(NEEDS))
    .action(async (query, accountQuery, opts) => {
      const api = await app.api();
      const [transactions, book] = await Promise.all([pendingOf(api), AccountBook.load(api)]);
      const transaction = resolveById(transactions, query, 'pending transaction');
      const account = book.resolve(accountQuery);
      if (account.id === moneySide(transaction)) {
        throw new UsageError(`${singleLine(account.name)} is the statement’s own account: choose where the money came from or went.`);
      }
      const choice: TransactionChoice = {
        transaction_id: transaction.id,
        account_id: account.id,
        ...(opts.category ? { category: opts.category } : {}),
        ...(opts.need ? { need: opts.need } : {}),
      };
      const updated = await categorize(api, [choice]);
      if (!updated.length) throw new NotFoundError('That transaction was not changed.');
      app.out.done(
        { updated },
        `“${singleLine(shownDescription(transaction))}” goes ${transaction.credit_flag ? 'from' : 'to'} ${singleLine(`${account.code} ${account.name}`)}. Post it with \`salli statements post\`.`,
      );
    });
}
