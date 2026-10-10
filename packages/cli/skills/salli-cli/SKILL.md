---
name: salli-cli
description: Operate the user's Salli (personal finance, tax, FIRE) through its `salli` command line. Use whenever the user asks about their accounts, spending, budgets, debts, investments, insurance, subscriptions, tax, net worth or financial independence, or asks you to record, import or change anything in their Salli ledger.
---

# Driving Salli from the command line

Salli keeps the user's money in a double-entry ledger and computes everything
derived from it — tax, budgets, FI score, reports — with deterministic engines.
You operate it through the `salli` command line, a client of the user's Salli
server.

## Ground rules

1. **Always pass `--json`.** stdout is then the API's JSON; progress and
   errors go to stderr. A non-zero exit code means the command failed: read
   stderr and tell the user, don't guess. Exit 3 means not signed in (the
   user runs `salli login`), 4 not found, 5 the server refused the request.
2. **Never compute money or tax yourself.** Every number you report comes from
   a `salli` command's output. If a figure isn't available from a command, say
   so instead of estimating it.
3. **Confirm before you write.** Before any command that adds, updates, posts,
   reverses or deletes, show the user exactly what will change (accounts,
   amounts, dates) and wait for a yes. Then pass `--yes` where the command
   asks for confirmation: there is no terminal for it to ask in. One command
   is the user's alone: `salli tax rules activate` has no `--yes` and refuses
   to run for you. Ask the user to run it themselves (see `salli-tax`).
4. **Posted entries are permanent.** Fix a wrong entry with
   `salli entries reverse <id> --yes` and then post the correct one. Never try
   to edit or delete a posted entry.
5. **Money is a string.** Amounts come back as strings like `"1500.00"`. Keep
   them as strings; pass amounts as plain numbers (`1500`, `1500.50`), no
   currency symbols.

## Running it

`salli` must be installed (`npm install --global @leafmonkeylabs/salli`) and
signed in (`salli whoami --json` says as whom, and to which server). If it is
not, ask the user to run `salli login` themselves: it opens a browser.

Accounts are named by code (`1000`), name (or any unique start of it) or id.
Other ids can be shortened to any unique prefix.

## What's where

| Command | For |
|---|---|
| `status` | net worth, this month, FI score and what is due, on one screen |
| `accounts` | chart of accounts: `list --balances`, `add`, `show <account>` (balance and history) |
| `add "<text>"` | an entry drafted by the AI from a sentence; `--dry-run` only shows the draft |
| `entries` | journal entries: `list`, `add`, `show <id>`, `reverse <id>`, `tag` |
| `import <file>`, `statements` | bank statements: import, then `statements pending`, `post`, `discard`, `categorize` |
| `ledger` | `trial-balance`, `income-statement` |
| `insights` | `cash-flow`, `spending`, `net-worth`, `recurring`, `forecast`, `safe-to-spend`, `signals` |
| `tax` | `year`, `compute`, `latest`, `packs`; `schema` (the rule-set JSON Schema) |
| `tax rules` | tax rule sets: `list`, `show <set> [--version]`, `create <file>`, `version <set> <file>`, `import <file\|url>`, `export`, `validate`, `propose`, `diff`, `evaluate`; `activate` is the user's, never yours |
| `budgets`, `debts`, `insurance`, `subscriptions` | each domain's records and reports |
| `holdings`, `portfolio` | holdings: `holdings list`, `holdings add`; `portfolio` (summary), `portfolio transactions add <holding> buy\|sell\|dividend\|…`, `portfolio lots <holding>`, `portfolio prices set <symbol> <close>`, `portfolio performance --from --to` |
| `fi`, `goals` | `fi score`, `history`, `projections`, `surplus`, `afford`, `strategy`; `goals list`, `goals allocate` |
| `reports` | `balance-sheet`, `net-worth`, `goal-progress`, `export` |
| `reminders` | `list`, `add`, `sync-alerts` |
| `advisor` | `run`, `latest`, `reports`, `apply`, `dismiss` |
| `profile` | the user's fact-find (`get`, `set`); `export` for all their data |
| `rules` | rules that book transactions that look a certain way; `suggest` |

`salli <command> --help` lists every subcommand and its options.

Related skills: `salli-record-transaction`, `salli-import-statement`,
`salli-monthly-review`, `salli-tax`.
