# The decision lab: better money decisions, computed by Salli, reasoned by your agent

Status: **approved (2026-10-11).** The decisions are recorded at the end. Each phase is its own PR.

## Why

Salli already tells people where they stand: the ledger, insights, the cash
forecast, safe-to-spend, signals, FI projections. What it can't yet do is help them
choose:
- Can I afford this, and should I pay cash or spread it?
- Should this year's bonus go on the loan, or be invested?
- What happens to my plans if I take the new job, the bigger flat, the car loan?
- Did the decision I made in March work out?

The decision lab answers those questions without anyone needing a finance
professional. It follows one rule, the same one as the rest of Salli:

> **Salli computes the consequences. Your AI agent reasons about them. You decide.
> Salli remembers, and checks back.**

- **Salli** supplies every number: deterministic, cited, reproducible.
- **The agent** supplies judgement: it asks what matters to you, weighs the
  trade-offs, and explains them. It's Claude or ChatGPT over MCP, or Salli's own
  agent.
- **The model** never does the arithmetic.

## What exists, and what has to be fixed first

There is no decision or journal code today. A survey of `main` (8aba380) found good
parts to build on:
- **Forecast:** the cash forecast core (`domain/reports/forecast.project`) accepts
  any list of flows.
- **FI:** the FI engine's month-by-month solver takes a contribution function.
- **Debt:** the debt payoff engine supports avalanche and snowball.
- **Tax:** the tax engine's `evaluate` is pure.
- **Storage:** append-only computations, versioned documents, and reminders that
  can point at a source record.

It also found inconsistencies. A decision lab built on top of them would give
answers that contradict each other:

| Today | Why it matters for decisions |
|---|---|
| **Three definitions of income and expenses.** FI sums gross amounts without netting reversals. Surplus divides by 12 regardless of history. Insights nets per calendar month. | A scenario's "monthly surplus" would disagree with the dashboard's. |
| **Three exchange-rate conventions:** the latest posting's rate, the posting-date value, and fetched rates | The same balance gets different base values in different engines |
| **Time scales don't line up:** the forecast in dated days, debt in undated month numbers, FI in whole years | Can't place a loan's payments, a debt-free date and an FI date on one timeline |
| **Real and nominal figures mixed:** FI is real, loans and the forecast are nominal | Fixed loan payments need an explicit inflation rule |
| **Debts counted in two places:** the declared `debts` table versus ledger liabilities | An extra debt payment never reduces the FI surplus |
| **Reads that write:** `compute_score` saves a row | A what-if must never change the user's history |
| **`today` hard-wired** in the FI service | Scenarios must be replayable for an *as of* date |
| **A prompt that breaks its own rule:** the `can_i_afford` MCP prompt asks the agent to subtract the purchase from the forecast itself | "Never your own arithmetic" |

So phase 1 builds one **baseline**: a single, consistent model of the user's money
that every engine and every scenario reads.

## The baseline

The baseline is a pure, dated model of the user's finances **as of** a given day.
It is built once per request, from the ledger and the user's declared data.

- **Income and expenses:** one definition, signed amounts netted per calendar
  month, averaged over the months actually observed (capped at 12). FI, surplus,
  insights and scenarios all use it.
- **Balances:** cash, investments, other assets and liabilities, each in its own
  currency.
  - "Investments" means accounts the user marked as investments (a role on the
    account), not a name that happens to match a pattern.
  - Liabilities link to the `debts` table where a debt has declared terms (rate
    and minimum payment). Without terms they count as balances only.
- **Exchange rates:** the published rate for the *as of* date (the FX port, as tax
  uses), recorded with the baseline.
- **Recurring flows:** found from history, plus declared subscriptions, as the
  forecast already does.
- **Assumptions:** the user's own (FI assumptions, and the active tax rules),
  otherwise labelled placeholders.

The baseline drives **two timelines**:
1. **A daily cash timeline** for the next 12 months, in nominal terms. It answers
   "when does cash get tight?"
