"""
Golden tests for the debt payoff engine — hand-computed amortization scenarios.
"""

from decimal import Decimal

from salli.domain.debt.engine import compute_payoff_plan
from salli.domain.debt.models import Debt

# ── Case 1: single debt, no extra payment — full hand-computed 2-month payoff ──
#
# Principal 100, APR 12% (1%/month), minimum payment 60.
# Month 1: interest = 100 * 0.01 = 1.00; payment = 60.00; principal = 59.00; balance = 41.00
# Month 2: interest = 41 * 0.01 = 0.41; payment = min(60, 41.41) = 41.41; balance = 0.00
# Total interest = 1.00 + 0.41 = 1.41


def test_single_debt_hand_computed_two_month_payoff():
    debt = Debt(
        name="SmallLoan",
        principal=Decimal("100"),
        apr=Decimal("0.12"),
        minimum_payment=Decimal("60"),
    )
    plan = compute_payoff_plan([debt], Decimal(0), "avalanche")

    assert plan.months_to_payoff == 2
    assert plan.total_interest_paid == Decimal("1.41")
    assert len(plan.schedule) == 2

    m1, m2 = plan.schedule
    assert m1.interest_paid == Decimal("1.00")
    assert m1.principal_paid == Decimal("59.00")
    assert m1.remaining_balance == Decimal("41.00")
    assert m2.payment == Decimal("41.41")
    assert m2.remaining_balance == Decimal(0)


# ── Case 2: avalanche targets the highest-APR debt first ───────────────────────
#
# HighAprLoan (5000 @ 20%) and LowAprLoan (1000 @ 5%), extra payment 200.
# Avalanche pays HighAprLoan's minimum + extra (100 + 200 = 300) in month 1;
# LowAprLoan only gets its minimum (50). Hand-verified against the engine's
# own quantized interest (83.33 and 4.17 respectively).


def test_avalanche_prioritizes_highest_apr_debt():
    high_apr = Debt(
        name="HighAprLoan",
        principal=Decimal("5000"),
        apr=Decimal("0.20"),
        minimum_payment=Decimal("100"),
    )
    low_apr = Debt(
        name="LowAprLoan",
        principal=Decimal("1000"),
        apr=Decimal("0.05"),
        minimum_payment=Decimal("50"),
    )
    plan = compute_payoff_plan([high_apr, low_apr], Decimal("200"), "avalanche")

    month1 = [e for e in plan.schedule if e.month == 1]
    high_apr_entry = next(e for e in month1 if e.debt_name == "HighAprLoan")
    low_apr_entry = next(e for e in month1 if e.debt_name == "LowAprLoan")

    assert high_apr_entry.payment == Decimal("300.00")  # minimum (100) + extra (200)
    assert high_apr_entry.interest_paid == Decimal("83.33")
    assert low_apr_entry.payment == Decimal("50.00")  # minimum only, no extra
    assert low_apr_entry.interest_paid == Decimal("4.17")


# ── Case 3: snowball targets the smallest-balance debt first ───────────────────
#
# Same two debts — snowball prioritizes LowAprLoan (smaller balance) instead.


def test_snowball_prioritizes_smallest_balance_debt():
    high_apr = Debt(
        name="HighAprLoan",
        principal=Decimal("5000"),
        apr=Decimal("0.20"),
        minimum_payment=Decimal("100"),
    )
    low_apr = Debt(
        name="LowAprLoan",
        principal=Decimal("1000"),
        apr=Decimal("0.05"),
        minimum_payment=Decimal("50"),
    )
    plan = compute_payoff_plan([high_apr, low_apr], Decimal("200"), "snowball")

    month1 = [e for e in plan.schedule if e.month == 1]
    high_apr_entry = next(e for e in month1 if e.debt_name == "HighAprLoan")
    low_apr_entry = next(e for e in month1 if e.debt_name == "LowAprLoan")

    assert low_apr_entry.payment == Decimal("250.00")  # minimum (50) + extra (200)
    assert high_apr_entry.payment == Decimal("100.00")  # minimum only, no extra


# ── Case 4: avalanche pays less total interest than snowball for the same debts ─


def test_avalanche_pays_less_total_interest_than_snowball():
    high_apr = Debt(
        name="HighAprLoan",
        principal=Decimal("5000"),
        apr=Decimal("0.20"),
        minimum_payment=Decimal("100"),
    )
    low_apr = Debt(
        name="LowAprLoan",
        principal=Decimal("1000"),
        apr=Decimal("0.05"),
        minimum_payment=Decimal("50"),
    )
    avalanche = compute_payoff_plan([high_apr, low_apr], Decimal("200"), "avalanche")
    snowball = compute_payoff_plan([high_apr, low_apr], Decimal("200"), "snowball")

    assert avalanche.total_interest_paid < snowball.total_interest_paid


# ── Case 5: no debts is a trivial, already-paid-off plan ───────────────────────


def test_no_debts_is_trivially_paid_off():
    plan = compute_payoff_plan([], Decimal("100"), "avalanche")
    assert plan.months_to_payoff == 0
    assert plan.total_interest_paid == Decimal(0)
    assert plan.schedule == []
