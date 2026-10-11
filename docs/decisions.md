# Principles and the decision journal

Salli computes the consequences of a decision ([scenarios](scenarios.md)),
your agent helps you reason about them, and you decide. Two things keep
what matters to you, and what you decided, with your money:

- **Principles**: your own rules of thumb, which Salli checks every option
  against. They are the only "should" Salli ever reports, and they are
  yours.
- **The decision journal**: a record of each decision you choose to keep:
  the options as Salli ran them, what you chose, and your reasons in your
  own words. It can't be edited or deleted. On the date you pick, Salli
  shows you what the option you chose projected against what happened.

```
salli principles add "Six months of essentials in cash" --check "emergency_months >= 6"
salli principles check cash.json instalments.json
salli decisions record --question "Laptop: pay cash or spread it?" \
    --option cash.json --option instalments.json --chosen "Pay cash" \
    --reasons "I'd rather not owe anything." --review-on 2027-04-11
salli decisions reviews
```

Over the API: `/v1/principles` and `/v1/decisions`. Over MCP:
`list_principles`, `add_principle`, `check_principles`, `record_decision`,
`list_decisions`, `get_decision`, `list_due_reviews` and `review_decision`.

## Principles

A principle is a label and a check: a statement that is true or false over
the figures below, written in the same safe expression language as tax
rules. It is parsed and evaluated by Salli, never by a model, so the same
figures always give the same answer.

```json
{ "schema": "salli.principle/1", "label": "Six months of essentials in cash",
  "check": "emergency_months >= 6" }
{ "schema": "salli.principle/1", "label": "Clear debt above 7% before investing",
  "check": "max_debt_rate_while_investing <= 0.07" }
{ "schema": "salli.principle/1", "label": "Never below 2,000 in checking",
  "check": "account_lowest >= 2000", "account": "<checking's id>" }
```

