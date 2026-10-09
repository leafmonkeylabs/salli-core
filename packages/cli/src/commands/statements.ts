/**
 * salli import <file>, and salli statements list | pending | post
 *
 * A statement is read on the server (PDF, Excel or CSV), each transaction
 * gets suggested accounts and a duplicate check, and nothing reaches the
 * ledger until it is approved.
 */
import { readFile, stat } from 'node:fs/promises';
import { basename, extname } from 'node:path';
import type { Command } from '@commander-js/extra-typings';
import {
  entriesCreate,
  entriesList,
  entriesReverse,
  statementsList,
  statementsPending,
  statementsPost,
  statementsUpload,
  type SalliClient,
} from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import type {
  EntryList,
  StatementList,
  StatementPending,
  StatementPost,
  StatementUpload,
  TodayStatementTransaction,
} from '../api-types';
import { CliError, UsageError } from '../errors';
import { singleLine } from '../output/text';
import { displayDate, displayRange } from '../util/dates';
import { resolveById } from '../util/resolve';
import { AccountBook, confirmAction, currencyArg, limitArg } from './shared';

type Transaction = TodayStatementTransaction & { id: string };

const MAX_BYTES = 10 * 1024 * 1024;

const MIME: Record<string, string> = {
  '.pdf': 'application/pdf',
  '.csv': 'text/csv',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.xls': 'application/vnd.ms-excel',
  '.txt': 'text/plain',
};

const isDuplicate = (t: TodayStatementTransaction): boolean =>
  t.dedup_status === 'exact_duplicate' || t.dedup_status === 'confirmed_duplicate';

/** Unique, complete, and not a possible duplicate: safe to post unreviewed. */
const isClean = (t: TodayStatementTransaction): boolean =>
  !!t.id && t.dedup_status === 'unique' && !!t.debit_account_id && !!t.credit_account_id;

function transactionTable(app: App, book: AccountBook, list: readonly TodayStatementTransaction[]): string {
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
    { header: 'ID', get: (t) => (t.id ?? '').slice(0, 8), style: (s) => c.dim(s) },
  ]);
}

interface Correction {
  transaction_id: string;
  reversed_entry: string;
  entry: string;
}

/**
 * Posts approved transactions. Ones whose accounts were changed in review
 * are posted too (so the server marks them done), then corrected: the
 * statement API takes only ids, so the entry it posts carries the suggested
 * account; it is reversed and re-entered with the chosen one.
 */
async function postApproved(
  app: App,
  api: SalliClient,
  statementId: string,
  approved: readonly Transaction[],
  changed: ReadonlyMap<string, { debit: string; credit: string }>,
): Promise<{ result: StatementPost; corrections: Correction[] }> {
  const result = (await api.call(statementsPost, {
    path: { statement_id: statementId },
    body: { approved_ids: approved.map((t) => t.id) },
    timeoutMs: 120_000,
  })) as StatementPost;
  const corrections: Correction[] = [];
  const toCorrect = approved.filter((t) => changed.has(t.id));
  if (toCorrect.length === 0) return { result, corrections };

  const dates = toCorrect.map((t) => t.date).sort();
  const entries = (await api.call(entriesList, {
    query: { from_date: dates[0] as string, to_date: dates[dates.length - 1] as string },
  })) as EntryList;
  for (const t of toCorrect) {
    const accounts = changed.get(t.id) as { debit: string; credit: string };
    const posted = entries.find((e) => e.external_ref === t.id && !e.reversed_by);
    if (!posted) {
      app.out.warn(`Could not find the entry for “${singleLine(t.description)}” to correct; check it with \`salli entries list\`.`);
      continue;
    }
    if (posted.postings.some((p) => p.direction > 0 && p.account_id === accounts.debit) && posted.postings.some((p) => p.direction < 0 && p.account_id === accounts.credit)) {
      continue; // the server already used the chosen accounts
    }
    const reversal = (await api.call(entriesReverse, { path: { entry_id: posted.id } })) as { id: string };
    try {
      const entry = (await api.call(entriesCreate, {
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
      })) as { id: string };
      corrections.push({ transaction_id: t.id, reversed_entry: posted.id, entry: entry.id });
    } catch (error) {
      throw new CliError(
        `“${t.description}” was posted and reversed, but re-entering it with your accounts failed: ${(error as Error).message}`,
        { hint: `Add it with \`salli entries add\` (reversal ${reversal.id.slice(0, 8)} cancels the original).` },
      );
    }
  }
  return { result, corrections };
}

