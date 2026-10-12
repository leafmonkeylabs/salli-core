# The decision lab, phase 3: tax, holdings, rent or buy, notifications

Status: **approved (2026-10-12).** The owner accepted every recommended
decision below. Building started with 3a and 3d, and both are built.
**3a, tax-aware scenarios,** is built (its "As built" notes close section
1). **3d, the notification port,** is built
([docs/self-host.md](../self-host.md#digests); as built in
[decision-lab.md](decision-lab.md#phases)). It extends the approved [decision lab design](decision-lab.md), whose
rules all still hold. The open questions are at the end, numbered on from that
design's decisions (6 onwards). Each sub-phase is its own PR.

Phase 3, as the approved design lists it:

| Item | The question it answers for a person deciding |
|---|---|
| **Tax-aware scenarios** | "If I take the raise, or pay into my pension, what do I actually keep?" |
| **Invest changes on the actual holdings** | "If I sell some of what I hold to pay for this, what does it fetch, and what gain do I realise?" |
| **A rent-or-buy template** | "Should I keep renting, or buy?", laid out as consequences, never as an answer |
| **The notification port** | "Tell me when something is waiting for me, without nagging me." |

The rules phase 3 keeps, as every phase does:

- **Salli never ranks options.** Results carry consequences, sensitivity and
  break-evens; `tests/guardrails.py` holds every new surface to it.
- **The model never computes.** Tax, gains, valuations and every message's
  content come from deterministic code.
- **Country-neutral.** Tax comes only from the person's own active rule set;
  no template, default or message holds a country's rule.
- **Placeholders are always labelled,** in `placeholders` and in the text.
- **No real users yet,** so anything that should change is replaced outright,
  with no compatibility shims.

## What the code says today

This survey of `main` (80a41f1) fixes what phase 3 builds on, and what
constrains it.

- **Tax is pure and annual.** `domain/taxrules/engine.evaluate(compiled,
  roles, answers)` takes role totals (Decimals) and answers and returns every
  line and `net` (after credits, so withholding is already taken off). Role
  totals come from the ledger by account `tax_role`, in each account's
  normal-balance direction (`domain/taxrules/inputs.role_postings`,
  `total_roles`), dated within `year.start` to `year.end`.
  `TaxRuleService.apply` gathers them and converts at each entry date's rate.
  `TaxService.resolve` picks the active rules by residency and year. Answers
  are not stored per user: every call passes them.
- **The baseline knows which rules apply, but not what they say.**
  `BaselineInputs.rule_sets` holds `RuleSetRef`s (country, year, version,
  content hash) of the active versions in the person's residency that cover
  the as-of date (`baseline_service.covering_rule_sets`). It holds no rule
  documents and no later years.
- **Scenario amounts are what reaches cash.** `income_change.monthly_net` is
  net by name. Nothing in `domain/scenarios/engine.py` reads a tax role.
- **The monthly timeline is real; the daily one nominal.**
  `timelines.deflators` gives each month's price level; recurring changes
  are in today's money, and one-offs, loan payments and investments in their
  own day's money.
- **Investments are one pool.** `timelines.monthly` keeps one `investments`
  figure, grown at one real return. `InvestChange` moves cash into it.
  Sensitivity (`comparison.sensitivity`) and the invest-against-debt
  break-even (`comparison.invest_vs_debt`) both vary that one return.
- **The portfolio is a second book.** `holdings` (`adapters/db/models.py`,
  `HoldingORM`) have no link to any ledger account. The baseline's
  investments are ledger accounts whose `asset_role` is `investment`, and
  nothing in `baseline_service.py` or `fi_service.py` reads holdings. Lots are
  first in, first out, or named (`domain/portfolio/lots.py`); there is no
  average-cost pooling. Prices are only those a person records
  (`application/market_data.StoredPriceHistory`); no provider ships, and
  nothing stores an expected return per holding.
- **Other assets keep their value in today's money,** and fund no
  withdrawals: `fi.asset_base` counts cash and investments less debts only.
  A one-off purchase buys no asset ("What a purchase buys isn't counted as an
  asset", `schema.OneOffChange`).
- **Nothing is sent today.** Reminders (`ReminderORM`, with `alert_type`,
  `source_domain`, `source_id`, `severity`) and signals
  (`domain/reports/signals.py`, `decision_review_due` among them) are pulled:
  by the API, MCP `get_signals` and the CLI. `ReminderService.sync_alerts`
  runs only when `POST /v1/reminders/sync-alerts` is called. The one
  scheduled per-user job, `salli-server jobs run-advisor`, is opt-in
  (`daily_briefing_enabled`). The profile holds no time zone.
- **The extension seam takes one of each policy.** `extensions.combine`
  refuses two meters, two entitlement policies or two identity providers.
  A notifier fits the same shape.

Two findings outside phase 3's scope, but in its way:

- **A tax-withheld account counts as cash.** An asset account's `asset_role`
  defaults to `cash` (`Account._asset_role_for_assets`), and
  `TaxRuleService.suggested_accounts` creates a rule set's suggested accounts
  without setting one. So a "Tax withheld" receivable becomes a cash account
  (`forecast.cash_accounts`), counted in cash, emergency months and
  safe-to-spend. Phase 3a fixes it (below).
- **A docstring names a method that doesn't exist.** `application/market_data.py`
  refers to `PortfolioService.refresh_prices`; there is none. Phase 3b
  corrects it.

## 1. Tax-aware scenarios

### The problem

A raise of 1,000 a month is not 1,000 a month in the bank. Today a person (or
their agent) must state the net figure themselves, and the agent is tempted
to work it out, which it must never do. A pension contribution, a deductible
expense or a taxable windfall has the same problem from the other side. The
person's active rule set already says how their tax works. Phase 3a runs a
scenario's taxable amounts through it.

### The design in one paragraph

A change may carry a **tax role** (`tax_role`): its amount then also adds to
that role's total, so it is before tax. For each tax year the scenario
touches, Salli projects the year's role totals twice, for the baseline and
for the scenario: what the ledger shows so far, plus the rest of the year at
the baseline's monthly average, plus the scenario's tagged amounts. It runs
both through the person's rules and takes the difference in `net`. That
difference is **the change in the year's tax.** It comes out of (or back
into) cash month by month, from the year's first tagged amount to the year's
last month, as part of the regular surplus. The result reports each year's
role totals, the change in tax and the rules that computed it. Untagged
changes behave exactly as now.

### Tagging, and the role's direction

Changes that can carry `tax_role`: `one_off`, `recurring`, `income_change`
and (3b) `sell`. The role must be declared by an active rule set covering the
change's date, or, for years no rules cover yet, by the latest active one
(below). Only roles of kind `income` or `deduction` can be tagged:

| Role kind | What adds to it | Example |
|---|---|---|
| `income` | money in (a cut, money out, subtracts) | a raise, a taxable bonus, a side income, a realised gain |
| `deduction` | money out (a refund, money in, subtracts) | a pension contribution paid from cash, a deductible cost |
| `withholding`, `other` | can't be tagged | A cash change has no natural direction for them. Withholding is projected from history (below). |

`stop_recurring` needs no tag. It stops one of the ledger's own flows, whose
income or expense account carries its `tax_role` already
(`insights.Recurring.account_id`), so the stop takes the flow off that role.

**Choice: by tagging a change, or by an account's `tax_role`?**

| Option | For | Against |
|---|---|---|
| **Tag the change** (`tax_role` on the change) | Direct. The role is named where the amount is. Works for money that has no ledger account yet (a new job). | A second place roles are named. |
| By the account's `tax_role` | One source of roles. | A change names a *cash* account, not an income or expense one, so every change would need a second account field. A new income has no account yet. |

**Recommended: tag the change**, validated against the person's declared
roles, and read the account's role only where the change refers to the
ledger's own flow (`stop_recurring`).

**`income_change` is renamed.** With a tag its amount is before tax, so
`monthly_net` becomes `monthly`: net when untagged, as today, and the role's
amount when tagged. No users, so no alias.

### A year's role totals

For each role and each tax year from the one containing the as-of date:

    projected = actual to the as-of date
              + the rest of the year at the baseline's monthly average for the role
              + the scenario's tagged amounts dated in the year (scenario only)

- **Actual to the as-of date:** `role_postings` over the baseline's entries
  (which go back about two years, so cover any year that has begun), from
  `year.start` to the as-of date. Pure, from `BaselineInputs.entries`.
- **The monthly average:** each role's postings netted per calendar month
  over the baseline's observed months (`Flows.months`, the same twelve or
  fewer), averaged as income and spending are. In today's money, so each
  future month's amount is the average times that month's price level
  (`timelines.deflators`), as the baseline's own surplus is. The rest of the
  as-of month is its share of days, as the baseline does.
- **Withholding** is projected the same way, from history. A tagged raise
  doesn't change it, so the change in `net` is the whole extra tax: what
  would be withheld more, or paid at settlement.
- **Currency:** actuals at each entry date's rate, as `TaxRuleService.apply`
  converts. Projected and tagged amounts at the baseline's as-of rate (the
  baseline's convention). The service fetches the dates' rates. A missing
  rate means no tax for that year, with a note, never a guessed rate.

**Choice: which tax year a month belongs to?** The rule set defines its
year's dates, and they may not start on the 1st.

| Option | For | Against |
|---|---|---|
| **Dated amounts by their day; a month's average by the year containing the month's last day** | Exact for everything dated (actuals, one-offs, recurring flows). Simple for the averages. | The average for a month that straddles a year's start falls wholly in one year. |
| Every amount pro rata by days | Exact in principle. | False precision: the average is an average. It also splits each month's tax across two years. |

**Recommended: the first.** It is deterministic, the docs can say it in a
sentence, and the dated amounts that decide a decision are exact.

### Annual tax, applied monthly

**Choice: annual or monthly tax in the timelines?**

| Option | For | Against |
|---|---|---|
| Report only: a "change in this year's tax" figure, timelines untouched | Smallest. What the approved design's figure table lists. | A tagged amount is before tax, so the timelines, FI and every break-even would count gross money as kept. |
| A lump at the year's end, or at a deadline | Like settlement. | Salli can't tell which of a rule set's `deadlines` is a payment (their keys are the author's own). Inventing a settlement date is a country assumption. |
| **Computed per tax year, spread over its months** | Rule sets are annual, so the computation is too. Spreading is how withholding works almost everywhere, and needs no date Salli doesn't have. | A person who settles once a year sees the cash a little early. |

**Recommended: computed per tax year, applied monthly.** Each year's change
is split equally over the months from the year's first tagged amount (the
month it falls in) to the year's last month, each part rounded to the
currency's smallest unit, the last taking what rounding left (as a loan's
last payment does). Each part is a regular flow on its month's last day
(`Changes.regular`), in that month's own money, so it moves the regular
surplus, the share invested, the daily cash and FI exactly as a recurring
cost would.

