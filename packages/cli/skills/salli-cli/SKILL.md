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

## Decisions: templates, what-ifs and options

When the user weighs a decision (can I afford it, cash or instalments, pay
down a debt or invest, a windfall, a new flat or a new job, a loan, an
emergency fund), start from a template where one fits: Salli builds the
options from their answers, runs every one, compares them and checks their
principles.

    salli decide --list --json
    salli decide afford-it --questions --json      # the questions, types, and the user's defaults
    salli decide afford-it --set price=2400 --set instalment_months=12 \
      --set instalment_rate=6.9% --json            # or --answers answers.json
    salli decide emergency-fund --set target_months=6 --set set_aside=200,500 --json
    salli decide rent-or-buy --answers home.json --json  # price, deposit, mortgages, costs, rent

Ask the user each question in plain words. A question with a default
(`default.note` says where it comes from: their only debt, what it owes,
their principle's cash target, the date) may be left out; one without must
be answered by them: never invent a price, a rate or a target. Lists
(`loans`, `splits`) go in an `--answers` file. The result holds the
comparison (as `salli compare` gives it), their principles' checks, the
time to a cash target for an emergency fund (`cover`), and `record`: what
recording needs besides their own choice, reasons and review date.

Rent or buy asks for the price, the deposit, one to three mortgages, buying,
owning and selling costs (0 is an answer to each) and the rent (one of
their recurring payments, `rent`, or `rent_monthly`). Its two growths
beyond inflation (`rent_growth`, `home_growth`) default to 0 as a labelled
placeholder, not a forecast: ask for their own view, never supply one, and
quote the `asset_growth` break-even (the growth at which the answer turns),
`level` (when each way of buying draws level with renting) and its notes on
what the comparison rests on.

When no template fits, build each option as a scenario and let Salli run it.

    salli whatif --buy 2400@2026-11-01 --json                  # a one-off purchase
    salli whatif --buy 18000 --loan 18000@6.9%x48 --json       # financed: price out, loan in
    salli whatif --recurring -450/month@2027-01-01 --json      # a new cost (or +80/week in)
    salli whatif --income +600/month@2027-01-01 --json         # take-home pay up (or - down)
    salli whatif --income +1000/month@2027-01-01 --tax-role salary --json  # before tax
    salli whatif --extra-payment "student loan:200/month" --json
    salli whatif --invest 5000 --account savings --json
    salli whatif --invest 1000 --holding <holding> --fees 4 --json   # into one of their holdings
    salli whatif --sell <holding>:4 --fees 2 --gain-tax-role <role> --json   # or --sell-value <holding>:2500
    salli whatif --cancel <key> --json                         # keys: salli insights recurring
    salli whatif --asset 450000@2027-03-01 --selling-costs 3% \
      --loan 360000@4.2%x300@2027-03-01 --json                 # a home: price out, mortgage in
    salli whatif ... --label "Pay cash" --save cash.json       # keep it as a document
    salli compare cash.json instalments.json --json            # 2 to 5 options

A scenario is a JSON document (`salli.scenario/1`; amounts and rates as
decimal strings, dates YYYY-MM-DD), so you can also write one and run it with
`salli whatif --file <path>`. Every figure comes as `baseline`, `scenario`
and `delta`: the lowest cash in the next twelve months and when, accounts
going below zero, safe-to-spend, net worth, cash, investments and debts at 1,
5, 10 and 20 years in today's money (with other assets: an asset bought
counts at its value less its selling costs, `other_assets_value` its value),
each debt's payoff and interest,
emergency-fund months, and the FI number and month (`fi.months_gained`).
`compare` adds `trade` (what each option gains and gives up against each
other), `sensitivity` (the same at the conservative and growth returns) and
`break_evens`, each with a sentence (`says`) saying where the answer changes:
quote it. If `is_stale` is true, ask the user to bring their ledger up to
date before deciding. Name the `placeholders` the figures rest on.

How fast a home's value (`--asset-growth`) or a rent (`--recurring-growth`)
grows beyond inflation is the user's own view, never yours: ask, and say
that without one it is 0 (`asset_growth` among the placeholders). The
`asset_growth` break-even says what growth would change the answer.

An amount is what reaches the user's cash unless it is tagged with a tax
role. When it is before tax (a raise, a taxable bonus, a pension
contribution), tag it with the role from their rules (`--tax-role`, or
`tax_role` in a document; `salli tax rules show <set>` lists the roles) and
let Salli compute the tax: `tax` gives each year's change and how it comes
out of cash, `tax.this_year` the current year's. Never work out what they
would keep yourself. If `tax.status` is `not_computed`, say so and quote
`tax.reason` (no active rules, a question to answer with `--tax-answer
key=value`, ...): the tagged amounts then count before tax.

