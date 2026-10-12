"""
Debt domain models — pure, frozen dataclasses, Decimal money. No I/O.

Mirrors the tax/fi/budget domains: a declared input (`Debt`) and a fully-recorded
output (`PayoffPlan`, with a month-by-month `PayoffScheduleEntry` trace) produced by
the pure `engine.compute_payoff_plan` function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

PayoffStrategy = Literal["avalanche", "snowball"]


@dataclass(frozen=True)
class Debt:
    """A declared debt — the input side, before a payoff plan is simulated."""

    name: str
    principal: Decimal  # current outstanding balance
    apr: Decimal  # annual percentage rate, e.g. Decimal("0.18") for 18%
    minimum_payment: Decimal
    #: What tells it apart from another debt of the same name; its name when
    #: not given. Two cards both called "Card" are still two debts.
    id: str = ""
    #: A loan's term in months, when it has one: its last scheduled payment
    #: (that month's) pays whatever is left, so a level payment rounded to
    #: the currency's smallest unit still clears it on time. None for a debt
    #: paid until it is paid (a card, a declared debt).
    term_months: int | None = None

    @property
    def key(self) -> str:
        return self.id or self.name


@dataclass(frozen=True)
class PayoffScheduleEntry:
    #: 1 for the first payment, 2 for the next, ...; 0 for an extra payment
    #: before the first (the baseline's timelines, `timelines.debt_paths`).
    month: int
    debt_name: str
    payment: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    remaining_balance: Decimal
    #: The calendar month the payment falls in ("YYYY-MM"), when the plan was
    #: given its first month; None otherwise.
    period: str | None = None
    debt_id: str = ""


@dataclass(frozen=True)
class PayoffPlan:
    strategy: PayoffStrategy
    months_to_payoff: int | None  # None if not paid off within the simulation horizon
    total_interest_paid: Decimal
    schedule: list[PayoffScheduleEntry] = field(default_factory=list[PayoffScheduleEntry])
    #: The calendar month of the last payment ("YYYY-MM"), when the plan is
    #: dated and pays everything off within its horizon; None otherwise.
    debt_free_period: str | None = None
