# Scenarios

A scenario is your [baseline](baseline.md) plus changes: a purchase, a loan,
a new rent, a raise, an extra payment on a debt, money invested, a
subscription cancelled. Salli runs it and reports every figure twice, under
your baseline and under the scenario, with the change between them. Nothing
is stored and nothing touches your books.

To weigh a decision, build each option as a scenario and compare them.
Salli shows what each option gains and gives up against the others, how the
answer moves with the return you assume, and the values at which it would
change. It never says which option is best: that is yours to weigh, with your
agent's help if you like.

    salli whatif --buy 2400@2026-11-02
    salli whatif --buy 2400 --loan 2400@6.9%x12 --label Instalments --save instalments.json
    salli compare cash.json instalments.json

Over the API: `POST /v1/scenarios/run` and `POST /v1/scenarios/compare`.
Over MCP: `run_scenario`, `compare_options`, and `get_scenario_schema` for
the document's JSON Schema.

## The document

A scenario is a JSON document, `salli.scenario/1`, so an agent can write one
reliably and you can keep one in a file.

```json
{
  "schema": "salli.scenario/1",
  "label": "Car on finance",
  "as_of": "2026-10-11",
  "horizon_years": 20,
  "changes": [
    { "type": "one_off", "date": "2026-12-01", "amount": "-18000.00", "account": "<checking's id>",
      "label": "The car" },
    { "type": "loan", "principal": "18000.00", "annual_rate": "0.069", "term_months": 48,
      "start": "2026-12-01", "into": "<checking's id>", "label": "Car loan" }
  ]
}
```

| Field | What it is |
|---|---|
| `schema` | Always `"salli.scenario/1"`. |
| `label` | What to call it. In a comparison, how the option is named. |
| `as_of` | The day your baseline is as of: today when you leave it out, never a day after today. |
| `horizon_years` | How far the monthly figures run: a whole number from 1 to 50. 20 when you leave it out. |
| `changes` | Up to 50 changes, below. |

The rules:

- **Amounts and rates are decimal strings**: `"-2400.00"`, `"+600"`,
  `"0.069"`. A JSON number is refused, because whoever wrote `0.1` may have
  meant it exactly and whatever serialised it may not have. A rate is a
  yearly fraction: `"0.069"` is 6.9%.
- **Amounts are in your base currency**, to its smallest unit: two decimals
  for euros, none for yen. Money in is positive, money out negative.
- **Dates are ISO** (`YYYY-MM-DD`) and on or after the as-of date: a scenario
  changes what comes next, not what happened.
- **Accounts and debts are yours.** An account a change names is one of your
  cash accounts held in your base currency; without one, a change moves your
  cash total. A debt is one of your active debts (`salli debts list`). Anyone
  else's id is "not found", exactly like one that doesn't exist.
- **Unknown fields are refused**, each problem with its path
  (`changes[2].amount`), every problem at once.

## Changes

| Type | Fields | What it does |
|---|---|---|
| `one_off` | `date`, `amount`, `account`?, `label` | Money in or out once. What a purchase buys isn't counted as an asset. |
| `recurring` | `amount`, `cadence` (`weekly`, `monthly`, `quarterly`, `yearly`), `start`, `end`?, `account`?, `label` | The same amount again and again: every seven days, or every one, three or twelve months on the start's day of the month. |
| `income_change` | `monthly_net`, `from`, `to`?, `label` | Your monthly net income changes, from a day's date each month. |
| `loan` | `principal`, `annual_rate`, `term_months` (1 to 600), `start`, `into`?, `label` | The money arrives on its start day. It is owed from that month's end and repaid in level monthly payments from the next month, rounded to your currency's smallest unit; the last payment clears what the rounding left. |
| `extra_debt_payment` | `debt`, `monthly`, `from`, `to`?, `label`? | Paid on one of your debts on top of its minimum, each month from `from`'s month to `to`'s, or until it is paid off. Debts are paid from the month after the as-of month. |
| `invest` | `amount`, `date`, `from`?, `label` | Cash moved into your investments, where it then grows at your real return. |
| `stop_recurring` | `key`, `from`, `label`? | A recurring flow your ledger shows stops: cancel a subscription. `salli insights recurring` lists each one's key. A transfer between your own accounts can't be stopped this way: it is no part of what you earn or spend. |

Fields marked ? are optional.

**Today's money or the day's own.** Recurring amounts, income changes and
stopped flows are in today's money: with your inflation set, each rises with
it, as your average spending does. One-offs, investments, loan payments and
extra payments are fixed in the money of their own day. With no inflation
set, the two are the same, and every result says inflation is a placeholder.

## What comes back

Every figure is `{"baseline", "scenario", "delta"}`. Money is a decimal
string in your currency's precision. A month's change is in months
(`delta_months`, later is positive), a day's in days.

