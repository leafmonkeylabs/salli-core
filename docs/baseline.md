# The baseline

The baseline is one model of your money as of a day. Salli builds it from your
ledger and what you have declared, and every figure that looks ahead starts
from it: your FI score and projections, the cash forecast, safe-to-spend, the
debt plan and the decision lab's [scenarios](scenarios.md). So they never
disagree about what you earn, spend, own or owe.

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
point counts what you invested. `salli insights forecast` and safe-to-spend
show the scheduled flows alone.

**Monthly, to a horizon of up to 50 years,** at each calendar month's end, in
today's money:

- **Cash** keeps what you don't invest of each month's surplus (below). Cash
  earns nothing, so in today's money it loses what inflation takes.
- **Investments** grow at your real return (the base scenario's), a twelfth of
  it a month, compounded, and take the share of each month's surplus you
  invest at its end.
- **Other assets** keep their value in today's money.
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
then your FIRE strategy's, then a round 4% placeholder. The share of your
surplus invested is yours, or the placeholder's 100%. Inflation has no
placeholder: with none set, nominal amounts (cash, fixed payments) keep their
real value, and the baseline lists inflation among its placeholders until you
set it (`salli fi assumptions set inflation 2.4% --source "<where from>"`).
Placeholders are round figures, not forecasts. Every response says which it
used.

## Financial independence

FI reads the monthly timeline. The FI number is a year of your spending (or
your FIRE strategy's target) over your safe withdrawal rate; the month FI is
reached is the first whose end your cash and investments, less your debts,
reach it, looked for up to 50 years ahead. The projections are the same
timeline with your investments at each scenario's real return. The share of
your surplus you invest grows with your investments; what you keep in cash
earns nothing. So the share you set moves the month: the less you invest,
the later it comes.

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

- Extra payments and new loans are changes a [scenario](scenarios.md) makes;
  the baseline is where they start.
- A target for your cash: once a one-off has spent some of it, the share of
  the surplus you invest doesn't rebuild it.
- A payment's day within its month.
