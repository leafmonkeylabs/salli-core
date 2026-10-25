"""
The person's FI plan beyond the assumptions: guaranteed income and spending
phases (docs/baseline.md#the-fi-plan). Pure domain: no I/O.

- **Guaranteed income streams**: a pension, an annuity, a provident fund's
  payout. Each has a start month, a monthly amount in today's money (`real`)
  or in the start month's own money (`nominal`), whether it is indexed
  (keeps its value against inflation from its start), an optional lump
  sum paid in its start month and an optional income role of the tax rules
  it is taxed under (`tax_role`), beside which withdrawals are taxed. A stream reduces the spending the FI number
  must fund from its start, and enters the monthly timeline as cash coming
  in. One that started on or before the as-of month is already in the
  ledger's income, so it only reduces the FI number.
- **Spending phases**: the monthly spending to live on (today's money) from
  an age on, by the person's date of birth on their profile. Before the
  first phase, or without a date of birth, the baseline's spending applies.

Stored as `user_profiles.fi_plan`; checked here, never chosen by a model.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, cast

_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
_MAX_ITEMS = 20
_MAX_TEXT = 500


@dataclass(frozen=True)
class IncomeStream:
    name: str
    #: "YYYY-MM": the first month it pays.
    start: str
    #: A month's payment (≥ 0), in today's money (`real`) or in the start
    #: month's own money (`nominal`).
    monthly: Decimal
    terms: Literal["real", "nominal"] = "real"
    #: Keeps its value against inflation from its start; else fixed in money.
    indexed: bool = True
    #: Paid once in its start month, in the same terms.
    lump_sum: Decimal = Decimal(0)
    source: str | None = None
    #: The income role of the active tax rules it is taxed under, if any:
    #: withdrawals are taxed beside it (`fi.gross_up`).
    tax_role: str | None = None

    def real_at(self, level: Decimal, level_at_start: Decimal) -> Decimal:
        """A month's payment in today's money, in a month whose price level
        (its own money over today's) is `level`; the start month's is
        `level_at_start`."""
        return self._real(self.monthly, level, level_at_start)

    def lump_real(self, level: Decimal, level_at_start: Decimal) -> Decimal:
        return self._real(self.lump_sum, level, level_at_start)

    def _real(self, amount: Decimal, level: Decimal, level_at_start: Decimal) -> Decimal:
        in_start_money = amount if self.terms == "nominal" else amount * level_at_start
        if self.indexed:
            return in_start_money / level_at_start
        return in_start_money / level


@dataclass(frozen=True)
class SpendingPhase:
    #: The age (in whole years) from which it applies.
    from_age: int
    #: Monthly spending to live on, in today's money.
    monthly: Decimal
    source: str | None = None


@dataclass(frozen=True)
class FiPlan:
    streams: tuple[IncomeStream, ...] = ()
    phases: tuple[SpendingPhase, ...] = ()
    #: From the profile; the phases need it.
    born: dt.date | None = None

    @property
    def empty(self) -> bool:
        return not self.streams and not self.phases

    def phase_spending(self, month: str) -> Decimal | None:
        """The phase's monthly spending in `month`, or None (no phase yet, or
        no date of birth)."""
        if self.born is None or not self.phases:
            return None
        year, number = int(month[:4]), int(month[5:7])
        age = year - self.born.year - (1 if number < self.born.month else 0)
        found: Decimal | None = None
        for phase in sorted(self.phases, key=lambda p: p.from_age):
            if age >= phase.from_age:
                found = phase.monthly
        return found

    def as_stored(self) -> dict[str, Any]:
        return {
            "income_streams": [
                {
                    "name": s.name,
                    "start": s.start,
                    "monthly": f"{s.monthly:f}",
                    "terms": s.terms,
                    "indexed": s.indexed,
                    "lump_sum": f"{s.lump_sum:f}",
                    "source": s.source,
                    "tax_role": s.tax_role,
                }
                for s in self.streams
            ],
            "spending_phases": [
                {"from_age": p.from_age, "monthly": f"{p.monthly:f}", "source": p.source}
                for p in self.phases
            ],
        }


def _amount(raw: object, what: str) -> Decimal:
    if isinstance(raw, float | bool) or raw is None:
        raise ValueError(f"{what} must be a decimal string such as '1200.00'")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ValueError(f"{what} must be a decimal string such as '1200.00'") from None
    if not value.is_finite() or value < 0:
        raise ValueError(f"{what} must be zero or more")
    return value


def _text(raw: object, what: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{what} must be text")
    text = " ".join(raw.split())
    if len(text) > _MAX_TEXT:
        raise ValueError(f"{what} is longer than {_MAX_TEXT} characters")
    return text or None


def _list(raw: object, what: str) -> Sequence[Mapping[str, Any]]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(cast("list[Any]", raw)) > _MAX_ITEMS:
        raise ValueError(f"{what} must be a list of at most {_MAX_ITEMS}")
    items = cast("list[Any]", raw)
    if not all(isinstance(i, Mapping) for i in items):
        raise ValueError(f"Each of {what} must be an object")
    return cast("list[Mapping[str, Any]]", items)


def parse(raw: object, born: dt.date | None = None) -> FiPlan:
    """A stored or sent plan, checked; a ValueError on the first problem."""
    if raw is None:
        return FiPlan(born=born)
    if not isinstance(raw, Mapping):
        raise ValueError("An FI plan is an object")
    doc = cast("Mapping[str, Any]", raw)
    streams: list[IncomeStream] = []
    for i, item in enumerate(_list(doc.get("income_streams"), "income_streams")):
        at = f"income_streams[{i}]"
        start = item.get("start")
        if not isinstance(start, str) or not _MONTH.fullmatch(start):
            raise ValueError(f"{at}.start must be a month, YYYY-MM")
        terms = item.get("terms", "real")
        if terms not in ("real", "nominal"):
            raise ValueError(f'{at}.terms must be "real" or "nominal"')
        indexed = item.get("indexed", True)
        if not isinstance(indexed, bool):
            raise ValueError(f"{at}.indexed must be true or false")
        name = _text(item.get("name"), f"{at}.name")
        if not name:
            raise ValueError(f"{at}.name must be non-empty text")
        streams.append(
            IncomeStream(
                name=name,
                start=start,
                monthly=_amount(item.get("monthly", "0"), f"{at}.monthly"),
                terms=terms,
                indexed=indexed,
                lump_sum=_amount(item.get("lump_sum", "0"), f"{at}.lump_sum"),
                source=_text(item.get("source"), f"{at}.source"),
                tax_role=_text(item.get("tax_role"), f"{at}.tax_role"),
            )
        )
    phases: list[SpendingPhase] = []
    for i, item in enumerate(_list(doc.get("spending_phases"), "spending_phases")):
        at = f"spending_phases[{i}]"
        age = item.get("from_age")
        if not isinstance(age, int) or isinstance(age, bool) or not 0 <= age <= 120:
            raise ValueError(f"{at}.from_age must be a whole age from 0 to 120")
        phases.append(
            SpendingPhase(
                age,
                _amount(item.get("monthly"), f"{at}.monthly"),
                _text(item.get("source"), f"{at}.source"),
            )
        )
    if len({p.from_age for p in phases}) != len(phases):
        raise ValueError("Two spending phases start at the same age")
    return FiPlan(tuple(streams), tuple(sorted(phases, key=lambda p: p.from_age)), born)


def lenient(raw: object, born: dt.date | None) -> FiPlan:
    """As stored, read leniently: a plan that no longer parses is none."""
    try:
        return parse(raw, born)
    except ValueError:
        return FiPlan(born=born)


NO_PLAN = FiPlan()
