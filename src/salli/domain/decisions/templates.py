"""
Decision templates (`salli.template/1`): a common decision as a short list
of typed questions, and the options its answers build, each a
`salli.scenario/1` document. Pure: no I/O, no model.

A template is a convenience, not advice. It asks what the person is
weighing, builds the options they describe, and leaves every figure to the
scenario engine and the choice to them. So a template:

- **asks typed questions**, each validated with a path people can follow
  (`answers.instalment_rate`): an amount in the base currency (above zero,
  or one where 0 is an answer), a whole number of months, a rate, a growth
  beyond inflation, a date, a choice, one of the person's debts, cash
  accounts, holdings or recurring payments, one of the income or deduction
  roles in their active tax rules, a short text, or a list of amounts, loans
  or splits;
- **draws a default only from what is honest**: the as-of date or the first
  of the next month, the person's own debts (the only one they have, and
  what it owes) and their own principles (the months of spending one asks
  cash to cover). A question with no honest default has none, and must be
  answered: a template never invents a price, a rate or a target, and never
  picks a holding, even the only one (where money goes is the person's). The
  one exception is rent-or-buy's two growths beyond inflation (a rent's, a
  home's), which default to 0 as a labelled placeholder (source
  `placeholder`): not a forecast, but how the baseline already treats every
  other asset and recurring amount, with the break-even beside it
  (docs/design/decision-lab-phase-3.md, decision 22);
- **builds options** as scenarios, by a pure function of the answers and the
  person's facts (`Facts`, read from their baseline and principles). It
  moves amounts where the answers say and never projects anything: what an
  option leads to is the engine's to say;
- **knows no country**: no tax relief, no product, no local rule. What is
  local comes from the person's own rule sets and principles.

Nothing here ranks, scores or recommends: a template's output names options,
never a "best" one (tests/unit/domain/test_decision_templates.py keeps it
so).
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Literal, cast

from pydantic import ValidationError

from salli.domain.baseline.models import Baseline
from salli.domain.currency import quantize, quantum
from salli.domain.decisions.principles import Principle
from salli.domain.reports import forecast as forecasting
from salli.domain.reports.insights import Cadence
from salli.domain.scenarios import schema
from salli.domain.taxrules.common import Problem, join_path
from salli.domain.taxrules.expr import FIGURE, Binary, Expr, Num, Ref

SCHEMA_ID = "salli.template/1"

#: The longest a text answer (a label, what something is) may be.
MAX_TEXT = 120
#: The figures a principle's cash target may be read from.
COVER_FIGURES = ("emergency_months", "emergency_months_in_12_months")

QuestionType = Literal[
    "amount",
    "amount_or_zero",
    "signed_amount",
    "months",
    "years",
    "number",
    "rate",
    "growth",
    "date",
    "choice",
    "debt",
    "account",
    "holding",
    "recurring",
    "tax_role",
    "text",
    "amounts",
    "loans",
    "splits",
]
DefaultSource = Literal[
    "as_of", "next_month", "your_debts", "your_principles", "salli", "placeholder"
]
#: What a placeholder default says, wherever one is used.
PLACEHOLDER_NOTE = "a placeholder, not a forecast: set your own view"


class TemplateError(ValueError):
    """A template, or answers to it, Salli can't build options from, with
    every problem found."""

    def __init__(self, problems: Sequence[Problem]) -> None:
        self.problems = tuple(problems)
        shown = "; ".join(str(p) for p in self.problems[:5])
        more = f" (and {len(self.problems) - 5} more)" if len(self.problems) > 5 else ""
        super().__init__(f"{len(self.problems)} problem(s): {shown}{more}")


class UnknownTemplate(KeyError):
    """No template has this id."""

    def __init__(self, template_id: str, known: Sequence[str]) -> None:
        self.template_id = template_id
        self.known = tuple(known)
        super().__init__(template_id)

    def __str__(self) -> str:
        return f"No decision template {self.template_id!r}; there are: {', '.join(self.known)}"


# ── What a template may read of the person's money ──────────────────────────


@dataclass(frozen=True)
class DebtFact:
    """One of the person's debts with terms: what it owes on the as-of date."""

    id: str
    name: str
    balance: Decimal
    apr: Decimal


@dataclass(frozen=True)
class AccountFact:
    """One of the person's cash accounts held in the base currency: the ones
    a scenario's change may move."""

    id: str
    name: str


@dataclass(frozen=True)
class HoldingFact:
    """One of the person's holdings a scenario can invest into (its
    transactions recorded, a price on or before the as-of date, and a rate
    into the base currency): their own id, symbol and name for it."""

    id: str
    symbol: str
    name: str


@dataclass(frozen=True)
class TaxRoleFact:
    """A role in the person's active tax rules a change may be tagged with:
    of kind income or deduction."""

    key: str
    kind: str
    label: str


