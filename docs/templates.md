# Decision templates

A template is a common decision, packaged as a few questions and the
options your answers build: can I afford it, debt or invest, a windfall, a
big recurring change, borrowing, an emergency fund. Salli builds each option
as a [scenario](scenarios.md), runs every one on your
[baseline](baseline.md), compares them and checks them against your
[principles](decisions.md#principles). It ranks none of them. Templates are
conveniences, not advice: they save writing the scenarios by hand, and say
nothing about which option to take.

    salli decide --list
    salli decide afford-it
    salli decide afford-it --set price=2400 --set instalment_months=12 --set instalment_rate=6.9%
    salli decide emergency-fund --set target_months=6 --set set_aside=200,500 --json

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
| `windfall` | the amount, whether it is new money or already in your cash, the day, the account; two to five splits | **Each split you propose**: amounts onto your debts and into your investments; what a split doesn't put to work stays in cash. |
| `big-change` | what it is, when it starts and ends; how much more (or less) you would spend and take home each month; anything paid once at the start | **As things are**, and **the change**: its costs and income each month, and the one-off at the start. The comparison shows the cash timing: the low point and when, and the most a new cost could be with cash staying above zero. |
| `borrow` | new borrowing or refinancing a debt; how much (to refinance, what the debt owes now); when; the account; whether the money is spent on the day; any fee; one to four loans, each a rate and a term | **Each loan**: its payment, total interest and effect on cash and FI. To refinance, the new loan's money pays the old debt off in its first month. **Don't borrow**, or **Keep the debt**: your baseline. |
| `emergency-fund` | how many months of spending you want your cash to cover; one to four amounts you could set aside each month; from when, and for how long | **As things are**, and **Set aside each amount**: kept in cash out of your monthly surplus rather than invested. With the months your cash covers now, and when it would cover your target. |

Every template also asks how many years the long-run figures run (20 unless
you say).

## Questions and defaults

`salli decide <template> --questions` (or `GET
/v1/decisions/templates/{id}`) lists a template's questions, each with:

| Field | What it is |
|---|---|
| `id` | What the answer is called. |
| `type` | `amount` (above zero, in your base currency, a decimal string), `signed_amount` (`"+450"` more, `"-200"` less), `months` and `years` (whole numbers), `number` (a decimal string, like months of spending), `rate` (a yearly fraction: `"0.069"` is 6.9%), `date` (`YYYY-MM-DD`, not before the as-of date), `choice`, `debt` and `account` (one of your own, by id), `text`, and the lists `amounts`, `loans` and `splits`. |
| `required` | Whether it must be answered when it has no default. |
| `when` | When it is asked: once another question is answered, or answered so. |
| `default` | What it is when you leave it out, where that comes from (`source`) and a sentence saying so (`note`). |

A default comes only from what is honest:

- **The date:** the as-of date, or the first of the next month (debts are
  paid from the month after the as-of month, so a payment onto one lands
  then at the earliest).
- **Your debts:** the debt, when you have only one; what a debt owes now,
  when you refinance it.
- **Your principles:** the months of spending you want your cash to cover, when a
  principle of yours says so exactly (`emergency_months >= 6`).
- **Salli's own:** a plain name for a purchase, "once", "new money", and the
  20-year horizon.

Nothing else has a default. A price, a rate, a target, an amount to set
aside: you give them, or the template asks. A template never invents a
figure about your money.

The answers are checked as a scenario is: each problem comes back with its
path (`answers.instalment_rate: is required`), every problem at once, and a
JSON number for an amount is refused. `answers_schema` is the answers' JSON
Schema, with your own debts and accounts listed by id.

## What starting a decision returns

`POST /v1/decisions/start` (`start_decision`, `salli decide`) takes the
template's id, your answers and, if you like, an as-of date, and returns
(`salli.decision-start/1`):

| Field | What it holds |
|---|---|
| `question` | A question for your journal. A suggestion: put it in your words. |
| `answers` | Each answer as used, with where it came from (`given`, or a default's source). |
| `options` | Each option's label, a sentence saying what it is (`describes`), the scenario as run and its hash. |
| `comparison` | The options side by side, the trade between each two, the sensitivity to the real return and the break-evens, exactly as [comparing options](scenarios.md#comparing-options) gives them. |
| `principles` | Which of your principles the baseline and each option keep, break or can't tell, with the figures each read, as [checking](decisions.md#checking) gives them. |
| `cover` | For an emergency fund: your target in cash (the months times your monthly spending as shown, in today's money), the months your cash covers now, and the first month at whose end cash covers the target, under your baseline and each option. |
| `placeholders`, `is_stale`, `data_as_of` | What the figures rest on, and how fresh your ledger is. |
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

## Setting aside

`afford-it`'s waiting and the emergency fund keep part of your monthly
surplus in cash. That is a scenario change of its own, `set_aside`
([scenarios](scenarios.md#changes)): each month, that much of the regular
surplus stays in cash before the share you invest is taken from the rest. It
moves no money of its own, and can't keep more than the month's surplus.
What isn't invested doesn't grow, so the long-run figures and the FI month
show what it costs.

## Not built yet

- A rent-or-buy template (phase 3).
- Tax: a template's options don't yet run through your tax rules, so tax
  relief, on pension contributions say, isn't in their figures. Your rule
  sets will supply it, never a template.
- Stopping a set-aside once cash covers the target: give it a number of
  months instead.