A holding is one of the user's own, by its symbol or id (`salli holdings
list`): never one they don't hold. A sale needs the holding linked to the
investment account that holds it (`salli holdings update <holding> --account
<account>`, after the user agrees), and can't sell more than that account
holds in the ledger: if it is refused, say so and ask them to bring the
ledger up to date. Salli prices a trade at the holding's last recorded price
(grown at their real return and inflation for a later month; it forecasts no
price) and replays its lots first in, first out unless lots are named in a
document: each `changes[n].holding` gives the units, price, fees, lots and
realised gain, which a `--gain-tax-role` (an income role) taxes. Fees are the
user's own figure: ask, and never assume one (without `--fees`, none are
counted, and the result says so). Mention their holdings as they named them;
never suggest buying or selling one, and never compare them.

## Principles and the decision journal

The user's principles are their own rules of thumb, a label and a check
over Salli's figures (`salli principles figures --json` lists them):

    salli principles list --json
    salli principles check cash.json instalments.json --json   # keeps / breaks / can't tell
    salli principles add "Six months of essentials in cash" --check "emergency_months >= 6"

Respect them, and quote each result's `reason`. You may suggest a principle
from what the user says matters to them; add one only after they have seen
the exact label and check and said yes.

When they decide, offer to record it: their question, the options (scenario
files), the one they chose, their reasons in their own words (never yours),
and when to look back. An entry can't be edited or deleted, so record it
only once they confirm:

    salli decisions record --question "…" --option cash.json --option wait.json \
      --chosen "Pay cash" --reasons "<their words>" --review-on 2027-04-11 --yes
    salli decisions reviews --json      # due: what was projected against what happened
    salli decisions review <id> --reflection "<their words>"
    salli decisions note <id> "<text>"
    salli decisions export --format markdown

A decision started with `salli decide` records in the same step, once they
have chosen and said yes:

    salli decide afford-it --answers answers.json --record --chosen "Pay cash" \
      --reasons "<their words>" --review-on 2027-04-11 --yes --json

Walk them through a due review with Salli's comparison, ask what they make
of it, and record their reflection only when they agree.

## Guardrails, whenever you help someone decide

- **Never compute.** Every figure comes from a `salli` command; quote it with
  its currency. Don't add, subtract, divide, project or estimate anything,
  and never work out tax or an amount after tax: tag the amount before tax
  with its tax role and let Salli compute it.
- **Never name a specific product, provider, fund or security of your own.**
  Speak of kinds of thing. You may refer to the user's own holdings as they
  named them, but never suggest buying or selling any security, theirs or
  another, and never compare their holdings as investments: choosing
  investments is for a licensed professional (below).
- **Regulated advice is for a licensed professional.** Where a choice is
  regulated financial advice where the user lives (insurance, pensions,
  choosing investments), say so and suggest a licensed professional there.
  Don't assume any country's rules; ask where they live if it matters.
- **Respect their principles.** Say which each option keeps or breaks; never
  set one aside.
- **Never rank.** Don't call an option best, recommended or right: lay out
  the trade, the sensitivity and the break-evens, name the placeholders the
  figures rest on, and leave the choice to them.
- **Never record a decision they haven't confirmed**, and never in your
  words: their reasons are theirs.

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
| `entries` | journal entries: `list`, `search [text]` (with Salli's totals over every match: quote them, never sum), `add`, `show <id>`, `reverse <id>`, `tag` |
| `import <file>`, `statements` | bank statements: import, then `statements pending`, `post`, `discard`, `categorize` |
| `ledger` | `trial-balance`, `income-statement` |
| `insights` | `cash-flow`, `spending`, `net-worth`, `recurring`, `forecast`, `safe-to-spend`, `signals` |
| `baseline` | the one model every figure comes from, as of a day (`--as-of`): months averaged, exchange rates and their source, account roles, debts, assumptions, and timelines to `--years` |
| `decide` | a common decision from a template (`--list`, `<template> --questions`, `<template> --set id=value` or `--answers <file>`): the options built and compared, the principles checked, and recorded with `--record` once the user confirms |
| `whatif`, `compare` | a scenario's figures against the baseline (from flags, or `--file`); two to five options side by side, with the trade, sensitivity and break-evens |
| `principles` | the user's rules of thumb: `list`, `add`, `edit`, `archive`, `check [files…]`, `figures` |
| `decisions` | the decision journal: `list`, `show`, `record`, `note`, `reviews`, `review`, `export`; entries are never edited or deleted |
| `tax` | your tax from your own active rules: `year`, `compute`, `latest`, `explain <line>`; `return prepare`, `return review <thread>`; `schema` (the rule-set JSON Schema) |
| `tax rules` | tax rule sets: `list`, `show <set> [--version]`, `create <file>`, `version <set> <file>`, `import <file\|url>`, `export`, `validate`, `propose`, `diff`, `evaluate`, `accounts <set> [--apply]`; `activate` is the user's, never yours |
| `budgets`, `debts`, `insurance`, `subscriptions` | each domain's records and reports |
| `holdings`, `portfolio` | holdings: `holdings list`, `holdings add`, `holdings update <holding> --account <account>` (the investment account that holds it; `--no-account` unlinks); `portfolio` (summary), `portfolio transactions add <holding> buy\|sell\|dividend\|…`, `portfolio lots <holding>`, `portfolio prices set <symbol> <close>`, `portfolio performance --from --to` |
| `fi`, `goals` | `fi score`, `history`, `projections`, `surplus`, `strategy`, `assumptions` (`set`, `clear`); `goals list`, `goals allocate` |
| `reports` | `balance-sheet`, `net-worth`, `goal-progress`, `export` |
| `reminders` | `list`, `add`, `seed` (filing deadlines from the active tax rules), `sync-alerts` |
| `advisor` | `run`, `latest`, `reports`, `briefing`, `daily-briefing` |
| `notifications` | the user's digest: `show`, `set` (`--on --time-zone <zone>`, `--off`, `--weekly`/`--monthly`, `--day`, `--hour`, `--items`), `preview` (the message that would go now; sends nothing), `log`. It says what is waiting, never what it is about. Turning it on or off is the user's choice: ask first |
| `profile` | the user's fact-find (`get`, `set`); `export` for all their data |
| `ui` | the console's address (`ui --no-open`), for the user to open in their own browser; signing in there, and activating tax rules there, is theirs |
| `sign-ins` | where the user is signed in (`list`); ending one (`revoke`) signs them out there: ask first |
| `rules` | rules that book transactions that look a certain way; `suggest` |

`salli <command> --help` lists every subcommand and its options.

Related skills: `salli-record-transaction`, `salli-import-statement`,
`salli-monthly-review`, `salli-tax`.
