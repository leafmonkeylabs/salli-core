# Decision templates

> **Experimental.** Part of the decision lab, which works but may change
> before the first pilots end: see [scope](scope.md).

A template is a common decision, packaged as a few questions and the
options your answers build: can I afford it, debt or invest, a windfall, a
big recurring change, borrowing, an emergency fund, rent or buy. Salli builds each option
as a [scenario](scenarios.md), runs every one on your
[baseline](baseline.md), compares them and checks them against your
[principles](decisions.md#principles). It ranks none of them. Templates are
conveniences, not advice: they save writing the scenarios by hand, and say
nothing about which option to take.

    salli decide --list
    salli decide afford-it
    salli decide afford-it --set price=2400 --set instalment_months=12 --set instalment_rate=6.9%
    salli decide emergency-fund --set target_months=6 --set set_aside=200,500 --json
    salli decide rent-or-buy --answers home.json --set home_growth=0.5%

Over the API: `GET /v1/decisions/templates`, `GET
/v1/decisions/templates/{id}` and `POST /v1/decisions/start`. Over MCP:
`list_decision_templates` and `start_decision`, and the
`think_through_decision` prompt, which walks an agent through the whole of
it.

## The templates

| Template | It asks | Options it builds |
|---|---|---|
| `afford-it` | the price, what it is, the day, the account; months and a rate to spread it; months to wait and what you would set aside meanwhile | **Pay cash**: the price out of cash on the day. **Spread over N months**: the same, borrowed back at your rate and repaid monthly. **Wait N months**: bought N months later, with what you set aside each month kept in cash until then. |
| `debt-or-invest` | the debt, the amount, once or every month (for how many months), from when; optionally how much of it on the debt in a split | **Pay down** the debt: the amount onto it on top of its payments. **Invest it**: the same amount moved into your investments on the same days. **Split**: the part you say onto the debt, the rest invested. |
| `windfall` | the amount, whether it is new money or already in your cash and, if new, whether it is taxable (its tax role), the day, the account; two to five splits | **Each split you propose**: amounts onto your debts and into your investments; what a split doesn't put to work stays in cash. |
| `big-change` | what it is, when it starts and ends; how much more (or less) you would spend and take home each month, and whether that pay is before tax (its tax role); anything paid once at the start | **As things are**, and **the change**: its costs and income each month, and the one-off at the start. The comparison shows the cash timing: the low point and when, and the most a new cost could be with cash staying above zero. |
| `borrow` | new borrowing or refinancing a debt; how much (to refinance, what the debt owes now); when; the account; whether the money is spent on the day; any fee; one to four loans, each a rate and a term | **Each loan**: its payment, total interest and effect on cash and FI. To refinance, the new loan's money pays the old debt off in its first month. **Don't borrow**, or **Keep the debt**: your baseline. |
| `emergency-fund` | how many months of spending you want your cash to cover; one to four amounts you could set aside each month; from when, and for how long | **As things are**, and **Set aside each amount**: kept in cash out of your monthly surplus rather than invested. With the months your cash covers now, and when it would cover your target. |
| `rent-or-buy` | the price, when you would buy, your deposit, the account; one to three mortgages, each a rate and a term; buying costs, owning costs a month and selling costs (0 is an answer to each); your rent (one of your recurring payments, or an amount); how fast you expect the rent and the home's value to grow beyond inflation | **Keep renting**: your rent goes on, stated as a recurring cost rising at the rent's growth. **Buy** (once per mortgage): the home bought from cash, the mortgage, buying and owning costs, and the rent stopped. With the month buying draws level with renting, and the house-price growth at which the answer turns ([below](#rent-or-buy)). |

Every template also asks how many years the long-run figures run (20 unless
you say).

## Questions and defaults

`salli decide <template> --questions` (or `GET
/v1/decisions/templates/{id}`) lists a template's questions, each with:

| Field | What it is |
|---|---|
| `id` | What the answer is called. |
| `type` | `amount` (above zero, in your base currency, a decimal string), `amount_or_zero` (the same, where `"0"` is an answer), `signed_amount` (`"+450"` more, `"-200"` less), `months` and `years` (whole numbers), `number` (a decimal string, like months of spending), `rate` (a yearly fraction: `"0.069"` is 6.9%), `growth` (a signed yearly fraction beyond inflation: `"0.01"` is 1% a year more than prices, `"-0.005"` half a percent less), `date` (`YYYY-MM-DD`, not before the as-of date), `choice`, `debt`, `account` and `holding` (one of your own, by id), `recurring` (one of your recurring payments out, by its key: `salli insights recurring`), `tax_role` (an `income` or `deduction` role of your active tax rules, by key), `text`, and the lists `amounts`, `loans` and `splits`. |
| `required` | Whether it must be answered when it has no default. |
| `when` | When it is asked: once another question is answered, or answered so. |
| `default` | What it is when you leave it out, where that comes from (`source`) and a sentence saying so (`note`). |

A default comes only from what is honest:

- **The date:** the as-of date, or the first of the next month. A payment
  onto a debt may start in the as-of month: it is paid at the month's end,
  before the debt's next scheduled payment
  ([scenarios](scenarios.md#in-the-as-of-month)).
- **Your debts:** the debt, when you have only one; what a debt owes now,
  when you refinance it.
- **Your principles:** the months of spending you want your cash to cover, when a
  principle of yours says so exactly (`emergency_months >= 6`).
- **Salli's own:** a plain name for a purchase, "once", "new money", and the
  20-year horizon.

Nothing else has a default. A price, a rate, a target, an amount to set
aside, a tax role, a holding: you give them, or the template asks. A template
never invents a figure about your money, and never picks a holding, even
when you have only one: where money goes is yours.

## Holdings

`debt-or-invest` and `windfall` ask, optionally, which of your holdings the
money invested goes into (`holding`: one with its transactions and a price
recorded, by its id). Named, each invest change goes into it, and the result
shows the units it buys at the holding's price
([scenarios](scenarios.md#holdings)); left out, the money goes into your
investments as a whole, as before. No template sells a holding: write a
`sell` change yourself, or use `salli whatif --sell`.

**One exception, labelled:** rent-or-buy's two growths beyond inflation
(`rent_growth`, `home_growth`) default to 0 with the source `placeholder`
and the note "a placeholder, not a forecast: set your own view". 0 beyond
inflation is not a forecast: it is how the baseline already treats every
other asset (it keeps its value in today's money) and every recurring
amount. Asking for a forecast of your local market before showing anything
would invite a guess presented as a fact; instead the result lists the
placeholders (`asset_growth`, `rent_growth`) and gives the break-even growth
beside them, the figure your own view must beat.

## Tax

`big-change` asks whether its pay change is before tax, and `windfall`
whether new money is taxable; each answer is a role of your own active tax
rules (`tax_role`). With one, the amount is before tax and the option's
change carries the role, so Salli works out the change in tax with your
rules ([scenarios](scenarios.md#tax)); without one, the amount is what
reaches your cash, as before. A template knows no tax relief or rate of its
own: whatever is taxed, and how, comes only from your rules. Answers to
your rules' questions go in `tax_answers` (`salli decide ... --tax-answer
key=value`), and into every option's `tax.answers`.

The answers are checked as a scenario is: each problem comes back with its
path (`answers.instalment_rate: is required`), every problem at once, and a
JSON number for an amount is refused. `answers_schema` is the answers' JSON
Schema, with your own debts and accounts listed by id.

## What starting a decision returns

`POST /v1/decisions/start` (`start_decision`, `salli decide`) takes the
template's id, your answers and, if you like, an as-of date and answers to
your tax rules' questions (`tax_answers`), and returns
(`salli.decision-start/1`):

| Field | What it holds |
|---|---|
| `question` | A question for your journal. A suggestion: put it in your words. |
| `answers` | Each answer as used, with where it came from (`given`, or a default's source). |
| `options` | Each option's label, a sentence saying what it is (`describes`), the scenario as run and its hash. |
| `comparison` | The options side by side, the trade between each two, the sensitivity to the real return and the break-evens, exactly as [comparing options](scenarios.md#comparing-options) gives them. |
| `principles` | Which of your principles the baseline and each option keep, break or can't tell, with the figures each read, as [checking](decisions.md#checking) gives them. |
| `cover` | For an emergency fund: your target in cash (the months times your monthly spending as shown, in today's money), the months your cash covers now, and the first month at whose end cash covers the target, under your baseline and each option. |
| `level` | For rent or buy: for each way of buying, the first month-end from the purchase on from which its net worth is at least keeping renting's at every month-end to the horizon (`month`, and `months` from the purchase), with the difference then and at the horizon. |
| `placeholders`, `is_stale`, `data_as_of` | What the figures rest on, any option's (an asset's growth, `asset_growth`; tax) and the template's own (a rent's growth, `rent_growth`), and how fresh your ledger is. |
| `record` | What recording needs besides your own: the question, each option's scenario with its as-of date, and the labels, one of which you choose. |

It stores nothing. Recording is the [journal's](decisions.md#the-decision-journal)
own step: `POST /v1/decisions` (`record_decision`, or `salli decide ...
--record`) with `record.question`, `record.options`, the label you chose,
your reasons in your words and a review date. The options carry their as-of
date, so the journal runs them on the same baseline you compared.

### When cash covers a target

The emergency fund's time to a target is read from the monthly timeline,
never worked out from a rate of saving: the first month at whose end your
cash, in today's money, is at or above the target, looked for up to 50
years ahead. Inflation doesn't move it, since both are in today's money.
With all of your surplus invested (the placeholder), cash doesn't grow as
things are, so the baseline never gets there; set what you really invest
(`surplus_invested`) before reading it.

## Rent or buy

Rent or buy is laid out as consequences, never as an answer. Both options
state the rent the same way: keeping renting stops the ledger's rent from
the day you would buy and puts it back as a recurring cost from the day it
is next due, rising at the rent's growth (a rent the ledger shows every two
weeks or twice a month goes back a month, at its monthly equivalent); with
no rent in the ledger, the amount you give is added as a new cost. Each way
of buying is a scenario of its own: the home bought from cash on the day
(an [`asset`](scenarios.md#changes), growing at the home's growth and
counted at its value less its selling costs), the mortgage (an ordinary
`loan` of the price less the deposit, into the same account), buying costs
once, owning costs each month in today's money, and the rent stopped.

So each option's FI number moves honestly: buying stops the rent and adds
the owning costs to the spending to live on, while the home itself funds no
withdrawals and the deposit no longer sits in cash.

What it reads, beside the comparison:

- **When buying draws level** (`level`): the first month-end from which
  buying's net worth is at least renting's, and stays at least level, to the
  horizon: how long the home must be kept, on these assumptions. Read from
  the monthly timelines, never solved.
- **The house-price growth at which buying ends level** (the
  `asset_growth` break-even): the lowest growth beyond inflation, between
  -5% and 10% a year, at which buying ends the horizon with at least
  renting's net worth. "Do you expect your home to grow more than 1.3% a
  year beyond inflation?" is a question you can answer, or research with
  sources.
- **The mortgage rate at which they cost the same** (the `loan_rate`
  break-even), as for any loan.

What it rests on, said plainly in its notes:

- the home's growth and the rent's are your view, or a labelled 0% beyond
  inflation, never a forecast: the break-even is the figure that matters;
- each mortgage's rate is held fixed for its term: resets aren't modelled;
- a home is one asset, illiquid and undiversified, and the comparison
  doesn't price that risk;
- owning costs are what you give: leaving them low flatters buying;
- tax on buying, owning or selling a home comes only from your own rules:
  a tax on buying is a buying cost you give, and nothing else about a
  home's tax is modelled;
- Salli knows nothing about any local property market, and research behind
  your figures needs its sources;
- the home counts at what it would fetch, its value less its selling
  costs, so buying starts behind by them.

### Reading one

Rent of 1,000.00 a month; a home for 200,000.00 with 50,000.00 down and a
mortgage of 150,000.00 at 0% over 120 months (1,250.00 a month), no buying
or owning costs, no growth, selling costs of 3%; none of the surplus
invested and no inflation. At the end of the first month, buying is
5,000.00 behind renting: cash 50,000.00 lower but for the month's rent not
paid (49,000.00), 150,000.00 owed, the home counted at 194,000.00. Each month
after, 250.00 more leaves cash (1,250.00 paid, 1,000.00 of rent not) and
1,250.00 less is owed: 1,000.00 a month. So buying draws level at the end
of the sixth month and stays ahead; without selling costs it is ahead from
the first. Over one year the house-price growth at which it ends level is
-3.42%; over twenty, buying ends ahead at every growth from -5% to 10%.

## Setting aside

`afford-it`'s waiting and the emergency fund keep part of your monthly
surplus in cash. That is a scenario change of its own, `set_aside`
([scenarios](scenarios.md#changes)): each month, that much of the regular
surplus stays in cash before the share you invest is taken from the rest. It
moves no money of its own, and can't keep more than the month's surplus.
What isn't invested doesn't grow, so the long-run figures and the FI month
show what it costs.

## Not built yet

- Selling the home on a day, a loan repaid early, shared ownership,
  offset or interest-only mortgages, moving costs, or a mortgage's interest
  as a tax deduction.
- A tax role on a template's costs (a deductible cost, a pension
  contribution): write the scenario yourself with the tag, for now.
- Stopping a set-aside once cash covers the target: give it a number of
  months instead.
