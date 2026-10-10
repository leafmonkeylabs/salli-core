"""
Deterministic investment portfolio engine.

Pure function: compute_summary(holdings, target_allocation, drift_threshold) ->
PortfolioSummary. No I/O — holdings carry their cost basis and current value in
the base currency (worked out from transactions and recorded prices, or as
declared); there is no live price feed or ticker lookup in the domain.

  • Allocation  — aggregates current value by asset class into percentages
  • Rebalancing — only computed when a target allocation is supplied; flags any
                  asset class whose drift from target meets or exceeds the
                  threshold (default 5 percentage points)
  • ROI         — total gain and gain % across all holdings
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from salli.domain.portfolio.models import (
    AllocationSlice,
    Holding,
    PortfolioSummary,
    RebalancingAlert,
)

_DEFAULT_DRIFT_THRESHOLD = Decimal("0.05")


#: Money is rounded to a cent by default, or to the currency's own smallest
#: unit when the caller passes it (1 for JPY, 0.001 for KWD).
_CENT = Decimal("0.01")


def _money(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def compute_summary(
    holdings: list[Holding],
    target_allocation: dict[str, Decimal] | None = None,
    drift_threshold: Decimal = _DEFAULT_DRIFT_THRESHOLD,
    money_quantum: Decimal = _CENT,
) -> PortfolioSummary:
    total_value = sum((h.current_value for h in holdings), Decimal(0))
    total_cost_basis = sum((h.cost_basis for h in holdings), Decimal(0))
    total_gain = total_value - total_cost_basis
    total_gain_pct = (total_gain / total_cost_basis) if total_cost_basis > 0 else Decimal(0)

    by_class: dict[str, Decimal] = {}
    for h in holdings:
        by_class[h.asset_class] = by_class.get(h.asset_class, Decimal(0)) + h.current_value

    allocation = [
        AllocationSlice(
            asset_class=asset_class,
            current_value=_money(value, money_quantum),
            pct_of_portfolio=_q4(value / total_value) if total_value > 0 else Decimal(0),
        )
        for asset_class, value in by_class.items()
    ]

    alerts: list[RebalancingAlert] = []
    if target_allocation:
        for asset_class in sorted(set(by_class) | set(target_allocation)):
            current_value = by_class.get(asset_class, Decimal(0))
            current_pct = _q4(current_value / total_value) if total_value > 0 else Decimal(0)
            target_pct = target_allocation.get(asset_class, Decimal(0))
            drift = current_pct - target_pct
            if abs(drift) >= drift_threshold:
                alerts.append(
                    RebalancingAlert(
                        asset_class=asset_class,
                        current_pct=current_pct,
                        target_pct=target_pct,
                        drift_pct=_q4(drift),
                    )
                )

    return PortfolioSummary(
        total_value=_money(total_value, money_quantum),
        total_cost_basis=_money(total_cost_basis, money_quantum),
        total_gain=_money(total_gain, money_quantum),
        total_gain_pct=_q4(total_gain_pct),
        allocation=allocation,
        alerts=alerts,
    )
