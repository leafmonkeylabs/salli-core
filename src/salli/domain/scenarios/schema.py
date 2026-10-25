"""
The scenario document, `salli.scenario/1`: its models, its JSON Schema, and
problems with paths people can follow.

A scenario is the baseline plus changes (docs/scenarios.md):

    {"schema": "salli.scenario/1", "as_of": "2026-10-11", "horizon_years": 20,
     "changes": [{"type": "one_off", "date": "2026-11-01", "amount": "-2400.00",
                  "label": "New laptop"}]}

Every model forbids unknown fields and is strict, as the tax rule-set
document is (domain/taxrules/common.py): amounts and rates are decimal
*strings*, and a JSON number is refused outright, because whoever wrote it
may have meant 0.1 and whatever serialised it may have produced
0.1000000000000000055… Dates are ISO (YYYY-MM-DD). Signed amounts may carry a
leading "+" ("+600.00"): money in is positive, money out negative.

What needs the user's money to check (that an account is a cash account in
the base currency, a date is not before the as-of date, an amount fits the
currency's smallest unit, a recurring flow's key exists) is the engine's
(`engine.run`), and what needs their books (that an account or a debt is
theirs) is the service's.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    PlainSerializer,
    StringConstraints,
    ValidationError,
    WithJsonSchema,
    model_validator,
)

from salli.domain.taxrules.arith import PRECISION, significant_digits
from salli.domain.taxrules.common import (
    IsoDate,
    Key,
    Label,
    Model,
    Problem,
    Rate,
    RoleKey,
    StringOrBoolean,
    join_path,
)

SCHEMA_ID = "salli.scenario/1"

#: At most this many changes in one scenario.
MAX_CHANGES = 50
#: The horizon, in years: the monthly timeline's longest.
MIN_HORIZON_YEARS = 1
MAX_HORIZON_YEARS = 50
DEFAULT_HORIZON_YEARS = 20
#: A loan's longest term: 50 years.
MAX_TERM_MONTHS = 600
#: An amount has at most this many digits before its point.
MAX_INTEGER_DIGITS = 15

Cadence = Literal["weekly", "monthly", "quarterly", "yearly"]

# ── amounts ────────────────────────────────────────────────────────────────────

AMOUNT_PATTERN = r"^[+-]?[0-9]+(\.[0-9]+)?$"
_AMOUNT = re.compile(AMOUNT_PATTERN)


def parse_amount(value: Any) -> Decimal:
    """`value` as a Decimal if it is a decimal string (an optional sign,
    digits, an optional fraction); ValueError otherwise. JSON numbers are
    refused."""
    if isinstance(value, bool | int | float):
        raise ValueError(
            'write amounts as decimal strings, like "-2400.00", not as JSON numbers '
            "(which may be read as binary floating point and rounded)"
        )
    if isinstance(value, Decimal):
        number = value
        if not number.is_finite():
            raise ValueError("must be a finite number")
    elif isinstance(value, str):
        if not _AMOUNT.fullmatch(value):
            raise ValueError(
                f"{value!r} is not a decimal string: an optional sign, digits and an "
                'optional fraction, like "-2400.00" or "+600" (no exponents, separators '
                "or spaces)"
            )
        number = Decimal(value)
    else:
        raise ValueError("must be a decimal string")
    if significant_digits(number) > PRECISION:
        raise ValueError(f"may have at most {PRECISION} significant digits")
    if number != 0 and number.adjusted() >= MAX_INTEGER_DIGITS:
        raise ValueError(f"may have at most {MAX_INTEGER_DIGITS} digits before the point")
    return number


def _positive(value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("must be greater than zero")
    return value


def _not_negative(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("can't be negative")
    return value


#: A number of units has at most this many decimal places (as a holding's
#: transactions do: domain/portfolio/lots.py) and fewer integer digits.
UNIT_PLACES = 18
UNIT_INTEGER_DIGITS = 20
UNITS_PATTERN = r"^\+?[0-9]+(\.[0-9]+)?$"


def parse_units(value: Any) -> Decimal:
    """`value` as a positive number of units: a decimal string with at most
    18 decimal places and 20 integer digits (ValueError otherwise)."""
    if isinstance(value, bool | int | float):
        raise ValueError('write units as decimal strings, like "4" or "6.5", not as JSON numbers')
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, str) and re.fullmatch(UNITS_PATTERN, value):
        number = Decimal(value)
    else:
        raise ValueError(f'{value!r} is not a number of units, like "4" or "6.5"')
    if not number.is_finite() or number <= 0:
        raise ValueError("must be greater than zero")
    exponent = number.normalize().as_tuple().exponent
    if isinstance(exponent, int) and -exponent > UNIT_PLACES:
        raise ValueError(f"may have at most {UNIT_PLACES} decimal places")
    if number.adjusted() >= UNIT_INTEGER_DIGITS:
        raise ValueError(f"may have at most {UNIT_INTEGER_DIGITS} digits before the point")
    return number


SignedAmount = Annotated[
    Decimal,
    BeforeValidator(parse_amount),
    PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": AMOUNT_PATTERN,
            "description": 'A signed decimal amount as a string: "-2400.00" out, "+600" in.',
        }
    ),
]
PositiveAmount = Annotated[
    Decimal,
    BeforeValidator(parse_amount),
    AfterValidator(_positive),
    PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^\+?[0-9]+(\.[0-9]+)?$",
            "description": 'A positive decimal amount as a string, like "5000.00".',
        }
    ),
]

Fees = Annotated[
    Decimal,
    BeforeValidator(parse_amount),
    AfterValidator(_not_negative),
    PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^\+?[0-9]+(\.[0-9]+)?$",
            "description": 'Fees as a decimal string, zero or more, like "4.00".',
        }
    ),
]
Units = Annotated[
    Decimal,
    BeforeValidator(parse_units),
    PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": UNITS_PATTERN,
            "description": 'A number of units as a decimal string, like "4" or "6.5".',
        }
    ),
]

#: An account's, a debt's or a holding's id, as the API gives it.
RefId = Annotated[str, StringConstraints(min_length=1, max_length=100)]
#: At most this many lots named in one sale.
MAX_LOTS = 100
#: A recurring flow's key, as `GET /v1/insights/recurring` gives it.
RecurringKey = Annotated[str, StringConstraints(min_length=1, max_length=100)]
#: At most this many answers to the tax rules' questions.
MAX_TAX_ANSWERS = 100
TermMonths = Annotated[int, Field(ge=1, le=MAX_TERM_MONTHS)]
#: The most a real growth may be either way, a year: 100%.
MAX_GROWTH = Decimal(1)


def _growth(value: Decimal) -> Decimal:
    if not -MAX_GROWTH <= value <= MAX_GROWTH:
        raise ValueError('a growth is a yearly fraction from "-1" to "1" ("0.01" is 1%)')
    return value


#: A yearly growth beyond inflation, signed: "0.01" is 1% a year more than
#: prices, "-0.02" 2% a year less.
RealGrowth = Annotated[
    Decimal,
    BeforeValidator(parse_amount),
    AfterValidator(_growth),
    PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": AMOUNT_PATTERN,
            "description": 'A yearly growth beyond inflation, as a signed fraction: "0.01" '
            'is 1% a year more than prices, "-0.02" 2% a year less.',
        }
    ),
]
HorizonYears = Annotated[int, Field(ge=MIN_HORIZON_YEARS, le=MAX_HORIZON_YEARS)]


def _ordered(first: Any, last: Any | None, what: str) -> None:
    if last is not None and last < first:
        raise ValueError(what)


# ── changes ────────────────────────────────────────────────────────────────────


class OneOffChange(Model):
    """Money in or out once, on a day: a purchase (negative), a gift
    received (positive). What a purchase buys isn't counted as an asset
    (an `asset` change is).
    With a `tax_role`, the amount is before tax: a taxable bonus in an
    income role, a deductible cost in a deduction role."""

    type: Literal["one_off"]
    date: IsoDate
    amount: SignedAmount
    #: The cash account it moves; without one, it moves your cash total.
    account: RefId | None = None
    #: A role of kind income or deduction in your tax rules: the amount
    #: then also adds to that role's total, and Salli works out the change
    #: in tax with your active rules.
    tax_role: RoleKey | None = None
    label: Label


class RecurringChange(Model):
    """The same amount again and again: a new rent (negative), a side income
    (positive). In today's money: with your inflation set, it rises with it,
    and with a `real_growth`, by that much more a year. With a `tax_role`,
    each amount is before tax."""

    type: Literal["recurring"]
    #: Each time, signed.
    amount: SignedAmount
    cadence: Cadence
    start: IsoDate
    #: The last day it can fall on; without one, it never stops.
    end: IsoDate | None = None
    account: RefId | None = None
    #: A role of kind income or deduction in your tax rules (see `one_off`).
    tax_role: RoleKey | None = None
    #: How much it grows a year beyond inflation, a twelfth a month,
    #: compounded, from its start's month: a rent rising faster than prices.
    #: Without one, 0: it keeps its value in today's money.
    real_growth: RealGrowth | None = None
    label: Label

    @model_validator(mode="after")
    def _dates(self) -> Self:
        _ordered(self.start, self.end, "end is before start")
        return self


class IncomeChange(Model):
    """Your monthly income changes by an amount from a day: a raise
    (positive), a cut (negative). In today's money. Without a `tax_role`,
    `monthly` is what reaches your cash (after tax); with one, it is before
    tax, in that role, and Salli works out the tax."""

    type: Literal["income_change"]
    monthly: SignedAmount
    from_: IsoDate = Field(alias="from")
    to: IsoDate | None = None
    #: A role of kind income in your tax rules (see `one_off`).
    tax_role: RoleKey | None = None
    label: Label

    @model_validator(mode="after")
    def _dates(self) -> Self:
        _ordered(self.from_, self.to, "to is before from")
        return self


class LoanChange(Model):
    """Money borrowed on a day and repaid in level monthly payments from the
    month after, the last one clearing it. Its payments are fixed in money of
    their own day."""

    type: Literal["loan"]
    principal: PositiveAmount
    #: A yearly fraction: "0.069" is 6.9%.
    annual_rate: Rate
    term_months: TermMonths
    start: IsoDate
    #: The cash account the money arrives in; without one, your cash total.
    into: RefId | None = None
    label: Label


class ExtraDebtPaymentChange(Model):
    """Paid on one of your debts on top of its minimum, each month from a
    day's month to another's (or until it is paid off)."""

    type: Literal["extra_debt_payment"]
    #: The debt's id (`GET /v1/debt/`).
    debt: RefId
    monthly: PositiveAmount
    from_: IsoDate = Field(alias="from")
    to: IsoDate | None = None
    label: Label | None = None

    @model_validator(mode="after")
    def _dates(self) -> Self:
        _ordered(self.from_, self.to, "to is before from")
        return self


class InvestChange(Model):
    """Cash moved into your investments on a day, where it then grows at
    your real return. Into one of your holdings (`holding`), it also shows
    the units it buys at the holding's last recorded price, and opens a lot
    a later sale in the same scenario can sell. Fees (yours, your broker's;
    none when left out) leave cash with the amount and never reach the
    investments."""

    type: Literal["invest"]
    amount: PositiveAmount
    date: IsoDate
    #: The cash account it leaves; without one, your cash total.
    from_: RefId | None = Field(default=None, alias="from")
    #: One of your holdings, by its id (`GET /v1/portfolio/`): a holding you
    #: already have. Salli never picks one.
    holding: RefId | None = None
    #: Of the amount, in your base currency: what your broker charges.
    fees: Fees | None = None
    label: Label

    @model_validator(mode="after")
    def _fees(self) -> Self:
        if self.fees is not None and self.fees >= self.amount:
            raise ValueError("fees are part of the amount, so must be less than it")
        return self


class SoldLot(Model):
    """One lot a sale sells from, and how many of its units."""

    #: The lot's id, as `GET /v1/portfolio/{id}/lots` gives it (the
    #: transaction that opened it); an earlier `invest` change into the same
    #: holding opens the lot `scenario-invest-<n>`, n its place in the list
    #: counted from 1.
    lot: RefId
    quantity: Units


class SellChange(Model):
    """Part of one of your holdings sold on a day: its units leave your
    investments at its last recorded price (grown at your real return and
    inflation to a later month: Salli forecasts no price), and the proceeds
    less fees arrive in cash. Salli replays the holding's lots with the sale
    (first in, first out, or the lots you name) and reports the gain you
    would realise; with a `tax_role`, the gain is taxed with your rules. The
    holding must be linked to the investment account that holds it, and the
    sale can't take out more than that account holds."""

    type: Literal["sell"]
    #: One of your holdings, by its id.
    holding: RefId
    #: The units to sell; or give `amount`, the value to sell.
    quantity: Units | None = None
    #: The value to sell, in your base currency, at the sale's price.
    amount: PositiveAmount | None = None
    date: IsoDate
    #: In your base currency: what your broker charges. Left out, none
    #: (and the result says no fees were given).
    fees: Fees | None = None
    #: The lots it sells from; without them, the oldest first.
    lots: Annotated[list[SoldLot], Field(max_length=MAX_LOTS)] | None = None
    #: The cash account the proceeds arrive in; without one, your cash total.
    into: RefId | None = None
    #: A role of kind income in your tax rules: the realised gain (a loss,
    #: negative) adds to that role's total.
    tax_role: RoleKey | None = None
    label: Label | None = None

    @model_validator(mode="after")
    def _what(self) -> Self:
        if self.quantity is not None and self.amount is not None:
            raise ValueError("give the units to sell (quantity) or the value (amount), not both")
        if self.quantity is None and self.amount is None and not self.lots:
            raise ValueError("give the units to sell (quantity) or the value to sell (amount)")
        if self.lots is not None and self.amount is not None:
            raise ValueError("a sale of named lots gives their units, not an amount")
        if self.lots:
            named = sum((lot.quantity for lot in self.lots), Decimal(0))
            if self.quantity is not None and named != self.quantity:
                raise ValueError(
                    f"the lots named add up to {format(named.normalize(), 'f')} units, not the "
                    f"{format(self.quantity.normalize(), 'f')} sold"
                )
            if len({lot.lot for lot in self.lots}) != len(self.lots):
                raise ValueError("a sale names each lot once")
        return self

    @property
    def units(self) -> Decimal | None:
        """The units sold, when given (by `quantity` or the lots named)."""
        if self.quantity is not None:
            return self.quantity
        if self.lots:
            return sum((lot.quantity for lot in self.lots), Decimal(0))
        return None


