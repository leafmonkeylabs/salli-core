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
    { "type": "income_change", "label": "New job", "monthly": "+600.00", "from": "2027-01-01" },
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
  - `GET /v1/decisions/templates`, `GET /v1/decisions/templates/{id}`,
    `POST /v1/decisions/start` (stores nothing)
  - `GET|POST /v1/principles`
  - `GET|POST /v1/decisions`
  - `POST /v1/decisions/{id}/notes`
  - `GET /v1/decisions/reviews`
  - `POST /v1/decisions/{id}/review`
- **CLI:**
  - `salli whatif` (a scenario from flags or a file)
  - `salli compare <a> <b> …`
  - `salli decide <template>` (interactive)
  - `salli decisions list|show|review|note` (2a adds `record`, `reviews`,
    `export`)
  - `salli principles list|add|check` (2a adds `edit`, `archive`,
    `figures`)
- **MCP:** the tools and prompt above.

## Phases

1. **Baseline and scenarios.** This is the foundation, and it fixes the
   inconsistencies.
   - **Status:** built. 1a, the baseline ([docs/baseline.md](../baseline.md));
     1b, scenarios, comparison, sensitivity and break-evens
     ([docs/scenarios.md](../scenarios.md)), with FI's month and projections
     read from the baseline's monthly timeline. Phase 2 is built (below).
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
   - **Status:** built. 2a: principles, the decision journal and reviews
     ([docs/decisions.md](../decisions.md)). 2b: templates,
     `start_decision`, `think_through_decision`, `salli decide` and the
     guardrails ([docs/templates.md](../templates.md)).
   - **As built in 2a:**
     - **Principles** (`salli.principle/1`) are a label and a check in the
       tax rules' expression language in a *figure mode*: figures are plain
       names (`emergency_months >= 6`), the dotted `role.`/`answer.`/`line.`
       references and the tax-only functions don't exist. They read a fixed,
       documented set of 32 figures computed from the same timelines as
       scenarios (cash over the next thirteen months, emergency months, net
       worth, cash, investments and debts at 1, 5, 10 and 20 years, interest,
       months to debt-free, the highest rate owed and owed while investing,
       what an option borrows, FI), each the value Salli shows. The design's
       "no debt above 0.07 while investing" is
       `max_debt_rate_while_investing <= 0.07`; "never below 2,000 in
       checking" is `account_lowest >= 2000` with the principle naming the
       account. A check reading a missing figure can't tell; nothing is
       counted or ranked.
     - **The journal** (`salli.decision/1`) records one to five options,
       each run by Salli itself (the client supplies no figure) with its
       figures, its principle checks and its projection month by month in
       each month's own money to a year past the review date, plus the
       choice, the person's reasons, the agent's summary (marked), the
       basis (fingerprint, versions, assumptions) and how it was recorded.
       Each entry, note and review is a self-describing document with a
       SHA-256 over its canonical JSON, returned exactly as stored so
       anyone can recompute it. Append-only in the repository and in the
       database (a trigger refuses UPDATE, DELETE and TRUNCATE; only erasing
       the account, which names the user for its transaction, deletes).
     - **Reviews** compare at the last month's end on or before the review:
       cash, investments, what is owed, net worth (the baseline as of that
       day) and spending a month since the decision, actual less projected,
       with the other options' projections beside it. A due review is a
       `decision_review_due` signal and a reminder (`source_domain`
       "decision"), set when the decision is recorded and done when it is
       reviewed.
     - **Interfaces** as designed, plus `PATCH /v1/principles/{id}`,
       `POST /v1/principles/{id}/archive`, `GET /v1/principles/figures`,
       `GET /v1/decisions/{id}` and the exports (JSON, Markdown); MCP
       `get_decision` beside the listed tools; CLI `salli principles
       edit|figures` and `salli decisions record|reviews|export`, so every
       operation has a command. The MCP tools that store something require
       `confirmed_by_user: true`.
   - **As built in 2b:**
     - **Templates** (`salli.template/1`) are the design's six, as code:
       typed questions (amounts, months and years, numbers, rates, dates,
       choices, the person's own debts and cash accounts, text, and lists of
       amounts, loans and splits), each checked with its path under
       `answers`, and a pure function from the answers and the person's
       facts (their debts, cash accounts and principles, read from their
       baseline) to two to five labelled `salli.scenario/1` options. A
       default comes only from the date (the as-of date, the first of next
       month), the person's own data (their only debt, what it owes, the
       months a principle `emergency_months >= N` asks for) or a plain
       default of Salli's (a name, "once", the 20-year horizon). We judged
       a placeholder for a price, a rate or a cash target to be advice in
       disguise, so a question without an honest default has none and must
       be answered; FI's placeholders still flag every result. Templates
       hold no country's rules. The ids are `afford-it`, `debt-or-invest`,
       `windfall`, `big-change`, `borrow` (new borrowing, or refinancing a
       debt) and `emergency-fund`. "Big recurring change" and "borrow" add
       an unchanged option ("As things are", "Don't borrow", "Keep the
       debt") so there are always two to compare; "Wait and save" waits the
       months the person says and sets aside what they say.
     - **Setting aside**, a new scenario change (`set_aside`): part of each
       month's regular surplus kept in cash before the share invested is
       taken from the rest. Waiting and an emergency fund needed it: with
       the surplus all invested (the placeholder), nothing else lets cash
       grow. It moves no money of its own, so no figure of an existing
       scenario changes, and the engine's version stays 2.
     - **The time to a cash target** comes from the engine
       (`engine.cover_target`): the first month at whose end cash, in
       today's money, covers the target months of spending (the monthly
       spending as shown, so the target is the product of two figures a
       reader sees), under the baseline and each option. Not a principle
       figure: the figure set takes no parameters, and a target is one.
     - **Starting a decision** (`POST /v1/decisions/start`,
       `start_decision`, `salli.decision-start/1`) runs the options through
       the comparison, the principles' checks and, for an emergency fund,
       the time to the target; it stores nothing, and carries what
       `record_decision` needs (a suggested question, each option with its
       as-of date, the labels). Recording stays the journal's own step.
     - **`think_through_decision`** follows the design's six steps, and
       `can_i_afford` runs the afford-it template. Both end with the same
       guardrails (never compute, never name a product, provider, fund or
       security, a licensed professional where a choice is regulated advice
       where the person lives, the person's principles respected, never a
       ranking, never a record they haven't confirmed), which the CLI skill
       and docs/ai-clients.md repeat. Tests hold templates, starts and
       their API and MCP answers to having no field that ranks or scores
       and no word that ranks or recommends (`tests/guardrails.py`), and
       the prompts to carrying each guardrail.
     - **Interfaces:** `GET /v1/decisions/templates` (in brief),
       `GET /v1/decisions/templates/{id}` (the questions, the person's
       defaults and the answers' JSON Schema), `POST /v1/decisions/start`;
       MCP `list_decision_templates` (with each template's questions) and
       `start_decision`; `salli decide --list`, `salli decide <template>`
       (asks in a terminal; `--answers`, `--set`, `--questions` for
       scripts) and `--record` to record in the same step, asking first.
     - A comparison's "none in range" sentence now names both options.
3. **Further.**
   - Tax-aware scenarios: hypothetical role totals through the active rule set.
   - "Invest" changes using the portfolio's actual holdings.
   - A rent-or-buy template.
   - The notification port.
   - **Status:** designed and approved (2026-10-12): [the phase 3 design](decision-lab-phase-3.md)
     (sub-phases 3a to 3d, and decisions 6 to 31). All four are built.
   - **As built in 3a:** tax-aware scenarios
     ([docs/scenarios.md](../scenarios.md#tax); the phase 3 design's "As
     built (3a)" notes): changes tagged with a tax role run through the
     person's active rules, and principles gain a 33rd figure,
     `tax_change_this_year`. The engine's version is 4: a stopped flow on
     an account with an income or deduction role now changes the tax.
   - **As built in 3b:** invest and sell changes on the person's own
     holdings ([docs/scenarios.md](../scenarios.md#holdings); the phase 3
     design's "As built (3b)" notes): a holding links to the investment
     account that holds it (`holdings.account_id`, migration
     `core_0020_holding_account`); `invest` takes a `holding` and `fees`, and
     a `sell` replays the holding's lots in memory, capped at what its
     account holds, its gain taxable through an income role. One real
     return; no price forecast; no template picks a holding; the guardrail
     allows the person's own holdings and forbids suggesting or comparing
     any. The engine's version stays 4.
   - **As built in 3c:** the rent-or-buy template
     ([docs/templates.md](../templates.md#rent-or-buy); the phase 3
     design's "As built (3c)" notes): an `asset` change counted at its value
     less its selling costs, `real_growth` on `recurring`, other assets by
     month, the house-price growth break-even and the month buying draws
     level. No figure changed, so the engine's version stays 4.
   - **As built in 3d:**
     - **The port** is as designed: `Notifier`, `Notification`,
       `NotificationItem` and `Delivery` in `application/ports.py` (the two
       message classes live in `domain/notifications/digest.py`, which builds
       them, and ports re-exports them), `NoNotifier` by default, and
       `Extension.notifier` merged like the meter. Core ships no sender;
       docs/self-host.md shows a minimal one.
     - **The message** says each item in a sentence from the wording table,
       a count, the earliest date and the link. A filing deadline gives its
       date only, not the rules' label for it: the label is text the person
       or their agent wrote, so it falls under decision 29's "never a name".
       The cash item's date is the first day the forecast is below zero, not
       the signal's lowest point. The person's own reminders count up to the
       day before the next digest; reviews up to today.
     - **Timing.** A monthly digest goes on the month's first chosen weekday.
       A failed send is retried at the chosen hour on a later day of the
       same period (never at another hour, so the quiet holds), three
       attempts in all. A first send happens only on the digest day: a run
       missed that day waits for the next period. An attempt whose outcome
       was never recorded stays `sending` and is never retried, since it may
       have gone.
     - **Doctor** reads when the job last ran from `instance_settings`, not
       the delivery log: a run with nothing to send logs nothing.
     - **Storage** is migration `core_0019_notifications` (the design said
       core_0020): `user_profiles.time_zone`, `notification_preferences` and
       `notification_deliveries`. `tzdata` is a dependency.
     - **Interfaces** as designed: `GET`/`PATCH
       /v1/notifications/preferences`, `GET /v1/notifications/preview`,
       `GET /v1/notifications/deliveries`, `POST
       /v1/notifications/cron/send-due`, `salli-server jobs send-digests`,
       and `salli notifications show|set|preview|log`. No MCP tools.

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
