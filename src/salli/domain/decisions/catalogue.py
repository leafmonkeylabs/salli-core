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

Each builds its options from the answers alone: an amount goes where the
answers say, on the day they say, and nothing is projected. Where a
template needs a day the person didn't give, it uses the as-of date or the
first of the next month (debts are paid from the month after the as-of
month, so a payment onto one lands then at the earliest). The time cash
takes to cover a target is the engine's (`engine.cover_target`), never
worked out here.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from salli.domain.decisions.templates import (
    Answers,
    Built,
    Choice,
    Default,
    Facts,
    LoanOffer,
    OptionBuilt,
    Question,
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


def _starts_next_month(answers: Answers, facts: Facts, key: str = "start") -> list[Problem]:
    day = answers.get(key)
    if isinstance(day, dt.date) and day < facts.next_month:
        return [
            Problem(
                f"answers.{key}",
                f"is in the as-of month: Salli pays debts from the month after it, so start "
                f"on {facts.next_month.isoformat()} or later",
            )
        ]
    return []


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


def _debt_or_invest_check(answers: Answers, facts: Facts) -> list[Problem]:
    problems = _starts_next_month(answers, facts)
    split: Decimal | None = answers.get("split_on_debt")
    if split is not None and split >= answers["amount"]:
        problems.append(
            Problem(
                "answers.split_on_debt",
                "is the part of the amount that goes on the debt, so less than the amount; "
                "the rest is invested",
            )
        )
    return problems


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
            f"{money} {cur} moved from cash into your investments, {when}.",
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
            "A payment onto a debt lands from next month at the earliest; the money is "
            "invested on the same day, so both start together.",
        ),
        Question(
            "split_on_debt",
            "amount",
            "To compare a split too: how much of it would go on the debt?",
            "The rest is invested. Leave it out to compare the two alone.",
        ),
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
    pay_day = max(day, facts.next_month)
    options: list[OptionBuilt] = []
    for split in answers["splits"]:
        changes: list[dict[str, Any]] = []
        if new:
            changes.append(
                {
                    "type": "one_off",
                    "date": day.isoformat(),
                    "amount": amount,
                    **_account(answers, "account"),
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
                    "from": pay_day.isoformat(),
                    "to": month_end(pay_day).isoformat(),
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
                    "label": "Invested",
                }
            )
            said.append(f"{facts.money(split.invest)} invested")
        describes = (
            f"Of {amount} {cur}: {', '.join(said)}; the rest kept in cash."
            if said
            else f"All {amount} {cur} kept in cash."
        )
        options.append(OptionBuilt(split.label, describes, scenario(split.label, years, changes)))
    notes: list[str] = []
    if day < facts.next_month and any(s.debts for s in answers["splits"]):
        notes.append(
            f"Debts are paid from {facts.next_month.isoformat()[:7]} on, so a payment onto one "
            "lands then."
        )
    return Built(
        question=f"How to use {amount} {cur}?",
        options=tuple(options),
        notes=tuple(notes),
    )


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
            "date",
            "date",
            "When does it arrive, or when would you use it?",
            "Money is invested on this day; a payment onto a debt lands in this month, or "
            "next month if this one is the as-of month.",
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
        changes.append(
            {
                "type": "income_change",
                "monthly_net": _signed(income, facts),
                "from": start.isoformat(),
                **({"to": end.isoformat()} if end else {}),
                "label": f"{label}: income",
            }
        )
        said.append(f"take-home pay {_signed(income, facts)} {cur} a month")
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
            'After tax, in your base currency: "+600" more, "-300" less. Leave it out if it '
            "stays the same.",
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


def _borrow_check(answers: Answers, facts: Facts) -> list[Problem]:
    problems: list[Problem] = []
    if answers["purpose"] == "refinance":
        problems += _starts_next_month(answers, facts)
    labels = [_loan_label(o) for o in answers["loans"]]
    if len(set(labels)) != len(labels):
        problems.append(
            Problem("answers.loans", "has two loans that would be called the same: label each")
        )
    return problems


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
        notes: tuple[str, ...] = (
            f"The new loan's money pays {debt.name} off in {start.isoformat()[:7]}, on top of "
            "that month's payment; whatever it doesn't need stays in cash.",
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
            "To refinance, from next month on: debts are paid from the month after this one.",
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


#: Every template, in the order they are listed.
TEMPLATES: tuple[Template, ...] = (
    AFFORD_IT,
    DEBT_OR_INVEST,
    WINDFALL,
    BIG_CHANGE,
    BORROW,
    EMERGENCY_FUND,
)
BY_ID: Mapping[str, Template] = {t.id: t for t in TEMPLATES}


def get(template_id: str) -> Template:
    """The template with this id; UnknownTemplate otherwise."""
    found = BY_ID.get(template_id)
    if found is None:
        raise UnknownTemplate(template_id, list(BY_ID))
    return found
