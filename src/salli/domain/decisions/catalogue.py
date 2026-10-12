"""
The decision templates Salli comes with (`salli.template/1`,
docs/templates.md). Pure.

| Template | Options it builds |
|---|---|
| `afford-it` | pay cash; spread it over the months you say, at the rate you say; wait the months you say, setting aside what you say |
| `debt-or-invest` | the money onto a debt; the same money invested; a split you say |
| `windfall` | the splits you propose, across debts, investing and cash |
| `big-change` | as things are; the change, with its cash timing |
| `borrow` | each loan you compare, against not borrowing (or keeping the debt as it is) |
| `emergency-fund` | as things are; each amount you could set aside a month |
| `rent-or-buy` | keep renting; buy, with each mortgage you compare |

Each builds its options from the answers alone: an amount goes where the
answers say, on the day they say, and nothing is projected. Where a
template needs a day the person didn't give, it uses the as-of date or the
first of the next month. A payment onto a debt may fall in the as-of month:
the engine pays it at that month's end, before the debt's first scheduled
payment. The time cash takes to cover a target is the engine's
(`engine.cover_target`), never worked out here, as is the month buying
draws level with renting (`comparison.level_from`). `debt-or-invest` and
`windfall` may invest into one of the person's own holdings, when they name
one (`_holding_question`); no template picks a holding, and none sells one.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from salli.domain.decisions.templates import (
    PLACEHOLDER_NOTE,
    Answers,
    Built,
    Choice,
    Default,
    Facts,
    Level,
    LoanOffer,
    OptionBuilt,
    Question,
    RecurringFact,
    Split,
    Template,
    UnknownTemplate,
    When,
    month_end,
    month_start,
    months_after,
    scenario,
)
from salli.domain.scenarios.schema import DEFAULT_HORIZON_YEARS, MAX_HORIZON_YEARS, MAX_TERM_MONTHS
from salli.domain.taxrules.common import Problem

# ── Defaults ─────────────────────────────────────────────────────────────────


def _holding_question() -> Question:
    """Which of the person's holdings money invested goes into: never a
    default, even when they hold only one (where money goes is theirs)."""
    return Question(
        "holding",
        "holding",
        "Into one of your holdings?",
        "One of your own holdings (salli holdings list), to see the units the money buys at "
        "its last recorded price. Leave it out to invest into your investments as a whole. "
        "Salli never picks one.",
    )


def _into(answers: Answers) -> dict[str, str]:
    holding: str | None = answers.get("holding")
    return {"holding": holding} if holding else {}


def _where(answers: Answers, facts: Facts) -> str:
    """Where money invested goes: the holding the person named, as they
    named it, or their investments."""
    named = facts.holding(answers.get("holding") or "")
    return named.name if named else "your investments"


def _in(answers: Answers, facts: Facts) -> str:
    named = facts.holding(answers.get("holding") or "")
    return f" in {named.name}" if named else ""


def _as_of(facts: Facts, _: Mapping[str, Any]) -> Default:
    return Default(
        facts.as_of.isoformat(), "as_of", "the as-of date (today, unless you chose a day)"
    )


def _next_month(facts: Facts, _: Mapping[str, Any]) -> Default:
    return Default(
        facts.next_month.isoformat(),
        "next_month",
        "the first of next month",
    )


def _only_debt(facts: Facts, _: Mapping[str, Any]) -> Default | None:
    if len(facts.debts) != 1:
        return None
    debt = facts.debts[0]
    return Default(
        debt.id, "your_debts", f"{debt.name}, the only debt you have that owes something"
    )


def _debt_balance(facts: Facts, answers: Mapping[str, Any]) -> Default | None:
    debt = facts.debt(str(answers.get("debt") or ""))
    if debt is None:
        return None
    return Default(facts.money(debt.balance), "your_debts", f"what {debt.name} owes now")


def _cover_principle(facts: Facts, _: Mapping[str, Any]) -> Default | None:
    if not facts.cover_principles:
        return None
    principle = facts.cover_principles[0]
    return Default(
        format(principle.months, "f"), "your_principles", f"from your principle “{principle.label}”"
    )


def _horizon(_: Facts, __: Mapping[str, Any]) -> Default:
    return Default(DEFAULT_HORIZON_YEARS, "salli", "Salli's usual horizon for long-run figures")


def _fixed(value: str, note: str) -> Any:
    def rule(_: Facts, __: Mapping[str, Any]) -> Default:
        return Default(value, "salli", note)

    return rule


def _horizon_question() -> Question:
    return Question(
        "horizon_years",
        "years",
        "How many years ahead do you want the long-run figures to run?",
        "Net worth and the break-evens are read at this horizon, in today's money. "
        "Payoff dates and the FI month are found wherever they fall.",
        default=_horizon,
        default_rule="20 years",
        minimum=1,
        maximum=MAX_HORIZON_YEARS,
    )


def _start_question(prompt: str, help: str, *, when: When | None = None) -> Question:
    return Question(
        "start",
        "date",
        prompt,
        help,
        default=_next_month,
        default_rule="the first of next month",
        when=when,
    )


# ── Wording ──────────────────────────────────────────────────────────────────


def _percent(rate: Decimal) -> str:
    text = format(rate * 100, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text or '0'}%"


def _months(n: int) -> str:
    return f"{n} month{'s' if n != 1 else ''}"


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _signed(value: Decimal, facts: Facts) -> str:
    text = facts.money(value)
    return text if text.startswith("-") else f"+{text}"


def _account(answers: Answers, key: str, field: str = "account") -> dict[str, str]:
    account = answers.get(key)
    return {field: account} if account else {}


# ── Afford it ────────────────────────────────────────────────────────────────


def _afford_check(answers: Answers, _: Facts) -> list[Problem]:
    if answers.get("instalment_months") is None and answers.get("wait_months") is None:
        return [
            Problem(
                "answers",
                "say how else you could pay: instalment_months (spread it), wait_months "
                "(wait and save), or both. A decision needs two options to compare",
            )
        ]
    return []


def _afford_build(answers: Answers, facts: Facts) -> Built:
    price = facts.money(answers["price"])
    what: str = answers["what"]
    day: dt.date = answers["date"]
    years: int = answers["horizon_years"]
    cur = facts.currency
    buy: dict[str, Any] = {
        "type": "one_off",
        "date": day.isoformat(),
        "amount": f"-{price}",
        **_account(answers, "account"),
        "label": what,
    }
    options = [
        OptionBuilt(
            "Pay cash",
            f"{price} {cur} out of cash on {day.isoformat()}.",
            scenario("Pay cash", years, [buy]),
        )
    ]
    months: int | None = answers.get("instalment_months")
    if months is not None:
        rate: Decimal = answers["instalment_rate"]
        label = f"Spread over {_months(months)}"
        loan = {
            "type": "loan",
            "principal": price,
            "annual_rate": format(rate, "f"),
            "term_months": months,
            "start": day.isoformat(),
            **_account(answers, "account", "into"),
            "label": f"{what}, over {_months(months)}",
        }
        options.append(
            OptionBuilt(
                label,
                f"The same {price} {cur} out on {day.isoformat()}, borrowed at {_percent(rate)} "
                f"a year and repaid in monthly payments over {_months(months)}.",
                scenario(label, years, [buy, loan]),
            )
        )
    wait: int | None = answers.get("wait_months")
    if wait is not None:
        when = months_after(day, wait)
        label = f"Wait {_months(wait)}"
        changes: list[dict[str, Any]] = [{**buy, "date": when.isoformat()}]
        save: Decimal | None = answers.get("save_monthly")
        describes = f"{price} {cur} out of cash on {when.isoformat()}"
        if save is not None:
            until = month_start(when) - dt.timedelta(days=1)
            changes.insert(
                0,
                {
                    "type": "set_aside",
                    "monthly": facts.money(save),
                    "from": day.isoformat(),
                    "to": until.isoformat(),
                    "label": f"Saving for {what}",
                },
            )
            describes += (
                f", with {facts.money(save)} {cur} of each month's surplus kept in cash until "
                "then rather than invested"
            )
        options.append(OptionBuilt(label, describes + ".", scenario(label, years, changes)))
    return Built(
        question=f"Can I afford {what} ({price} {cur}), and how would I pay for it?",
        options=tuple(options),
    )


AFFORD_IT = Template(
    id="afford-it",
    title="Afford it",
    summary="Whether a purchase fits, and how you might pay for it: cash, spread over "
    "months, or wait and save.",
    builds=(
        "Pay cash: the price out of cash on the day",
        "Spread it: the same, borrowed back at your rate and repaid over your months",
        "Wait and save: bought later, with what you set aside each month until then",
    ),
    questions=(
        Question("price", "amount", "What does it cost?", "In your base currency.", required=True),
        Question(
            "what",
            "text",
            "What is it?",
            "A few words: what the options call it.",
            default=_fixed("The purchase", "a plain name for it"),
            default_rule="“The purchase”",
        ),
        Question(
            "date",
            "date",
            "When would you pay?",
            "The day the money would go out, if you pay cash.",
            default=_as_of,
            default_rule="the as-of date",
        ),
        Question(
            "account",
            "account",
            "Which cash account would it come out of?",
            "Leave it out to take it from your cash as a whole.",
        ),
        Question(
            "instalment_months",
            "months",
            "Could you spread it? Over how many months?",
            "Leave it out if spreading it isn't on offer.",
            minimum=1,
            maximum=MAX_TERM_MONTHS,
        ),
        Question(
            "instalment_rate",
            "rate",
            "At what yearly rate?",
            'As a fraction: "0.069" is 6.9%, "0" an interest-free offer. Ask the lender for '
            "the rate it would charge you.",
            required=True,
            when=When("instalment_months"),
        ),
        Question(
            "wait_months",
            "months",
            "Could you wait? For how many months?",
            "Leave it out if waiting isn't an option.",
            minimum=1,
            maximum=120,
        ),
        Question(
            "save_monthly",
            "amount",
            "How much of your monthly surplus would you set aside while you wait?",
            "Kept in cash each month until you buy, rather than invested. Leave it out to "
            "wait without setting anything aside.",
            when=When("wait_months"),
        ),
        _horizon_question(),
    ),
    check=_afford_check,
    build=_afford_build,
)


# ── Debt or invest ───────────────────────────────────────────────────────────


def _debt_or_invest_check(answers: Answers, _: Facts) -> list[Problem]:
    split: Decimal | None = answers.get("split_on_debt")
    if split is not None and split >= answers["amount"]:
        return [
            Problem(
                "answers.split_on_debt",
                "is the part of the amount that goes on the debt, so less than the amount; "
                "the rest is invested",
            )
        ]
    return []


def _debt_or_invest_build(answers: Answers, facts: Facts) -> Built:
    debt = facts.debt(answers["debt"])
    assert debt is not None
    amount: Decimal = answers["amount"]
    start: dt.date = answers["start"]
    monthly = answers["how"] == "monthly"
    count: int = answers["months"] if monthly else 1
    last = month_end(start, count - 1)
    years: int = answers["horizon_years"]
    cur = facts.currency
    days = [months_after(start, k) for k in range(count)]

    def pay(value: Decimal) -> dict[str, Any]:
        return {
            "type": "extra_debt_payment",
            "debt": debt.id,
            "monthly": facts.money(value),
            "from": start.isoformat(),
            "to": last.isoformat(),
            "label": f"Extra on {debt.name}",
        }

    def invest(value: Decimal) -> list[dict[str, Any]]:
        return [
            {
                "type": "invest",
                "amount": facts.money(value),
                "date": day.isoformat(),
                **_into(answers),
                "label": "Invested",
            }
            for day in days
        ]

    when = (
        f"in {start.isoformat()[:7]}"
        if not monthly
        else f"each month from {start.isoformat()[:7]} to {last.isoformat()[:7]}"
    )
    money = facts.money(amount)
    pay_label = f"Pay down {debt.name}"
    options = [
        OptionBuilt(
            pay_label,
            f"{money} {cur} onto {debt.name} on top of its payments, {when} (until it is paid "
            "off, if that is sooner).",
            scenario(pay_label, years, [pay(amount)]),
        ),
        OptionBuilt(
            "Invest it",
            f"{money} {cur} moved from cash into {_where(answers, facts)}, {when}.",
            scenario("Invest it", years, invest(amount)),
        ),
    ]
    split: Decimal | None = answers.get("split_on_debt")
    if split is not None:
        rest = amount - split
        options.append(
            OptionBuilt(
                "Split",
                f"{facts.money(split)} {cur} onto {debt.name} and {facts.money(rest)} {cur} "
                f"invested, {when}.",
                scenario("Split", years, [pay(split), *invest(rest)]),
            )
        )
    every = " a month" if monthly else ""
    return Built(
        question=f"{money} {cur}{every}: onto {debt.name}, or invested?",
        options=tuple(options),
        notes=(
            "Once a debt is paid off, extra payments onto it stop, and that money stays in "
            "cash; the payments its schedule called for join your monthly surplus.",
        ),
    )


DEBT_OR_INVEST = Template(
    id="debt-or-invest",
    title="Debt or invest",
    summary="The same money onto a debt, or invested, or split between them: once, or every month.",
    builds=(
        "Pay down the debt: the money onto it on top of its payments",
        "Invest it: the same money moved into your investments",
        "Split: the part you say onto the debt, the rest invested",
    ),
    questions=(
        Question(
            "debt",
            "debt",
            "Which debt?",
            "One of your debts with terms (salli debts list).",
            required=True,
            default=_only_debt,
            default_rule="your only debt, when you have one",
        ),
        Question("amount", "amount", "How much?", "In your base currency.", required=True),
        Question(
            "how",
            "choice",
            "Once, or every month?",
            "A sum you have now, or an amount you could put towards it each month.",
            default=_fixed("once", "a single sum"),
            default_rule="once",
            choices=(Choice("once", "Once"), Choice("monthly", "Every month")),
        ),
        Question(
            "months",
            "months",
            "For how many months?",
            "How long you would keep it up.",
            required=True,
            minimum=1,
            maximum=48,
            when=When("how", "monthly"),
        ),
        _start_question(
            "From when?",
            "The day the first payment goes onto the debt, or is invested: both start "
            "together. In this month, a payment onto the debt lands at the month's end, "
            "before its next scheduled payment.",
        ),
        Question(
            "split_on_debt",
            "amount",
            "To compare a split too: how much of it would go on the debt?",
            "The rest is invested. Leave it out to compare the two alone.",
        ),
        _holding_question(),
        _horizon_question(),
    ),
    check=_debt_or_invest_check,
    build=_debt_or_invest_build,
)


# ── A windfall or a surplus ──────────────────────────────────────────────────


def _windfall_check(answers: Answers, facts: Facts) -> list[Problem]:
    problems: list[Problem] = []
    amount: Decimal = answers["amount"]
    splits: Sequence[Split] = answers["splits"]
    for i, split in enumerate(splits):
        total = sum((p.amount for p in split.debts), Decimal(0)) + (split.invest or Decimal(0))
        if total > amount:
            problems.append(
                Problem(
                    f"answers.splits[{i}]",
                    f"puts {facts.money(total)} to work, more than the {facts.money(amount)} "
                    "there is: what isn't put onto a debt or invested stays in cash",
                )
            )
    return problems


def _windfall_build(answers: Answers, facts: Facts) -> Built:
    amount = facts.money(answers["amount"])
    day: dt.date = answers["date"]
    new = answers["arrives"] == "new"
    years: int = answers["horizon_years"]
    cur = facts.currency
    options: list[OptionBuilt] = []
    for split in answers["splits"]:
        changes: list[dict[str, Any]] = []
        if new:
            role: str | None = answers.get("tax_role")
            changes.append(
                {
                    "type": "one_off",
                    "date": day.isoformat(),
                    "amount": amount,
                    **_account(answers, "account"),
                    **({"tax_role": role} if role else {}),
                    "label": "The windfall",
                }
            )
        said: list[str] = []
        for part in split.debts:
            debt = facts.debt(part.debt)
            assert debt is not None
            changes.append(
                {
                    "type": "extra_debt_payment",
                    "debt": debt.id,
                    "monthly": facts.money(part.amount),
                    "from": day.isoformat(),
                    "to": month_end(day).isoformat(),
                    "label": f"Onto {debt.name}",
                }
            )
            said.append(f"{facts.money(part.amount)} onto {debt.name}")
        if split.invest is not None:
            changes.append(
                {
                    "type": "invest",
                    "amount": facts.money(split.invest),
                    "date": day.isoformat(),
                    **_account(answers, "account", "from"),
                    **_into(answers),
                    "label": "Invested",
                }
            )
            said.append(f"{facts.money(split.invest)} invested{_in(answers, facts)}")
        describes = (
            f"Of {amount} {cur}: {', '.join(said)}; the rest kept in cash."
            if said
            else f"All {amount} {cur} kept in cash."
        )
        if new and answers.get("tax_role"):
            describes += f" It arrives before tax, as {answers['tax_role']}."
        options.append(OptionBuilt(split.label, describes, scenario(split.label, years, changes)))
    return Built(question=f"How to use {amount} {cur}?", options=tuple(options))


WINDFALL = Template(
    id="windfall",
    title="Use a windfall or surplus",
    summary="A sum (a bonus, a gift, savings built up) shared out the ways you propose, "
    "across debts, investing and cash.",
    builds=(
        "Each split you propose: amounts onto debts and into investments, the rest kept in cash",
    ),
    questions=(
        Question("amount", "amount", "How much is it?", "In your base currency.", required=True),
        Question(
            "arrives",
            "choice",
            "Is it new money, or already in your cash?",
            "New money arrives on the day (a bonus, a gift); a surplus is already in your cash.",
            default=_fixed("new", "new money arriving"),
            default_rule="new money",
            choices=(
                Choice("new", "New money: it arrives on the day"),
                Choice("in_cash", "Already in my cash"),
            ),
        ),
        Question(
            "tax_role",
            "tax_role",
            "Is it taxable? In which of your tax rules' roles?",
            "Leave it out if the amount is what reaches you. If it is taxable before it "
            "reaches you (a bonus, say), name the role your active tax rules count it in: the "
            "amount is then before tax, and Salli works out the tax with your rules.",
            when=When("arrives", "new"),
        ),
        Question(
            "date",
            "date",
            "When does it arrive, or when would you use it?",
            "Money is invested on this day, and a payment onto a debt lands in its month: "
            "in this month, at the month's end, before the debt's next scheduled payment.",
            default=_as_of,
            default_rule="the as-of date",
        ),
        Question(
            "account",
            "account",
            "Which cash account does it arrive in, or come from?",
            "Leave it out to use your cash as a whole.",
        ),
        Question(
            "splits",
            "splits",
            "How would you share it out?",
            "Two to five ways, each with a label: amounts onto your debts, an amount "
            "invested. What a split doesn't put to work stays in cash.",
            required=True,
            min_items=2,
            max_items=5,
        ),
        _holding_question(),
        _horizon_question(),
    ),
    check=_windfall_check,
    build=_windfall_build,
)


# ── A big recurring change ───────────────────────────────────────────────────


def _big_change_check(answers: Answers, _: Facts) -> list[Problem]:
    problems: list[Problem] = []
    if all(answers.get(k) is None for k in ("monthly_costs", "monthly_income", "upfront")):
        problems.append(
            Problem(
                "answers",
                "say what changes: monthly_costs, monthly_income, upfront, or more than one",
            )
        )
    end: dt.date | None = answers.get("end")
    if end is not None and end <= answers["start"]:
        problems.append(Problem("answers.end", "is on or before the start"))
    if answers["label"] == "As things are":
        problems.append(
            Problem("answers.label", "is the name of the other option: call it something else")
        )
    return problems


def _big_change_build(answers: Answers, facts: Facts) -> Built:
    label: str = answers["label"]
    start: dt.date = answers["start"]
    end: dt.date | None = answers.get("end")
    years: int = answers["horizon_years"]
    cur = facts.currency
    changes: list[dict[str, Any]] = []
    said: list[str] = []
    upfront: Decimal | None = answers.get("upfront")
    if upfront is not None:
        changes.append(
            {
                "type": "one_off",
                "date": start.isoformat(),
                "amount": f"-{facts.money(upfront)}",
                **_account(answers, "account"),
                "label": f"{label}: at the start",
            }
        )
        said.append(f"{facts.money(upfront)} {cur} once on {start.isoformat()}")
    costs: Decimal | None = answers.get("monthly_costs")
    if costs is not None:
        changes.append(
            {
                "type": "recurring",
                "amount": _signed(-costs, facts),
                "cadence": "monthly",
                "start": start.isoformat(),
                **({"end": end.isoformat()} if end else {}),
                **_account(answers, "account"),
                "label": f"{label}: costs",
            }
        )
        said.append(f"spending {_signed(costs, facts)} {cur} a month")
    income: Decimal | None = answers.get("monthly_income")
    if income is not None:
        role: str | None = answers.get("income_tax_role")
        changes.append(
            {
                "type": "income_change",
                "monthly": _signed(income, facts),
                "from": start.isoformat(),
                **({"to": end.isoformat()} if end else {}),
                **({"tax_role": role} if role else {}),
                "label": f"{label}: income",
            }
        )
        said.append(
            f"pay before tax {_signed(income, facts)} {cur} a month, as {role}"
            if role
            else f"take-home pay {_signed(income, facts)} {cur} a month"
        )
    span = f"from {start.isoformat()}" + (f" to {end.isoformat()}" if end else "")
    return Built(
        question=f"{label}: what would it do to my money?",
        options=(
            OptionBuilt(
                "As things are", "No change: your baseline.", scenario("As things are", years, [])
            ),
            OptionBuilt(
                label, f"{_sentence('; '.join(said))}, {span}.", scenario(label, years, changes)
            ),
        ),
    )


BIG_CHANGE = Template(
    id="big-change",
    title="Big recurring change",
    summary="A new flat, a new job, a car: what changes month after month, and what it "
    "costs at the start, against things as they are.",
    builds=(
        "As things are: your baseline",
        "The change: its costs and income each month from the start, and anything paid once",
    ),
    questions=(
        Question(
            "label",
            "text",
            "What is the change?",
            "A few words: “New flat”, “New job”, “A car”.",
            required=True,
        ),
        _start_question("When would it start?", "The day the first month's costs or pay change."),
        Question(
            "monthly_costs",
            "signed_amount",
            "How much more would you spend a month?",
            'In your base currency: "+450" more, "-200" less. Leave it out if spending stays '
            "the same.",
        ),
        Question(
            "monthly_income",
            "signed_amount",
            "How much more would you take home a month?",
            'In your base currency: "+600" more, "-300" less. After tax, unless you name the '
            "tax role it is paid in (next): then before tax. Leave it out if it stays the same.",
        ),
        Question(
            "income_tax_role",
            "tax_role",
            "Is that pay before tax? In which of your tax rules' roles?",
            "Leave it out if the amount is take-home pay. If it is before tax, name the role "
            "your active tax rules count it in (your salary's, say): Salli then works out the "
            "tax with your rules.",
            when=When("monthly_income"),
        ),
        Question(
            "upfront",
            "amount",
            "Anything to pay once at the start?",
            "A deposit, moving costs, a down payment. Leave it out if there's none.",
        ),
        Question(
            "end",
            "date",
            "Does it end? On what day?",
            "Leave it out if it goes on.",
        ),
        Question(
            "account",
            "account",
            "Which cash account would the costs come out of?",
            "Leave it out to use your cash as a whole.",
        ),
        _horizon_question(),
    ),
    check=_big_change_check,
    build=_big_change_build,
)


# ── Borrow or refinance ──────────────────────────────────────────────────────


def _borrow_start(facts: Facts, answers: Mapping[str, Any]) -> Default:
    if answers.get("purpose") == "refinance":
        return _next_month(facts, answers)
    return _as_of(facts, answers)


def _loan_label(offer: LoanOffer) -> str:
    return offer.label or f"{_percent(offer.annual_rate)} over {_months(offer.term_months)}"


def _borrow_check(answers: Answers, _: Facts) -> list[Problem]:
    labels = [_loan_label(o) for o in answers["loans"]]
    if len(set(labels)) != len(labels):
        return [Problem("answers.loans", "has two loans that would be called the same: label each")]
    return []


def _borrow_build(answers: Answers, facts: Facts) -> Built:
    principal = facts.money(answers["principal"])
    start: dt.date = answers["start"]
    years: int = answers["horizon_years"]
    cur = facts.currency
    refinance = answers["purpose"] == "refinance"
    debt = facts.debt(answers["debt"]) if refinance else None
    fee: Decimal | None = answers.get("fee")
    options: list[OptionBuilt] = []
    for offer in answers["loans"]:
        label = _loan_label(offer)
        changes: list[dict[str, Any]] = [
            {
                "type": "loan",
                "principal": principal,
                "annual_rate": format(offer.annual_rate, "f"),
                "term_months": offer.term_months,
                "start": start.isoformat(),
                **_account(answers, "into", "into"),
                "label": label,
            }
        ]
        terms = f"{principal} {cur} at {_percent(offer.annual_rate)} a year over {_months(offer.term_months)}"
        if debt is not None:
            changes.append(
                {
                    "type": "extra_debt_payment",
                    "debt": debt.id,
                    "monthly": principal,
                    "from": start.isoformat(),
                    "to": month_end(start).isoformat(),
                    "label": f"Pay off {debt.name}",
                }
            )
            describes = f"Borrow {terms} from {start.isoformat()}, and pay {debt.name} off with it"
        elif answers["spent"] == "spent":
            changes.append(
                {
                    "type": "one_off",
                    "date": start.isoformat(),
                    "amount": f"-{principal}",
                    **_account(answers, "into"),
                    "label": answers["what"],
                }
            )
            describes = (
                f"Borrow {terms} from {start.isoformat()}, spent on {answers['what']} that day"
            )
        else:
            describes = f"Borrow {terms} from {start.isoformat()}, kept in cash"
        if fee is not None:
            changes.append(
                {
                    "type": "one_off",
                    "date": start.isoformat(),
                    "amount": f"-{facts.money(fee)}",
                    **_account(answers, "into"),
                    "label": "Fee",
                }
            )
            describes += f", with a fee of {facts.money(fee)} {cur}"
        options.append(OptionBuilt(label, describes + ".", scenario(label, years, changes)))
    if debt is not None:
        keep = f"Keep {debt.name}"
        options.append(
            OptionBuilt(keep, f"{debt.name} as it is: your baseline.", scenario(keep, years, []))
        )
        question = f"Refinance {debt.name}?"
        when = (
            f"at the end of {start.isoformat()[:7]}, before its next payment"
            if start < facts.next_month
            else f"in {start.isoformat()[:7]}, on top of that month's payment"
        )
        notes: tuple[str, ...] = (
            f"The new loan's money pays {debt.name} off {when}; whatever it doesn't need "
            "stays in cash.",
        )
    else:
        options.append(
            OptionBuilt(
                "Don't borrow", "No loan: your baseline.", scenario("Don't borrow", years, [])
            )
        )
        question = f"Borrow {principal} {cur}? Which loan?"
        notes = ()
    return Built(question=question, options=tuple(options), notes=notes)


BORROW = Template(
    id="borrow",
    title="Borrow or refinance",
    summary="Loans side by side, each with its payment and total interest, and what it does "
    "to your cash and FI: for new borrowing, or to replace a debt you have.",
    builds=(
        "Each loan you compare: its payments, interest and effect on cash and FI",
        "Don't borrow, or keep the debt as it is: your baseline",
    ),
    questions=(
        Question(
            "purpose",
            "choice",
            "New borrowing, or replacing a debt you have?",
            "Refinancing pays one of your debts off with the new loan.",
            default=_fixed("borrow", "new borrowing"),
            default_rule="new borrowing",
            choices=(Choice("borrow", "New borrowing"), Choice("refinance", "Refinance a debt")),
        ),
        Question(
            "debt",
            "debt",
            "Which debt would it replace?",
            "One of your debts with terms (salli debts list).",
            required=True,
            default=_only_debt,
            default_rule="your only debt, when you have one",
            when=When("purpose", "refinance"),
        ),
        Question(
            "principal",
            "amount",
            "How much would you borrow?",
            "In your base currency. To refinance, what the debt owes now, unless you say "
            "otherwise.",
            required=True,
            default=_debt_balance,
            default_rule="to refinance: what the debt owes now",
        ),
        Question(
            "start",
            "date",
            "When would you take it out?",
            "The day the money arrives. To refinance, the old debt is paid off with it in "
            "that month: in this month, at the month's end, before its next payment.",
            default=_borrow_start,
            default_rule="the as-of date; to refinance, the first of next month",
        ),
        Question(
            "into",
            "account",
            "Which cash account would the money go into?",
            "Leave it out to use your cash as a whole.",
        ),
        Question(
            "spent",
            "choice",
            "Is the money spent on the day, or kept in cash?",
            "Spent on what you borrow it for, or kept as cash.",
            default=_fixed("spent", "spent on what it is for"),
            default_rule="spent",
            choices=(Choice("spent", "Spent on the day"), Choice("kept", "Kept in cash")),
            when=When("purpose", "borrow"),
        ),
        Question(
            "what",
            "text",
            "What is it for?",
            "A few words: what the purchase is called in the options.",
            default=_fixed("What it pays for", "a plain name for it"),
            default_rule="“What it pays for”",
            when=When("spent", "spent"),
        ),
        Question(
            "fee",
            "amount",
            "Any fee to pay when you take it out?",
            "An arrangement fee, paid from cash. Leave it out if there's none.",
        ),
        Question(
            "loans",
            "loans",
            "Which loans would you compare?",
            "One to four, each with its yearly rate and its term in months, and a label if "
            "you like. Use the rates the lenders would charge you.",
            required=True,
            min_items=1,
            max_items=4,
        ),
        _horizon_question(),
    ),
    check=_borrow_check,
    build=_borrow_build,
)


# ── Emergency fund ───────────────────────────────────────────────────────────


def _emergency_build(answers: Answers, facts: Facts) -> Built:
    target: Decimal = answers["target_months"]
    start: dt.date = answers["start"]
    months: int | None = answers.get("months")
    years: int = answers["horizon_years"]
    cur = facts.currency
    to = month_end(start, months - 1) if months is not None else None
    span = f"from {start.isoformat()[:7]}" + (f" to {to.isoformat()[:7]}" if to else ", for good")
    options = [
        OptionBuilt(
            "As things are", "No change: your baseline.", scenario("As things are", years, [])
        )
    ]
    for amount in answers["set_aside"]:
        money = facts.money(amount)
        label = f"Set aside {money} a month"
        options.append(
            OptionBuilt(
                label,
                f"{money} {cur} of each month's surplus kept in cash, {span}, rather than "
                "invested.",
                scenario(
                    label,
                    years,
                    [
                        {
                            "type": "set_aside",
                            "monthly": money,
                            "from": start.isoformat(),
                            **({"to": to.isoformat()} if to else {}),
                            "label": "Emergency fund",
                        }
                    ],
                ),
            )
        )
    return Built(
        question=f"How to build cash to cover {format(target, 'f')} months of spending?",
        options=tuple(options),
        cover_months=target,
    )


EMERGENCY_FUND = Template(
    id="emergency-fund",
    title="Emergency fund",
    summary="How many months of spending your cash covers now, and when it would cover your "
    "target, as things are and with each amount you could set aside.",
    builds=(
        "As things are: your baseline",
        "Set aside each amount you say, every month: kept in cash rather than invested",
    ),
    questions=(
        Question(
            "target_months",
            "number",
            "How many months of spending do you want your cash to cover?",
            "Counted in your essential spending when your spending carries need tags, all of "
            "it otherwise. Yours to choose.",
            required=True,
            default=_cover_principle,
            default_rule="the months your principle asks for, when you have one",
            maximum=120,
        ),
        Question(
            "set_aside",
            "amounts",
            "How much could you set aside each month?",
            "One to four amounts to compare, each kept in cash out of your monthly surplus "
            "rather than invested.",
            required=True,
            min_items=1,
            max_items=4,
        ),
        _start_question("From when?", "The month you would start setting it aside."),
        Question(
            "months",
            "months",
            "For how many months?",
            "Leave it out to keep going.",
            minimum=1,
            maximum=MAX_TERM_MONTHS,
        ),
        _horizon_question(),
    ),
    check=lambda _a, _f: [],
    build=_emergency_build,
    notes=(
        "Cash earns nothing in Salli's figures, so what you set aside instead of investing "
        "shows in the long-run figures too.",
    ),
)


# ── Rent or buy ──────────────────────────────────────────────────────────────

KEEP_RENTING = "Keep renting"
#: A scenario's cadences: a rent the ledger shows at another (every two
#: weeks, twice a month) is stated again monthly, at its monthly equivalent.
_STATED = {"weekly": "weekly", "monthly": "monthly", "quarterly": "quarterly", "yearly": "yearly"}
_PER_MONTH = {"biweekly": Decimal(26) / Decimal(12), "semimonthly": Decimal(2)}
_UNIT = {"weekly": "week", "monthly": "month", "quarterly": "quarter", "yearly": "year"}


def _placeholder(_: Facts, __: Mapping[str, Any]) -> Default:
    return Default("0", "placeholder", PLACEHOLDER_NOTE)


def _mortgage_label(offer: LoanOffer) -> str:
    return (
        offer.label or f"Mortgage, {_percent(offer.annual_rate)} over {_months(offer.term_months)}"
    )


def _buy_label(offer: LoanOffer, offers: int) -> str:
    return "Buy" if offers == 1 else f"Buy, {offer.label or _loan_label(offer)}"


def _rent_or_buy_check(answers: Answers, _: Facts) -> list[Problem]:
    problems: list[Problem] = []
    if answers["deposit"] >= answers["price"]:
        problems.append(
            Problem(
                "answers.deposit",
                "is less than the price: the mortgage is the price less the deposit",
            )
        )
    rent, monthly = answers.get("rent"), answers.get("rent_monthly")
    if rent is None and monthly is None:
        problems.append(
            Problem(
                "answers.rent",
                "is required: name your rent among your recurring payments (rent), or give "
                'what you pay a month (rent_monthly, "0" if none)',
            )
        )
    elif rent is not None and monthly is not None:
        problems.append(
            Problem(
                "answers.rent_monthly",
                "is for a rent the ledger doesn't show: leave it out when you name rent",
            )
        )
    offers: Sequence[LoanOffer] = answers["mortgages"]
    labels = [_buy_label(o, len(offers)) for o in offers]
    if len(set(labels)) != len(labels):
        problems.append(
            Problem(
                "answers.mortgages", "has two mortgages that would be called the same: label each"
            )
        )
    return problems


def _growth_text(answers: Answers, key: str, what: str) -> str:
    growth: Decimal = answers[key]
    if answers.sources.get(key) == "placeholder":
        return f"{what} 0% a year beyond inflation (a placeholder)"
    return f"{what} {_percent(growth)} a year beyond inflation"


def _growth_field(answers: Answers, key: str) -> dict[str, str]:
    """The growth as the person gave it; nothing for the placeholder, so the
    engine (for the home) or the start (for the rent) labels it."""
    if answers.sources.get(key) == "placeholder":
        return {}
    return {"real_growth": format(answers[key], "f")}


def _rent_changes(answers: Answers, facts: Facts, day: dt.date) -> tuple[list[dict[str, Any]], str]:
    """Keep renting's changes, and what it is in a sentence: the ledger's rent
    stopped from the day and stated again as a recurring cost growing at the
    rent's growth (so both options state rent the same way), or a rent the
    ledger doesn't show added as a new cost."""
    cur = facts.currency
    grows = _growth_text(answers, "rent_growth", "growing")
    growth = _growth_field(answers, "rent_growth")
    key: str | None = answers.get("rent")
    if key is not None:
        fact = facts.payment(key)
        assert fact is not None
        cadence = _STATED.get(fact.cadence)
        if cadence is not None:
            amount, start = fact.amount, fact.first_on_or_after(day)
        else:
            cadence = "monthly"
            amount, start = facts_money(fact, facts), day
        changes: list[dict[str, Any]] = [
            {
                "type": "stop_recurring",
                "key": key,
                "from": day.isoformat(),
                "label": "Rent as it is",
            },
            {
                "type": "recurring",
                "amount": f"-{facts.money(amount)}",
                "cadence": cadence,
                "start": start.isoformat(),
                **({"account": fact.account} if fact.account else {}),
                **growth,
                "label": f"Rent: {fact.payee}",
            },
        ]
        return changes, (
            f"Rent to {fact.payee} goes on: {facts.money(amount)} {cur} a {_UNIT[cadence]} from "
            f"{start.isoformat()}, {grows}."
        )
    monthly: Decimal = answers["rent_monthly"]
    if monthly == 0:
        return [], "No rent, as now: your baseline."
    return [
        {
            "type": "recurring",
            "amount": f"-{facts.money(monthly)}",
            "cadence": "monthly",
            "start": day.isoformat(),
            **_account(answers, "account"),
            **growth,
            "label": "Rent",
        }
    ], f"Rent of {facts.money(monthly)} {cur} a month from {day.isoformat()}, {grows}."