2. **A monthly timeline** out to the horizon (up to 50 years), with calendar dates.
   It answers "where does this leave me?"
   - Net worth, liquid cash, investments and debts are in **today's money** (real
     terms).
   - Fixed nominal payments (loans, instalments) are deflated by the user's
     inflation figure. With none set, they keep their real value, and that is
     stated as a placeholder assumption.
   - Debt schedules land on calendar months.

## Scenarios

A scenario is the baseline plus **changes**. It is a validated document
(`salli.scenario/1`), so that an agent can build one reliably:

```jsonc
{
  "schema": "salli.scenario/1",
  "as_of": "2026-10-11",          // default: today
  "horizon_years": 20,
  "changes": [
    { "type": "one_off", "date": "2026-11-01", "amount": "-2400.00", "account": "checking",
      "label": "New laptop" },
    { "type": "loan", "label": "Car loan", "principal": "18000.00", "annual_rate": "0.069",
      "term_months": 48, "start": "2026-12-01", "into": "checking" },
    { "type": "recurring", "label": "New flat", "amount": "-450.00", "cadence": "monthly",
      "start": "2027-01-01" },
    { "type": "income_change", "label": "New job", "monthly_net": "+600.00", "from": "2027-01-01" },
    { "type": "extra_debt_payment", "debt": "student-loan", "monthly": "200.00", "from": "2026-11-01" },
    { "type": "invest", "label": "Bonus", "amount": "5000.00", "date": "2026-12-15",
      "from": "checking" }
  ]
}
```

**Rules for changes:**
- Amounts are decimal strings in a stated currency, defaulting to the base currency.
- Rates are fractions, and dates are ISO.
- Every change refers only to the user's own accounts and debts. That's checked, as
  every write in Salli now is.

**What a scenario returns.** Each figure comes with its value under the baseline
and the change against it:

| Area | Figures |
|---|---|
| Cash, next 12 months | The lowest balance and its date, accounts that go below zero, and safe-to-spend until the next income |
| Monthly, to the horizon | Net worth, liquid cash, investments and debts in today's money, at 1, 5, 10 and 20 years and at the horizon |
| Debt | Each debt's payoff date, the total interest, and the debt-free date |
| Resilience | Emergency-fund months (liquid cash over essential spending), before and after |
| Financial independence | The FI number, the FI date (month and year), and months gained or lost |
| Tax (phase 3) | The change in this year's tax, from the active rule set, when a change touches income |

Every result also records:
- the assumptions used, with placeholders flagged;
- the versions of the rule set and the FI assumptions;
- the *as of* date;
- a content hash of the inputs.

Re-running a recorded scenario reproduces it exactly. **A scenario never writes to
the user's books.**

**Comparing options.** A comparison takes two to five scenarios (the options) and
returns their figures side by side. Salli doesn't rank them. It reports:
- **The trade:** what each option gains and gives up against the others.
- **Sensitivity:** the same options under the conservative and growth scenarios
  (the base return minus or plus 2 points).
- **Break-even values**, solved exactly: the return at which investing beats paying
  down a 6.9% loan, or the income at which a recurring cost stops pushing cash
  below zero.

That turns *"it depends"* into *"it depends on whether you expect more than 4.8%
after inflation"*, and that is precisely what an agent and a person can reason
about.

## Decision templates

These are common decisions, packaged as a short list of questions plus the
scenarios they generate. They are conveniences, not advice:

| Template | Options it builds |
|---|---|
| **Afford it** | Pay cash now, spread it over N months, wait and save |
| **Debt or invest** | Extra payments on a debt, the same money invested, or a split |
| **Use a windfall or surplus** | The splits the user or agent proposes, across debts, goals, cash and investing |
| **Big recurring change** (a new flat, a new job, a car) | Before and after, with the cash timing |
| **Borrow or refinance** | Loans side by side: payment, total interest, effect on cash and FI |
| **Emergency fund** | Months covered now, and the time to reach a target |

Templates contain no country-specific rules. Anything local, such as tax relief on
pension contributions, comes from the user's rule sets and principles.

## Principles: the user's own rules of thumb

