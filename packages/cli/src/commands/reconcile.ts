/**
 * salli reconcile list | add | show | clear | complete: a bank statement's
 * closing balance against the postings cleared in the ledger.
 */
import type { Command } from "@commander-js/extra-typings";
import {
  reconciliationStatementsAdd,
  reconciliationStatementsClear,
  reconciliationStatementsComplete,
  reconciliationStatementsGet,
  reconciliationStatementsList,
  type ReconciliationStatus,
} from "@leafmonkeylabs/salli-sdk";
import type { App } from "../app";
import { singleLine } from "../output/text";
import { displayDate, displayRange, parseDate } from "../util/dates";
import { AccountBook, amountArg } from "./shared";

export function registerReconcile(program: Command, app: App): void {
  const reconcile = program
    .command("reconcile")
    .description("Reconcile your accounts with the bank’s statements");

  const show = (status: ReconciliationStatus): void => {
    const out = app.out;
    const c = out.colors;
    const cur = status.currency;
    out.line(
      `${out.heading(singleLine(status.account_name))} ${c.dim(`· ${displayRange(status.period_start, status.period_end, out.locale)} · ${cur}`)}`,
    );
    out.line(
      out.table(status.postings, [
        { header: "", get: (p) => (p.cleared ? "✓" : " ") },
        { header: "DATE", get: (p) => displayDate(p.entry_date, out.locale) },
        {
          header: "DESCRIPTION",
          get: (p) => singleLine(p.description),
          shrink: true,
        },
        {
          header: "AMOUNT",
          get: (p) => out.amount(p.amount, cur),
          align: "right",
        },
        {
          header: "ID",
          get: (p) => p.posting_id.slice(0, 8),
          style: (s) => c.dim(s),
        },
      ]),
    );
    out.line(
      `Opening ${out.amount(status.opening_balance, cur)} · cleared ${out.amount(status.cleared_total, cur)} · closing ${out.amount(status.closing_balance, cur)}`,
    );
    out.line(c.bold(`Difference ${out.amount(status.difference, cur)}`));
    if (status.reconciliation)
      out.success(
        `Reconciled by ${status.reconciliation.completed_by} on ${displayDate(status.reconciliation.completed_at.slice(0, 10), out.locale)}.`,
      );
  };

  /** A posting id, or the start of one, among the statement's. */
  const postingIds = (
    status: ReconciliationStatus,
    queries: readonly string[],
  ): string[] =>
    queries.map(
      (q) =>
        status.postings.find(
          (p) => p.posting_id === q || p.posting_id.startsWith(q),
        )?.posting_id ?? q,
    );

  reconcile
    .command("list", { isDefault: true })
    .description(
      "Statements with the bank’s balances, and whether each is reconciled",
    )
    .action(async () => {
      const api = await app.api();
      const data = await api.call(reconciliationStatementsList);
      app.out.emit(data, {
        records: (d) => d.statements,
        human: (d) => {
          if (!d.statements.length) {
            app.out.note(
              "No statements with balances yet. Import an MT940 or camt.053 file, or add one with `salli reconcile add`.",
            );
            return;
          }
          app.out.line(
            app.out.table(d.statements, [
              {
                header: "ACCOUNT",
                get: (s) => singleLine(s.account_name),
                shrink: true,
              },
              {
                header: "PERIOD",
                get: (s) =>
                  displayRange(s.period_start, s.period_end, app.out.locale),
              },
              {
                header: "CLOSING",
                get: (s) => app.out.amount(s.closing_balance, s.currency),
                align: "right",
              },
              {
                header: "STATUS",
                get: (s) => (s.reconciliation ? "reconciled" : "open"),
              },
              {
                header: "ID",
                get: (s) => s.statement_id.slice(0, 8),
                style: (t) => app.out.colors.dim(t),
              },
            ]),
          );
        },
      });
    });

  reconcile
    .command("add")
    .argument("<account>", "The bank or card account (code, name or id)")
    .description(
      "A statement typed in from the bank’s: its period and balances",
    )
    .requiredOption("--from <date>", "The first day it covers")
    .requiredOption("--to <date>", "The last day it covers")
    .requiredOption(
      "--opening <amount>",
      "Its opening balance (held, or owed on a card)",
    )
    .requiredOption("--closing <amount>", "Its closing balance")
    .option("--bank <name>", "The bank’s name")
    .action(async (accountQuery, opts) => {
      const now = app.runtime.now();
      const api = await app.api();
      const account = (await AccountBook.load(api)).resolve(accountQuery);
      const status = await api.call(reconciliationStatementsAdd, {
        body: {
          account_id: account.id,
          period_start: parseDate(opts.from, now, "--from"),
          period_end: parseDate(opts.to, now, "--to"),
          opening_balance: amountArg(opts.opening, "--opening"),
          closing_balance: amountArg(opts.closing, "--closing"),
          ...(opts.bank ? { bank: opts.bank } : {}),
        },
      });
      app.out.emit(status, { human: show });
    });

  reconcile
    .command("show")
    .argument("<statement>", "A statement id")
    .description("Its postings, the cleared total and the difference")
    .action(async (statementId) => {
      const api = await app.api();
      const status = await api.call(reconciliationStatementsGet, {
        path: { statement_id: statementId },
      });
      app.out.emit(status, { human: show });
    });

  reconcile
    .command("clear")
    .argument("<statement>", "A statement id")
    .argument(
      "<postings...>",
      "Posting ids (or their start) the statement shows",
    )
    .description("Mark postings cleared: matched to the statement’s lines")
    .option("--undo", "Mark them not cleared")
    .action(async (statementId, postings, opts) => {
      const api = await app.api();
      const before = await api.call(reconciliationStatementsGet, {
        path: { statement_id: statementId },
      });
      const status = await api.call(reconciliationStatementsClear, {
        path: { statement_id: statementId },
        body: {
          posting_ids: postingIds(before, postings),
          cleared: !opts.undo,
        },
      });
      app.out.emit(status, { human: show });
    });

  reconcile
    .command("complete")
    .argument("<statement>", "A statement id")
    .description("Record the reconciliation: only at a difference of zero")
    .action(async (statementId) => {
      const api = await app.api();
      const status = await api.call(reconciliationStatementsComplete, {
        path: { statement_id: statementId },
      });
      app.out.emit(status, { human: show });
    });
}