class StopRecurringChange(Model):
    """A recurring flow your ledger shows (a subscription, a bill, an income)
    stops from a day: cancel a subscription. Name it by its key."""

    type: Literal["stop_recurring"]
    #: Its key, as `GET /v1/insights/recurring` shows it.
    key: RecurringKey
    from_: IsoDate = Field(alias="from")
    label: Label | None = None


class SetAsideChange(Model):
    """Part of each month's regular surplus kept in cash, rather than shared
    out between cash and investments: saving towards an emergency fund or a
    purchase. Each month from a day's month to another's (or for good), that
    much of the surplus stays in cash first, and the share you invest is of
    what is left. It can't keep more than the month's surplus: a month with
    less keeps all of it and invests nothing. Fixed in each month's own
    money, like a standing order."""

    type: Literal["set_aside"]
    monthly: PositiveAmount
    from_: IsoDate = Field(alias="from")
    to: IsoDate | None = None
    label: Label | None = None

    @model_validator(mode="after")
    def _dates(self) -> Self:
        _ordered(self.from_, self.to, "to is before from")
        return self


class AssetChange(Model):
    """Something bought that holds its value: a home. The price leaves cash
    on the day (a move, like an investment), and the asset is counted from
    that month's end among your other assets, growing at its `real_growth`
    a twelfth a month, compounded, from the next. It counts in net worth at
    what it would fetch: its value less its selling costs. Like your other
    assets, it funds no withdrawals in FI."""

    type: Literal["asset"]
    #: What it costs, out of cash on the day.
    price: PositiveAmount
    date: IsoDate
    #: The cash account the price leaves; without one, your cash total.
    from_: RefId | None = Field(default=None, alias="from")
    #: How much its value grows a year beyond inflation. Without one, 0 (it
    #: keeps its value in today's money), listed as the `asset_growth`
    #: placeholder.
    real_growth: RealGrowth | None = None
    #: What selling it would cost, as a share of its value: "0.03" is 3%.
    #: Without one, 0.
    selling_costs: Rate | None = None
    label: Label