Salli doesn't decide what is wise. People often do have rules, though: *keep six
months of essentials in cash*, *pay off anything above 7% before investing*, *never
drop below 2,000 in checking*. Principles are those rules, **as user data**. The
user writes them, or the agent suggests and the user accepts.

```jsonc
{ "label": "Six months of essentials in cash", "check": "emergency_months >= 6" }
{ "label": "Clear expensive debt first", "check": "no debt above 0.07 while investing" }
```

- **Checking:** every option is checked against the user's principles, and Salli
  reports which ones an option keeps or breaks.
- **Evaluation:** checks are evaluated by the same safe expression language as the
  tax rules, over scenario figures, so they stay deterministic and need no model.
- **Prescriptiveness on the user's terms:** this is the only "should" in Salli, and
  it's the user's own.

## The decision journal

When a person decides, Salli records:
- the question;
- the options, as scenario snapshots with their hashes, assumptions and versions;
- the option chosen;
- **their reasons, in their words**;
- the agent's summary, if any, marked as the agent's;
- a review date.

Entries can't be edited once recorded. Later notes append to an entry rather than
changing it.

**Reviews.** On the review date:
- Salli compares what was projected with what happened: the balance, the spending,
  the debt and the net worth, against the snapshot.
- A *decision review due* reminder appears with the other reminders (as a
  `source_domain="decision"` alert) and in the signals.
- The agent can pull due reviews and walk the user through them.
- The result is appended to the entry.

Over time, the journal becomes a record of how a person decides and how it
turned out. It's private, plain-text exportable, and theirs.

## How the agent uses it

- **MCP tools:**
  - `get_baseline`
  - `run_scenario`
  - `compare_options`
  - `list_decision_templates`
  - `start_decision` (template to options)
  - `list_principles`
  - `check_principles`
  - `record_decision` (the user confirms first)
  - `list_due_reviews`
  - `review_decision`
- **MCP prompt** `think_through_decision(question)` tells the agent to:
  1. ask what the person is weighing, and what matters to them;
  2. build the options as scenarios with Salli, never by hand;
  3. compare them, run the sensitivity and check the user's principles;
  4. explain the trade-offs in plain language, quoting Salli's figures and naming
     the assumptions they rest on;
  5. say what would change the answer (the break-even values);
  6. leave the choice to the person, and record it with their reasons if they want.
- **The rewritten `can_i_afford` prompt** builds the purchase as a scenario, so the
  agent no longer subtracts anything itself.
- **Guardrails,** in the prompts and the skills. The agent:
  - never computes;
  - never names specific products or securities;
  - points to a licensed professional where a decision is regulated advice in the
    user's country (insurance, pensions, choosing investments), without assuming
    any country's rules;
  - respects the user's principles;
  - never records a decision the person hasn't confirmed.

## Nudges

Nudges are quiet, useful and rare:
- **Phase 1:**
  - in the product: the status screen's *Needs attention*, signals and reminders;
  - from the agent, which pulls due reviews and signals when the person talks to
    it;
  - in the CLI.
- **Later:** a notification port that a deployment can implement (email, push,
  chat), so that the hosted product or a self-hoster can deliver digests. Salli
  core ships no sender.
- **Never:** streaks, scores-as-games, countdowns or urgency.

## Interfaces

- **API:**
  - `GET /v1/baseline`
  - `POST /v1/scenarios/run` (stores nothing)
  - `POST /v1/scenarios/compare`
  - `GET /v1/decisions/templates`
  - `GET|POST /v1/principles`
  - `GET|POST /v1/decisions`
  - `POST /v1/decisions/{id}/notes`
  - `GET /v1/decisions/reviews`
  - `POST /v1/decisions/{id}/review`
- **CLI:**
  - `salli whatif` (a scenario from flags or a file)
  - `salli compare <a> <b> …`
  - `salli decide <template>` (interactive)
  - `salli decisions list|show|review|note`
  - `salli principles list|add|check`
- **MCP:** the tools and prompt above.

## Phases