@dataclass(frozen=True)
class RecurringFact:
    """One of the person's recurring payments out (a rent, a bill), as the
    ledger shows it: what a template may stop and state again. Only a key
    the ledger shows as one payment out of a cash account, whose amount is
    known in the base currency."""

    key: str
    payee: str
    #: How often, as the ledger shows it (`weekly` … `yearly`).
    cadence: Cadence
    #: Each time, above zero, in the base currency.
    amount: Decimal
    #: The cash account it leaves, when a change may name it (one of the
    #: person's cash accounts in the base currency; not a card).
    account: str | None
    #: The next day it is expected, and the days of the month it falls on.
    next_expected: dt.date
    anchor_days: tuple[int, ...] = ()

    def first_on_or_after(self, day: dt.date) -> dt.date:
        """The first day it is expected on or after `day`."""
        found = forecasting.schedule(
            self.next_expected,
            self.cadence,
            self.anchor_days,
            day,
            day + dt.timedelta(days=400),
        )
        return next((d for d in found if d >= day), day)


@dataclass(frozen=True)
class CoverPrinciple:
    """A principle asking cash to cover a number of months of spending
    (`emergency_months >= 6`)."""

    label: str
    months: Decimal


@dataclass(frozen=True)
class Facts:
    """What a template reads of the person's money, for its defaults and to
    check their answers: never a figure an option leads to."""

    as_of: dt.date
    currency: str
    debts: tuple[DebtFact, ...] = ()
    accounts: tuple[AccountFact, ...] = ()
    cover_principles: tuple[CoverPrinciple, ...] = ()
    tax_roles: tuple[TaxRoleFact, ...] = ()
    holdings: tuple[HoldingFact, ...] = ()
    recurring: tuple[RecurringFact, ...] = ()

    @property
    def next_month(self) -> dt.date:
        """The first day of the month after the as-of date's: the first
        month of things to come, and of a debt's scheduled payments."""
        return month_start(self.as_of, 1)

    def debt(self, debt_id: str) -> DebtFact | None:
        return next((d for d in self.debts if d.id == debt_id), None)

    def account(self, account_id: str) -> AccountFact | None:
        return next((a for a in self.accounts if a.id == account_id), None)

    def tax_role(self, key: str) -> TaxRoleFact | None:
        return next((r for r in self.tax_roles if r.key == key), None)

    def holding(self, holding_id: str) -> HoldingFact | None:
        return next((h for h in self.holdings if h.id == holding_id), None)

    def payment(self, key: str) -> RecurringFact | None:
        return next((r for r in self.recurring if r.key == key), None)

    def money(self, value: Decimal) -> str:
        """An amount as a decimal string to the currency's smallest unit."""
        return format(quantize(value, self.currency, strict=False), "f")


def cover_months_of(expr: Expr) -> Decimal | None:
    """N, when a check is exactly `emergency_months >= N` (or `N <=
    emergency_months`, or the same of the months in twelve months)."""
    node = expr.root
    if not isinstance(node, Binary):
        return None
    if (
        node.op == ">="
        and isinstance(node.left, Ref)
        and isinstance(node.right, Num)
        and node.left.namespace == FIGURE
        and node.left.key in COVER_FIGURES
    ):
        return node.right.value
    if (
        node.op == "<="
        and isinstance(node.left, Num)
        and isinstance(node.right, Ref)
        and node.right.namespace == FIGURE
        and node.right.key in COVER_FIGURES
    ):
        return node.left.value
    return None


def cover_principles(principles: Sequence[tuple[Principle, Expr]]) -> tuple[CoverPrinciple, ...]:
    """The principles (each with its compiled check) that ask cash to cover
    a number of months of spending, in their order."""
    out: list[CoverPrinciple] = []
    for principle, expr in principles:
        months = cover_months_of(expr)
        if months is not None and months > 0:
            out.append(CoverPrinciple(principle.label, months))
    return tuple(out)


def facts_of(baseline: Baseline, principles: Sequence[tuple[Principle, Expr]] = ()) -> Facts:
    """The facts a template reads, from the person's baseline and their
    principles in use (each with its compiled check)."""
    return Facts(
        as_of=baseline.as_of,
        currency=baseline.currency,
        debts=tuple(
            DebtFact(d.debt_id, d.name, d.balance, d.apr) for d in baseline.debts if d.balance > 0
        ),
        accounts=tuple(
            AccountFact(b.account_id, b.name)
            for b in baseline.balances
            if b.role == "cash" and b.currency == baseline.currency and b.is_active
        ),
        cover_principles=cover_principles(principles),
        tax_roles=tax_roles_of(baseline),
        holdings=tuple(
            HoldingFact(h.holding_id, h.symbol, h.name)
            for h in baseline.holdings
            if h.tracked and h.price is not None and h.fx_rate is not None
        ),
        recurring=recurring_of(baseline),
    )