Change = Annotated[
    OneOffChange
    | RecurringChange
    | IncomeChange
    | LoanChange
    | ExtraDebtPaymentChange
    | InvestChange
    | StopRecurringChange
    | SetAsideChange
    | SellChange
    | AssetChange,
    Field(discriminator="type"),
]

CHANGE_TYPES = (
    "one_off",
    "recurring",
    "income_change",
    "loan",
    "extra_debt_payment",
    "invest",
    "stop_recurring",
    "set_aside",
    "sell",
    "asset",
)


class ScenarioTax(Model):
    """What the tax rules need from the scenario besides amounts: answers
    to their questions (a filing status, say), by key, checked against each
    year's rules as a computation checks them."""

    answers: Annotated[dict[Key, StringOrBoolean], Field(max_length=MAX_TAX_ANSWERS)] = Field(
        default_factory=dict[str, str | bool]
    )


class Scenario(Model):
    """The baseline plus changes."""

    schema_: Literal["salli.scenario/1"] = Field(alias="schema")
    #: What to call it ("Pay cash"): how a comparison names the option.
    label: Label | None = None
    #: The day the baseline is as of; today when omitted.
    as_of: IsoDate | None = None
    #: How far the monthly figures run, in years. The FI month and the debts'
    #: payoff are found wherever they fall, within 50 years.
    horizon_years: HorizonYears = DEFAULT_HORIZON_YEARS
    changes: Annotated[list[Change], Field(max_length=MAX_CHANGES)] = Field(
        default_factory=list[Change]
    )
    #: Answers to your tax rules' questions, for changes tagged with a
    #: `tax_role`.
    tax: ScenarioTax | None = None