### Real and nominal

Bands and allowances are nominal; the monthly timeline is in today's money.
So each year's role totals are formed in **that year's own money** (the
averages and recurring amounts grown by the person's inflation, as the
timelines grow them), run through the rules, and the change in tax lands as
nominal flows, which the timeline deflates like any other. With no inflation
set, the two are the same, and inflation is already listed as a placeholder.

### Years no rules cover

People write one rule set per year, so a 20-year scenario runs mostly beyond
them. Without tax there, a tagged raise would count gross from next year on,
and FI would move by a figure no rules computed.

**Choice: what happens beyond the last active year?**

| Option | For | Against |
|---|---|---|
| No tax beyond the covered years | Nothing assumed. | Gross money counted as kept for most of the horizon, which is worse than any assumption. |
| **The latest active rules carried forward, with every amount in them held level in today's money** (labelled `tax_rules_carried_forward`) | Rules a person checked and activated, under the same stationarity the baseline already assumes (average flows held level in today's money). Nothing invented. | Thresholds really are often frozen nominally. |
| The latest rules carried forward with nominal thresholds frozen | Shows "fiscal drag". | A forecast of policy. Not Salli's to make. |

**Recommended: carry the latest active rules forward, level in today's
money,** labelled. It is done by evaluating on totals deflated to the
latest active year's money and reflating the result, which is the same as
indexing every threshold. A year with its own active rules always uses them,
and replaces the placeholder for that year. Each year in the result says
which rules computed it and whether they were carried forward.

### No rules, draft rules, questions

- **Only active rules compute.** A draft, validated or proposed version never
  does: the invariant that only the user activates rules, and only active
  rules compute, holds for scenarios too.
- **No residency, no active rules, a role no active rules declare, a
  question with no answer and no default, a missing rate:** the scenario
  still runs. Projections never block on missing assumptions. Tagged amounts
  then flow before tax, and the result says so plainly: `tax.status` is
  `"not_computed"`, `tax.reason` names what is missing and what to do (the
  same wording as `NoTaxRulesError`), and `placeholders` lists `"tax"`. A
  principle reading a tax figure can't tell.
- **Answers** to a rule set's questions go in the scenario, so a recorded
  option reproduces: a new optional `tax` object, `{"answers": {"<key>":
  value}}`, checked against each year's rules as `evaluate` checks them. A
  template's start takes `tax_answers` and puts them in every option.

**Choice: an unknown role with no active rules**: refuse, or run?
**Recommended: run, labelled** (above). A role no rule set of the person's
declares at all is still refused with its path, as a mistyped id is.

### What comes back

A new `tax` section in every scenario result, baseline / scenario / delta as
everywhere:

| Field | What it holds |
|---|---|
| `status`, `reason` | `"computed"`, `"not_computed"` with why, or `"none"` (nothing tagged, so nothing to compute; no rules are read). |
| `years[]` | Each tax year from the as-of date's to the horizon (the result shows the first two and each checkpoint's year; the timeline uses all): `year`, `start`, `end`, `rules` (`RuleSetRef`, and `carried_forward`), `roles` (each touched role's `actual`, `projected` and `scenario` totals), `net` (baseline / scenario / delta), and the monthly parts. |
| `this_year` | The as-of date's tax year in brief: the change in its tax, the rules, and the figures it rests on. The approved design's "change in this year's tax". |
| `total_change` | The change in tax over the horizon, in today's money. |

The principles' figure set gains one figure, `tax_change_this_year` (amount,
nominal: the change in the as-of date's tax year's `net`; 0 for the
baseline), documented in docs/decisions.md as every figure is. That makes 33.