def recurring_of(baseline: Baseline) -> tuple[RecurringFact, ...]:
    """The person's recurring payments out a template may name: each key the
    ledger shows as one payment out of a cash account (not a transfer
    between their own accounts), with its amount in the base currency
    (converted at the as-of rate when it is held in another), by key."""
    own = {b.account_id for b in baseline.balances}
    cash = baseline.cash_accounts
    # The accounts a change may name: cash-role accounts in the base
    # currency (a card's payments go back on the cash total).
    movable = {
        b.account_id
        for b in baseline.balances
        if b.role == "cash" and b.currency == baseline.currency and b.is_active
    }
    counts: dict[str, int] = {}
    for r in baseline.recurring:
        counts[r.key] = counts.get(r.key, 0) + 1
    rates = {x.currency: x.rate for x in baseline.rates if x.rate is not None}
    out: list[RecurringFact] = []
    for r in baseline.recurring:
        if r.direction != "out" or r.account_id in own or counts[r.key] != 1:
            continue
        account = r.money_account_id if r.money_account_id in cash else None
        currency = cash[account][0] if account else r.currency
        amount = r.money_amount if account else None
        if amount is None and r.currency == currency:
            amount = r.typical_amount
        if amount is None:
            continue
        if currency != baseline.currency:
            rate = rates.get(currency)
            if rate is None:
                continue
            amount = amount * rate
        amount = quantize(amount, baseline.currency, strict=False)
        if amount <= 0:
            continue
        out.append(
            RecurringFact(
                r.key,
                r.payee,
                r.cadence,
                amount,
                account if account in movable else None,
                dt.date.fromisoformat(r.next_expected),
                tuple(r.anchor_days),
            )
        )
    return tuple(sorted(out, key=lambda f: f.key))


def tax_roles_of(baseline: Baseline) -> tuple[TaxRoleFact, ...]:
    """The roles a change may be tagged with: those of kind income or
    deduction in the person's active tax rules, each once, by key."""
    found: dict[str, TaxRoleFact] = {}
    for rules in baseline.tax.rules:
        for role in rules.document.roles:
            if role.kind in ("income", "deduction") and role.key not in found:
                found[role.key] = TaxRoleFact(role.key, role.kind, role.label)
    return tuple(sorted(found.values(), key=lambda r: r.key))


# ── Dates ────────────────────────────────────────────────────────────────────


def month_start(day: dt.date, months: int = 0) -> dt.date:
    """The first day of the month `months` after `day`'s."""
    index = day.year * 12 + day.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


def month_end(day: dt.date, months: int = 0) -> dt.date:
    """The last day of the month `months` after `day`'s."""
    first = month_start(day, months)
    return first.replace(day=calendar.monthrange(first.year, first.month)[1])


def months_after(day: dt.date, months: int) -> dt.date:
    """The same day of the month `months` later, kept to a short month."""
    first = month_start(day, months)
    return first.replace(day=min(day.day, calendar.monthrange(first.year, first.month)[1]))


# ── Questions ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Default:
    """A default an answer takes when it isn't given: its value (as the
    answer would be written), where it comes from, and a sentence saying so."""

    value: Any
    source: DefaultSource
    note: str


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class When:
    """A question is asked only when another has an answer (`equals` None)
    or a particular one."""

    question: str
    equals: str | None = None

    def holds(self, values: Mapping[str, Any]) -> bool:
        if self.question not in values or values[self.question] is None:
            return False
        return self.equals is None or values[self.question] == self.equals

    def text(self) -> str:
        if self.equals is None:
            return f"{self.question} is answered"
        return f"{self.question} is {self.equals}"


DefaultRule = Callable[[Facts, Mapping[str, Any]], Default | None]


