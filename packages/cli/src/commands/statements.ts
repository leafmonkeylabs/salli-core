/**
 * salli import <file>, and salli statements list | pending | post
 *
 * A statement is read on the server (PDF, Excel or CSV), each transaction
 * gets suggested accounts and a duplicate check, and nothing reaches the
 * ledger until it is approved.
 */
import type { Command } from '@commander-js/extra-typings';
import {
  entriesCreate,
  entriesList,
  entriesReverse,
  statementsList,
  statementsPending,
  statementsPost,
  statementsUpload,
  type PostedStatementTransactions,
  type SalliClient,
  type StatementTransaction,
  type StatementUpload,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { CliError, UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, displayRange } from '../util/dates';
import { readUpload } from '../util/files';
import { resolveById } from '../util/resolve';
import { AccountBook, confirmAction, currencyArg, limitArg } from './shared';

type Transaction = StatementTransaction;

/** The accounts chosen in review for a transaction, where they differ from the suggestion. */
interface AccountChoice {
  debit: string;
  credit: string;
}

const MAX_BYTES = 10 * 1024 * 1024;

const isDuplicate = (t: Transaction): boolean =>
  t.dedup_status === 'exact_duplicate' || t.dedup_status === 'confirmed_duplicate';

/**
 * Not a duplicate, not a possible one, and complete: safe to post unreviewed.
 * (The server says "pending" for a transaction that matched nothing, and may
 * say "unique".)
 */
const isClean = (t: Transaction): boolean =>
  !!t.id && !isDuplicate(t) && t.dedup_status !== 'fuzzy_match' && !!t.debit_account_id && !!t.credit_account_id;

/** What a statement transaction says, to recognise it in another listing. */
const contentOf = (t: Transaction): string =>
  JSON.stringify([t.date, t.description, t.amount, t.currency, t.credit_flag, t.bank_ref]);

/**
 * An upload's transactions, each with the id it is approved by.
 *
 * The server persists the transactions it read but answers the upload with
 * their ids empty; the statement's pending transactions carry them, so each
 * one is matched there by what it says. When the upload carries its ids,
 * it is returned as it is, and this goes away once every server does.
 */
async function withIds(app: App, api: SalliClient, upload: StatementUpload): Promise<Transaction[]> {
  if (upload.transactions.every((t) => t.id)) return upload.transactions;
  const { transactions: pending } = await api.call(statementsPending, { path: { statement_id: upload.statement_id } });
  const used = new Set<string>();
  const matched = upload.transactions.flatMap((t) => {
    if (t.id) return [t];
    const match = pending.find((p) => !used.has(p.id) && contentOf(p) === contentOf(t));
    if (!match) return [];
    used.add(match.id);
    return [{ ...t, id: match.id }];
  });
  const missing = upload.transactions.length - matched.length;
  if (missing) app.out.warn(`${missing} transaction${missing === 1 ? '' : 's'} could not be found to approve; see \`salli statements pending\`.`);
  return matched;
}

function transactionTable(app: App, book: AccountBook, list: readonly Transaction[]): string {
  const c = app.out.colors;
  return app.out.table(list, [
    { header: 'DATE', get: (t) => displayDate(t.date, app.out.locale) },
    { header: 'DESCRIPTION', get: (t) => t.description, shrink: true },
    { header: 'AMOUNT', get: (t) => `${app.out.money(t.amount, t.currency)} ${t.credit_flag ? 'in' : 'out'}`, align: 'right' },
    { header: 'FROM', get: (t) => book.name(t.credit_account_id), shrink: true },
    { header: 'TO', get: (t) => book.name(t.debit_account_id), shrink: true },
    { header: 'SURE', get: (t) => app.out.percent(t.confidence, 0), align: 'right' },
    {
      header: 'CHECK',
      get: (t) => (isDuplicate(t) ? 'duplicate' : t.dedup_status === 'fuzzy_match' ? 'maybe a duplicate' : !t.debit_account_id || !t.credit_account_id ? 'needs an account' : ''),
      style: (s) => c.yellow(s),
    },
    { header: 'ID', get: (t) => t.id.slice(0, 8), style: (s) => c.dim(s) },
  ]);
}

interface Correction {
  transaction_id: string;
  reversed_entry: string;
  entry: string;
}

/** Posts approved transactions, with the accounts chosen in review. */
async function postApproved(
  app: App,
  api: SalliClient,
  statementId: string,
  approved: readonly Transaction[],
  changed: ReadonlyMap<Transaction, AccountChoice>,
): Promise<{ result: PostedStatementTransactions; corrections: Correction[] }> {
  const result = await api.call(statementsPost, {
    path: { statement_id: statementId },
    body: { approved_ids: approved.map((t) => t.id) },
    timeoutMs: 120_000,
  });
  const corrections = await applyAccountChoices(
    app,
    api,
    approved.filter((t) => changed.has(t)),
    changed,
  );
  return { result, corrections };
}

/**
 * Gives posted statement transactions the accounts chosen in review.
 *
 * The statement API takes only the ids to post, so the entry it posts
 * carries the account it suggested; each changed one is reversed and
 * re-entered with the chosen accounts. When the API takes accounts per
 * transaction, they go in the post request instead and this goes away.
 */
async function applyAccountChoices(
  app: App,
  api: SalliClient,
  toCorrect: readonly Transaction[],
  changed: ReadonlyMap<Transaction, AccountChoice>,
): Promise<Correction[]> {
  const corrections: Correction[] = [];
  if (toCorrect.length === 0) return corrections;
  const dates = toCorrect.map((t) => t.date).sort();
  const entries = await api.call(entriesList, {
    query: { from_date: dates[0] as string, to_date: dates[dates.length - 1] as string },
  });
  for (const t of toCorrect) {
    const accounts = changed.get(t);
    if (!accounts) continue;
    const posted = entries.find((e) => e.external_ref === t.id && !e.reversed_by);
    if (!posted) {
      app.out.warn(`Could not find the entry for “${singleLine(t.description)}” to correct; check it with \`salli entries list\`.`);
      continue;
    }
    if (posted.postings.some((p) => p.direction > 0 && p.account_id === accounts.debit) && posted.postings.some((p) => p.direction < 0 && p.account_id === accounts.credit)) {
      continue; // the server already used the chosen accounts
    }
    const reversal = await api.call(entriesReverse, { path: { entry_id: posted.id } });
    try {
      const entry = await api.call(entriesCreate, {
        body: {
          entry_date: t.date,
          description: t.description,
          source: 'statement',
          external_ref: t.id,
          postings: [
            { account_id: accounts.debit, direction: 1, amount: t.amount, currency: t.currency },
            { account_id: accounts.credit, direction: -1, amount: t.amount, currency: t.currency },
          ],
        },
      });
      corrections.push({ transaction_id: t.id, reversed_entry: posted.id, entry: entry.id });
    } catch (error) {
      throw new CliError(
        `“${singleLine(t.description)}” was posted and reversed, but re-entering it with your accounts failed: ${(error as Error).message}`,
        { hint: `Add it with \`salli entries add\` (reversal ${reversal.id.slice(0, 8)} cancels the original).` },
      );
    }
  }
  return corrections;
}

async function review(
  app: App,
  book: AccountBook,
  transactions: Transaction[],
): Promise<{ approved: Transaction[]; changed: Map<Transaction, AccountChoice>; skipped: Transaction[] }> {
  const out = app.out;
  const c = out.errColors;
  const approved: Transaction[] = [];
  const skipped: Transaction[] = [];
  // Keyed by the transaction itself, so a choice can never land on another.
  const changed = new Map<Transaction, AccountChoice>();
  let approveRest = false;

  for (const [i, t] of transactions.entries()) {
    const position = c.dim(`[${i + 1}/${transactions.length}]`);
    if (isDuplicate(t)) {
      out.info(`${position} ${displayDate(t.date, out.locale)} ${singleLine(t.description)} ${c.dim('— already in your ledger, skipped')}`);
      skipped.push(t);
      continue;
    }
    if (approveRest) {
      if (isClean(t)) approved.push(t);
      else skipped.push(t);
      continue;
    }
    for (;;) {
      const accounts = changed.get(t) ?? { debit: t.debit_account_id ?? '', credit: t.credit_account_id ?? '' };
      out.info('');
      out.info(`${position} ${c.bold(displayDate(t.date, out.locale))}  ${c.bold(singleLine(t.description))}`);
      out.info(
        `      ${out.money(t.amount, t.currency)} ${t.credit_flag ? 'in' : 'out'} · from ${book.name(accounts.credit || null)} to ${book.name(accounts.debit || null)}` +
          c.dim(` · ${out.percent(t.confidence, 0)} sure${changed.has(t) ? ' · changed' : ''}`),
      );
      if (t.dedup_status === 'fuzzy_match') out.warn('      This looks like something already in your ledger.');
      const complete = !!accounts.debit && !!accounts.credit;
      const choice = await app.prompter.select<string>({
        message: complete ? 'Post this one?' : 'It needs an account first',
        options: [
          ...(complete ? [{ value: 'approve', label: 'Approve' }] : []),
          { value: 'skip', label: 'Skip (leave it pending)' },
          { value: 'change', label: 'Change an account' },
          { value: 'rest', label: 'Approve this and every remaining clear one' },
          { value: 'stop', label: 'Stop reviewing (post what is approved so far)' },
        ],
        initialValue: complete ? 'approve' : 'change',
      });
      if (choice === 'change') {
        const side = await app.prompter.select<'credit' | 'debit'>({
          message: 'Which side?',
          options: [
            { value: 'credit', label: `From: ${book.name(accounts.credit || null)}` },
            { value: 'debit', label: `To: ${book.name(accounts.debit || null)}` },
          ],
        });
        const account = await app.prompter.search({
          message: side === 'credit' ? 'Which account paid?' : 'Which account received it?',
          options: book.accounts.filter((a) => a.is_active).map((a) => ({ value: a.id, label: `${a.code} ${a.name}`, hint: a.type })),
          placeholder: 'Type to search',
        });
        changed.set(t, { ...accounts, [side]: account });
        continue;
      }
      if (choice === 'approve') approved.push(t);
      else if (choice === 'skip') skipped.push(t);
      else if (choice === 'rest') {
        if (complete) approved.push(t);
        approveRest = true;
      } else if (choice === 'stop') {
        skipped.push(...transactions.slice(i).filter((x) => !approved.includes(x)));
        return { approved, changed, skipped };
      }
      break;
    }
  }
  return { approved, changed, skipped };
}

export function registerStatements(program: Command, app: App): void {
  program
    .command('import')
    .argument('<file>', 'A bank statement: PDF, Excel (.xlsx/.xls) or CSV')
    .description('Import a bank statement: review each transaction, then post the ones you approve')
    .option('--currency <code>', 'The statement’s currency (default: your base currency)')
    .option('--bank <name>', 'The bank, as a hint for reading the file')
    .option('-y, --yes', 'Approve every transaction that is unique and complete, without asking')
    .option('--allow-possible-duplicates', 'With --yes, approve possible duplicates too (they need a person to check)')
    .addHelpText(
      'after',
      `
Duplicates of what is already in your ledger are skipped. With --yes,
possible duplicates (unless --allow-possible-duplicates) and transactions
without a suggested account stay pending for you to review later
(salli statements pending).

Examples:
  $ salli import ~/Downloads/september.pdf
  $ salli import statement.csv --currency EUR --yes`,
    )
    .action(async (file, opts) => {
      const upload = await readUpload(file, MAX_BYTES);
      const name = upload.name;
      const api = await app.api();
      const spinner = app.prompter.spinner();
      spinner.start(`Reading ${name}`);
      let parsed: StatementUpload;
      try {
        parsed = await api.call(statementsUpload, {
          body: { file: upload },
          query: { ...(opts.bank ? { bank: opts.bank } : {}), ...(opts.currency ? { currency: currencyArg(opts.currency) } : {}) },
          timeoutMs: 5 * 60_000,
        });
      } finally {
        spinner.stop();
      }
      const book = await AccountBook.load(api);
      const out = app.out;
      const read = parsed.transactions.length;
      const period = parsed.period_start ? ` for ${displayRange(parsed.period_start, parsed.period_end, out.locale)}` : '';
      out.info(`Read ${read} transaction${read === 1 ? '' : 's'} from ${singleLine(parsed.bank || name)}${period}.`);
      for (const problem of parsed.errors) out.warn(singleLine(String(problem)));
      const transactions = await withIds(app, api, parsed);

      let decision: { approved: Transaction[]; changed: Map<Transaction, AccountChoice>; skipped: Transaction[] };
      if (opts.yes) {
        const approve = (t: Transaction): boolean =>
          isClean(t) ||
          (opts.allowPossibleDuplicates === true && t.dedup_status === 'fuzzy_match' && !!t.debit_account_id && !!t.credit_account_id);
        decision = { approved: transactions.filter(approve), changed: new Map(), skipped: transactions.filter((t) => !approve(t)) };
      } else if (app.prompter.interactive) {
        decision = await review(app, book, transactions);
      } else {
        // No one to ask: leave everything pending, say how to finish.
        out.emit(parsed, {
          records: () => transactions,
          human: () => out.line(transactionTable(app, book, transactions)),
        });
        out.note(
          `Nothing posted. Review in a terminal with \`salli statements pending\`, or post with \`salli statements post ${parsed.statement_id.slice(0, 8)} --all --yes\`.`,
        );
        return;
      }

      const posted = decision.approved.length
        ? await postApproved(app, api, parsed.statement_id, decision.approved, decision.changed)
        : { result: { posted: 0, entry_ids: [] } satisfies PostedStatementTransactions, corrections: [] };
      const skipped = decision.skipped.map((t) => t.id);
      out.emit(
        { upload: parsed, posted: posted.result, corrections: posted.corrections, skipped },
        {
          human: () => {
            const duplicates = decision.skipped.filter(isDuplicate).length;
            const pending = decision.skipped.length - duplicates;
            out.success(
              `Posted ${posted.result.posted} of ${transactions.length}` +
                (duplicates ? `; ${duplicates} already in your ledger` : '') +
                (pending ? `; ${pending} left pending (salli statements pending)` : '') +
                '.',
            );
            if (posted.corrections.length) {
              out.note(
                `${posted.corrections.length} posted with the accounts you chose: the server records a statement transaction with the account it suggested, so each was corrected with a reversing entry and a new one.`,
              );
            }
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
      const data = await api.call(statementsList, { query: opts.limit ? { limit: opts.limit } : {} });
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
              { header: 'BANK', get: (s) => s.bank ?? '', shrink: true },
              { header: 'PERIOD', get: (s) => (s.period_start ? displayRange(s.period_start, s.period_end, app.out.locale) : '') },
              { header: 'STATUS', get: (s) => s.status },
              { header: 'IMPORTED', get: (s) => displayDate(s.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  async function pendingFor(api: SalliClient, statementId: string | undefined): Promise<{ statementIds: string[]; transactions: Transaction[] }> {
    let ids: string[];
    if (statementId) {
      const { statements: list } = await api.call(statementsList);
      ids = [statementId.length >= 32 ? statementId : resolveById(list, statementId, 'statement').id];
    } else {
      ids = (await api.call(statementsList)).statements.map((s) => s.id);
    }
    // Pending transactions are read per statement; the server today answers
    // with every pending transaction whichever statement is asked, so they
    // are merged by id.
    const seen = new Map<string, Transaction>();
    for (const id of ids) {
      const data = await api.call(statementsPending, { path: { statement_id: id } });
      for (const t of data.transactions) if (!seen.has(t.id)) seen.set(t.id, t);
    }
    return { statementIds: ids, transactions: [...seen.values()] };
  }

  statements
    .command('pending')
    .argument('[statement]', 'A statement id (or its start); default: all statements')
    .description('Transactions read from statements but not posted yet')
    .action(async (statementId) => {
      const api = await app.api();
      const [{ transactions }, book] = await Promise.all([pendingFor(api, statementId), AccountBook.load(api)]);
      app.out.emit(
        { transactions },
        {
          records: (d) => d.transactions,
          human: () => {
            if (transactions.length === 0) {
              app.out.note('Nothing pending.');
              return;
            }
            app.out.line(transactionTable(app, book, transactions));
          },
        },
      );
    });

  statements
    .command('post')
    .argument('<statement>', 'Statement id (or its start)')
    .argument('[transactions...]', 'Transaction ids (or their starts) to post')
    .description('Post pending transactions to the ledger')
    .option('--all', 'Every pending transaction that is unique and complete')
    .option('-y, --yes', 'Do not ask for confirmation')
    .action(async (statementId, ids, opts) => {
      if (!opts.all && ids.length === 0) throw new UsageError('Name the transactions to post, or pass --all.');
      if (opts.all && ids.length > 0) throw new UsageError('Pass transaction ids, or --all, not both.');
      const api = await app.api();
      const { statementIds, transactions } = await pendingFor(api, statementId);
      const chosen = opts.all ? transactions.filter(isClean) : ids.map((id) => resolveById(transactions, id, 'pending transaction'));
      if (chosen.length === 0) {
        app.out.note('Nothing to post.');
        return;
      }
      if (opts.all) {
        const ok = await confirmAction(app, opts.yes, `Post ${chosen.length} transaction${chosen.length === 1 ? '' : 's'} to your ledger?`);
        if (!ok) return;
      }
      const result = await api.call(statementsPost, {
        path: { statement_id: statementIds[0] as string },
        body: { approved_ids: chosen.map((t) => t.id) },
        timeoutMs: 120_000,
      });
      if (app.out.machine) app.out.emit(result, { human: () => undefined });
      else {
        app.out.success(`Posted ${result.posted} transaction${result.posted === 1 ? '' : 's'}.`);
        if (result.posted < chosen.length) app.out.note(`${chosen.length - result.posted} were not posted: duplicates, or missing an account.`);
      }
    });
}