1. **Baseline and scenarios.** This is the foundation, and it fixes the
   inconsistencies.
   - **Status:** built. 1a, the baseline ([docs/baseline.md](../baseline.md));
     1b, scenarios, comparison, sensitivity and break-evens
     ([docs/scenarios.md](../scenarios.md)), with FI's month and projections
     read from the baseline's monthly timeline. Phase 2 is next.
   - **As built in 1b:** the schema's seven change types (one-off, recurring,
     income change, loan, extra debt payment, invest, stop a recurring flow);
     results as baseline / scenario / delta, with a content hash of the
     scenario and the baseline's fingerprint; comparisons report the trade as
     figure deltas, sensitivity at the conservative and growth returns, and
     three break-evens solved by bisection to the cent or the basis point
     (investing against paying down a debt, a recurring cost's cash floor, a
     loan's rate against another option). `POST /v1/fi/simulate-purchase` is
     gone: a purchase is a scenario, compared cash against instalments.
   - **The surplus invested:** each month's regular surplus (the average
     surplus, less debts' scheduled payments, freed ones added back, plus a
     scenario's recurring changes) is split by a new planning assumption,
     `surplus_invested` (0 to 1, a labelled placeholder of 1): that share
     grows at the real return, the rest stays in cash. One-offs, a loan's
     money, investments and extra payments are moves that go where they
     say. So a debt-or-invest comparison treats both sides alike, and
     breaks even at the debt's own rate (the first draft kept the whole
     surplus in cash and found 1.9% against a 4.5% loan); FI moved back to
     roughly where the pre-baseline engine had it.
   - **The baseline:** the single income and expense definition, the
     investment-account role, debts linked to liabilities, rates for the *as of*
     date, an injectable *as of*, and pure reads (no writes on read).
   - **Scenarios:** the `salli.scenario/1` schema and engine (cash, monthly, debt,
     FI), comparison, sensitivity and break-evens.
   - **Interfaces:** the API, MCP and CLI for run and compare.
   - **Fix:** the rewritten `can_i_afford`.
   - **Tests:** hand-worked golden scenarios, plus property tests (an empty change
     list equals the baseline; adding a cost never improves cash).
2. **Decisions.**
   - Templates.
   - Principles: the schema, safe-expression checks and their interfaces.
   - The journal, which is append-only.
   - Reviews, with reminders and signals.
   - The `think_through_decision` prompt.
   - Guardrails in the prompts and skills.
3. **Further.**
   - Tax-aware scenarios: hypothetical role totals through the active rule set.
   - "Invest" changes using the portfolio's actual holdings.
   - A rent-or-buy template.
   - The notification port.

There are no real users yet, so phase 1 changes FI's figures (savings rate, FI
date) outright as the definitions are reconciled. Nothing is kept for
compatibility.

## Risks

- **False precision.** A 20-year projection isn't a forecast. Mitigations:
  - results always show the assumptions, and flag placeholders;
  - sensitivity is shown by default;
  - long-horizon figures are labelled as projections in today's money.
- **The agent overreaching.** It recommends from its own beliefs, or names
  products. Mitigations:
  - the prompts and skills carry the guardrails;
  - Salli's tools return consequences, never "best";
  - principles keep the "should" with the user.
- **Scope creep in phase 1.** Reconciling the engines touches FI, insights and debt.
  Mitigation: golden tests for each engine are written first, from today's
  behaviour, so every changed figure changes on purpose and the test says why.

## Decisions (2026-10-11)

| # | Question | Decision |
|---|---|---|
| 1 | How prescriptive | Salli shows consequences, sensitivity and break-evens, and never ranks. The user's agent advises, within guardrails. Any "should" in Salli is the user's own principles. |
| 2 | Who first | People who run Salli and talk to it through an AI agent (Claude, Claude Code, ChatGPT) or the CLI. The hosted apps get the same API later. |
| 3 | Nudges | In-product, agent-pulled and CLI first. A notification port for email, push or chat comes later, implemented outside core. |
| 4 | Principles | In phase 2. |
| 5 | Reconciling FI | FI's figures change where the definitions change, with golden tests documenting each change. Nothing is kept for compatibility. |