#: The change types that may carry a `tax_role`.
TAGGABLE = (OneOffChange, RecurringChange, IncomeChange, SellChange)
#: The change types that name one of your holdings.
WITH_HOLDING = (InvestChange, SellChange)


def hashable(scenario: Scenario) -> dict[str, Any]:
    """The scenario as its content hash reads it: as written (by alias),
    without the optional fields it leaves out (tax, a real growth), so a
    scenario without them hashes as it did before they existed."""
    data = scenario.model_dump(mode="python", by_alias=True)
    if data.get("tax") is None:
        data.pop("tax", None)
    for change in data.get("changes", []):
        for name in ("tax_role", "real_growth"):
            if name in change and change[name] is None:
                del change[name]
        # An invest into no holding, without fees, hashes as it did before
        # they existed.
        if change.get("type") == "invest":
            for key in ("holding", "fees"):
                if key in change and change[key] is None:
                    del change[key]
    return data


# ── loading, problems, JSON Schema ─────────────────────────────────────────────


def load(data: Any) -> Scenario:
    """`data` as a validated scenario (pydantic's ValidationError otherwise;
    `problems` turns that into problems with paths)."""
    if isinstance(data, Scenario):
        return data
    return Scenario.model_validate(data)


_WHOLE_NUMBERS = {
    "horizon_years": (
        f"is a whole number of years from {MIN_HORIZON_YEARS} to {MAX_HORIZON_YEARS}"
    ),
    "term_months": f"is a whole number of months from 1 to {MAX_TERM_MONTHS}",
}


