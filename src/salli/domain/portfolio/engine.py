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
  • Costs       — the holdings' expense ratios (the person's own figures),
                  weighted by value, and what they take in a year
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
    bands: dict[str, Decimal] | None = None,
) -> PortfolioSummary:
    """`bands`, each class's own drift threshold (an investment policy's),
    in place of `drift_threshold` for the classes it names."""
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
            # A policy's band is how far a class may move: outside it, past it.
            outside = (
                abs(drift) > bands.get(asset_class, Decimal(0))
                if bands is not None
                else abs(drift) >= drift_threshold
            )
            if outside:
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


def running_costs(
    holdings: list[tuple[str, Decimal, Decimal | None]], money_quantum: Decimal = _CENT
) -> dict[str, object]:
    """Expense ratios (the person's own figures) rolled up: (symbol, value,
    yearly ratio or None) each. The weighted ratio is over the holdings that
    have one; the yearly cost is what they take from the portfolio's value
    in a year at today's values; holdings without one are named."""
    known = [(value, ratio) for _, value, ratio in holdings if ratio is not None]
    covered = sum((value for value, _ in known), Decimal(0))
    yearly = sum((value * ratio for value, ratio in known), Decimal(0))
    return {
        "weighted_expense_ratio": (
            str((yearly / covered).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
            if covered > 0
            else None
        ),
        "yearly_cost": str(_money(yearly, money_quantum)),
        "value_covered": str(_money(covered, money_quantum)),
        "without_ratio": [symbol for symbol, _, ratio in holdings if ratio is None],
    }