def facts_money(fact: RecurringFact, facts: Facts) -> Decimal:
    """A payment the ledger shows every two weeks or twice a month, a month."""
    return Decimal(facts.money(fact.amount * _PER_MONTH[fact.cadence]))


def _rent_or_buy_build(answers: Answers, facts: Facts) -> Built:
    cur = facts.currency
    price: Decimal = answers["price"]
    deposit: Decimal = answers["deposit"]
    principal = price - deposit
    day: dt.date = answers["date"]
    years: int = answers["horizon_years"]
    buying: Decimal = answers["buying_costs"]
    owning: Decimal = answers["owning_costs"]
    selling: Decimal = answers["selling_costs"]
    offers: Sequence[LoanOffer] = answers["mortgages"]
    key: str | None = answers.get("rent")

    rent_changes, rent_says = _rent_changes(answers, facts, day)
    options = [OptionBuilt(KEEP_RENTING, rent_says, scenario(KEEP_RENTING, years, rent_changes))]
    home: dict[str, Any] = {
        "type": "asset",
        "price": facts.money(price),
        "date": day.isoformat(),
        **_account(answers, "account", "from"),
        **_growth_field(answers, "home_growth"),
        "selling_costs": format(selling, "f"),
        "label": "The home",
    }
    costs: list[dict[str, Any]] = []
    if buying > 0:
        costs.append(
            {
                "type": "one_off",
                "date": day.isoformat(),
                "amount": f"-{facts.money(buying)}",
                **_account(answers, "account"),
                "label": "Buying costs",
            }
        )
    if owning > 0:
        costs.append(
            {
                "type": "recurring",
                "amount": f"-{facts.money(owning)}",
                "cadence": "monthly",
                "start": day.isoformat(),
                **_account(answers, "account"),
                "label": "Owning costs",
            }
        )
    stop = (
        [{"type": "stop_recurring", "key": key, "from": day.isoformat(), "label": "Rent stopped"}]
        if key is not None
        else []
    )
    for offer in offers:
        label = _buy_label(offer, len(offers))
        mortgage = {
            "type": "loan",
            "principal": facts.money(principal),
            "annual_rate": format(offer.annual_rate, "f"),
            "term_months": offer.term_months,
            "start": day.isoformat(),
            **_account(answers, "account", "into"),
            "label": _mortgage_label(offer),
        }
        says = (
            f"{facts.money(price)} {cur} on {day.isoformat()}: {facts.money(deposit)} {cur} down "
            f"from cash and a mortgage of {facts.money(principal)} {cur} at "
            f"{_percent(offer.annual_rate)} a year over {_months(offer.term_months)}; "
            f"{facts.money(buying)} {cur} of buying costs once and {facts.money(owning)} {cur} "
            f"a month of owning costs; the home {_growth_text(answers, 'home_growth', 'growing')}, "
            f"counted at its value less {_percent(selling)} selling costs"
            + ("; the rent stopped from that day." if key is not None else ".")
        )
        options.append(
            OptionBuilt(label, says, scenario(label, years, [home, mortgage, *costs, *stop]))
        )

    rent_placeholder = answers.sources.get("rent_growth") == "placeholder" and bool(rent_changes)
    notes: list[str] = []
    if answers.sources.get("home_growth") == "placeholder":
        notes.append(
            "The home's growth beyond inflation is 0%, a placeholder, not a forecast: set your "
            "own view. The asset_growth break-even says what growth would change the answer."
        )
    if rent_placeholder:
        notes.append(
            "The rent's growth beyond inflation is 0% (it rises with inflation), a placeholder, "
            "not a forecast: set your own view."
        )
    notes.append(
        "`level` reads, for each way of buying, the first month-end from the purchase on from "
        "which its net worth is at least keeping renting's at every month-end to the horizon: "
        "how long the home must be kept for buying to have drawn level, on these assumptions."
    )
    return Built(
        question=f"Keep renting, or buy a home for {facts.money(price)} {cur}?",
        options=tuple(options),
        notes=tuple(notes),
        placeholders=("rent_growth",) if rent_placeholder else (),
        level=Level(KEEP_RENTING, day.isoformat()[:7]),
    )