def problems(error: ValidationError, *, option: int | None = None) -> list[Problem]:
    """pydantic's errors as problems, with paths into the document
    (`changes[2].amount`); within a comparison's `option`, under
    `options[n]`."""
    out: list[Problem] = []
    for err in error.errors(include_url=False):
        loc: list[str | int] = list(err["loc"])
        # pydantic names the change type it tried after a change's index,
        # which is no part of the document.
        if len(loc) > 2 and loc[0] == "changes" and loc[2] in CHANGE_TYPES:
            del loc[2]
        loc = ["from" if part == "from_" else part for part in loc]
        loc = ["schema" if part == "schema_" else part for part in loc]
        message = str(err["msg"]).removeprefix("Value error, ")
        if err["type"] == "missing":
            message = "is required"
        elif err["type"] == "extra_forbidden":
            message = "is not a field here"
        elif err["type"] == "union_tag_invalid":
            message = f"is not a change type; the types are: {', '.join(CHANGE_TYPES)}"
        elif err["type"] == "union_tag_not_found":
            message = f"needs a type: one of {', '.join(CHANGE_TYPES)}"
        elif loc and loc[-1] in _WHOLE_NUMBERS:
            message = _WHOLE_NUMBERS[str(loc[-1])]
        elif err["type"] == "too_long" and loc == ["changes"]:
            message = f"has more than {MAX_CHANGES} changes"
        prefix: list[str | int] = [] if option is None else ["options", option]
        out.append(Problem(join_path(*prefix, *loc), message))
    return out


def json_schema() -> dict[str, Any]:
    """The document's JSON Schema (Draft 2020-12), for agents writing one. The
    checks that need the user's money are the engine's (see the module)."""
    schema = Scenario.model_json_schema(by_alias=True, mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Salli scenario ({SCHEMA_ID})",
        **schema,
    }


__all__ = [
    "CHANGE_TYPES",
    "MAX_GROWTH",
    "DEFAULT_HORIZON_YEARS",
    "MAX_CHANGES",
    "MAX_HORIZON_YEARS",
    "MAX_TERM_MONTHS",
    "SCHEMA_ID",
    "TAGGABLE",
    "AssetChange",
    "Cadence",
    "Change",
    "ExtraDebtPaymentChange",
    "IncomeChange",
    "InvestChange",
    "LoanChange",
    "OneOffChange",
    "RealGrowth",
    "RecurringChange",
    "Scenario",
    "ScenarioTax",
    "SellChange",
    "SetAsideChange",
    "SoldLot",
    "StopRecurringChange",
    "WITH_HOLDING",
    "hashable",
    "json_schema",
    "load",
    "problems",
]
