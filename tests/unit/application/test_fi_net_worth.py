"""The FI snapshot counts what is owned and owed as net worth over time does:
every account on its own sign, closed ones included."""

from __future__ import annotations

from decimal import Decimal

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account
from tests.fakes import FakeUoW
from tests.unit.application.test_goal_progress import _balance_entry


async def test_a_closed_account_with_a_balance_is_still_owned():
    closed = Account(
        id="sav", user_id="u1", code="1100", name="Old savings", type="asset", currency="LKR",
        is_active=False,
    )  # fmt: skip
    uow = FakeUoW("LKR")
    uow.ledger.accounts = [closed]
    uow.ledger.entries = [_balance_entry("sav", "500")]

    snapshot = await FiService(uow.factory()).build_snapshot("u1")
    assert snapshot.total_assets == Decimal(500)
    # Closed, it is still cash: liquid savings.
    assert snapshot.liquid_savings == Decimal(500)