@dataclass(frozen=True)
class Question:
    """One thing a template asks: typed, with what it means, and its default
    when there is an honest one."""

    id: str
    type: QuestionType
    #: What to ask, as a question.
    prompt: str
    #: What it means, and how the answer is used.
    help: str
    #: Whether it must be answered when it has no default.
    required: bool = False
    #: The default, from the person's facts and the answers before it.
    default: DefaultRule | None = None
    #: Where the default comes from, for a reader who hasn't answered yet.
    default_rule: str | None = None
    choices: tuple[Choice, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    #: For the list types: how many items.
    min_items: int | None = None
    max_items: int | None = None
    #: Asked only when this holds.
    when: When | None = None


# ── Answers ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LoanOffer:
    """A loan to compare: its rate and term, and what to call it."""

    annual_rate: Decimal
    term_months: int
    label: str | None = None


@dataclass(frozen=True)
class DebtPart:
    debt: str
    amount: Decimal


@dataclass(frozen=True)
class Split:
    """One way of sharing out a sum: amounts onto debts and into
    investments; the rest stays in cash."""

    label: str
    debts: tuple[DebtPart, ...] = ()
    invest: Decimal | None = None


@dataclass(frozen=True)
class Answers:
    """The answers as Salli read them, each typed, and where each came from:
    "given", or a default's source."""

    values: Mapping[str, Any]
    sources: Mapping[str, str]
    notes: Mapping[str, str] = field(default_factory=dict[str, str])

    def __getitem__(self, key: str) -> Any:
        return self.values.get(key)

    def get(self, key: str) -> Any:
        return self.values.get(key)


_DECIMAL = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _amount(value: Any, facts: Facts, *, signed: bool = False, zero: bool = False) -> Decimal:
    number = schema.parse_amount(value)
    if zero and number < 0:
        raise ValueError('must be zero or more: "0" if there is none')
    if not signed and not zero and number <= 0:
        raise ValueError("must be greater than zero")
    if signed and number == 0:
        raise ValueError("must not be zero: leave it out instead")
    if number != quantize(number, facts.currency, strict=False):
        raise ValueError(
            f"has more decimals than {facts.currency}'s smallest unit "
            f"({quantum(facts.currency, strict=False)})"
        )
    return number


def _whole(value: Any, question: Question) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("must be a whole number, like 12")
    low = question.minimum if question.minimum is not None else 1
    if value < low or (question.maximum is not None and value > question.maximum):
        top = f" to {question.maximum}" if question.maximum is not None else " or more"
        raise ValueError(f"is a whole number from {low}{top}")
    return value


def _number(value: Any, question: Question) -> Decimal:
    if isinstance(value, bool | int | float) or not isinstance(value, str):
        raise ValueError('write it as a decimal string, like "6" or "4.5"')
    if not _DECIMAL.fullmatch(value):
        raise ValueError(f'{value!r} is not a decimal string, like "6" or "4.5"')
    number = Decimal(value)
    if number <= 0:
        raise ValueError("must be greater than zero")
    if question.maximum is not None and number > question.maximum:
        raise ValueError(f"may be at most {question.maximum}")
    return number


def _rate(value: Any) -> Decimal:
    if isinstance(value, bool | int | float) or not isinstance(value, str):
        raise ValueError('write a rate as a decimal string, a yearly fraction: "0.069" is 6.9%')
    if not _DECIMAL.fullmatch(value):
        raise ValueError(f'{value!r} is not a yearly fraction, like "0.069" for 6.9%')
    number = Decimal(value)
    if number > 1:
        raise ValueError('a rate is a fraction between "0" and "1" ("0.069" is 6.9%)')
    return number


_SIGNED_DECIMAL = re.compile(r"^[+-]?[0-9]+(\.[0-9]+)?$")


def _growth(value: Any) -> Decimal:
    if isinstance(value, bool | int | float) or not isinstance(value, str):
        raise ValueError(
            'write a growth as a decimal string, a yearly fraction beyond inflation: "0.01" '
            'is 1% a year, "-0.005" half a percent less'
        )
    if not _SIGNED_DECIMAL.fullmatch(value):
        raise ValueError(f'{value!r} is not a yearly fraction, like "0.01" for 1% or "-0.005"')
    number = Decimal(value)
    if not -schema.MAX_GROWTH <= number <= schema.MAX_GROWTH:
        raise ValueError('a growth is a yearly fraction from "-1" to "1" ("0.01" is 1%)')
    return number


def _recurring(value: Any, facts: Facts) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("is one of your recurring payments, by its key (salli insights recurring)")
    if facts.payment(value) is None:
        yours = ", ".join(f"{r.payee} ({r.key})" for r in facts.recurring) or "none"
        raise ValueError(
            f"{value!r} is not one of your recurring payments out of a cash account; yours: "
            f"{yours}. If the ledger doesn't show it, give the amount instead"
        )
    return value


def _date(value: Any, facts: Facts) -> dt.date:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("must be a date written YYYY-MM-DD")
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("must be a date written YYYY-MM-DD") from None
    if day < facts.as_of:
        raise ValueError(
            f"is before the as-of date ({facts.as_of.isoformat()}): a decision is about what "
            "comes next"
        )
    return day


def _tax_role(value: Any, facts: Facts) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("is a role in your active tax rules, by its key")
    if facts.tax_role(value) is None:
        yours = ", ".join(f"{r.key} ({r.kind})" for r in facts.tax_roles)
        raise ValueError(
            f"{value!r} is not an income or deduction role of your active tax rules; "
            + (f"yours: {yours}" if yours else "you have no active tax rules")
        )
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("is a few words of text")
    text = " ".join(value.split())
    if len(text) > MAX_TEXT:
        raise ValueError(f"may be at most {MAX_TEXT} characters")
    return text


def _debt(value: Any, facts: Facts) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("is one of your debts, by its id (salli debts list)")
    if facts.debt(value) is None:
        names = ", ".join(f"{d.name} ({d.id})" for d in facts.debts) or "none"
        raise ValueError(f"{value!r} is not one of your debts owing something; yours: {names}")
    return value


def _holding(value: Any, facts: Facts) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("is one of your holdings, by its id (salli holdings list)")
    if facts.holding(value) is None:
        names = ", ".join(f"{h.name} ({h.id})" for h in facts.holdings) or "none"
        raise ValueError(
            f"{value!r} is not one of your holdings with its transactions and a price "
            f"recorded; yours: {names}"
        )
    return value


def _account(value: Any, facts: Facts) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("is one of your cash accounts, by its id")
    if facts.account(value) is None:
        raise ValueError(
            f"{value!r} is not one of your cash accounts in {facts.currency}: name one, or "
            "leave it out to use your cash as a whole"
        )
    return value


class _Problems:
    def __init__(self) -> None:
        self.found: list[Problem] = []

    def add(self, path: str, message: str) -> None:
        self.found.append(Problem(path, message))


def _items(value: Any, question: Question, path: str, out: _Problems) -> list[Any] | None:
    if not isinstance(value, list):
        out.add(path, "is a list")
        return None
    items = cast("list[Any]", value)
    low, high = question.min_items or 1, question.max_items
    if len(items) < low or (high is not None and len(items) > high):
        out.add(path, f"has {len(items)}; it takes {low} to {high}")
        return None
    return items


def _fields(item: Any, path: str, allowed: set[str], out: _Problems) -> Mapping[str, Any] | None:
    if not isinstance(item, dict):
        out.add(path, "is an object")
        return None
    mapping = cast("dict[str, Any]", item)
    for key in sorted(set(mapping) - allowed):
        out.add(join_path(path, key), "is not a field here")
    return mapping


def _parse(question: Question, value: Any, facts: Facts, path: str, out: _Problems) -> Any:
    """The answer, typed, or None with its problems added."""

    def attempt(fn: Callable[[], Any], at: str = path) -> Any:
        try:
            return fn()
        except ValueError as error:
            out.add(at, str(error))
            return None

    match question.type:
        case "amount":
            return attempt(lambda: _amount(value, facts))
        case "amount_or_zero":
            return attempt(lambda: _amount(value, facts, zero=True))
        case "signed_amount":
            return attempt(lambda: _amount(value, facts, signed=True))
        case "months" | "years":
            return attempt(lambda: _whole(value, question))
        case "number":
            return attempt(lambda: _number(value, question))
        case "rate":
            return attempt(lambda: _rate(value))
        case "growth":
            return attempt(lambda: _growth(value))
        case "date":
            return attempt(lambda: _date(value, facts))
        case "text":
            return attempt(lambda: _text(value))
        case "debt":
            return attempt(lambda: _debt(value, facts))
        case "account":
            return attempt(lambda: _account(value, facts))
        case "holding":
            return attempt(lambda: _holding(value, facts))
        case "recurring":
            return attempt(lambda: _recurring(value, facts))
        case "tax_role":
            return attempt(lambda: _tax_role(value, facts))
        case "choice":
            values = [c.value for c in question.choices]
            if value not in values:
                out.add(path, f"is one of: {', '.join(values)}")
                return None
            return cast("str", value)
        case "amounts":
            items = _items(value, question, path, out)
            if items is None:
                return None
            parsed = [
                attempt(lambda v=v: _amount(v, facts), join_path(path, i))
                for i, v in enumerate(items)
            ]
            if len(set(parsed)) != len(parsed):
                out.add(path, "has the same amount twice: give each once")
            return None if any(p is None for p in parsed) else parsed
        case "loans":
            return _loans(question, value, path, out)
        case "splits":
            return _splits(question, value, facts, path, out)


def _loans(question: Question, value: Any, path: str, out: _Problems) -> list[LoanOffer] | None:
    items = _items(value, question, path, out)
    if items is None:
        return None
    offers: list[LoanOffer] = []
    ok = True
    for i, item in enumerate(items):
        at = join_path(path, i)
        mapping = _fields(item, at, {"annual_rate", "term_months", "label"}, out)
        if mapping is None:
            ok = False
            continue
        rate: Decimal | None = None
        term: int | None = None
        label: str | None = None
        if "annual_rate" not in mapping:
            out.add(join_path(at, "annual_rate"), "is required")
        else:
            try:
                rate = _rate(mapping["annual_rate"])
            except ValueError as error:
                out.add(join_path(at, "annual_rate"), str(error))
        if "term_months" not in mapping:
            out.add(join_path(at, "term_months"), "is required")
        else:
            try:
                term = _whole(
                    mapping["term_months"],
                    Question(
                        "term_months", "months", "", "", minimum=1, maximum=schema.MAX_TERM_MONTHS
                    ),
                )
            except ValueError as error:
                out.add(join_path(at, "term_months"), str(error))
        if mapping.get("label") is not None:
            try:
                label = _text(mapping["label"])
            except ValueError as error:
                out.add(join_path(at, "label"), str(error))
        if rate is None or term is None:
            ok = False
            continue
        offers.append(LoanOffer(rate, term, label))
    return offers if ok else None


def _splits(
    question: Question, value: Any, facts: Facts, path: str, out: _Problems
) -> list[Split] | None:
    items = _items(value, question, path, out)
    if items is None:
        return None
    splits: list[Split] = []
    ok = True
    for i, item in enumerate(items):
        at = join_path(path, i)
        mapping = _fields(item, at, {"label", "debts", "invest"}, out)
        if mapping is None:
            ok = False
            continue
        label: str | None = None
        try:
            label = _text(mapping.get("label"))
        except ValueError as error:
            out.add(join_path(at, "label"), str(error) if "label" in mapping else "is required")
        parts: list[DebtPart] = []
        raw = mapping.get("debts", [])
        if not isinstance(raw, list):
            out.add(join_path(at, "debts"), "is a list of {debt, amount}")
            raw = []
        seen: set[str] = set()
        for j, part in enumerate(cast("list[Any]", raw)):
            pat = join_path(at, "debts", j)
            fields = _fields(part, pat, {"debt", "amount"}, out)
            if fields is None:
                ok = False
                continue
            debt: str | None = None
            amount: Decimal | None = None
            for name in ("debt", "amount"):
                if name not in fields:
                    out.add(join_path(pat, name), "is required")
                    continue
                try:
                    if name == "debt":
                        debt = _debt(fields[name], facts)
                    else:
                        amount = _amount(fields[name], facts)
                except ValueError as error:
                    out.add(join_path(pat, name), str(error))
            if debt is None or amount is None:
                ok = False
                continue
            if debt in seen:
                out.add(join_path(pat, "debt"), "is in this split already: give each debt once")
                ok = False
            seen.add(debt)
            parts.append(DebtPart(debt, amount))
        invest: Decimal | None = None
        if mapping.get("invest") is not None:
            try:
                invest = _amount(mapping["invest"], facts)
            except ValueError as error:
                out.add(join_path(at, "invest"), str(error))
                ok = False
        if label is None:
            ok = False
            continue
        splits.append(Split(label, tuple(parts), invest))
    if ok and len({s.label for s in splits}) != len(splits):
        out.add(path, "has two splits with one label: give each its own")
        ok = False
    return splits if ok else None


# ── Templates ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OptionBuilt:
    """One option a template built: its label, what it is in a sentence,
    and the scenario Salli runs."""

    label: str
    describes: str
    scenario: schema.Scenario


@dataclass(frozen=True)
class Level:
    """For a template that asks when one option draws level with another
    (rent or buy): the option the others are read against, and the month
    from which to read (the purchase's)."""

    against: str
    from_month: str


@dataclass(frozen=True)
class Built:
    """What a template built from the answers."""

    #: A question for the journal, if the person wants one; theirs to
    #: change.
    question: str
    options: tuple[OptionBuilt, ...]
    #: The months of spending to read the time to, for a template that
    #: asks for one (the emergency fund).
    cover_months: Decimal | None = None
    notes: tuple[str, ...] = ()
    #: The template's own placeholders, beside the engine's: an answer a
    #: placeholder default gave that no scenario field says ("rent_growth").
    placeholders: tuple[str, ...] = ()
    #: When each option draws level with one, read from the timelines.
    level: Level | None = None


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    summary: str
    #: The options it builds, described.
    builds: tuple[str, ...]
    questions: tuple[Question, ...]
    #: What the person checks across answers, beyond each one's own.
    check: Callable[[Answers, Facts], list[Problem]]
    build: Callable[[Answers, Facts], Built]
    notes: tuple[str, ...] = ()

    def question(self, question_id: str) -> Question | None:
        return next((q for q in self.questions if q.id == question_id), None)


def resolve(template: Template, data: Any, facts: Facts) -> Answers:
    """The answers to `template`, each parsed and checked, with defaults
    filled in where honest; TemplateError with every problem found (each
    under `answers.`)."""
    out = _Problems()
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise TemplateError([Problem("answers", "is an object of answers, by question id")])
    given = cast("dict[str, Any]", data)
    known = {q.id for q in template.questions}
    for key in sorted(set(given) - known):
        out.add(
            join_path("answers", key),
            f"is not a question of {template.id}; its questions are: {', '.join(q.id for q in template.questions)}",
        )
    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    notes: dict[str, str] = {}
    for q in template.questions:
        path = join_path("answers", q.id)
        value = given.get(q.id)
        if q.when is not None and not q.when.holds(values):
            if value is not None:
                out.add(path, f"is asked only when {q.when.text()}")
            continue
        if value is not None:
            parsed = _parse(q, value, facts, path, out)
            if parsed is not None:
                values[q.id] = parsed
                sources[q.id] = "given"
            continue
        default = q.default(facts, values) if q.default else None
        if default is not None:
            parsed = _parse(q, default.value, facts, path, out)
            if parsed is not None:
                values[q.id] = parsed
                sources[q.id] = default.source
                notes[q.id] = default.note
        elif q.required:
            out.add(path, f"is required: {q.prompt}")
    answers = Answers(values, sources, notes)
    if out.found:
        raise TemplateError(out.found)
    problems = template.check(answers, facts)
    if problems:
        raise TemplateError(problems)
    return answers


def tax_answers(data: Any) -> schema.ScenarioTax | None:
    """Answers to the person's tax rules' questions (`tax_answers`), as every
    option's `tax`; TemplateError with each problem under `tax_answers`."""
    if data is None or data == {}:
        return None
    try:
        return schema.ScenarioTax.model_validate({"answers": data})
    except ValidationError as error:
        raise TemplateError(
            [
                Problem(join_path("tax_answers", *[str(x) for x in e["loc"][1:]]), e["msg"])
                for e in error.errors(include_url=False)
            ]
        ) from None


def build(template: Template, data: Any, facts: Facts, tax: Any = None) -> tuple[Answers, Built]:
    """The answers read and the options built, each with the answers to the
    tax rules' questions (`tax`) when given; TemplateError with every
    problem found (a scenario a template built that isn't valid is a bug,
    reported with its option's path rather than hidden)."""
    answers = resolve(template, data, facts)
    asked = tax_answers(tax)
    built = template.build(answers, facts)
    labels = [o.label for o in built.options]
    if len(set(labels)) != len(labels):
        raise TemplateError(
            [Problem("answers", "two options would have one label: give each its own")]
        )
    if asked is not None:
        built = replace(
            built,
            options=tuple(
                OptionBuilt(o.label, o.describes, o.scenario.model_copy(update={"tax": asked}))
                for o in built.options
            ),
        )
    return answers, built


def scenario(
    label: str, horizon_years: int, changes: Sequence[Mapping[str, Any]]
) -> schema.Scenario:
    """A scenario document, validated as any other is."""
    try:
        return schema.load(
            {
                "schema": schema.SCHEMA_ID,
                "label": label,
                "horizon_years": horizon_years,
                "changes": list(changes),
            }
        )
    except ValidationError as error:
        raise TemplateError(
            [Problem(f"options[{label}].{p.path}", p.message) for p in schema.problems(error)]
        ) from None


# ── Views ────────────────────────────────────────────────────────────────────


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, LoanOffer):
        return {
            "annual_rate": format(value.annual_rate, "f"),
            "term_months": value.term_months,
            **({"label": value.label} if value.label else {}),
        }
    if isinstance(value, Split):
        return {
            "label": value.label,
            "debts": [{"debt": p.debt, "amount": format(p.amount, "f")} for p in value.debts],
            **({"invest": format(value.invest, "f")} if value.invest is not None else {}),
        }
    if isinstance(value, list):
        return [_jsonable(v) for v in cast("list[Any]", value)]
    return value


