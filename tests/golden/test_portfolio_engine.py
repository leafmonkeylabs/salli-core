"""
Golden tests for the investment portfolio engine — hand-computed scenarios.
"""

from decimal import Decimal

from salli.domain.portfolio.engine import compute_summary
from salli.domain.portfolio.models import Holding

# ── Case 1: allocation and gain across three asset classes, no target ──────────
#
# Total value = 130000 + 52000 + 20000 = 202000; total cost = 170000
# Gain = 32000; gain % = 32000/170000 = 0.188235... -> 0.1882
# equity % = 130000/202000 = 0.643564... -> 0.6436
# bond %   = 52000/202000  = 0.257425... -> 0.2574
# cash %   = 20000/202000  = 0.099009... -> 0.0990


def test_allocation_and_gain_hand_computed():
    holdings = [
        Holding(
            symbol="VOO",
            name="S&P 500 ETF",
            asset_class="equity",
            cost_basis=Decimal("100000"),
            current_value=Decimal("130000"),
        ),
        Holding(
            symbol="BND",
            name="Bond Fund",
            asset_class="bond",
            cost_basis=Decimal("50000"),
            current_value=Decimal("52000"),
        ),
        Holding(
            symbol="CASH",
            name="Savings",
            asset_class="cash",
            cost_basis=Decimal("20000"),
            current_value=Decimal("20000"),
        ),
    ]
    summary = compute_summary(holdings)

    assert summary.total_value == Decimal("202000.00")
    assert summary.total_cost_basis == Decimal("170000.00")
    assert summary.total_gain == Decimal("32000.00")
    assert summary.total_gain_pct == Decimal("0.1882")

    equity = next(a for a in summary.allocation if a.asset_class == "equity")
    bond = next(a for a in summary.allocation if a.asset_class == "bond")
    cash = next(a for a in summary.allocation if a.asset_class == "cash")
    assert equity.pct_of_portfolio == Decimal("0.6436")
    assert bond.pct_of_portfolio == Decimal("0.2574")
    assert cash.pct_of_portfolio == Decimal("0.0990")


# ── Case 2: small drift under the threshold produces no alerts ─────────────────


def test_small_drift_under_threshold_produces_no_alerts():
    holdings = [
        Holding(
            symbol="VOO",
            name="S&P 500 ETF",
            asset_class="equity",
            cost_basis=Decimal("100000"),
            current_value=Decimal("130000"),
        ),
        Holding(
            symbol="BND",
            name="Bond Fund",
            asset_class="bond",
            cost_basis=Decimal("50000"),
            current_value=Decimal("52000"),
        ),
        Holding(
            symbol="CASH",
            name="Savings",
            asset_class="cash",
            cost_basis=Decimal("20000"),
            current_value=Decimal("20000"),
        ),
    ]
    target = {"equity": Decimal("0.60"), "bond": Decimal("0.30"), "cash": Decimal("0.10")}
    summary = compute_summary(holdings, target_allocation=target)
    assert summary.alerts == []


# ── Case 3: large drift triggers alerts, including for an unheld target class ──
#
# equity: 180000/200000 = 0.90 vs target 0.60 -> drift +0.30 (alert)
# bond:   20000/200000  = 0.10 vs target 0.30 -> drift -0.20 (alert)
# crypto: 0/200000      = 0.00 vs target 0.10 -> drift -0.10 (alert, fully unheld)


def test_large_drift_triggers_alerts_including_unheld_class():
    holdings = [
        Holding(
            symbol="VOO",
            name="S&P 500 ETF",
            asset_class="equity",
            cost_basis=Decimal("100000"),
            current_value=Decimal("180000"),
        ),
        Holding(
            symbol="BND",
            name="Bond Fund",
            asset_class="bond",
            cost_basis=Decimal("50000"),
            current_value=Decimal("20000"),
        ),
    ]
    target = {"equity": Decimal("0.60"), "bond": Decimal("0.30"), "crypto": Decimal("0.10")}
    summary = compute_summary(holdings, target_allocation=target)

    assert len(summary.alerts) == 3
    equity_alert = next(a for a in summary.alerts if a.asset_class == "equity")
    bond_alert = next(a for a in summary.alerts if a.asset_class == "bond")
    crypto_alert = next(a for a in summary.alerts if a.asset_class == "crypto")

    assert equity_alert.drift_pct == Decimal("0.3000")
    assert bond_alert.drift_pct == Decimal("-0.2000")
    assert crypto_alert.current_pct == Decimal("0.0000")
    assert crypto_alert.drift_pct == Decimal("-0.1000")


# ── Case 4: no holdings is a trivial, empty summary ─────────────────────────────


def test_no_holdings_is_trivially_empty():
    summary = compute_summary([])
    assert summary.total_value == Decimal(0)
    assert summary.total_cost_basis == Decimal(0)
    assert summary.total_gain == Decimal(0)
    assert summary.total_gain_pct == Decimal(0)
    assert summary.allocation == []
    assert summary.alerts == []
