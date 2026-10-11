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
6. **Say when a figure rests on a placeholder.** FI figures are in real terms
   (today's money). Where the user has set no return, withdrawal rate or share
   of their surplus invested, a round placeholder stands in: when a result's
   `assumptions.status` is
   `"placeholder"`, tell the user, quoting `assumptions.message`, and offer to
   set their own (below). Salli knows no country's figures, and neither should
   you invent one.

## Planning assumptions

The user's own figures, each with where it comes from:

    salli fi assumptions --json                      # what applies; which are placeholders
    salli fi assumptions set real-return 5% --source "<url or publication>" --json
    salli fi assumptions set swr 3.5% --source "<…>" --json
    salli fi assumptions set inflation 3% --source "<…>" --json   # adds future-money figures
    salli fi assumptions set surplus-invested 80% --source "<what it rests on>" --json
    salli fi assumptions clear inflation --json

`real-return` is after inflation; or set `nominal-return` together with
`inflation`, not both. Research a figure from a citable source (a statistics
office or central bank for inflation, long-run studies for returns), show the
user the figure and its source, and set it only once they agree. Projections
show nominal (future-money) figures only once inflation is set.

`surplus-invested` is the share, from 0 to 100%, of each month's surplus the
user actually invests; the rest stays in cash, which earns nothing. The
placeholder assumes all of it. It is no rate to research: ask the user, or
show them their regular transfers to investment accounts
(`salli insights recurring`), and never guess. It moves the FI month and
every comparison of investing against paying down a debt.

## Decisions: what-ifs and options

When the user weighs a decision (can I afford it, cash or instalments, pay
down a debt or invest, a new flat or a new job), build each option as a
scenario and let Salli run it. Never subtract, add or project anything
yourself, and never say which option is best: Salli doesn't rank them, and
neither do you.

    salli whatif --buy 2400@2026-11-01 --json                  # a one-off purchase
    salli whatif --buy 18000 --loan 18000@6.9%x48 --json       # financed: price out, loan in
    salli whatif --recurring -450/month@2027-01-01 --json      # a new cost (or +80/week in)
    salli whatif --income +600/month@2027-01-01 --json         # a raise, or a cut (-)
    salli whatif --extra-payment "student loan:200/month" --json
    salli whatif --invest 5000 --account savings --json
    salli whatif --cancel <key> --json                         # keys: salli insights recurring
    salli whatif ... --label "Pay cash" --save cash.json       # keep it as a document
    salli compare cash.json instalments.json --json            # 2 to 5 options

A scenario is a JSON document (`salli.scenario/1`; amounts and rates as
decimal strings, dates YYYY-MM-DD), so you can also write one and run it with
`salli whatif --file <path>`. Every figure comes as `baseline`, `scenario`
and `delta`: the lowest cash in the next twelve months and when, accounts
going below zero, safe-to-spend, net worth, cash, investments and debts at 1,
5, 10 and 20 years in today's money, each debt's payoff and interest,
emergency-fund months, and the FI number and month (`fi.months_gained`).
`compare` adds `trade` (what each option gains and gives up against each
other), `sensitivity` (the same at the conservative and growth returns) and
`break_evens`, each with a sentence (`says`) saying where the answer changes:
quote it. If `is_stale` is true, ask the user to bring their ledger up to
date before deciding. Name the `placeholders` the figures rest on.

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
| `accounts` | chart of accounts: `list --balances`, `add`, `show <account>` (balance and history); `--asset-role cash\|investment\|other` says what an asset account holds |
| `add "<text>"` | an entry drafted by the AI from a sentence; `--dry-run` only shows the draft |
| `entries` | journal entries: `list`, `add`, `show <id>`, `reverse <id>`, `tag` |
| `import <file>`, `statements` | bank statements: import, then `statements pending`, `post`, `discard`, `categorize` |
| `ledger` | `trial-balance`, `income-statement` |
| `insights` | `cash-flow`, `spending`, `net-worth`, `recurring`, `forecast`, `safe-to-spend`, `signals` |
| `baseline` | the one model every figure comes from, as of a day (`--as-of`): months averaged, exchange rates and their source, account roles, debts, assumptions, and timelines to `--years` |
| `whatif`, `compare` | a scenario's figures against the baseline (from flags, or `--file`); two to five options side by side, with the trade, sensitivity and break-evens |
| `tax` | your tax from your own active rules: `year`, `compute`, `latest`, `explain <line>`; `return prepare`, `return review <thread>`; `schema` (the rule-set JSON Schema) |
| `tax rules` | tax rule sets: `list`, `show <set> [--version]`, `create <file>`, `version <set> <file>`, `import <file\|url>`, `export`, `validate`, `propose`, `diff`, `evaluate`, `accounts <set> [--apply]`; `activate` is the user's, never yours |
| `budgets`, `debts`, `insurance`, `subscriptions` | each domain's records and reports |
| `holdings`, `portfolio` | holdings: `holdings list`, `holdings add`; `portfolio` (summary), `portfolio transactions add <holding> buy\|sell\|dividend\|…`, `portfolio lots <holding>`, `portfolio prices set <symbol> <close>`, `portfolio performance --from --to` |
| `fi`, `goals` | `fi score`, `history`, `projections`, `surplus`, `strategy`, `assumptions` (`set`, `clear`); `goals list`, `goals allocate` |
| `reports` | `balance-sheet`, `net-worth`, `goal-progress`, `export` |
| `reminders` | `list`, `add`, `seed` (filing deadlines from the active tax rules), `sync-alerts` |
| `advisor` | `run`, `latest`, `reports`, `apply`, `dismiss` |
| `profile` | the user's fact-find (`get`, `set`); `export` for all their data |
| `rules` | rules that book transactions that look a certain way; `suggest` |

`salli <command> --help` lists every subcommand and its options.

Related skills: `salli-record-transaction`, `salli-import-statement`,
`salli-monthly-review`, `salli-tax`.
