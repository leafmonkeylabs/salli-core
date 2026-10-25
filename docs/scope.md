# Scope

Salli's surface is frozen until the first pilots have run. **No new engine
is added before then**: the work is making what exists dependable for the
people using it. Bugs, security, imports, data for a new market (tax rule
sets, capital-market assumptions, bank formats, all under `markets/`) and
what a pilot shows is missing from a core flow are in; a new kind of
calculation, model or page is not.

**Exempt by the owner (household basics, for the phone app):** changing an
entry's category after booking (`POST /v1/entries/{id}/recategorise`), debts
with a rate from first run, a monthly budget (`/v1/budget/monthly`,
`/current`, `/trend`; the `budget_over` and `budget_pace` signals) and push
alerts (`/v1/devices`, `salli-server jobs send-push`).

Nothing listed as experimental is being removed. It works and is tested; it
may change shape, or be cut back, once pilots show whether people use it.

## Core

What a pilot is judged on, and what the freeze protects:

| Area | What it is | Docs |
|---|---|---|
| The books | Double-entry ledger, accounts, entries and reversals, closed books, the hash chain, exports | [books.md](books.md) |
| Imports | Statement files (CSV, PDF, Excel, OFX/QFX, QIF, camt.053, MT940), bank formats, review, rules, duplicates, drafts, bank feeds where an extension supplies one | [books.md](books.md#imports) |
| Reconciliation | A statement's cleared postings against the bank's balance | [books.md](books.md#reconciling-with-the-bank) |
| The baseline | One dated model of the person's money, and the figures read from it: net worth, cash forecast, safe to spend, insights | [baseline.md](baseline.md) |
| Financial independence | The FI number, date and score, the person's assumptions | [baseline.md](baseline.md) |
| Tax rules | The rule-set engine, rule sets as data, computing the person's tax line by line | [taxrules.md](taxrules.md) |
| The AI connector | The MCP server and its sign-in, read tools and gated writes | [ai-clients.md](ai-clients.md), [connectors.md](connectors.md) |
| Clients | The `salli` CLI, the console's Home, Cash, Attention, Independence, Books, Tax and Settings | [self-host.md](self-host.md#the-console) |
| Running it | Self-hosting, the hosted path, backups, `salli-server` | [self-host.md](self-host.md), [hosting.md](hosting.md) |

## Experimental

Working, documented and tested, and marked as experimental where the docs
describe them. The engines without a pilot user yet are also marked in the
API (`x-experimental: true` and the `experimental` tag on their operations)
and in `salli --help` ("Experimental:"); their tools and prompts are out of what
an AI agent sees over MCP unless the owner sets `SALLI_EXPERIMENTAL=true`
(the API keeps them either way):

| Area | Docs |
|---|---|
| The decision lab: scenarios, templates, principles, the decision journal and reviews | [scenarios.md](scenarios.md), [templates.md](templates.md), [decisions.md](decisions.md) |
| The odds: Monte Carlo of returns, with spending guardrails | [baseline.md](baseline.md) |
| Insurance needs and cover targets (policies and the cover report are core) | `salli insurance --help` |
| The investment policy: drift, look-through, tax-aware sales; and the wash-sale flag on lots | `salli ips --help` |
| The monthly briefing and the agents (the tax agent, return preparation) | [ai-clients.md](ai-clients.md) |
| The phone app (in development) | [design/mobile.md](design/mobile.md) |
| Usage counts for the owner (`salli-server stats`, off by default; `--send` reports the weekly totals to a URL the owner sets) | [self-host.md](self-host.md#usage-reports) |

## After the pilots

What the pilots show decides what moves from experimental to core, what is
cut back, and which engine, if any, comes next.