| Area | Figures |
|---|---|
| **Cash, the next twelve months** | The lowest your cash gets and the day; each cash account at its lowest, and which go below zero; cash at the end of the twelfth month; safe-to-spend until your next income (the baseline's window, so the two compare). |
| **Monthly, in today's money** | Net worth, cash, investments and debts at 1, 5, 10 and 20 years and at the horizon. |
| **Debts** | Each debt's payoff month and interest, and a new loan's; the interest on all of them; the month you are debt-free. |
| **Resilience** | The months of spending your cash covers at its low point and at the end of the year: over essential spending when your spending carries need tags, over all of it otherwise. |
| **FI** | The FI number, the month you reach it, and the months gained (positive) or lost. |

Cash earns nothing, investments grow at your real return, and debts follow
their schedules, as on the [baseline's monthly timeline](baseline.md#the-two-timelines).
The FI month and the debts' payoff are found wherever they fall within 50
years, whatever horizon you choose.

**The FI number** is a year of the spending you would live on, over your
safe withdrawal rate. Under a scenario it is built on the spending the
scenario leaves for good: a recurring cost with no end adds to it, a
cancelled subscription takes from it, and a one-off, a loan or an income
change leaves it as it is. A FIRE strategy that names its own target
spending keeps that target.

**Break-evens on one scenario.** For each recurring cost in a scenario whose
cash goes below zero in the next twelve months, the most it could be, each
time, with cash staying at or above zero: solved to the cent (or your
currency's smallest unit). "None in range" means cash goes below zero even
without it.

**What every result records**, so it can be checked and reproduced:

- the assumptions it used, each with where it came from, and which are
  placeholders (`placeholders`);
- the versions behind it: the document's schema, the engine, a content hash
  of the FI assumptions, your FIRE strategy's version, and the active tax
  rule sets that cover the as-of date;
- the as-of date, and how fresh your ledger is (`data_as_of`; `is_stale`
  when its newest entry is more than 45 days old);
- `hash`: a content hash of the scenario (its as-of date filled in) and of
  everything your baseline was built from (`baseline_fingerprint`). Key order
  and how an amount was written don't change it. The same hash means the same
  figures.

## Comparing options

`salli compare a.json b.json` (or `compare_options`) takes two to five
scenarios with one as-of date and one horizon, each with its own label. An
option without a label is named after its file, or "Option n".

- **Side by side.** Each option's figures, as a run gives them, against one
  baseline.
- **The trade.** For each option against each other one, the figures where
  it comes out ahead (`gains`) and behind (`gives_up`), as deltas: more cash,
  net worth or investments is ahead; fewer debts, less interest, a smaller FI
  number and an earlier month are ahead. That is all it says. No figure is
  weighed against another, and no option is called better.
- **Sensitivity.** The options' net worth at the horizon and FI month under
  the conservative and growth real returns as well as the base one: the base
  less and plus two points, or your FIRE strategy's own three. Cash earns
  nothing, so only the long-run figures move. If an option's lead holds at
  all three, it doesn't rest on the return; if it flips, the return you
  expect decides it.
- **Break-evens**, each with a sentence (`says`) saying what it means:
  - **The return at which investing beats paying down a debt**, where one
    option invests and the other pays a debt down instead: the lowest real
    return, to a basis point (0.01%), between -5% and 15%, at which the
    investing option ends the horizon with at least the other's net worth.
  - **The most a recurring cost can be** with cash staying above zero, as for
    one scenario.
  - **The loan rate at which two financing options cost the same**, where an
    option has a loan the other doesn't: the highest rate, to a basis point,
    between 0% and 100%, at which it ends the horizon with at least the other
    option's net worth.

  Each is solved by bisection on whole numbers (cents, basis points), so the
  same inputs always give the same answer. "None in range" says which option
  is ahead across the whole range (`ahead`).

A break-even turns "it depends" into "it depends on whether you expect more
than 1.9% a year after inflation". That is a question you can answer, or ask
your agent to research with sources.

### Reading one: cash or instalments

A laptop for 2,400.00, paid at once or over 12 months at 6.9%:

| | Baseline | Pay cash | Instalments |
|---|---:|---:|---:|
| Lowest cash | 15,740.01 | 15,072.91 | 15,740.01 |
| Interest on debts | 2,009.25 | 2,009.25 | 2,099.93 |
| Net worth in 5 years | 473,816.13 | 471,416.13 | 471,325.45 |

Instalments keep the low point where it was and cost 90.68 of interest
(eleven payments of 207.55 and a last of 207.63); paying cash costs no
interest and takes the low point down by 667.10. The loan-rate break-even is
0%: with no inflation set, any rate above it costs more than paying cash.
Which matters more, the buffer or the 90.68, is yours to say.

## For agents

- Build every option with the schema (`get_scenario_schema`), and let Salli
  run and compare them. Never subtract, add, divide or project anything
  yourself, not even roughly.
- Quote Salli's figures, with their currency, and the sentence of each
  break-even.
- Name the assumptions that are placeholders. If `is_stale` is true, ask the
  user to bring their ledger up to date before deciding.
- Never say which option is best. Lay out the trade, the sensitivity and
  what would change the answer, and leave the choice to the user.
- A problem comes back with its path (`changes[0].date: is before the as-of
  date`): fix the document and run it again.

## Not modelled yet

- Tax: a change to your income doesn't yet run through your tax rules.
- A recurring surplus invested each month: an `invest` change moves one
  amount on one day. Your surplus stays in cash, which earns nothing, as on
  the baseline.
- What a purchase buys, as an asset you own.
- Amounts in a currency other than your base currency, and accounts held in
  one.
- The day within its month a debt's payment falls on.