def answers_view(template: Template, answers: Answers) -> list[dict[str, Any]]:
    """The answers as used, in the template's order, each with where it
    came from."""
    return [
        {
            "id": q.id,
            "value": _jsonable(answers.values[q.id]),
            "source": answers.sources[q.id],
            "note": answers.notes.get(q.id),
        }
        for q in template.questions
        if q.id in answers.values
    ]


_AMOUNT_SCHEMA: dict[str, Any] = {
    "type": "string",
    "pattern": r"^\+?[0-9]+(\.[0-9]+)?$",
    "description": 'An amount above zero in your base currency, as a decimal string: "2400.00".',
}
_RATE_SCHEMA: dict[str, Any] = {
    "type": "string",
    "pattern": r"^[0-9]+(\.[0-9]+)?$",
    "description": 'A yearly rate as a fraction, a decimal string: "0.069" is 6.9%.',
}
_GROWTH_SCHEMA: dict[str, Any] = {
    "type": "string",
    "pattern": _SIGNED_DECIMAL.pattern,
    "description": 'A yearly growth beyond inflation, a signed fraction as a decimal string: "0.01" '
    'is 1% a year more than prices, "-0.005" half a percent less.',
}


def _value_schema(q: Question, facts: Facts | None) -> dict[str, Any]:
    match q.type:
        case "amount":
            return dict(_AMOUNT_SCHEMA)
        case "amount_or_zero":
            return {
                "type": "string",
                "pattern": r"^\+?[0-9]+(\.[0-9]+)?$",
                "description": 'An amount in your base currency as a decimal string, "0" if there '
                'is none: "1200.00".',
            }
        case "signed_amount":
            return {
                "type": "string",
                "pattern": schema.AMOUNT_PATTERN,
                "description": 'A signed amount in your base currency: "+450.00" more, "-200" less.',
            }
        case "months" | "years":
            return {
                "type": "integer",
                "minimum": q.minimum or 1,
                **({"maximum": q.maximum} if q.maximum else {}),
            }
        case "number":
            return {
                "type": "string",
                "pattern": r"^[0-9]+(\.[0-9]+)?$",
                "description": 'A number above zero as a decimal string: "6" or "4.5".',
            }
        case "rate":
            return dict(_RATE_SCHEMA)
        case "growth":
            return dict(_GROWTH_SCHEMA)
        case "date":
            return {"type": "string", "format": "date", "pattern": _DATE.pattern}
        case "text":
            return {"type": "string", "minLength": 1, "maxLength": MAX_TEXT}
        case "choice":
            return {"type": "string", "enum": [c.value for c in q.choices]}
        case "debt":
            out: dict[str, Any] = {"type": "string", "description": "One of your debts, by its id."}
            if facts is not None and facts.debts:
                out["enum"] = [d.id for d in facts.debts]
            return out
        case "account":
            out = {
                "type": "string",
                "description": "One of your cash accounts in your base currency, by its id.",
            }
            if facts is not None and facts.accounts:
                out["enum"] = [a.id for a in facts.accounts]
            return out
        case "holding":
            out = {
                "type": "string",
                "description": "One of your own holdings, by its id. Salli never picks one.",
            }
            if facts is not None and facts.holdings:
                out["enum"] = [h.id for h in facts.holdings]
            return out
        case "recurring":
            out = {
                "type": "string",
                "description": "One of your recurring payments out, by its key (salli insights "
                "recurring)"
                + (
                    ": " + ", ".join(f"{r.key} ({r.payee})" for r in facts.recurring) + "."
                    if facts is not None and facts.recurring
                    else "."
                ),
            }
            if facts is not None and facts.recurring:
                out["enum"] = [r.key for r in facts.recurring]
            return out
        case "tax_role":
            out = {
                "type": "string",
                "description": "A role of kind income or deduction in your active tax rules, "
                "by its key.",
            }
            if facts is not None and facts.tax_roles:
                out["enum"] = [r.key for r in facts.tax_roles]
            return out
        case "amounts":
            return {
                "type": "array",
                "items": dict(_AMOUNT_SCHEMA),
                "minItems": q.min_items or 1,
                **({"maxItems": q.max_items} if q.max_items else {}),
            }
        case "loans":
            return {
                "type": "array",
                "minItems": q.min_items or 1,
                **({"maxItems": q.max_items} if q.max_items else {}),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["annual_rate", "term_months"],
                    "properties": {
                        "annual_rate": dict(_RATE_SCHEMA),
                        "term_months": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": schema.MAX_TERM_MONTHS,
                        },
                        "label": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT},
                    },
                },
            }
        case "splits":
            debt = _value_schema(Question("debt", "debt", "", ""), facts)
            return {
                "type": "array",
                "minItems": q.min_items or 1,
                **({"maxItems": q.max_items} if q.max_items else {}),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["label"],
                    "properties": {
                        "label": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT},
                        "debts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["debt", "amount"],
                                "properties": {"debt": debt, "amount": dict(_AMOUNT_SCHEMA)},
                            },
                        },
                        "invest": dict(_AMOUNT_SCHEMA),
                    },
                },
            }


