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
whole minimum. Paying more than that comes out of your cash. When a debt is
paid off, its payment stays with you.

## The two timelines

**Daily cash, for the as-of month and the twelve after it,** in each day's own
money. Your cash accounts carried through what keeps happening (the salary,
the rent, the subscriptions your ledger shows, and those you declared but it
hasn't shown yet), then the rest of an average month spread evenly over its
days, so each month ends where the monthly plan says. `salli insights
forecast` and safe-to-spend show the scheduled flows alone.

**Monthly, to a horizon of up to 50 years,** at each calendar month's end, in
today's money:

- **Cash** grows by your average surplus each month. The surplus stays in
  cash: the baseline doesn't assume you invest it. Cash earns nothing, so in
  today's money it loses what inflation takes.
- **Investments** grow at your real return (the base scenario's), a twelfth of
  it a month, compounded.
- **Other assets** keep their value in today's money.
- **Debts** follow their schedules. Fixed payments are deflated by your
  inflation figure.
- **Net worth** is all of them together.

The daily timeline's month-ends are the monthly timeline's cash, before it is
turned into today's money.

## Assumptions and placeholders

The real return and the safe withdrawal rate are yours where you set them,
then your FIRE strategy's, then a round 4% placeholder. Inflation has no
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
timeline with your investments at each scenario's real return. So the
surplus you keep in cash, which earns nothing, doesn't count as invested: a
[scenario](scenarios.md) that invests it says so, and shows the months it
gains.

## What it records

Each baseline keeps a fingerprint of everything it was built from, and the
active tax rule sets in your tax residency that cover its as-of date. A
scenario's result records both, so the same inputs can be shown to give the
same figures.

## What is not modelled yet

- Investing the surplus month by month, extra payments and new loans are
  changes a [scenario](scenarios.md) makes; the baseline is where they start.
- A payment's day within its month.
