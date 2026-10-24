# Scenarios

A scenario is your [baseline](baseline.md) plus changes: a purchase, a loan,
a new rent, a raise, an extra payment on a debt, money invested, part of a
holding sold, a subscription cancelled, a home bought. Salli runs it and reports every figure twice, under
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
    salli whatif --sell FUND:4 --fees 2 --gain-tax-role gains

Over the API: `POST /v1/scenarios/run` and `POST /v1/scenarios/compare`.
Over MCP: `run_scenario`, `compare_options`, and `get_scenario_schema` for
the document's JSON Schema. For common decisions, a
[template](templates.md) builds the options for you.

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
| `tax`? | `{"answers": {"<key>": value}}`: answers to your tax rules' questions (a filing status, say), for changes tagged with a tax role ([Tax](#tax)). |

The rules:

- **Amounts and rates are decimal strings**: `"-2400.00"`, `"+600"`,
  `"0.069"`. A JSON number is refused, because whoever wrote `0.1` may have
  meant it exactly and whatever serialised it may not have. A rate is a
  yearly fraction: `"0.069"` is 6.9%.
- **Amounts are in your base currency**, to its smallest unit: two decimals
  for euros, none for yen. Money in is positive, money out negative.
- **Dates are ISO** (`YYYY-MM-DD`) and on or after the as-of date: a scenario
  changes what comes next, not what happened.
- **Accounts, debts and holdings are yours.** An account a change names is
  one of your cash accounts held in your base currency; without one, a change
  moves your cash total. A debt is one of your active debts (`salli debts
  list`), a holding one of your holdings (`salli holdings list`). Anyone
  else's id is "not found", exactly like one that doesn't exist, so no
  security you don't hold can get into a scenario.
- **Unknown fields are refused**, each problem with its path
  (`changes[2].amount`), every problem at once.

## Changes