### FI and the break-evens

**Choice: does after-tax change FI's figures and the break-evens?**
**Recommended: yes, through the timelines, and in no other way.**

- The change in tax moves the regular surplus, so it moves what is invested,
  cash, net worth and the FI month, as any recurring amount does.
- **The FI number doesn't change with it.** The tax on a salary is not
  spending to live on once it has stopped, so the change in tax is not added
  to the spending the FI number is built on. Tax on withdrawals in
  retirement is out of scope, and the docs say so.
- **Break-evens rerun the translation**, tax included, at each step of
  their bisection, so the cash floor of a tagged recurring cost and the loan
  rate at which two options cost the same are after tax. Evaluations are
  memoised by (rules hash, role totals, answers), since most years repeat.
- **Investment growth isn't taxed** by any role: the docs ask the person to
  set their real return after the tax they pay on it.

### Where it lives

| Layer | Change |
|---|---|
| `domain/taxrules/inputs.py` | `monthly_role_totals(postings, months)`: role totals netted per calendar month (pure, beside `total_roles`). |
| `domain/baseline/models.py`, `build.py` | `BaselineInputs.tax`: the active rule documents in the person's residency for the as-of year and later, their role postings and the rates the service fetched. `Baseline.tax`: each year's actual and average role totals. The fingerprint includes them. |
| `domain/scenarios/tax.py` (new) | Pure: years and the months they own, projected totals, evaluation through `taxrules.engine.evaluate`, carry-forward, the monthly parts, memoisation. |
| `domain/scenarios/schema.py` | `tax_role` on `one_off`, `recurring`, `income_change`; `income_change.monthly`; the scenario's `tax.answers`. |
| `domain/scenarios/engine.py` | The translator collects tagged amounts; `run` adds the tax parts to `Changes.regular` and the `tax` section to `ScenarioResult`. `views.py` shows it. |
| `domain/decisions/figures.py`, `catalogue.py`, `templates.py` | `tax_change_this_year`; a `tax_role` question type (the person's taggable roles); `big-change` asks whether its pay change is before tax and in which role; `windfall` whether new money is taxable. |
| `application/services/baseline_service.py` | Gathers `BaselineInputs.tax` (rule documents, rates for actual entry dates). |
| `application/services/tax_rule_service.py` | Suggested asset accounts are created with `asset_role` `other`, so a tax-withheld receivable is no longer cash (the finding above). |
| Interfaces | No new route: `POST /v1/scenarios/run`, `POST /v1/scenarios/compare` and `POST /v1/decisions/start` return the section. `salli whatif` gets `--tax-role`; the MCP tool descriptions say how to tag. OpenAPI and the SDK regenerated. |

**Schema and data.** `salli.scenario/1` gains optional fields and keeps its
id, as 2b's `set_aside` did. No migration: rule sets, accounts and entries
are already stored. `ENGINE_VERSION` stays 3: an untagged scenario's figures
don't change (if review finds one that does, it goes to 4).

### Out of scope

- Withholding that changes with pay. It is projected from history; the
  change in `net` covers it.
- When tax is actually settled, refunds' timing, instalment schemes.
- Tax on investment growth, dividends, and withdrawals in retirement.
- A loan's interest as a deduction (a mortgage's, say). It is possible later
  as a tag on `loan`, its interest per year read from the schedule, and is
  listed for after 3c.

### Risks

- **Role totals are only as right as the books.** Salary booked net, with
  no gross and no withholding, gives the wrong tax. The result shows the
  totals it used (actual, projected, scenario), so the person can see it.
- **Projection is an average.** A bonus month in the history inflates the
  rest of the year. Shown, and labelled as projected.
- **Carried-forward rules** may differ from next year's law. Labelled per
  year; adding the year's rules replaces them.
- **Cost.** Bisection reruns the translation about 20 times per break-even,
  each up to 51 tax years. Memoisation and level years keep it small; a
  benchmark in the PR shows it.

### Tests

- **Golden, hand-worked** (`tests/golden/`), on a fictional rule set *XA
  2031*: a relief of 12,000 on `salary`, then 20% to 40,000 and 40% above;
  year 2031-01-01 to 2031-12-31; no inflation set; as of 2031-06-30; salary
  4,000 a month all year so far (actual 24,000, average 4,000).
  - Baseline 2031: projected 48,000; taxed 36,000 at 20% = **7,200.00**.
  - A raise of 1,000 a month from 2031-07-01, tagged `salary`: 54,000;
    taxed 42,000 = 8,000.00 + 800.00 = **8,800.00**; change **1,600.00**,
    from July to December: 266.67 five times and 266.65 in December. Each
    month's surplus rises by 733.33 (733.35 in December).
  - 2032, no rules active: XA 2031 carried forward. 48,000 gives 7,200.00
    and 60,000 gives 8,000.00 + 3,200.00 = 11,200.00: a change of
    **4,000.00**, 333.33 eleven times and 333.37 in December, labelled
    `tax_rules_carried_forward`.
  - The same raise untagged: no `tax` years, and every figure as today.
- **Properties** (`tests/properties/`): a scenario with nothing tagged has
  `tax.status` `"none"` and every figure equal to today's engine; a tag of
  0 changes nothing; each year's monthly parts add up to its change exactly;
  at an as-of date on a tax year's last day, the baseline's projected tax
  equals `TaxService.compute_tax` for that year (the scenario and the tax
  page never disagree); evaluating twice gives the same result, memoised or
  not.
- **Conformance:** the golden runs over each fictional jurisdiction in
  `tests/taxrules/conformance/` (a taper, a filing-status question, stacked
  gains, a capped contribution, a formula tariff, a rebate, final-rate
  income), so no shape of rule breaks the projection.
- **Guards:** `test_no_country_knowledge` over the new code and docs;
  `assert_never_ranks` over the `tax` section; a test that only an `active`
  version is ever evaluated (a draft with a passing example still gives
  `not_computed`).

### As built (3a)

Built as designed, with these choices where the design left room, or the
code asked for one:

- **Where the inputs live.** `BaselineInputs.tax` (`TaxInputs`) holds the
  active versions in the residency whose year ends on or after the as-of
  date, plus the latest that ended before it (the one later years carry
  forward), why there are none in `NoTaxRulesError`'s words, and the rates
  fetched (the as-of date's, and each posting day in the year before it
  that needs one). `Baseline.tax` (`BaselineTax`) holds the role postings
  to the as-of date and each role's monthly average; each year's actual is
  taken from the postings by `domain/scenarios/tax.py`, since a year's
  dates depend on which rules compute it. The fingerprint includes the
  rules' refs and rates only when there are rules, so a baseline without
  any fingerprints as before.
