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


@dataclass(frozen=True)
class PayoffScheduleEntry:
    month: int
    debt_name: str
    payment: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    remaining_balance: Decimal


@dataclass(frozen=True)
class PayoffPlan:
    strategy: PayoffStrategy
    months_to_payoff: int | None  # None if not paid off within the simulation horizon
    total_interest_paid: Decimal
    schedule: list[PayoffScheduleEntry] = field(default_factory=list[PayoffScheduleEntry])
