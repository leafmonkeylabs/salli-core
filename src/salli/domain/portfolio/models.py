"""
Investment portfolio domain models — pure, frozen dataclasses, Decimal money. No I/O.

Mirrors the tax/fi/budget/debt domains. A `Holding` here is what the summary
needs — its cost basis and current value in the base currency — whether those
come from its transactions and recorded prices (lots.py, valuation.py) or were
declared by the user. Nothing is fetched from a live market-data feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Holding:
    """A declared investment holding — the input side, before a summary is computed."""

    symbol: str
    name: str
    asset_class: str  # e.g. "equity", "bond", "cash", "real_estate", "crypto"
    cost_basis: Decimal  # total amount invested
    current_value: Decimal  # total current worth, as last declared by the user


@dataclass(frozen=True)
class AllocationSlice:
    asset_class: str
    current_value: Decimal
    pct_of_portfolio: Decimal  # 0..1


@dataclass(frozen=True)
class RebalancingAlert:
    """Only produced when a target allocation was supplied and a class's drift
    from that target meets or exceeds the drift threshold."""

    asset_class: str
    current_pct: Decimal
    target_pct: Decimal
    drift_pct: Decimal  # current - target; positive = overweight, negative = underweight


@dataclass(frozen=True)
class PortfolioSummary:
    total_value: Decimal
    total_cost_basis: Decimal
    total_gain: Decimal
    total_gain_pct: Decimal  # 0 if total_cost_basis is 0
    allocation: list[AllocationSlice] = field(default_factory=list[AllocationSlice])
    alerts: list[RebalancingAlert] = field(default_factory=list[RebalancingAlert])
