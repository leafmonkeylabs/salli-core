---
name: salli-cli
description: Operate a self-hosted Salli (personal finance, tax, FIRE) through its `salli` CLI. Use whenever the user asks about their accounts, spending, budgets, debts, investments, insurance, subscriptions, tax, net worth or financial independence, or asks you to record, import or change anything in their Salli ledger.
---

# Driving Salli from the command line

Salli keeps the user's money in a double-entry ledger and computes everything
derived from it — tax, budgets, FI score, reports — with deterministic engines.
You operate it through the `salli` CLI.

## Ground rules

1. **Always pass `--json`.** stdout is then one JSON document; progress and
   errors go to stderr. A non-zero exit code means the command failed — read
   stderr and tell the user, don't guess.
2. **Never compute money or tax yourself.** Every number you report comes from
   a `salli` command's output. If a figure isn't available from a command, say
   so instead of estimating it.
3. **Confirm before you write.** Before any command that adds, updates, posts,
   reverses or deletes, show the user exactly what will change (accounts,
   amounts, dates) and wait for a yes.
4. **Posted entries are permanent.** Fix a wrong entry with
   `salli entry reverse <id>` and then post the correct one. Never try to edit
   or delete a posted entry.
5. **Money is a string.** Amounts come back as strings like `"1500.00"`. Keep
   them as strings; pass amounts as plain numbers (`1500`, `1500.50`), no
   commas or currency symbols.

## Running it

From the Salli checkout: `uv run salli <group> <command> --json`. The CLI acts
as the user in `SALLI_USER_ID` (set by `salli setup`).

Ids in list output can be shortened to any unique prefix.

## What's where

| Group | For |
|---|---|
| `accounts` | chart of accounts: `list`, `add`, `show <id>` (balance + history) |
| `entry` | journal entries: `add`, `show <id>`, `reverse <id>`, `parse "<text>"` |
| `parse` | bank statements: `upload <file>`, `pending`, `post <ids...>` |
| `ledger` | `trial-balance`, `income-statement` |
| `tax` | `compute`, `latest`, `packs` |
| `budget`, `debt`, `portfolio`, `insurance`, `subscription` | each domain's records and reports |
| `fi` | `score`, `history`, `projections`, `surplus`, `goals …`, `strategy …` |
| `reports` | `balance-sheet`, `net-worth`, `goal-progress`, `export` |
| `reminders` | `list`, `add`, `sync-alerts` |
| `advisor` | `run`, `reports …` |
| `profile` | the user's fact-find; `export` for all their data |

`salli <group> --help` lists every command and its options.

Related skills: `salli-record-transaction`, `salli-import-statement`,
`salli-monthly-review`, `salli-tax`.
