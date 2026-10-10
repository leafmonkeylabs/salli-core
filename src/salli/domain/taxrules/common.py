"""
Field types the rule-set schema and its building blocks share, and `Problem`,
the shape every complaint about a document takes.

Every model forbids unknown fields and is strict: a JSON `true` is not the
string "true", a number is not a date. Amounts, rates and limits are decimal
*strings*. A JSON number is refused outright, because whoever wrote it may have
meant 0.1 and whatever serialised it may have produced 0.1000000000000000055…
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
)

from salli.domain.currency import is_currency
from salli.domain.jurisdiction import COUNTRIES
from salli.domain.taxrules.arith import PRECISION, Rounding, RoundingMode, significant_digits
from salli.domain.taxrules.expr import KEY_PATTERN, MAX_LENGTH

# ── problems ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Problem:
    """One thing wrong with (or worth knowing about) a document. `path` points
    into it the way people read JSON: `blocks[2].of`, `band_tables.general`,
    or `$` for the document as a whole. `snippet` shows an expression with a
    caret under the mistake, when there is one."""

    path: str
    message: str
    snippet: str | None = None

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class RuleSetError(Exception):
    """A document that can't be used, with every problem found in it (not just
    the first)."""

    def __init__(self, problems: list[Problem] | tuple[Problem, ...]) -> None:
        self.problems = tuple(problems)
        shown = "; ".join(str(p) for p in self.problems[:5])
        more = f" (and {len(self.problems) - 5} more)" if len(self.problems) > 5 else ""
        super().__init__(f"{len(self.problems)} problem(s): {shown}{more}")


def join_path(*parts: str | int) -> str:
    """`("blocks", 2, "of")` → `blocks[2].of`."""
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else part
    return out or "$"


# ── the base model ─────────────────────────────────────────────────────────────


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


# ── decimals ───────────────────────────────────────────────────────────────────

DECIMAL_PATTERN = r"^-?[0-9]+(\.[0-9]+)?$"
_DECIMAL = re.compile(DECIMAL_PATTERN)


def parse_decimal(value: Any) -> Decimal:
    """`value` as a Decimal if it is a decimal string (or already a finite
    Decimal) with at most `PRECISION` significant digits; ValueError otherwise.
    JSON numbers are refused: see the module docstring."""
    if isinstance(value, bool | int | float):
        raise ValueError(
            'write amounts, rates and limits as decimal strings, like "0.15", not as '
            "JSON numbers (which may be read as binary floating point and rounded)"
        )
    if isinstance(value, Decimal):
        number = value
        if not number.is_finite():
            raise ValueError("must be a finite number")
    elif isinstance(value, str):
        if not _DECIMAL.fullmatch(value):
            raise ValueError(
                f"{value!r} is not a decimal string: digits with an optional fraction, "
                'like "1800000" or "0.15" (no exponents, separators or spaces)'
            )
        number = Decimal(value)
    else:
        raise ValueError("must be a decimal string")
    if significant_digits(number) > PRECISION:
        raise ValueError(f"may have at most {PRECISION} significant digits")
    return number


def _non_negative(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("must not be negative")
    return value


def _positive(value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("must be greater than zero")
    return value


def _rate(value: Decimal) -> Decimal:
    if not Decimal(0) <= value <= Decimal(1):
        raise ValueError('a rate is a fraction between "0" and "1" ("0.15" is 15%)')
    return value


Figure = Annotated[
    Decimal,
    BeforeValidator(parse_decimal),
    PlainSerializer(lambda d: format(d, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": DECIMAL_PATTERN,
            "description": 'A decimal number written as a string, like "1800000" or "0.15".',
        }
    ),
]
NonNegativeFigure = Annotated[Figure, AfterValidator(_non_negative)]
PositiveFigure = Annotated[Figure, AfterValidator(_positive)]
Rate = Annotated[Figure, AfterValidator(_rate)]


# ── dates ──────────────────────────────────────────────────────────────────────

_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _date(value: Any) -> datetime.date:
    if isinstance(value, datetime.datetime):
        raise ValueError("must be a date (YYYY-MM-DD), not a date and time")
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and _DATE.fullmatch(value):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError("must be a date written YYYY-MM-DD")


IsoDate = Annotated[
    datetime.date,
    BeforeValidator(_date),
    PlainSerializer(lambda d: d.isoformat(), return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date", "pattern": _DATE.pattern}),
]


# ── names and text ─────────────────────────────────────────────────────────────

#: A key: what the document calls a source, question, table, line, form …
Key = Annotated[str, StringConstraints(pattern=f"^{KEY_PATTERN}$", max_length=64)]
#: A role key is also an account's `tax_role`, which is kept in a VARCHAR(30).
RoleKey = Annotated[str, StringConstraints(pattern=f"^{KEY_PATTERN}$", max_length=30)]
#: A compiled line's key, which may have dotted parts (`general.band_1.tax`).
LineKey = Annotated[
    str, StringConstraints(pattern=f"^{KEY_PATTERN}(\\.{KEY_PATTERN})*$", max_length=128)
]
ExprText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_LENGTH),
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 1,
            "maxLength": MAX_LENGTH,
            "description": "An expression in the salli.tax expression language (docs/taxrules.md).",
        }
    ),
]


def _string_or_boolean(value: Any) -> Any:
    if isinstance(value, int | float) and not isinstance(value, bool):
        raise ValueError('write numbers as decimal strings, like "1800000", not as JSON numbers')
    return value


#: An answer or example input: a decimal string, a choice, or true/false.
StringOrBoolean = Annotated[str | bool, BeforeValidator(_string_or_boolean)]

Label = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Text = Annotated[str, StringConstraints(min_length=1, max_length=10_000)]
Url = Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=2_000)]


def is_user_assigned_country(code: str) -> bool:
    """ISO 3166-1 leaves AA, QM–QZ, XA–XZ and ZZ to users, so they never name a
    real country: the conformance suite's fictional jurisdictions use them."""
    return (
        code in ("AA", "ZZ")
        or (code[:1] == "Q" and "M" <= code[1:2] <= "Z")
        or (code[:1] == "X" and "A" <= code[1:2] <= "Z")
    )


def _country(code: str) -> str:
    if code in COUNTRIES or is_user_assigned_country(code):
        return code
    raise ValueError(
        f"{code!r} is not an ISO 3166-1 alpha-2 country code (or a user-assigned one: "
        "AA, QM–QZ, XA–XZ, ZZ)"
    )


def _currency(code: str) -> str:
    if code == code.upper() and is_currency(code):
        return code
    raise ValueError(f"{code!r} is not an upper-case ISO 4217 currency code")


CountryCode = Annotated[
    str,
    AfterValidator(_country),
    WithJsonSchema({"type": "string", "pattern": "^[A-Z]{2}$"}),
]
CurrencyCode = Annotated[
    str,
    AfterValidator(_currency),
    WithJsonSchema({"type": "string", "pattern": "^[A-Z]{3}$"}),
]


# ── rounding ───────────────────────────────────────────────────────────────────


class RoundingSpec(Model):
    """Round to a multiple of `unit`: "1" for whole units, "0.01" for
    hundredths. Modes are described in arith.ROUNDING_MODES."""

    mode: RoundingMode
    unit: PositiveFigure

    def to_rounding(self) -> Rounding:
        return Rounding(self.mode, self.unit)