| Type | Fields | What it does |
|---|---|---|
| `one_off` | `date`, `amount`, `account`?, `tax_role`?, `label` | Money in or out once. What a purchase buys isn't counted as an asset: an `asset` change is. |
| `recurring` | `amount`, `cadence` (`weekly`, `monthly`, `quarterly`, `yearly`), `start`, `end`?, `account`?, `tax_role`?, `real_growth`?, `label` | The same amount again and again: every seven days, or every one, three or twelve months on the start's day of the month. With a `real_growth` (a signed yearly fraction, `"0.01"`), it grows by that much a year beyond inflation, a twelfth a month, compounded, from its start's month: a rent rising faster than prices. Without one, it keeps its value in today's money, as before. |
| `income_change` | `monthly`, `from`, `to`?, `tax_role`?, `label` | Your monthly income changes, from a day's date each month: what reaches your cash, or, with a `tax_role`, before tax. |
| `loan` | `principal`, `annual_rate`, `term_months` (1 to 600), `start`, `into`?, `label` | The money arrives on its start day. It is owed from that month's end and repaid in level monthly payments from the next month, rounded to your currency's smallest unit; the last payment clears what the rounding left. |
| `extra_debt_payment` | `debt`, `monthly`, `from`, `to`?, `label`? | Paid on one of your debts on top of its minimum, each month from `from`'s month to `to`'s, or until it is paid off. In the as-of month, before the debt's first payment, it is paid at the month's end ([below](#in-the-as-of-month)). |
| `invest` | `amount`, `date`, `from`?, `holding`?, `fees`?, `label` | Cash moved into your investments, where it then grows at your real return. Fees (yours) leave cash with the amount and never reach the investments. Into one of your holdings, it also buys units at its price ([below](#holdings)). |
| `sell` | `holding`, `quantity` or `amount`, `date`, `fees`?, `lots`?, `into`?, `tax_role`?, `label`? | Part of one of your holdings sold: its value leaves your investments, and the proceeds less fees arrive in cash. Salli replays its lots and reports the gain you would realise ([below](#holdings)). |
| `stop_recurring` | `key`, `from`, `label`? | A recurring flow your ledger shows stops: cancel a subscription. `salli insights recurring` lists each one's key. A transfer between your own accounts can't be stopped this way: it is no part of what you earn or spend. |
| `set_aside` | `monthly`, `from`, `to`?, `label`? | Part of each month's surplus kept in cash, rather than shared out: saving towards an emergency fund or a purchase. Each month from `from`'s month to `to`'s (or for good), that much of the regular surplus stays in cash first, and the share you invest is of what is left. It can't keep more than the month's surplus. |
| `asset` | `price`, `date`, `from`?, `real_growth`?, `selling_costs`?, `label` | Something bought that holds its value: a home. The price leaves cash on the day; the asset counts among your other assets from that month's end, growing at its `real_growth` a year beyond inflation (a twelfth a month, compounded, from the next month; a signed fraction, 0 without one, labelled the `asset_growth` placeholder). It counts in net worth at what it would fetch: its value less `selling_costs`, a share of it (`"0.03"` is 3%; 0 without). Like your other assets it funds no withdrawals, so FI doesn't count it. A mortgage is an ordinary `loan`. |

Fields marked ? are optional. An amount is what reaches your cash, unless
the change carries a `tax_role`: then it is before tax, and Salli works out
the tax ([below](#tax)).

**Regular, or a move.** Recurring changes, income changes and stopped flows
are part of your regular surplus, and are shared out like your baseline's
own: the share of it you invest (`surplus_invested`, all of it as a
placeholder) goes into your investments at each month's end, the rest stays
in cash. One-offs, a loan's money, investments, an asset's price and extra payments are moves:
they go in or out of cash, and only where they say. A loan's payments, like
your debts', are scheduled: they come out of the regular surplus, and once
the loan or debt is paid off its payment is freed into it, including when an
extra payment cleared it early. A set-aside is neither: it moves no money of
its own, but keeps part of the regular surplus in cash before the rest is
shared out, so less is invested. A month whose regular surplus is a deficit
invests nothing and draws on cash, never on your investments; if cash runs
out, it goes below zero and the result's `notes` say from when. See
[the baseline](baseline.md#your-surplus-and-what-you-invest-of-it).

### In the as-of month

A debt's first scheduled payment falls in the month after the as-of month,
and a loan's in the month after it is taken out. An extra payment in the
month before (the as-of month for your debts; for a loan, the month it is
taken out) counts all the same, as a one-off on its day does. It is paid at
that month's end, up to what the debt owes, out of your cash: the debt owes
that much less before its schedule starts, and the next month's interest is
on what is left. A payment that clears the debt pays it off in that month;
nothing more is scheduled, and its payment joins your regular surplus from
the next month, as any paid-off debt's does. On the daily timeline it
leaves cash as every extra payment does, spread over the rest of its month.

**Today's money or the day's own.** Recurring amounts, income changes and
stopped flows are in today's money: with your inflation set, each rises with
it, as your average spending does (and a recurring amount by its
`real_growth` beyond it). One-offs, investments, sales, an asset's price,
loan payments, extra payments, amounts set aside and the change in tax are
fixed in the money of their own day. An asset is counted in today's money
from the month it is bought: its price deflated to that month, grown by its
real growth after it. With no inflation
set, the two are the same, and every result says inflation is a placeholder.

## Tax

A raise of 1,000 a month is not 1,000 a month in the bank. Tag a change
with a **tax role** (`tax_role`) and its amount is before tax: Salli runs it
through your own active [tax rules](taxrules.md) and takes the change in
tax out of cash for you. Never work the net figure out yourself, and never
let an agent do it: tag the gross one.

    salli whatif --income +1000/month@2027-01-01 --tax-role salary

- **Which roles.** A role your rule sets declare, of kind `income` or
  `deduction`. Money in adds to an income role (a cut subtracts); money out
  adds to a deduction role (a pension contribution, a deductible cost; a
  refund subtracts). Withholding is projected from your ledger, and an
  `other` role has no direction, so neither can be tagged. A role none of
  your rule sets declares is refused with its path, as a mistyped id is.
  `one_off`, `recurring` and `income_change` take a tag; a `stop_recurring`
  needs none: the flow it stops comes off its account's own tax role.
- **Each tax year's totals.** For each year the scenario touches, from the
  one containing the as-of date, each role's total is projected twice, for
  your baseline and for the scenario: what your ledger shows from the
  year's start to the as-of date, plus the rest of the year at the role's
  monthly average (over the months your baseline observes, grown with your
  inflation), plus, for the scenario, the tagged amounts dated in the year.
  A dated amount belongs to the year containing its day; a month's average
  to the year containing the month's last day. The totals are in each
  year's own money, converted into your rules' currency at each entry's
  rate (what has happened) or the as-of date's (what is projected).
- **The change in tax** is the scenario's `net` less your baseline's, from
  the same rules and your answers to their questions (the scenario's
  `tax.answers`). Withholding is projected from history and a tagged raise
  doesn't change it, so the change is the whole extra tax: withheld more,
  or settled.
- **Applied monthly.** Each year's change is spread equally over the months
  from the year's first tagged amount to its last month, each part rounded
  to your currency's smallest unit and the last taking what rounding left,
  as a regular cash flow at each month's end. So it moves the regular
  surplus, what you invest, your cash, net worth and the FI month, as a
  recurring cost would. If you settle once a year, you see the cash a
  little early.
- **Years with no rules of their own** carry your latest active rules
  forward, with every amount in them held level in today's money (the
  totals deflated by your inflation to the rules' year, evaluated, and the
  tax grown back), labelled `tax_rules_carried_forward` in `placeholders`
  and on each such year. A year with its own active rules always uses them.
- **Only active rules compute.** With no residency, no rule set, only
  drafts, a role the year's rules don't declare, a question with no answer
  and no default, or a missing exchange rate, the scenario still runs:
  tagged amounts count before tax, `tax.status` is `"not_computed"`,
  `tax.reason` says what is missing and what to do, and `"tax"` is among the
  placeholders.
- **What tax doesn't touch.** The FI number: the tax on a salary is not
  spending to live on once it has stopped. Investment growth: no role
  taxes it, so set your real return after the tax you pay on it. Tax on
  withdrawals in retirement, when tax is settled, and a loan's interest as
  a deduction are out of scope.

The result's `tax` section:

| Field | What it holds |
|---|---|
| `status`, `reason` | `"computed"`, `"not_computed"` (with why), or `"none"` (nothing tagged; no rules are read). |
| `years` | The first two tax years touched, and those of the monthly checkpoints (the timeline uses every year): each year's dates, its `status`, the `rules` that computed it (with `carried_forward`), each touched role's `actual`, `projected` and `scenario` totals in the rules' currency, `net` under each, the `change` in your base currency, and the `monthly` parts. |
| `this_year` | The as-of date's tax year, as in `years`, when the scenario touches it. |
| `change_this_year` | The change in that year's tax: 0 when nothing in it is tagged, null when it isn't computed. The principles' figure `tax_change_this_year`. |
| `total_change` | The change in tax over the horizon, in today's money. |

The break-evens rerun everything, the tax included, at each step, so the
cash floor of a tagged cost and the loan rate at which two options cost the
same are after tax. Each year's evaluation is memoised, so this stays quick.

**Read the totals.** The tax is only as right as your books: a salary booked
net, with no gross and no withholding, gives the wrong tax. The result shows
the totals it used, so you can check them; a bonus month in your history
lifts the average. See the [worked example](#reading-one-a-raise-before-tax).

### Reading one: a raise before tax

Rules of a fictional country, XA, for 2031: a relief of 12,000, then 20%
to 40,000 and 40% above. As of 2031-06-30, with a salary of 4,000 a month so
far, the year's salary is projected at 24,000 + 6 × 4,000 = 48,000, taxed
7,200.00. A raise of 1,000 a month from July, tagged `salary`, makes it
54,000: 8,000.00 + 800.00 = 8,800.00. The change, 1,600.00, comes out of
cash July to December, 266.67 a month and 266.65 in December, so each
month's surplus rises by 733.33 rather than 1,000.00. In 2032, with no rules
of its own, the 2031 rules carried forward tax 60,000 at 11,200.00: 4,000.00
more, 333.33 a month (333.37 in December), labelled
`tax_rules_carried_forward`.

## Holdings

An `invest` may go into one of your holdings, and a `sell` sells part of
one, so a scenario can say what a sale fetches, what fees take and the gain
you would realise, from the holding's own lots. The investments stay one
pool growing at your one real return: holdings give prices, units, lots,
fees and gains, never an expected return of their own, so sensitivity and
the break-evens still vary one figure, and Salli never sets one security
against another.

- **Your holdings, by your id.** A change names a holding by its id, and the
  result calls it by your symbol and name. There is no way to put a security
  you don't hold into a scenario: add the holding first.
- **The ledger counts.** Your investments are your investment accounts in
  the ledger. A sale needs its holding linked to the investment account that
  holds it (`salli holdings update FUND --account brokerage`, `PATCH
  /v1/portfolio/{id}` with `account_id`), and can't take out more than that
  account's value on the as-of date, counted at the holding's price on that
  date and after the scenario's earlier trades on that account's holdings:
  "your ledger holds 1,200.00 in Brokerage and this sale is worth 1,500.00:
  bring the ledger up to date, or sell less". An invest needs no link: the
  money joins the pool either way. Where a linked account and its holdings'
  value at their recorded prices differ, the baseline's `notes` say by how
  much; nothing is reconciled silently.
- **The price** is the holding's last price recorded on or before the as-of
  date (a close you recorded, or one of its own trades), adjusted for splits.
  A trade in a later month is at that price grown at your real return and
  inflation through the months before the trade's month, the growth your
  investments have in the monthly timeline; every trade converts at the
  as-of exchange rate. Salli forecasts no security's price and no exchange
  rate, and the result's `notes` say so. A price older than 45 days is
  `stale`. Sensitivity and the break-evens price a later trade at the return
  they vary.
- **Units.** An invest buys (amount − fees) / rate / price units, to 18
  places, and opens a lot (`scenario-invest-<n>`, n its place among the
  changes from 1) that a later sale in the same scenario can sell. A sale
  sells `quantity` units, or `amount` (its value, in your base currency) /
  rate / price units, or the units of the `lots` it names.
- **Lots.** First in, first out, unless the sale names lots (`lots`: each
  `{lot, quantity}`, a lot's id as `salli portfolio lots` shows it). Salli
  replays the holding's recorded transactions with the sale appended, in
  memory (`lots.replay`, unchanged); nothing is written. A sale of more than
  is held then, or of a lot that isn't, is refused at its path. There is no
  average-cost pooling: where an authority matches sales by average cost,
  the gain may differ, and Salli doesn't guess which method applies.
- **Fees** are your own figure (your broker's), in your base currency. Left
  out, they are zero, and the result says "no fees given".
- **The gain** is the proceeds less fees less the consumed lots' cost, in the
  holding's currency and in yours (each lot at the rate it was bought at;
  the sale at the as-of rate). With a `tax_role` (a role of kind income in
  your rules) it adds to that role's total, a loss subtracts, and your rules
  decide what a loss does; the change in tax follows as for any tagged
  change ([above](#tax)).

Each trade comes back in its change, as `changes[n].holding`: the units, the
price and what it rests on (`price_basis`), the fees or that none were given,
the value in both currencies, and for a sale the lots consumed, their cost
and the gain.

### Reading one: a sale with fees, taxed

A fund you call "My index fund": 10 units bought at 100.00 with 5.00 of
fees (a lot costing 1,005.00), a close of 150.00 on the as-of date, held in
a brokerage account the ledger says holds 1,500.00. Selling 4 units with
2.00 of fees, first in, first out: proceeds 600.00, cost 402.00 (4/10 of the
lot), a gain of 196.00. Cash rises by 598.00, the investments fall by
600.00, and net worth by the 2.00 of fees. Tagged with an income role
`gains` under the XA rules above (salary and gains taxed together), the
year's tax rises from 7,200.00 to 7,239.20: 39.20 more, 5.60 a month from
June to December. Investing 1,000.00 into it with 4.00 of fees buys 6.64
units: cash falls by 1,000.00, the investments rise by 996.00.

## What comes back

Every figure is `{"baseline", "scenario", "delta"}`. Money is a decimal
string in your currency's precision. A month's change is in months
(`delta_months`, later is positive), a day's in days.

| Area | Figures |
|---|---|
| **Cash, the next twelve months** | The lowest your cash gets and the day; each cash account at its lowest, and which go below zero; cash at the end of the twelfth month; safe-to-spend until your next income (the baseline's window, so the two compare). |
| **Monthly, in today's money** | Net worth, cash, investments and debts at 1, 5, 10 and 20 years and at the horizon; other assets as net worth counts them (`other_assets`: an asset a scenario buys at its value less its selling costs) and their value before selling costs (`other_assets_value`) beside them. |
| **Debts** | Each debt's payoff month and interest, and a new loan's; the interest on all of them; the month you are debt-free. |
| **Resilience** | The months of spending your cash and savings cover at its low point and at the end of the year: over essential spending when your spending carries need tags, over all of it otherwise. |
| **FI** | The FI number, the month you reach it, and the months gained (positive) or lost. |
| **Tax** | For changes tagged with a tax role, each tax year's role totals and the change in tax, from your active rules ([Tax](#tax)). |

The share of your surplus you invest grows with your investments at your
real return, cash earns nothing, and debts follow their schedules, as on the
[baseline's monthly timeline](baseline.md#the-two-timelines). The lowest cash
counts the share you invest leaving cash at each month's end; the
emergency-fund months count cash alone.
The FI month and the debts' payoff are found wherever they fall within 50
years, whatever horizon you choose.

**The FI number** is a year of the spending you would live on, over your
safe withdrawal rate. Under a scenario it is built on the spending the
scenario leaves for good: a recurring cost with no end adds to it, a
cancelled subscription takes from it, and a one-off, a loan, an income
change or a change in tax leaves it as it is.

**Break-evens on one scenario.** For each recurring cost in a scenario whose
cash goes below zero in the next twelve months, the most it could be, each
time, with cash staying at or above zero: solved to the cent (or your
currency's smallest unit). "None in range" means cash goes below zero even
without it.

**What every result records**, so it can be checked and reproduced:

- the assumptions it used, each with where it came from, and which are
  placeholders (`placeholders`: FI's, inflation, `tax` or
  `tax_rules_carried_forward` when the tax isn't computed or rests on rules
  carried forward, and `asset_growth` when an asset has no growth of its
  own);
- the versions behind it: the document's schema, the engine, a content hash
  of the FI assumptions, and the active tax rule sets that cover the as-of date;
- the as-of date, and how fresh your ledger is (`data_as_of`; `is_stale`
  when its newest entry is more than 45 days old);
- `hash`: a content hash of the scenario (its as-of date filled in), of
  everything your baseline was built from (`baseline_fingerprint`) and of
  the engine's version. Key order and how an amount was written don't change
  it. The same hash means the same figures: the engine's version changes
  whenever the same scenario would give different figures. It is 4: since
  [tax](#tax), stopping a flow whose account carries an income or deduction
  role of your active rules changes your tax. Assets and a recurring
  amount's real growth are new inputs, and left out they change nothing, so
  they kept it at 4.

**The timelines, when asked for.** `?timeline=true` on a run or a
comparison (`salli whatif --timeline --json`, `salli compare --timeline
--json`) adds `timeline` to each result: every day of the cash forecast
(`daily`: the as-of date to the end of the twelfth month, cash under your
baseline and under the scenario, in each day's own money) and every point of
the monthly timeline (`monthly`: the as-of date, then each month's end to the
horizon, cash and net worth as `{"baseline", "scenario", "delta"}` in today's
money). They are the lines every figure above is read from, for drawing them
(the console's charts); the figures and the hash are the same either way.
Without it, `timeline` is null.

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
  less and plus two points. Cash earns
  nothing, so only the long-run figures move. If an option's lead holds at
  all three, it doesn't rest on the return; if it flips, the return you
  expect decides it.
- **Break-evens**, each with a sentence (`says`) saying what it means:
  - **The return at which investing beats paying down a debt**, where one
    option invests and the other pays a debt down instead: the lowest real
    return, to a basis point (0.01%), between -5% and 15%, at which the
    investing option ends the horizon with at least the other's net worth.
    The payments paying down frees are invested at your share, as the
    investing option's money is, so at a share of 100% it falls at the
    debt's own rate (see below).
  - **The most a recurring cost can be** with cash staying above zero, as for
    one scenario.
  - **The loan rate at which two financing options cost the same**, where an
    option has a loan the other doesn't: the highest rate, to a basis point,
    between 0% and 100%, at which it ends the horizon with at least the other
    option's net worth.
  - **The growth at which buying an asset ends level** (`asset_growth`),
    where an option buys one (an `asset` change) the other doesn't: the
    lowest growth of its value beyond inflation, to a basis point, between
    -5% and 10% a year, at which it ends the horizon with at least the other
    option's net worth. A higher growth never lowers it, so it is exact.

  Each is solved by bisection on whole numbers (cents, basis points), so the
  same inputs always give the same answer. "None in range" says which option
  is ahead across the whole range (`ahead`), and of which.

A break-even turns "it depends" into "it depends on whether you expect more
than 4.5% a year after inflation". That is a question you can answer, or ask
your agent to research with sources.

### Reading one: a bonus on the debt, or invested

A bonus of 5,000.00 in December, paid off a student loan at 4.5% or
invested, over ten years. Both come out of cash. Paying down clears the loan
in 2029-01 rather than 2033-03 and saves 1,025.83 of interest; from then on
its 120.00 a month is freed and, at a share of 100%, invested.

| | Invest | Pay down |
|---|---:|---:|
| Net worth in 10 years, against the baseline, at 4% | +2,404.72 | +2,558.51 |
| Lead at 2% / 4% / 6% (Invest less Pay down) | -661.78 / -153.80 / +536.35 | |
| The break-even return | 4.51% | |

At the loan's own 4.5%, the 5,000.00 invested and the payments that paying
it down frees grow to the same, but for the cents the loan's interest is
rounded to each month: so investing first comes out at least level at
4.51%, a basis point above. That is the standard answer, and the one to expect when both sides
are treated alike: invest only if you expect more than the debt costs.

Set your share to 0 and the break-even falls to 1.90%: the payments paying
down frees then sit in cash, which earns nothing, while the 5,000.00
invested compounds. That compares money that grows with money that doesn't,
so set the share to what you really invest before reading a break-even.

### Reading one: cash or instalments

A laptop for 2,400.00, paid at once or over 12 months at 6.9%:

| | Baseline | Pay cash | Instalments |
|---|---:|---:|---:|
| Lowest cash | 13,998.91 | 11,598.91 | 13,821.01 |
| Interest on debts | 2,009.25 | 2,009.25 | 2,099.93 |
| Net worth in 5 years | 485,551.81 | 483,151.81 | 482,585.47 |

With all of the surplus invested (the placeholder), paying cash takes the
price out of cash for good: the surplus you invest doesn't rebuild it, so
the low point is 2,400.00 lower. Instalments keep the low point within
177.90 of where it was and cost 90.68 of interest (eleven payments of 207.55
and a last of 207.63), but the payments come out of the surplus you would
invest, and what it would have earned goes with them: by five years they
cost 566.34 more than paying cash. So paying cash ends ahead at every loan
rate, and there is no break-even in range. Set your share to 0 and both come
out of cash: the break-even is then 0%, any rate above it costing more.
Which matters more, the buffer or the money, is yours to say.

## For agents

- Build every option with the schema (`get_scenario_schema`), and let Salli
  run and compare them. Never subtract, add, divide or project anything
  yourself, not even roughly.
- Never work out an amount after tax. When a change is before tax (a raise,
  a bonus, a pension contribution), tag it with the role from the user's
  rules and let Salli compute the tax. If `tax.status` is `"not_computed"`,
  say so, and why (`tax.reason`).
- Quote Salli's figures, with their currency, and the sentence of each
  break-even.
- Name the assumptions that are placeholders. If `is_stale` is true, ask the
  user to bring their ledger up to date before deciding.
- Say what share of the surplus the figures assume invested
  (`assumptions.surplus_invested`): it decides the FI month and every
  comparison of investing against paying down a debt. While it is the
  placeholder, ask the user what they really invest, and set it only once
  they agree.
- Never say which option is best. Lay out the trade, the sensitivity and
  what would change the answer, and leave the choice to the user.
- A problem comes back with its path (`changes[0].date: is before the as-of
  date`): fix the document and run it again.
- Refer to the user's holdings as they named them. Never suggest buying or
  selling any security, theirs or another, and never compare holdings as
  investments: choosing investments is for a licensed professional. Fees are
  the user's figure: ask, never assume one.

## Not modelled yet

- Tax on investment growth, dividends and withdrawals in retirement; when
  tax is settled; a loan's interest as a deduction.
- A target for your cash: after a one-off has spent some of it, the share of
  the surplus you invest doesn't rebuild it unless a scenario sets an amount
  aside (`set_aside`), and a set-aside doesn't stop by itself once cash
  covers a target. The [emergency-fund template](templates.md) reads when
  it does.
- Selling an asset on a day, and repaying a loan on a day: an asset is
  counted at what it would fetch at every month's end instead.
- An asset's running costs: add them as a `recurring` cost.
- An expected return per holding, a price, dividend or exchange-rate
  forecast, buying a security you don't hold yet (add the holding first),
  and average-cost pooling or wash-sale rules for lots.
- Amounts in a currency other than your base currency, and accounts held in
  one.
- The day within its month a debt's payment falls on.