def answers_schema(template: Template, facts: Facts | None = None) -> dict[str, Any]:
    """The JSON Schema (Draft 2020-12) of the answers object: every question
    by its id. None is required by the schema itself: a question with a
    default may be left out, and which others are needed depends on the
    answers (`required` and `when` on each question say)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Answers to the {template.title} template ({SCHEMA_ID})",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            q.id: {**_value_schema(q, facts), "title": q.prompt, "description": q.help}
            for q in template.questions
        },
    }


def question_view(q: Question, facts: Facts | None) -> dict[str, Any]:
    default = q.default(facts, {}) if (q.default and facts is not None) else None
    return {
        "id": q.id,
        "type": q.type,
        "prompt": q.prompt,
        "help": q.help,
        "required": q.required,
        "when": None if q.when is None else {"question": q.when.question, "equals": q.when.equals},
        "default": None
        if default is None
        else {"value": _jsonable(default.value), "source": default.source, "note": default.note},
        "default_rule": q.default_rule,
        "choices": [{"value": c.value, "label": c.label} for c in q.choices],
        "minimum": q.minimum,
        "maximum": q.maximum,
        "min_items": q.min_items,
        "max_items": q.max_items,
    }


def summary_view(template: Template) -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "id": template.id,
        "title": template.title,
        "summary": template.summary,
        "builds": list(template.builds),
    }


def template_view(template: Template, facts: Facts | None = None) -> dict[str, Any]:
    """A template with its questions, each default as it stands for the
    person (`facts`; none without), and the answers' JSON Schema."""
    return {
        **summary_view(template),
        "questions": [question_view(q, facts) for q in template.questions],
        "answers_schema": answers_schema(template, facts),
        "notes": list(template.notes),
    }