async function review(
  app: App,
  book: AccountBook,
  transactions: Transaction[],
): Promise<{ approved: Transaction[]; changed: Map<string, { debit: string; credit: string }>; skipped: Transaction[] }> {
  const out = app.out;
  const c = out.errColors;
  const approved: Transaction[] = [];
  const skipped: Transaction[] = [];
  const changed = new Map<string, { debit: string; credit: string }>();
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
      const accounts = changed.get(t.id) ?? { debit: t.debit_account_id ?? '', credit: t.credit_account_id ?? '' };
      out.info('');
      out.info(`${position} ${c.bold(displayDate(t.date, out.locale))}  ${c.bold(singleLine(t.description))}`);
      out.info(
        `      ${out.money(t.amount, t.currency)} ${t.credit_flag ? 'in' : 'out'} · from ${book.name(accounts.credit || null)} to ${book.name(accounts.debit || null)}` +
          c.dim(` · ${out.percent(t.confidence, 0)} sure${changed.has(t.id) ? ' · changed' : ''}`),
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
        changed.set(t.id, { ...accounts, [side]: account });
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
    .addHelpText(
      'after',
      `
Duplicates of what is already in your ledger are skipped. With --yes,
possible duplicates and transactions without a suggested account stay
pending for you to review later (salli statements pending).

Examples:
  $ salli import ~/Downloads/september.pdf
  $ salli import statement.csv --currency EUR --yes`,
    )
    .action(async (file, opts) => {
      let info;
      try {
        info = await stat(file);
      } catch {
        throw new UsageError(`No such file: ${file}`);
      }
      if (!info.isFile()) throw new UsageError(`Not a file: ${file}`);
      if (info.size > MAX_BYTES) throw new UsageError(`${basename(file)} is larger than the server accepts (10 MB).`);
      const api = await app.api();
      const bytes = await readFile(file);
      const name = basename(file);
      const spinner = app.prompter.spinner();
      spinner.start(`Reading ${name}`);
      let upload: StatementUpload;
      try {
        upload = (await api.call(statementsUpload, {
          body: { file: new File([bytes], name, { type: MIME[extname(name).toLowerCase()] ?? 'application/octet-stream' }) },
          query: { ...(opts.bank ? { bank: opts.bank } : {}), ...(opts.currency ? { currency: currencyArg(opts.currency) } : {}) },
          timeoutMs: 5 * 60_000,
        })) as StatementUpload;
      } finally {
        spinner.stop();
      }
      const book = await AccountBook.load(api);
      const out = app.out;
      const transactions = upload.transactions.filter((t): t is Transaction => !!t.id);
      const period = upload.period_start ? ` for ${displayRange(upload.period_start, upload.period_end, out.locale)}` : '';
      out.info(`Read ${transactions.length} transaction${transactions.length === 1 ? '' : 's'} from ${singleLine(upload.bank || name)}${period}.`);
      for (const problem of upload.errors) out.warn(singleLine(String(problem)));

      let decision: { approved: Transaction[]; changed: Map<string, { debit: string; credit: string }>; skipped: Transaction[] };
      if (opts.yes) {
        decision = { approved: transactions.filter(isClean), changed: new Map(), skipped: transactions.filter((t) => !isClean(t)) };
      } else if (app.prompter.interactive) {
        decision = await review(app, book, transactions);
      } else {
        // No one to ask: leave everything pending, say how to finish.
        out.emit(upload, {
          records: (u) => u.transactions,
          human: (u) => out.line(transactionTable(app, book, u.transactions)),
        });
        out.note(
          `Nothing posted. Review in a terminal with \`salli statements pending\`, or post with \`salli statements post ${upload.statement_id.slice(0, 8)} --all --yes\`.`,
        );
        return;
      }

      const posted = decision.approved.length
        ? await postApproved(app, api, upload.statement_id, decision.approved, decision.changed)
        : { result: { posted: 0, entry_ids: [] } as StatementPost, corrections: [] };
      const skipped = decision.skipped.map((t) => t.id);
      out.emit(
        { upload, posted: posted.result, corrections: posted.corrections, skipped },
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
      const data = (await api.call(statementsList, { query: opts.limit ? { limit: opts.limit } : {} })) as StatementList;
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
              { header: 'STATUS', get: (s) => s.status ?? '' },
              { header: 'IMPORTED', get: (s) => displayDate(s.created_at, app.out.locale) },
            ]),
          );
        },
      });
    });

  async function pendingFor(api: SalliClient, statementId: string | undefined): Promise<{ statementIds: string[]; transactions: Transaction[] }> {
    let ids: string[];
    if (statementId) {
      const list = ((await api.call(statementsList)) as StatementList).statements;
      ids = [statementId.length >= 32 ? statementId : resolveById(list, statementId, 'statement').id];
    } else {
      ids = ((await api.call(statementsList)) as StatementList).statements.map((s) => s.id);
    }
    // Pending transactions are read per statement; the server today answers
    // with every pending transaction whichever statement is asked, so they
    // are merged by id.
    const seen = new Map<string, Transaction>();
    for (const id of ids) {
      const data = (await api.call(statementsPending, { path: { statement_id: id } })) as StatementPending;
      for (const t of data.transactions) if (t.id && !seen.has(t.id)) seen.set(t.id, t as Transaction);
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
      const result = (await api.call(statementsPost, {
        path: { statement_id: statementIds[0] as string },
        body: { approved_ids: chosen.map((t) => t.id) },
        timeoutMs: 120_000,
      })) as StatementPost;
      if (app.out.machine) app.out.emit(result, { human: () => undefined });
      else {
        app.out.success(`Posted ${result.posted} transaction${result.posted === 1 ? '' : 's'}.`);
        if (result.posted < chosen.length) app.out.note(`${chosen.length - result.posted} were not posted: duplicates, or missing an account.`);
      }
    });
}