- **Status, per year.** Each touched year is `computed` or `not_computed`
  with its reason; the result's `status` is `not_computed` when any touched
  year is (its `reason` the first year's, the rest in `notes`), and the
  years that did compute still apply. `years` lists only years with tagged
  amounts (an untouched year's change is zero); the view shows the first
  two and the checkpoints' years. `this_year` is null, and the figure 0,
  when nothing in the as-of year is tagged; the figure is missing when that
  year's tax isn't computed, or there are no rules to place it in a year.
- **Stops** take their account's role only when the active rules declare it
  as `income` or `deduction`; otherwise a stop has no tax, as before.
- **Answers** a rule set doesn't ask, or that don't fit their question, are
  refused with their path (`tax.answers.<key>`), as a mistyped id is; a
  question with no answer and no default leaves its year not computed.
- **The service** refuses a tag no rule set of the person's declares at all
  (a new port method, `declared_role_kinds`, over the versions
  `declared_roles` reads), or one of kind `withholding` or `other`, at
  `changes[i].tax_role`. The engine refuses the latter too, from the active
  rules.
- **A carried-forward year's label** is the next year's number when the
  rules' label is their start year ("2031" → "2032"), otherwise its dates.
  A year with no earlier active rules (only later ones) is not computed.
- **Placeholders** gain `tax_rules_carried_forward` whenever a computed year
  carries rules forward, beside the per-year `carried_forward`.
- **Memoised** on the baseline (`BaselineTax.memo`) by rules hash, totals,
  answers: a comparison of two tagged options with a loan-rate break-even
  and cash floors on the XA household took 0.86 s against 0.50 s untagged,
  six evaluations memoised in all.
- **Templates:** `big-change` asks `income_tax_role`, `windfall` `tax_role`
  (when the money is new); neither has a default. No template tags a cost.
- **The CLI:** `salli whatif --tax-role <role>` tags every `--income`,
  `--recurring` and `--buy` amount, `--tax-answer key=value` answers a
  question; `salli decide --tax-answer` too. The run shows each tax year's
  net under the baseline and the scenario, and the change.
- **`ENGINE_VERSION` is 4,** not 3 as designed. No existing golden
  changed, and a scenario that tags nothing gives exactly the figures it
  gave, but one existing input can: a `stop_recurring` of a flow whose
  account carries a role the person's active rules declare as income or
  deduction now changes the tax. The rule is that the version moves
  whenever the same inputs would give different figures, so it moved, as
  it did from 2 to 3.
- Suggested asset accounts are created with `asset_role` `other`; no other
  default made a tax account cash.

## 2. Invest changes on the actual holdings

### The problem

Today `invest` moves money into "your investments" and `one_off` takes money
out; neither knows what the person holds. Someone who wants to sell part of
a holding to fund a deposit can't see what it fetches at its price, what
fees take, or the gain they would realise and its tax. And investing into a
holding they already own can't be shown in units at its price.

### What it does

- **`invest` gains `holding`** (one of the person's holdings, by id) and
  `fees`. The amount leaves cash; the amount less fees joins the
  investments; the result shows the units bought at the holding's last
  recorded price on or before the as-of date (with its date and source, as
  `valuation.Valuation` reports a price), and opens a hypothetical lot at
  that cost for any later sale in the same scenario.
- **A new `sell` change:** `holding`, `quantity` (or `amount`, its value to
  sell), `date`, `fees`?, `lots`? (named lots; first in, first out without),
  `into`? (a cash account), `tax_role`? (where the realised gain goes),
  `label`. Salli replays the holding's transactions with the sale appended
  (`lots.replay`, unchanged, in memory; nothing is written) and reports the
  units, proceeds, fees, the lots consumed and the realised gain, in the
  holding's currency and the base currency. Proceeds less fees go into
  cash; the sale's value leaves the investments.
- **A sale later than the as-of date** is at the last recorded price grown
  at the person's real return (and inflation) to the sale's month, at the
  as-of exchange rate: the same growth the investments have in the timeline.
  Salli forecasts no security's price and no exchange rate, and says so in
  the result.
- **The realised gain feeds tax** through `tax_role` (3a): a gain adds to an
  `income` role, a loss subtracts from it, and the rules decide what a loss
  does (`max(0, …)`, stacked bands; `stackland.json` shows the shape).

### Meeting the ledger

The baseline's investments are ledger accounts; the portfolio is a separate
book with no link to them. A sale's value must come out of something the
baseline counts, or a scenario makes money from nothing.

**Choice: how holdings meet the baseline?**

| Option | For | Against |
|---|---|---|
| **Link a holding to the investment account that holds it** (`holdings.account_id`, as `debts.account_id` links a debt). The ledger stays the one source of balances; the link says where a holding sits. | The phase-1 pattern. No figure has two sources. | A person must link their holdings. A ledger kept at cost and a portfolio at market price disagree, and the result says so. |
| Value linked investment accounts at their holdings' market value | Investments at market. | Two sources for one balance, and FI moves for everyone who records prices: the inconsistency phase 1 removed. |
| No link; trust the person | Nothing to set up. | A sale of a holding the ledger doesn't count creates money. |

**Recommended: link, ledger first.** A `sell` needs its holding linked to one
of the person's investment-role accounts, and can't take out more than that
account's value on the as-of date ("your ledger holds 1,200.00 in Brokerage
and this sale is worth 1,500.00: bring the ledger up to date, or sell
less"). When a linked account's ledger value and its holdings' value at
recorded prices differ, the baseline's `notes` say by how much, and never
reconcile them silently. An `invest` into a holding needs no link: the money
joins the pool either way.

### One real return

**Choice: buy specific holdings with their own expected returns, or keep
one real return?**

| Option | For | Against |
|---|---|---|
| **One real return for everything**; holdings supply prices, units, lots, fees and gains | No figure invented. Sensitivity and the invest-against-debt break-even stay exact (they vary one return). Salli never sets one security against another. | A person who expects different things of different holdings can't show it. |
| Each holding its own expected return (the person's figure, the base return as placeholder), the pool split by holding | Richer. | An expected return per security is the judgement the guardrails keep from Salli and the agent: comparing them is choosing investments, regulated advice in most places. Sensitivity and break-evens need a return per holding. The baseline changes for everyone who sets one. |
| Per-holding returns only for what a scenario moves | Leaves the baseline alone. | Inconsistent: selling X and buying Y gains Y's return over the base, not over X's. |

**Recommended: one real return.** Holdings make a scenario truer about
prices, fees, units and gains; they don't make it a forecast of securities.
**Where an expected return would come from** therefore doesn't arise: there
is none per holding. The one return is the person's own, or the labelled
4% placeholder, as now. If the owner later wants per-holding returns, they
would be the person's own, stored with a source like an FI assumption,
with the base return as the labelled placeholder, and never a default from
Salli. That is listed as a later step, not phase 3.

### Fees and lots

- **Fees are the person's own figure** (their broker's). No default: left
  out, a fee is zero, and the result says "no fees given".
- **Lots:** first in, first out unless the change names lots, exactly as
  recorded sales work. Where an authority matches by average cost, the gain
  may differ; `lots.py` has no pooling, and the docs say so rather than
  guess which method applies.
- A sale can't take more units than the replay holds on its date (the
  replay's own `TransactionError`, reported with the change's path).

### Never naming a security

Salli never names or suggests a security, and phase 3b keeps that so:

- A change refers to a holding **by the person's own id**. A symbol or a
  holding that isn't theirs is "not found", like any other id. There is no
  way to put a security they don't hold into a scenario.
- Holdings appear **as the person named them** (their symbol and name are
  their data, like an account's name). No list of securities, no market
  data and no expected return per holding is shipped.
- **Templates never pick a holding.** The new `holding` question lists only
  the person's own and has no default, even when they hold one (choosing
  where money goes is the person's, unlike "your only debt").
- **The guardrails are reworded**, in `mcp_server.GUARDRAILS`, the CLI skill
  and docs/ai-clients.md: the agent may refer to the person's own holdings
  as they named them, but never suggests buying or selling any security,
  theirs or another, never compares holdings as investments, and points to a
  licensed professional for choosing investments. Tests hold the prompts to
  the new wording.

### Where it lives

| Layer | Change |
|---|---|
| `domain/scenarios/schema.py` | `holding` and `fees` on `invest`; `SellChange`. |
| `domain/scenarios/holdings.py` (new) | Pure: units at a price, a hypothetical replay (`lots.replay` with the sale appended), proceeds, the gain in both currencies, a later sale's grown price. |
| `domain/baseline/models.py`, `build.py` | `BaselineInputs.holdings`: each holding's transactions, its latest price on or before the as-of date, its link; `Baseline.holdings`, and the note when a linked account and its holdings disagree. |
| `adapters/db/models.py`, migration `core_0019` | `holdings.account_id`, nullable, a foreign key to `accounts`; refused unless an investment-role asset account of the same user. |
| `application/services/portfolio_service.py` | Setting the link (`account_id` on `PATCH /v1/portfolio/{holding_id}`), checked as `debts.account_id` is. |
| `application/services/scenario_service.py` | `holdings_named` beside `accounts_named` and `debts_named`: every holding id is the caller's own. |
| `domain/decisions/templates.py`, `catalogue.py` | A `holding` question type. `debt-or-invest` and `windfall` may name a holding to invest into; no template sells. |
| Interfaces | `salli holdings update --account`, `salli whatif --sell`, MCP descriptions; OpenAPI and the SDK regenerated. |

**Data.** One migration (the link). `ENGINE_VERSION` doesn't move (4,
since 3a): `invest` without a holding is unchanged.

### Out of scope

- Buying a security the person doesn't hold yet (they add the holding first).
- Price, dividend or exchange-rate forecasts; dividends are inside the one
  real return.
- Average-cost pooling, wash-sale or bed-and-breakfast rules: rule sets
  can't express lot matching today, and adding it is engine work with a new
  conformance jurisdiction.

### Risks

- **Ledger and portfolio drift.** Shown as a note; a sale is capped at what
  the ledger holds.
- **The agent overreaching** from "your holdings" to "which holding". The
  guardrails above, and one return so there is nothing to compare.
- **Stale prices.** The price's date is in the result, and `is_stale`-style
  wording when it is older than 45 days, as for the ledger.

### Tests

- **Golden, hand-worked:** a holding in the base currency; bought 10 units
  at 100.00 with 5.00 of fees (a lot costing 1,005.00); a close of 150.00 on
  the as-of date; linked to an investment account holding 1,500.00.
  - Sell 4 units on the as-of date with 2.00 of fees, first in, first out:
    proceeds 600.00, cost 402.00, **gain 196.00**; cash +598.00, investments
    −600.00, net worth −2.00; tagged with an `income` role `gains`, that
    role +196.00.
  - Invest 1,000.00 into it with 4.00 of fees: **6.64 units** at 150.00;
    cash −1,000.00, investments +996.00.
  - A sale of 11 units: refused at `changes[0].quantity`.
  - A sale worth more than the account's 1,500.00: refused, with the
    sentence above.
- **Properties:** a sale and an invest of the same value on the same day,
  with no fees, leave every figure unchanged; with fees, net worth falls by
  exactly the fees; `realised + unrealised = proceeds − fees + value − cost`
  (the lot engine's own invariant) holds on the hypothetical replay; the
  stored transactions are byte-for-byte the same after any scenario.
- **Guards:** a template never builds an option naming a holding the answers
  didn't; no response field holds an expected return per holding;
  `assert_never_ranks` over results with holdings; the prompts carry the new
  guardrail.

## 3. A rent-or-buy template

### The problem

Rent or buy is one of the biggest decisions people make, and the one most
often settled by a rule of thumb ("rent is dead money"). The honest answer
is a comparison resting on a few assumptions the person can see and
question: what the home's value does, what the deposit would have earned,
what owning costs, how long they stay. Salli can lay out those consequences
and say at what house-price growth the answer turns.

### What it asks

`rent-or-buy`, in the style of the six (`domain/decisions/catalogue.py`):

| Question | Type | Default |
|---|---|---|
| The price | `amount` | none: required |
| When you would buy | `date` | the first of next month |
| Your deposit | `amount` | none: required |
| The cash account it comes from | `account` | optional: without one, your cash total |
| One to three mortgages: rate and term | `loans` (existing) | none: required |
| Buying costs (fees and taxes paid once) | `amount_or_zero` (new) | none: required, and 0 is an answer |
| Owning costs a month (maintenance, insurance, service charges, property taxes), in today's money | `amount_or_zero` | none: required |
| Your rent now | `recurring` (new: one of the ledger's recurring outflows, by key), or an amount if the ledger doesn't show it | none |
| How rent grows beyond inflation, a year | `rate` | 0 (it rises with inflation), labelled `rent_growth` placeholder |
| How the home's value grows beyond inflation, a year | `rate` | 0 (it keeps its value in today's money), labelled `asset_growth` placeholder |
| The costs of selling, as a share of the value | `rate` | none: required, and 0 is an answer |
| How many years the long-run figures run | `years` | 20 |

**Choice: should house-price and rent growth have a default?** 2b judged a
placeholder for a price, a rate or a target to be advice in disguise, and
gave such questions no default.

| Option | For | Against |
|---|---|---|
| Required, no default | Consistent with 2b. | The person must state a forecast of their local market before seeing anything, which invites a guess presented as a fact. |
| **0% beyond inflation, labelled as a placeholder, with the break-even beside it** | Not a forecast: it is how the baseline already treats every other asset (`other_assets` keep their value in today's money) and every recurring amount (in today's money). Flagged in `placeholders` and the answer's `source`. The break-even then says exactly what growth the person's own view must beat. | A departure from 2b's rule, for these two rates only. |

**Recommended: the labelled 0% placeholder,** a new default source
`placeholder` whose note says "a placeholder, not a forecast: set your own
view", only for these two rates. Prices, deposits, rates, costs and selling
costs stay required.

### The options it builds

- **Keep renting.** The rent continues: the ledger's rent stopped from the
  date (`stop_recurring`) and put back as a `recurring` cost growing at the
  rent growth, so both options state rent the same way. With no rent in the
  ledger, the rent is added as a new cost (renting somewhere new).
- **Buy, with each mortgage** (one option per offer, as `borrow` does):
  - the home bought on the date (a new `asset` change, below), the price out
    of cash;
  - the mortgage (`loan`, principal = price − deposit, `into` the account),
    so cash falls by the deposit;
  - buying costs (`one_off`), owning costs (`recurring`);
  - the rent stopped from the date (`stop_recurring`).

So each option's FI number moves honestly: buying stops rent and adds owning
costs to the spending to live on, while the home itself funds no
withdrawals (`fi.asset_base`), and the deposit no longer grows as
investments.

### New engine pieces

| Piece | What it does |
|---|---|
| **`asset` change**: `price`, `date`, `from`?, `real_growth`?, `selling_costs`?, `label` | Something bought that holds value. The price leaves cash on the date (a move); the asset joins other assets and grows at its real growth, a twelfth a month, compounded, as investments do. Without `real_growth`, 0 (today's behaviour for other assets), listed as the `asset_growth` placeholder. It closes the scenarios doc's "what a purchase buys, as an asset you own". |
| **`real_growth` on `recurring`** | The amount grows by that much a year beyond inflation, compounded monthly. Default 0: exactly today's behaviour. Used for rent, and for any cost that outpaces prices. |
| **`MonthPoint.other_assets` by month** | Today other assets are a constant; they become a series, the baseline's own plus each asset's value. |

A mortgage is already a `loan` (terms to 600 months, level payments, its
last clearing it). No mortgage-specific code.

**Choice: what an asset counts for in net worth?**

| Option | For | Against |
|---|---|---|
| Its value | Conventional. | Buying looks level on day one, though selling the next day would lose the selling costs; the year buying comes out ahead is flattered. |
| **Its value less its selling costs** ("what it would fetch") | Honest at every month; the break-even year means something. | Net worth drops at purchase by the selling costs, which surprises some. The result says why. |
| A modelled sale at the end | Exact for one horizon. | Needs a "repay the loan on a day" change and a date the person may not know. |

**Recommended: its value less its selling costs,** with the value itself in
the result beside it.

### Break-evens

| Break-even | How | Meaningful because |
|---|---|---|
| **The house-price growth at which buying ends the horizon level with renting** | Bisection on `real_growth` in basis points, −5% to 10%, as `invest_vs_debt` does on the return. "None in range" says which option is ahead throughout. | It turns the person's guess into the question that decides it: "do you expect your home to grow more than 1.3% a year beyond inflation?" |
| **The month buying first draws level and stays at least level** | Read from the monthly timelines, as `cover_target` reads cash: the first month-end from which buying's net worth is at least renting's to the horizon. Not solved: read. | The classic "how long must I stay" figure, exactly. |
| The mortgage rate at which they cost the same | The existing `loan_rate` break-even: a buy option has a loan the rent option doesn't. | Already built. |

Sensitivity stays as it is (the real return ±2 points): it moves what the
deposit would have earned, which is the other half of the comparison.

### Honesty about its assumptions

The template's notes, `start`'s result and docs/templates.md say plainly:

- the home's growth and the rent's are the person's view (or a labelled 0%
  beyond inflation), not a forecast; the break-even is the figure that
  matters;
- the mortgage rate is fixed for its term; resets aren't modelled;
- a home is one asset, illiquid and undiversified; the comparison doesn't
  price that risk;
- owning costs are what the person gives; leaving them low flatters buying;
- tax on buying, owning or selling a home comes only from the person's rule
  sets (a buying tax as a buying cost they give; anything else is out of
  scope for 3c);
- Salli knows nothing about any local property market, and the agent's
  research must cite sources.

### Where it lives

`domain/scenarios/schema.py` (`AssetChange`, `RecurringChange.real_growth`),
`engine.py` (translation), `domain/baseline/timelines.py` (assets in
`Changes`, other assets by month), `comparison.py` (the growth break-even;
the "first ahead" month as a reading, beside `cover_target`),
`domain/decisions/catalogue.py` (`RENT_OR_BUY`), `templates.py` (the
`recurring` and `amount_or_zero` question types; the `placeholder` default
source; `Facts` gains the person's recurring outflows), `start.py` (the two
readings in `salli.decision-start/1`). No migration. `ENGINE_VERSION`
doesn't move (4, since 3a): nothing existing changes.

### Out of scope

A modelled sale and a loan repaid on a day; a mortgage's interest as a tax
deduction (after 3a, a tag on `loan`); shared ownership, offset or
interest-only mortgages; moving costs at the end; property taxes as a rule.

### Risks

The comparison is dominated by two numbers the person supplies (growth and
horizon); the break-evens and labels are the mitigation. A person renting
from family with no ledger rent: the "rent now" question takes an amount.

### Tests

- **Golden, hand-worked:** as of 2031-06-30; no inflation;
  `surplus_invested` 0; rent 1,000.00 a month in the ledger. Buy on
  2031-07-01 for 200,000.00 with 50,000.00 down; a mortgage of 150,000.00
  at 0% over 120 months (1,250.00 a month from August); no buying or owning
  costs; growth 0; selling costs 3% (the home counted at 194,000.00).
  - End of July: cash −50,000.00 + 1,000.00 (July's rent saved), owed
    150,000.00, home 194,000.00: net worth **−5,000.00** against renting.
  - Each month after: −250.00 cash (1,250.00 paid, 1,000.00 of rent saved)
    and 1,250.00 less owed: **+1,000.00** a month.
  - Buying is first level with renting, and stays at least level, at the
    end of **2031-12** (0.00).
  - With selling costs 0: ahead from the end of July (+1,000.00).
- **Properties:** buying's net worth at the horizon never falls as growth
  rises (so bisection is sound); at the found growth buying is level or
  ahead, and a basis point lower it is behind; an asset with growth 0 and
  no selling costs bought for cash leaves net worth unchanged; `real_growth`
  0 on a recurring change gives today's figures exactly.
- **Guards:** `assert_never_ranks` over the start (no "rent is dead money",
  no "better"); the template holds no rate, price or rule beyond the two
  labelled placeholders (a test lists every default and its source).

## 4. The notification port

### The problem

The approved design keeps nudges quiet: in the product, pulled by the agent,
in the CLI. Someone who doesn't open Salli for a month misses a decision
review they asked for, or a filing reminder from their own rules. Phase 3d
adds a way for a deployment to deliver a **digest**, without core sending
anything itself, and without becoming a nag.

### The port

In `application/ports.py`, beside the other seams:

```python
@dataclass(frozen=True)
class NotificationItem:
    kind: Literal["decision_review_due", "reminder_due", "filing_deadline",
                  "cash_below_zero_ahead", "transactions_to_review"]
    title: str          # Salli's own words, from a fixed table
    count: int
    date: str | None    # the earliest date it concerns


@dataclass(frozen=True)
class Notification:
    id: str             # stable: hash of (user, kind, period); the idempotency key
    user_id: str
    kind: Literal["digest"]
    period: str         # "2026-W42" or "2026-10"
    subject: str
    text: str           # plain text, complete as it is
    items: tuple[NotificationItem, ...]
    link: str | None    # SALLI_PUBLIC_URL, when set; never a token


class Delivery(StrEnum):
    SENT = "sent"
    NO_DESTINATION = "no_destination"   # the deployment has nowhere to send it
    FAILED = "failed"                   # retried on the next run, at most three times


class Notifier(ABC):
    @abstractmethod
    async def send(self, notification: Notification) -> Delivery: ...
```

- **Core builds every message**: subject, text and items, deterministic,
  from a fixed wording table in a pure module (`domain/notifications/`). A
  sender renders it (an email, a push, a chat message) and may restyle it,
  but gets nothing else to put in. No model is called.
- **The destination is the deployment's.** Core passes the user's id and
  never stores an email for sending, a push token or a chat id; the
  extension keeps its own (its own tables, migrations, purgers and
  exporters, which the seam already supports) and returns `NO_DESTINATION`
  when it has none.
- **The extension seam:** `Extension.notifier`, merged in
  `extensions.combine` like a meter (two notifiers stop startup).
  `application/defaults.py` gains `NoNotifier`, which sends nothing.
  `salli-server doctor` says which notifier is enabled, if any.

### What triggers one

| Item | From | In by default |
|---|---|---|
| A decision ready for review | reminders with `source_domain` "decision" due, undone | yes |
| A reminder due | the person's own reminders | yes |
| A filing deadline | reminders with `source_domain` "tax_rules" within 14 days | yes |
| Cash forecast below zero | the `low_balance_ahead` signal at `high` | yes |
| Transactions waiting to be reviewed | the `review_waiting` signal | no |

Other signals (a price change, a new recurring charge, a spending spike, the
savings rate) stay in the product: they are interesting, not waiting for the
person. Before building a digest, the job runs `ReminderService.sync_alerts`
for the user, so alerts are current.

**Choice: digests only, or also single messages?** **Recommended: digests
only** in phase 3: one message per period at most, holding everything
waiting. A single "cash runs out" message is the kind of urgency the
design rules out, and a weekly digest is soon enough for everything above.

### Frequency, timing and quiet

- **Off until the person turns it on.** Opt-in, like the daily briefing.
- **Weekly or monthly,** on a weekday and an hour the person picks, in their
  time zone: a new profile field, `time_zone` (IANA), required to opt in.
  Salli's plain default is Monday at 09:00. Every other hour is quiet;
  nothing is sent outside the chosen hour, so "quiet hours" need no setting
  of their own.
- **Nothing waiting, nothing sent.** No "you haven't checked in" message,
  ever.
- **At most one digest a period,** enforced by the delivery log's unique
  key (user, period). A failed send is retried on the next run within the
  same period, at most three times; then it waits for the next period.

### Who configures it

| Who | What |
|---|---|
| **The person** | Opt-in, cadence, day, hour, time zone, and which items (`GET` and `PATCH /v1/notifications/preferences`; `salli notifications show` and `set`). `GET /v1/notifications/preview` (`salli notifications preview`) shows exactly the message that would go now, built by the same code. `GET /v1/notifications/deliveries` (`salli notifications log`) lists what was sent, when, and its items. |
| **The operator** | Installs and enables a notifier extension (`SALLI_EXTENSIONS`), and schedules `salli-server jobs send-digests` hourly in cron; or calls `POST /v1/notifications/cron/send-due` behind `X-Cron-Secret`, as the advisor's cron route works (`EXEMPT` in the CLI's coverage test). |
| **A self-hoster plugging in a sender** | A package with an entry point in `salli.extensions` whose `build` returns `Extension(name=..., notifier=MyNotifier(...))`, holding its own destinations and secrets. docs/self-host.md gets a short example in prose and a snippet; core ships no sender, no SMTP settings and no push keys. |

Without a notifier, the job says "no notifier is enabled" and exits 0, and
preferences still save (the preview works), so a person can set things up
before the operator does.

### Privacy

A digest goes through somebody's mail server, push service or chat
platform. So **a message says what is waiting, never what it is about**:

- **In it:** each item's kind from the fixed table, how many, the earliest
  date, and the link.
- **Never in it:** an amount, a balance, an account's or a payee's name, a
  decision's question or reasons, a note, a rule set's figure, anything from
  the ledger, the person's email.

So "1 decision ready for review (since 2027-04-11)" and "Your cash forecast
goes below zero on 2027-05-02", never the question they decided or the
figure. The delivery log keeps the items (kinds, counts, dates) and the
message's hash, not its text. Erasing the account deletes the preferences
and the log in the same transaction (`delete_all`), and "export my data"
carries both.

**Choice: one level of detail, or a "detailed" option?** **Recommended: one
level, as above,** in phase 3. A detailed option could follow if a
deployment's channel is end-to-end private, but Salli can't know that.

### The "never" list, as tests

From the approved design: no streaks, scores-as-games, countdowns or
urgency. Kept by the wording table and a guard over every message the
builder can produce (all item kinds, counts 1 and many):

- no word from `RANKING_WORDS` (`tests/guardrails.py`), and none from a new
  `URGENCY_WORDS`: urgent, hurry, today only, last chance, don't miss,
  act fast, deadline approaching, streak, in a row, days left, countdown,
  score, level, points, and no `!`;
- no count of consecutive anything; no message when nothing is waiting;
- a date, never "N days left".

A filing deadline says its date and the rules' own label for it, nothing
more pressing.

### Where it lives

| Layer | Change |
|---|---|
| `domain/notifications/` (new) | Pure: the wording table, `build_digest(items, period, preferences)`, a `Notification` or none, the period and the local hour from a time zone. |
| `application/ports.py`, `defaults.py`, `extensions.py` | `Notifier`, `Notification`, `Delivery`; `NoNotifier`; `Extension.notifier`, `Contributions.notifier`. |
| `application/services/notification_service.py` (new) | Preferences, preview, `send_due(now)`: who is due this hour, sync alerts, build, send, log. One user's failure never stops the rest (as `run-advisor` does), and exceptions are logged by type only. |
| `adapters/db/models.py`, migration `core_0020` | `notification_preferences` (user, on, cadence, weekday, hour, items), `notification_deliveries` (id, user, period, items, hash, status, attempts, sent_at; unique user and period); `user_profiles.time_zone`. |
| `interfaces/cli/jobs.py`, routers, `packages/cli` | `salli-server jobs send-digests`; the routes and `salli notifications` commands above. |

### Out of scope

A sender of any kind; instant messages; per-item schedules; digests of the
advisor's AI report (it is a model's text, so it stays in the product);
MCP tools for preferences (they are the person's own switch).

### Risks

- **Nagging.** Opt-in, one digest a period, nothing when nothing waits, and
  the guard.
- **Leaking through a channel.** The privacy rule above, enforced by a test
  that builds digests from a ledger full of distinctive names and amounts
  and checks none appears.
- **Time zones and clock changes.** The job runs hourly and matches the
  local hour through `zoneinfo`; an hour skipped by a clock change sends at
  the next run, and the unique period key stops a repeat.
- **A forgotten scheduler.** `doctor` reports a notifier with no job run in
  the last day, from the delivery log.

### Tests

Without a real sender: a `RecordingNotifier` in tests keeps what it is
given. Unit tests for the builder (each item, the period, the time zone,
nothing waiting); service tests with an injected clock (due this hour or
not, opted out, already sent this period, retry after `FAILED`, stop after
three); `combine` refusing two notifiers; the job with `NoNotifier`; an
integration test that erasing a user removes their preferences and log; the
privacy and "never" guards above; `assert_never_ranks` on every message.

## The order of building

```
3a  tax-aware scenarios ───────────────┬──► 3b  holdings (gains taxed through 3a's tags)
                                       │
3c  rent or buy (engine pieces, then the template) ── after 3a, or beside it
3d  the notification port ──────────── independent, from the start
```

| Sub-phase | Depends on | Can run beside | Why this order |
|---|---|---|---|
| **3a** Tax-aware scenarios | nothing | 3d | The largest, and the tags it adds are what 3b's realised gains feed. It also fixes suggested tax accounts counting as cash. |
| **3b** Holdings | 3a (the sell's `tax_role`) | 3c, 3d | The link, buying and selling could start earlier, but taxing a gain is what makes a sale's figure worth reading. |
| **3c** Rent or buy | nothing in principle; land after 3a | 3d, and 3b | It touches `schema.py`, `engine.py` and `timelines.py` as 3a does; landing after 3a avoids reworking both. Two PRs fit: the engine pieces (`asset`, `real_growth`, other assets by month, the growth break-even), then the template. |
| **3d** Notification port | nothing | everything | Its own modules, tables and job. |

Each sub-phase updates its docs as it lands (docs/scenarios.md,
docs/templates.md, docs/decisions.md, docs/taxrules.md, docs/ai-clients.md,
docs/self-host.md and CLAUDE.md where an invariant is added) and records
"as built" notes in decision-lab.md, as phases 1 and 2 did.

## Risks across phase 3

- **More assumptions, more false precision.** Tax carried forward, house
  growth, a later sale's price. Each is labelled per figure, listed in
  `placeholders`, and paired with the break-even that says what would
  change the answer.
- **The engine's cost.** Tax per year inside bisection, a lot replay per
  sale. Memoised, benchmarked in each PR, and bounded by the 50-change and
  five-option limits.
- **The agent overreaching** into tax advice ("you should contribute more")
  or securities ("sell X"). The guardrails, reworded for holdings; Salli's
  results never say either.
- **Two books meeting.** The holdings link is a new reconciliation, like
  debts' in phase 1, and the notes make every disagreement visible.
- **Scope creep in 3a.** Tax touches the baseline, the scenario engine,
  figures and templates. Goldens first, as phase 1 did: every existing
  golden must pass unchanged before tax is added.

## Decisions (2026-10-12)

Numbered on from the approved design's. The owner accepted each recommendation
as it stands; the sections above give the options that were weighed.

| # | Question | Decision |
|---|---|---|
| 6 | How a scenario's amounts reach tax | A change carries a `tax_role` (only `income` or `deduction` roles); a stopped ledger flow keeps its account's role. Accounts' roles are not used for new changes. |
| 7 | `income_change`'s amount | Renamed `monthly`: net when untagged, before tax when tagged. No alias. |
| 8 | Annual or monthly tax in the timelines | Computed per tax year with the person's rules; the year's change is spread equally over its months from its first tagged amount, a regular flow at each month's end. |
| 9 | Which tax year a month belongs to | A dated amount by its day; a month's projected average by the year containing the month's last day. |
| 10 | A year's role totals | Actual to the as-of date, plus the rest of the year at the baseline's monthly average for the role, plus the scenario's tagged amounts. Withholding projected from history. |
| 11 | Real and nominal | Each year's totals in that year's own money (grown by the person's inflation); the change in tax lands as nominal flows and is deflated like any other. |
| 12 | Years no active rules cover | The latest active rules carried forward with every amount level in today's money, labelled `tax_rules_carried_forward` per year; a year's own active rules always replace them. |
| 13 | No residency, no active rules, a draft, missing answers | Only active rules compute. Otherwise the scenario runs with tagged amounts before tax, `tax.status` `not_computed` with the reason, and `"tax"` among the placeholders. Answers go in the scenario (`tax.answers`). |
| 14 | Does after-tax move FI and the break-evens | Yes, through the regular surplus and the timelines; break-evens rerun with tax. The FI number doesn't include the change in tax. Investment growth stays untaxed; the docs say to set the real return after tax. |
| 15 | A new principle figure | `tax_change_this_year` (nominal), making 33. |
| 16 | Suggested asset accounts | Created with `asset_role` `other`, so a tax-withheld receivable isn't cash. |
| 17 | How holdings meet the baseline | A holding links to the investment-role account that holds it (`holdings.account_id`); the ledger stays the one source of balances. A sale needs the link and can't exceed the account's value; disagreements are noted, never reconciled silently. |
| 18 | One real return, or one per holding | One real return. Holdings supply prices, units, lots, fees and realised gains, never an expected return. Per-holding returns, if ever, would be the person's own figures and are not in phase 3. |
| 19 | A later sale's price | The last recorded price grown at the person's real return (and inflation) to the sale's month, at the as-of exchange rate. No price or rate forecast. |
| 20 | Fees and lots | Fees are the person's, zero when not given and said so. First in, first out unless lots are named; no average-cost pooling in phase 3. |
| 21 | Never naming securities | Holdings only by the person's own id and as they named them; no template default picks a holding; the guardrails reworded to allow the person's own holdings and forbid suggesting or comparing any. |
| 22 | Rent-or-buy defaults | Prices, deposit, mortgages, costs and selling costs required (0 allowed where it is an answer). Rent and house-price growth beyond inflation default to 0, as a labelled `placeholder` source, with the growth break-even beside it. |
| 23 | New engine pieces for rent or buy | An `asset` change (bought from cash, grows at its own real growth, 0 by default); `real_growth` on `recurring`; other assets by month. A mortgage is a `loan`. |
| 24 | An asset in net worth | Its value less its selling costs, with the value shown beside it. |
| 25 | Rent-or-buy break-evens | The house-price growth at which buying ends level (bisection, −5% to 10%); the month buying first draws level and stays at least level (a reading); the existing loan-rate break-even. |
| 26 | The notifier | A `Notifier` port; core builds the whole message; the destination is the extension's. One notifier per deployment through the extension seam; `NoNotifier` by default; core ships no sender. |
| 27 | What a notification is | A digest only, weekly or monthly at the person's chosen local hour; opt-in; nothing sent when nothing waits; at most one per period. |
| 28 | What triggers items | Decision reviews due, reminders due, filing deadlines within 14 days, cash below zero ahead; transactions to review on request. Other signals stay in the product. |
| 29 | What a message may contain | Item kinds, counts, dates and a link. Never an amount, a name, a question, a note or anything from the ledger. One level of detail in phase 3. |
| 30 | The "never" list | Enforced by tests over every message: no ranking or urgency words, no streaks or countdowns, no `!`. |
| 31 | The order | 3a, then 3b; 3c after 3a (two PRs: engine, then template); 3d beside any of them. `salli.scenario/1` keeps its id; `ENGINE_VERSION` moves only if an existing figure changes. |
