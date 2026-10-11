"""
The debt payoff plan for the household's declared debts
(tests/golden/household.py).

First pinned from the debt service as it computed before the baseline; each
figure the reconciliation changed is updated here with a comment saying why
("was …").
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.debt_service import DebtService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


def _debts() -> DebtService:
    uow = h.uow()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=today)
    return DebtService(uow.factory(), baselines=baselines, today=today)


async def test_the_avalanche_plan_with_100_extra():
    plan = await _debts().get_payoff_plan(h.USER, Decimal("100"), "avalanche")

    # The car loan starts from what its ledger account owes (9,900.00): was
    # its declared principal (10,200.00). The student loan, which the ledger
    # doesn't hold, from its declared 8,000.00.
    assert [(d["debt_id"], d["balance"], d["source"]) for d in plan["debts"]] == [
        ("debt-car", "9900.00", "account"),
        ("debt-student", "8000.00", "declared"),
    ]
    assert plan["months_to_payoff"] == 35  # unchanged
    assert plan["total_interest_paid"] == "1346.06"  # was 1,401.26, on 300 more
    # New: on calendar months, from the month after the as-of date.
    assert plan["as_of"] == "2026-10-11"
    assert (plan["first_month"], plan["debt_free_month"]) == ("2026-11", "2029-09")
    first = plan["schedule"][:2]
    assert [(e["month"], e["period"], e["debt_name"]) for e in first] == [
        (1, "2026-11", "Car loan"),
        (1, "2026-11", "Student loan"),
    ]
    assert first[0] == {
        "month": 1,
        "period": "2026-11",
        "debt_id": "debt-car",
        "debt_name": "Car loan",
        "payment": "450.00",
        "principal_paid": "401.32",  # was 399.85
        "interest_paid": "48.68",  # was 50.15
        "remaining_balance": "9498.68",  # was 9,800.15
    }
    last = plan["schedule"][-1]
    # Was 530.15: less is left by the end.
    assert (last["month"], last["period"], last["debt_name"], last["payment"]) == (
        35,
        "2029-09",
        "Student loan",
        "62.60",
    )


async def test_an_extra_payment_below_zero_is_refused_whoever_asks():
    """Was checked by the API alone: MCP and the agent passed anything on."""
    with pytest.raises(ValueError, match="from 0"):
        await _debts().get_payoff_plan(h.USER, Decimal("-50"), "avalanche")
    with pytest.raises(ValueError, match="avalanche or snowball"):
        await _debts().get_payoff_plan(h.USER, Decimal("0"), "fastest")  # type: ignore[arg-type]
