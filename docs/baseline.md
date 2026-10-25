# The baseline

The baseline is one model of your money as of a day. Salli builds it from your
ledger and what you have declared, and every figure that looks ahead starts
from it: your FI score and projections, the cash forecast, safe-to-spend, the
debt plan and the decision lab's [scenarios](scenarios.md), and so does every
[net worth](#net-worth). So they never disagree about what you earn, spend,
own or owe.

See it with `salli baseline`, `GET /v1/baseline`, or the MCP tool
`get_baseline`. Each shows the definitions below as data: the months it
averaged, the rates it used and who published them, each account's role, and
which assumptions are placeholders. Reading it changes nothing.

## As of a day

The baseline is as of a day: today unless you ask for another
(`salli baseline --as-of 2026-06-30`). Nothing dated after that day is read,
so the baseline as of a past day is what Salli knew then, give or take
entries you booked late.

## Income and spending

One definition, used everywhere:

- **Netted per calendar month.** Amounts on income and expense accounts are
  signed and added up month by month. A reversal cancels the entry it
  reverses; a refund cancels the purchase.
- **Averaged over the full months observed.** At most the twelve calendar
  months before the as-of month. The as-of month isn't over, so it isn't
  averaged in. Nor are months before your first income or expense: someone
  with three months of records is averaged over three. A ledger begun
  part-way through a month counts that month.
- **In your base currency at each posting's own rate.** Money that came and
  went is worth what it was worth when it moved.

The surplus is income less spending. Essential spending is spending tagged
`need: essential`; until something carries a need tag there is no essential
figure, and the baseline says how much of your spending is tagged.

`salli insights cash-flow` shows the same months and the same average.

## Balances and their roles

Each account's balance is its own: in its currency, from what its postings
add up to on the as-of day. Its role says what it is:

| Role | Which accounts | Counts as |
|---|---|---|
| Cash | Asset accounts whose role is cash (the default) | Money to spend or fall back on, and your emergency fund |
| Savings | Asset accounts you mark as savings: a savings account, an emergency fund, a term deposit | Cash you keep: counted as cash in net worth, FI, your emergency fund and the monthly timeline, never in the daily cash timeline or free until payday |
| Investment | Asset accounts you mark as investments | Invested: it grows at your real return |
| Other asset | Asset accounts you mark as other: a home, a car | Owned, but neither cash nor investable |
| Liability | Liability accounts | Owed |

Set an asset account's role with `salli accounts update 1500 --asset-role
other`. Salli never guesses it from the account's name.

**Holdings** are not counted: your investment accounts are, so no figure has
two sources. A holding may be linked to the investment account that holds it
(`salli holdings update FUND --account brokerage`), which lets a
[scenario](scenarios.md#holdings) sell it. The baseline values each holding
as of its day (its transactions replayed, at its last price recorded on or
before it, at the as-of exchange rate), and where a linked account's ledger
value and its holdings' value differ, its `notes` say by how much and that
the ledger's figure is the one counted. Nothing is reconciled silently:
bring the ledger up to date, or record a price.

The daily cash timeline also counts the cards you spend from (a liability a
statement is imported into, or one that paid for several kinds of thing), so
a card's balance counts against your cash.

## Exchange rates

A balance in another currency is valued at the published rate for the as-of
date, from the same source tax converts with. The baseline records each rate,
its source and the day it is for: a Sunday's rate is Friday's. If no rate is
published, that currency's balances are left out of the totals and the
baseline says so, rather than showing a wrong value.

## Debts

A debt with terms (a rate and a minimum payment) is counted once:

- **Linked** to the liability account that holds it in your ledger
  (`salli debts update <debt> --account 2100`), it owes what that account
  says. The debt adds its rate and minimum payment.
- **Not linked**, it owes its declared principal, which the ledger doesn't
  hold.

## Net worth

Net worth is everything owned less everything owed as the baseline counts
them: each account at the published rate for the day, judged on its own sign
(an overdrawn account is owed), and each debt once. Every net worth Salli
gives is this one: `salli status`, the balance sheet (`salli reports
balance-sheet`, today), FI, the MCP overview, and net worth over time
(`salli insights net-worth`), each of whose points is the baseline's as of
that month's end (this month's, today) at that day's rates, with `notes`
saying what a day without a rate left out.

A liability without a debt's terms is a balance only. A debt's first payment
falls in the month after the as-of month, and its schedule runs on calendar
months.

Your average surplus already pays part of each debt's payment: a linked
debt's interest, which your books record as spending, or an unlinked debt's
whole minimum. The rest of its scheduled payment comes out of your regular
surplus (below). When a debt is paid off, its payment is freed and joins the
surplus, and you invest your share of it. An extra payment on top of the
schedule, which a [scenario](scenarios.md) can make, comes out of your cash;
in the as-of month, before the first payment, it is paid at the month's end
([scenarios](scenarios.md#in-the-as-of-month)).

## The two timelines

**Daily cash, for the as-of month and the twelve after it,** in each day's own
money. Your cash accounts carried through what keeps happening (the salary,
the rent, the subscriptions your ledger shows, and those you declared but it
hasn't shown yet), then the rest of an average month spread evenly over its
days, and the share of the month's surplus you invest leaving cash on its
last day. So each month ends where the monthly plan says, and the lowest
point counts what you invested. `salli insights forecast` shows the
scheduled flows alone.

**Free until payday** (`salli insights safe-to-spend`) is the lowest your
cash gets before money next comes in, from the scheduled flows and a usual
day's everyday spending: your average month's spending less what is
scheduled to a spending account (a move to investments or a debt isn't
spending), day by day. Then less a cushion, a tenth of a usual month's
spending, and the cash you set aside for goals. It is an estimate from your
past spending, never below zero, and the answer lists each part.

**Monthly, to a horizon of up to 50 years,** at each calendar month's end, in
today's money:

- **Cash** keeps what you don't invest of each month's surplus (below). With
  an active [capital-market assumptions pack](#capital-market-assumptions),
  cash (above zero) earns the pack's cash yield after inflation; without
  one it earns nothing, so in today's money it loses what inflation takes.
  [Guaranteed income](#the-fi-plan) that starts after the as-of month comes
  into cash from its start, and its lump sum in its first month.
- **Investments** grow at your real return (the base scenario's), a twelfth of
  it a month, compounded, and take the share of each month's surplus you
  invest at its end.
- **Other assets** keep their value in today's money. An asset a
  [scenario](scenarios.md#changes) buys joins them from the month it is
  bought, grows at its own real growth, and counts at its value less its
  selling costs.
- **Debts** follow their schedules. Fixed payments are deflated by your
  inflation figure.
- **Net worth** is all of them together.

The daily timeline's month-ends are the monthly timeline's cash, before it is
turned into today's money.

## Your surplus, and what you invest of it

Each month's money comes in two kinds:

- **The regular surplus** is what happens month after month: your average
  surplus, plus what of your debts' payments it already pays, less the
  debts' scheduled payments. When a debt is paid off, its payment is freed
  and joins it. In a [scenario](scenarios.md), recurring costs and income,
  income changes and cancelled subscriptions add to it, and a new loan's
  payments come out of it until the loan is paid off.
- **Moves** go where they say: a one-off in or out of cash, the money a loan
  brings in, money moved into your investments, an extra payment onto a
  debt.

The share of the regular surplus you invest goes into your investments at
each month's end and grows at your real return; the rest stays in cash. It is
a planning assumption, from 0 to 100%:

    salli fi assumptions set surplus-invested 30% --source "my standing order"

Until you set it, a placeholder assumes all of it, as projections of
financial independence conventionally do, and every response lists it among
the placeholders. Set what you actually invest: at 0% the whole surplus stays
in cash.

The rest of the as-of month counts too: what is scheduled for it (a salary
still to come) and its share of an average month's unscheduled spending, at
today's prices.

A month whose regular surplus is a deficit invests nothing: the deficit comes
out of cash, never out of your investments. If cash runs out, the timeline
lets it go below zero and says from when (`notes`), rather than selling
investments for you.

A regular transfer to an investment account that your ledger shows is no part
of your surplus: the daily timeline shows it on its day, and the rest of the
month gives it back. What the timelines invest is the share.

Your emergency-fund months and safe-to-spend count cash alone: what you
invest never counts towards them.

## Assumptions and placeholders

The real return and the safe withdrawal rate are yours where you set them,
else a round 4% placeholder. No model chooses them. The share of your
surplus invested is yours, or the placeholder's 100%. Inflation has no
placeholder: with none set, nominal amounts (cash, fixed payments) keep their
real value, and the baseline lists inflation among its placeholders until you
set it (`salli fi assumptions set inflation 2.4% --source "<where from>"`).
Placeholders are round figures, not forecasts. Every response says which it
used.

## Financial independence

FI reads the monthly timeline. The FI number at a month is a year of the
spending to fund then, grossed up for tax on withdrawals, over your safe
withdrawal rate; the month FI is reached is the first whose end your cash
and investments, less your debts, reach that month's number, looked for up
to 50 years ahead. The projections are the same timeline with your
investments at each scenario's real return. The share of your surplus you
invest grows with your investments; what you keep in cash earns the cash
yield, or nothing. So the share you set moves the month: the less you
invest, the later it comes.

- **The spending to fund** is your average monthly spending, or your
  [spending phase's](#the-fi-plan) for your age that month (plus a
  scenario's change in spending), less the guaranteed income paying that
  month. Without a plan every month's number is the same.
- **Gross of tax.** When your active tax rules (in your base currency)
  declare an income role keyed `withdrawal`, the year's spending is grossed
  up to what must be withdrawn so that, after the tax those rules take on
  it, the spending is left (the as-of year's rules, their bands level in
  today's money). The tax is marginal: what the rules take on the year's
  guaranteed income that names an income role (`tax_role`) with the
  withdrawal, less what they take on that income alone. Without such a role it is not, and the
  odds say so (`withdrawal_tax.status` `not_computed`). Add the role to
  your rule set to have it taxed.

## The FI plan

Guaranteed income and spending phases, yours to set (`salli fi plan set
plan.json`, `PUT /v1/fi/plan`); no model chooses them:

```json
{
  "income_streams": [
    {"name": "Work pension", "start": "2049-04", "monthly": "1200.00",
     "terms": "real", "indexed": true, "lump_sum": "30000.00",
     "tax_role": "pension", "source": "statement of 2026"}
  ],
  "spending_phases": [
    {"from_age": 60, "monthly": "3000.00"},
    {"from_age": 75, "monthly": "2200.00"}
  ]
}
```

- **A stream** (a pension, an annuity, a provident fund's payout) pays
  `monthly` from `start`, in today's money (`terms` `real`) or in the start
  month's own money (`nominal`). `indexed` keeps its value against inflation
  from its start; otherwise it is fixed in money and inflation wears it
  down. `lump_sum` is paid once in its start month. A stream that started
  on or before the as-of month is already in your ledger's income, so it
  only reduces the FI number. `tax_role`, optional, is the income role of
  your tax rules it is taxed under: withdrawals are taxed beside it.
- **A phase** is the monthly spending to live on, in today's money, from an
  age on, by the date of birth on your profile. Before the first, or
  without a date of birth, your average spending applies.

## Capital-market assumptions

A pack (`salli.cma/1`) is user data, as tax rules are: per asset class an
expected yearly return after inflation and a volatility, the correlations
between classes, the yield cash earns after inflation, inflation, and the
mix the figures are for; each figure with its source and the day it was
given. A country's pack is a document a person or their agent writes and
cites; Salli holds none. Import one (`salli fi cma import pack.json`,
`POST /v1/fi/cma-packs`): it is stored as written and never changes (an
edit is a new import; the same document twice is one pack). Activate one
(`salli fi cma activate <id>`): at most one is active.

With an active pack, where you set no figure of your own:

- the real return is the mix's expected return (`Σ wᵢ rᵢ`);
- inflation is the pack's, if it gives one;
- cash earns the pack's cash yield;
- the [odds](#the-odds) draw returns with the mix's volatility
  (`√(wᵀΣw)`, from the classes' volatilities and correlations);
- [debt or invest](templates.md) sets investing against the debt under it.

Without one, a neutral placeholder pack stands in (one class at the 4% real
return placeholder, a 12% volatility, cash earning nothing), labelled
wherever it is used. Every FI response carries `assumptions.cma` when a pack
of yours is active.

The format, as JSON Schema (draft 2020-12):

```json
{
  "type": "object",
  "required": ["format", "name", "version", "asset_classes", "cash_yield", "mix"],
  "properties": {
    "format": {"const": "salli.cma/1"},
    "name": {"type": "string"},
    "version": {"type": "string"},
    "asset_classes": {
      "type": "object", "minProperties": 1, "maxProperties": 20,
      "additionalProperties": {
        "type": "object", "required": ["real_return", "volatility"],
        "properties": {
          "label": {"type": "string"},
          "real_return": {"$ref": "#/$defs/figure"},
          "volatility": {"$ref": "#/$defs/figure"}
        }
      }
    },
    "correlations": {
      "type": "array",
      "items": {
        "allOf": [{"$ref": "#/$defs/figure"}],
        "required": ["a", "b"],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}}
      }
    },
    "cash_yield": {"$ref": "#/$defs/figure"},
    "inflation": {"$ref": "#/$defs/figure"},
    "degrees_of_freedom": {"$ref": "#/$defs/figure"},
    "mix": {
      "type": "object", "minProperties": 1,
      "additionalProperties": {"type": "string", "pattern": "^(0(\\.\\d+)?|1(\\.0+)?)$"}
    }
  },
  "$defs": {
    "figure": {
      "type": "object", "required": ["value", "source", "date"],
      "properties": {
        "value": {"type": "string", "pattern": "^-?\\d+(\\.\\d+)?$"},
        "source": {"type": "string", "minLength": 1, "maxLength": 500},
        "date": {"type": "string", "format": "date"}
      }
    }
  }
}
```

Values are yearly fractions in decimal strings ("0.05" is 5%): a real return
from -0.10 to 0.20, a volatility from 0 to 0.80, a cash yield from -0.10 to
0.10, inflation from -0.05 to 1, a correlation from -1 to 1; the optional
`degrees_of_freedom` of the odds' Student-t draws, from 3 to 100 (the
lower, the fatter the tails; without it, 5, a labelled placeholder). A correlation
not listed is 0; the mix names classes of the pack and sums to 1. An example,
for a fictional market XA:

```json
{
  "format": "salli.cma/1",
  "name": "XA reference", "version": "2031-06",
  "asset_classes": {
    "equity": {"label": "Equity",
      "real_return": {"value": "0.05", "source": "XA statistics", "date": "2031-05-31"},
      "volatility": {"value": "0.18", "source": "XA statistics", "date": "2031-05-31"}},
    "bonds": {"label": "Bonds",
      "real_return": {"value": "0.01", "source": "XA statistics", "date": "2031-05-31"},
      "volatility": {"value": "0.06", "source": "XA statistics", "date": "2031-05-31"}}
  },
  "correlations": [
    {"a": "equity", "b": "bonds", "value": "0.2", "source": "XA", "date": "2031-05-31"}
  ],
  "cash_yield": {"value": "0.01", "source": "XA bank", "date": "2031-05-31"},
  "mix": {"equity": "0.6", "bonds": "0.4"}
}
```

## The odds

`salli fi odds` (`GET /v1/fi/odds`; a scenario's: `--file`, `POST
/v1/scenarios/odds`; MCP `get_fi_odds`) runs a seeded Monte Carlo on the
monthly timeline, in today's money. No model computes or chooses any of it.

- **Returns.** Each of `paths` paths (1,000 by default) draws a month's real
  return for the investments from a Student-t distribution, whose fat tails
  bring crashes and booms more often than a normal's: the real return over
  twelve, the volatility over √12 (the draws scaled to keep it), with the
  pack's `degrees_of_freedom` (else 5, listed in `placeholders`). Draws come from a seeded generator
  (`seed`, 1 by default), each written to nine places as a Decimal, so the
  same seed gives the same figures.
- **Building up**, to the retirement month (`retire_month`, by default the
  FI month): the investments grow at the path's returns and take what the
  timeline moves into them; cash and debts follow the timeline.
- **Drawing down**, after it: your cash and investments less debts are one
  pool at the path's returns, less each month's spending to fund, grossed
  up for tax. `success` is the share of paths that never run out by the
  horizon (`horizon_years`, 50 by default); `reach` the share whose asset
  base reaches the FI number within it.
- **Percentile paths**: the 10th, 50th and 90th percentile of the asset base
  at each whole year.
- **A horizon-derived withdrawal rate**, beside yours (or the placeholder):
  for each path the highest constant real withdrawal, as a share of the
  pool at retirement, that lasts the years drawn down (exactly
  12 / Σₖ 1/Gₖ, with Gₖ the path's growth to month k); the rate shown is the
  one `success_level` (90% by default) of paths sustain. It informs; the FI
  number still uses your rate.
- **Guardrails** (`--guardrails 20%`): each year after retirement, a
  withdrawal rate more than the band above the starting one cuts spending
  by `--adjust` (10%), more than the band below raises it. They report the
  share of paths that last, that cut at some point, and the 10th percentile
  of the lowest spending reached.

`placeholders` lists every placeholder the odds rest on (`volatility` while
no pack is active). The odds are not a forecast.

## What it records

Each baseline keeps a fingerprint of everything it was built from, and the
active tax rule sets in your tax residency that cover its as-of date. A
scenario's result records both, so the same inputs can be shown to give the
same figures.

For [tax in scenarios](scenarios.md#tax) it also gathers your active rule
sets for the as-of year and later (and the latest before, which later years
carry forward), the postings on accounts whose tax role they declare, each
role's monthly average over the months observed, and the exchange rates
those need. With rules to compute with, they are in the fingerprint too.
Your holdings (their transactions, recorded prices and links, to the as-of
date) are in it once you have any.

## What is not modelled yet

- Serial correlation and asset classes drawn apart: the odds draw one
  return for the mix a month, each month independent.
- Taxable income in retirement beyond guaranteed income streams (gains,
  rent): the gross-up taxes the withdrawal beside those streams alone.

- Extra payments and new loans are changes a [scenario](scenarios.md) makes;
  the baseline is where they start.
- A target for your cash: once a one-off has spent some of it, the share of
  the surplus you invest doesn't rebuild it.
- A payment's day within its month.
