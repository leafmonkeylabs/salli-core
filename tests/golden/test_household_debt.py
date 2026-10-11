"""
The debt payoff plan for the household's declared debts
(tests/golden/household.py).

Pinned from the debt service as it computes before the baseline: every figure
the reconciliation changes changes on purpose, with a comment saying why.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.debt_service import DebtService
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


async def test_the_avalanche_plan_with_100_extra():
    plan = await DebtService(h.uow().factory()).get_payoff_plan(h.USER, Decimal("100"), "avalanche")

    # From the declared principals: the car loan at 10,200 (its ledger account
    # says 9,900 is owed), the student loan at 8,000.
    assert plan["months_to_payoff"] == 35
    assert plan["total_interest_paid"] == "1401.26"
    first = plan["schedule"][:2]
    # Undated: month 1, month 2, ...
    assert [(e["month"], e["debt_name"]) for e in first] == [
        (1, "Car loan"),
        (1, "Student loan"),
    ]
    assert first[0] == {
        "month": 1,
        "debt_name": "Car loan",
        "payment": "450.00",
        "principal_paid": "399.85",
        "interest_paid": "50.15",
        "remaining_balance": "9800.15",
    }
    last = plan["schedule"][-1]
    assert (last["month"], last["debt_name"], last["payment"]) == (35, "Student loan", "530.15")