A check may use the figures by name, numbers (`2_000`, `0.07`),
comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`), `and`, `or`, `not`,
arithmetic (`+ - * /`) and `min`, `max`, `abs`, `clamp`, `round` and `if`:
`lowest_cash >= 6 * monthly_spending`, `not any_account_below_zero and
fi_months_gained >= 0`.

Salli checks a principle when you add or edit it, and refuses it with each
problem and where it is: a figure that doesn't exist (with the nearest
name), a check that is a number rather than true or false, `account_lowest`
without an account, an account that isn't one of your cash accounts.

Principles are preferences, not records: you can edit one (its version
counts up) or archive one (it stays, unused). A decision already recorded
keeps each principle as it stood, with its version and content hash.

### The figures

Every figure is computed for your baseline and for each option, from the
same timelines as [scenarios](scenarios.md), and is the value Salli shows
you: an amount to your currency's smallest unit, months of spending to the
hundredth, a rate exactly. **Nominal** amounts are in each day's or month's
own money; **real** ones in today's money. `salli principles figures` (or
`GET /v1/principles/figures`) lists them.

| Figure | Unit | What it is |
|---|---|---|
| `lowest_cash` | amount, nominal | The lowest your cash accounts together get on any day of the as-of month and the twelve after it. |
| `cash_in_12_months` | amount, nominal | Your cash at the end of the twelfth month. |
| `safe_to_spend` | amount, nominal | What could go out on the as-of date without cash dropping below zero before money next comes in. |
| `account_lowest` | amount in the account's currency, nominal | The lowest the principle's own account gets over the same months. Needs the principle's `account`. |
| `any_account_below_zero` | true or false | Whether any cash account goes below zero over the same months. |
| `monthly_spending` | amount, real | The spending emergency months are counted in: essential spending when your spending carries need tags, all of it otherwise. |
| `emergency_months` | months | The months of that spending your cash covers at its lowest. |
| `emergency_months_in_12_months` | months | The same at the end of the twelfth month. |
| `net_worth_1y`, `_5y`, `_10y`, `_20y` | amount, real | Net worth at the end of the month 1, 5, 10 or 20 years on. |
| `cash_1y` … `cash_20y` | amount, real | Cash, likewise. |
| `investments_1y` … `investments_20y` | amount, real | Investments, grown at the real return, likewise. |
| `debts_1y` … `debts_20y` | amount, real | What debts with terms (and the option's loans) still owe, likewise. |
| `total_interest` | amount, nominal | The interest every debt and loan costs over its schedule. |
| `debt_free_months` | months (whole) | Months from the as-of month until the last debt is paid off; 0 when nothing is owed. |
| `max_debt_rate` | rate | The highest yearly rate of any debt owed at any month's end in the next 50 years, the option's loans included; 0 when nothing is owed. |
| `max_debt_rate_while_investing` | rate | The highest yearly rate of any debt still owed at the end of a month in which money moves into investments (the share of your surplus you invest, or an invest change); 0 when no debt is owed while you invest. |
| `borrowed` | amount, nominal | What the option borrows: its loans' principal together; 0 for your baseline. |
| `fi_number` | amount, real | A year of the spending you would live on, over your safe withdrawal rate. |
| `fi_months` | months (whole) | Months from the as-of month to the month you reach it. |
| `fi_months_gained` | months (whole) | Months sooner (positive) or later (negative) than your baseline; 0 for your baseline. |

The monthly figures come from the 50-year timeline whatever horizon a
scenario shows, so a check at ten years works on a five-year scenario.

A figure Salli can't give is missing, with the reason: no spending in your
ledger to count months of, FI not reached within 50 years, an account the
forecast doesn't carry. A check that reads a missing figure **can't tell**;
it is never counted as kept or broken.

`max_debt_rate_while_investing` reads the share of your surplus you invest
(`surplus_invested`): while that is the placeholder, all of it, every month
invests while any debt is owed, so "clear dear debt before investing" is
broken by any debt dearer than its limit. Set your own share first (`salli
fi assumptions set surplus_invested …`).

### Checking

`salli principles check a.json b.json` (`POST /v1/principles/check`,
`check_principles`) runs none to five options on your baseline and says,
for your baseline and for each option, which principles it **keeps**,
**breaks** or **can't tell**, with the figures each check read and a
sentence saying why (`account_lowest >= 5000 doesn't hold: account_lowest
is 4883.77.`). Nothing is stored, and nothing is counted or ranked: an
option that keeps more principles is not "better", because which principle
matters most is yours to weigh.

## The decision journal

When you decide, you can record it. Salli runs every option itself, on
your baseline as of the day (your own accounts and debts only), checks your
principles, and keeps an entry (`salli.decision/1`):

| Field | What it holds |
|---|---|
| `question` | What you were deciding, in your words. |
| `options` | Each option as recorded: the scenario document as run, its content hash (`scenario_hash`), its figures (the principle figures above), each principle's check, and what it projected month by month (`projection`) from the as-of date to a year past the review date: cash, investments, what is owed, net worth and spending, in each month's own money. |
| `baseline` | Your baseline's figures and checks, for comparison. |
| `basis` | What every option rests on: the baseline's fingerprint, the engine's and the FI assumptions' versions, the assumptions with the placeholders flagged, and how fresh your ledger was. |
| `principles` | Your principles as they stood, each with its version and hash. |
| `chosen` | The label of the option you chose. |
| `reasons` | Your reasons, in your own words. |
| `agent_summary` | Your agent's summary, if there is one, marked as the agent's (`author: "agent"`) and named. |
| `review_on` | When to look back: from the end of the as-of month on. |
| `recorded_at`, `recorded_via` | When, and how: the API, or an agent over MCP with your confirmation. |

Recording sets a reminder for the review date (with your other reminders,
`source_domain` "decision").

### Append-only

An entry can't be edited or deleted, through any interface: there is no
route, command or tool that does it, the storage only adds, and the
database itself refuses a change. What you think later is appended:

- **Notes** (`salli decisions note`, `POST /v1/decisions/{id}/notes`), each
  its own document (`salli.decision-note/1`).
- **Reviews** (below), each its own document (`salli.decision-review/1`).

Each names the hash of the entry it is about. Erasing your account erases
your journal with it, and only then.

### The hash, and checking it

An entry's `hash` is the SHA-256 of its canonical JSON: keys sorted, no
whitespace, ASCII only (anything else as `\u` escapes), every amount and
rate a decimal string. Salli returns entries exactly as recorded, so anyone
holding one (or the JSON export) can recompute the hash and see it is
unchanged, without Salli:

```python
import hashlib, json
def digest(document):
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()
```

Salli does the same on every read and says so (`verified`). Notes and
reviews have hashes of their own, in the same way.

### Reviews

From the review date on, the decision is **due** (`salli decisions
reviews`, `GET /v1/decisions/reviews`, `list_due_reviews`, and a
`decision_review_due` signal). A review compares at a month's end: the last
one on or before the day you review (that day itself, if it is one). There,
what the option you chose projected meets your baseline as of that day:

- cash, investments, what is owed and net worth, each in that day's own
  money;
- spending a month, on average over the full months since the decision
  (the as-of month was already under way), projected against what your
  ledger shows you spent.

Each comes with the difference, actual less projected. Nothing is judged:
a difference is what happened, and why is yours to say. The other options'
projections for the same day are shown beside it, as what they expected,
never as what would have happened. If your ledger hasn't been kept up to
date, the review says so first: what happened is only what the ledger
shows.

You add your reflection, in your own words (`salli decisions review <id>
--reflection …`, `POST /v1/decisions/{id}/review`), and the review is
appended with Salli's comparison; the reminder is done. You can review
again later; each review appends.

### Export

`salli decisions export` writes the journal as Markdown, to read or keep;
`--format json` (`GET /v1/decisions/export`) as one document
(`salli.decision-journal/1`) holding every entry, note and review exactly
as recorded, each with its hash. "Export my data" carries it too.

## For agents

- **Never compute.** Every figure comes from Salli's tools. Quote a
  check's `reason`, a comparison's figures and differences.
- **Principles are the person's.** Respect them when you lay out options;
  never count, score or rank options by them. You may suggest a principle
  from what someone tells you matters to them, as a suggestion: store it
  (`add_principle`, with `confirmed_by_user: true`) only after they have
  seen the exact label and check and said yes.
- **Never record a decision the person hasn't confirmed**, and never
  choose for them. When they have decided, offer to record it: show them
  the question, the options, the one they chose, their reasons and the
  review date, and call `record_decision` with `confirmed_by_user: true`
  only after their yes. Their reasons are their words, not yours; your own
  summary goes in `agent_summary`, where it is recorded as yours.
- **Reviews.** Pull due reviews (`list_due_reviews`) when the person talks
  to you, walk them through Salli's comparison, ask what they make of it,
  and record their reflection (`review_decision`, `confirmed_by_user:
  true`) only when they agree to the words.
- An entry is permanent. Don't offer to change one; a note says what has
  changed since.

## Not yet

- Templates for common decisions, `salli decide`, the
  `think_through_decision` prompt (phase 2b).
- Reviews compare at month-ends, in nominal money; a review doesn't yet
  attribute a difference to the assumption behind it.
- Tax: an option's change in tax isn't among the figures (phase 3).