RENT_OR_BUY = Template(
    id="rent-or-buy",
    title="Rent or buy",
    summary="Keep renting, or buy a home with each mortgage you compare: laid out as "
    "consequences, with the house-price growth at which the answer turns.",
    builds=(
        "Keep renting: your rent goes on, rising at the rent's growth",
        "Buy, with each mortgage: the home from cash and the mortgage, buying and owning "
        "costs, and the rent stopped",
    ),
    questions=(
        Question(
            "price", "amount", "What would the home cost?", "In your base currency.", required=True
        ),
        Question(
            "date",
            "date",
            "When would you buy?",
            "The day the price leaves cash and the mortgage arrives; the rent stops from it.",
            default=_next_month,
            default_rule="the first of next month",
        ),
        Question(
            "deposit",
            "amount",
            "How much would you put down?",
            "Out of your cash. The mortgage is the price less it.",
            required=True,
        ),
        Question(
            "account",
            "account",
            "Which cash account would the money come out of?",
            "The deposit, buying costs and owning costs. Leave it out to use your cash as a whole.",
        ),
        Question(
            "mortgages",
            "loans",
            "Which mortgages would you compare?",
            "One to three, each with its yearly rate and its term in months (up to 600), and a "
            "label if you like. Use the rates the lenders would offer you: each is held fixed for "
            "its whole term.",
            required=True,
            min_items=1,
            max_items=3,
        ),
        Question(
            "buying_costs",
            "amount_or_zero",
            "What would buying cost, once (fees, and any tax on buying)?",
            'Paid from cash on the day; "0" if nothing. A tax on buying is yours to give, from '
            "your own rules: Salli knows no country's.",
            required=True,
        ),
        Question(
            "owning_costs",
            "amount_or_zero",
            "What would owning cost a month (maintenance, insurance, service charges, property "
            "taxes)?",
            'In today\'s money, from the day you buy; "0" if nothing. Leaving them low flatters '
            "buying.",
            required=True,
        ),
        Question(
            "rent",
            "recurring",
            "Which of your recurring payments is your rent?",
            "By its key (salli insights recurring): it goes on if you keep renting, and stops if "
            "you buy. Leave it out if your ledger doesn't show your rent, and give rent_monthly.",
        ),
        Question(
            "rent_monthly",
            "amount_or_zero",
            "If your ledger doesn't show your rent: what is it a month?",
            'In today\'s money; "0" if you pay none. Keeping renting then adds it as a new cost.',
        ),
        Question(
            "rent_growth",
            "growth",
            "How fast do you expect your rent to grow beyond inflation, a year?",
            'A signed fraction: "0.01" is 1% a year more than prices, "-0.005" half a percent '
            "less. Your own view; left out, 0 (it rises with inflation), labelled a placeholder.",
            default=_placeholder,
            default_rule="0, a placeholder",
        ),
        Question(
            "home_growth",
            "growth",
            "How fast do you expect the home's value to grow beyond inflation, a year?",
            "A signed fraction, as for the rent. Your own view; left out, 0 (it keeps its value "
            "in today's money), labelled a placeholder. The break-even says what growth would "
            "change the answer.",
            default=_placeholder,
            default_rule="0, a placeholder",
        ),
        Question(
            "selling_costs",
            "rate",
            "What would selling the home cost, as a share of its value?",
            '"0.03" is 3%: agents\' fees and any tax on selling; "0" is an answer. The home '
            "counts in net worth at its value less them.",
            required=True,
        ),
        _horizon_question(),
    ),
    check=_rent_or_buy_check,
    build=_rent_or_buy_build,
    notes=(
        "The growth of the home's value and of the rent is your own view, or a labelled 0% "
        "beyond inflation, never a forecast: the house-price growth at which the answer turns "
        "(the asset_growth break-even) is the figure that matters.",
        "Each mortgage's rate is held fixed for its term: resets aren't modelled.",
        "A home is one asset, illiquid and undiversified: the comparison doesn't price that risk.",
        "Owning costs are what you give: leaving them low flatters buying.",
        "Tax on buying, owning or selling a home comes only from your own rules: a tax on "
        "buying is a buying cost you give; nothing else about a home's tax is modelled.",
        "Salli knows nothing about any local property market: research behind your figures "
        "needs its sources.",
        "The home counts in net worth at what it would fetch, its value less its selling "
        "costs, so buying starts behind by them; like any other asset it funds no withdrawals "
        "in FI.",
    ),
)


#: Every template, in the order they are listed.
TEMPLATES: tuple[Template, ...] = (
    AFFORD_IT,
    DEBT_OR_INVEST,
    WINDFALL,
    BIG_CHANGE,
    BORROW,
    EMERGENCY_FUND,
    RENT_OR_BUY,
)
BY_ID: Mapping[str, Template] = {t.id: t for t in TEMPLATES}


def get(template_id: str) -> Template:
    """The template with this id; UnknownTemplate otherwise."""
    found = BY_ID.get(template_id)
    if found is None:
        raise UnknownTemplate(template_id, list(BY_ID))
    return found
