"""The FI snapshot counts what is owned and owed as net worth over time does:
every account on its own sign, closed ones included."""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account
from tests.fakes import FakeProfiles
from tests.unit.application.test_goal_progress import FakeGoalRepo, _balance_entry


class Ledger:
    def __init__(self, accounts, entries):
        self.accounts, self.entries = accounts, entries

    async def get_accounts(self, user_id, include_inactive=False):
        return [a for a in self.accounts if include_inactive or a.is_active]

    async def get_entries(self, user_id, from_date=None, to_date=None):
        return self.entries


async def test_a_closed_account_with_a_balance_is_still_owned():
    closed = Account(
        id="sav", user_id="u1", code="1100", name="Old savings", type="asset", currency="LKR",
        is_active=False,
    )  # fmt: skip
    ledger = Ledger([closed], [_balance_entry("sav", "500")])

    @asynccontextmanager
    async def factory():
        class UoW:
            pass

        uow = UoW()
        uow.ledger, uow.goals, uow.user_profiles = ledger, FakeGoalRepo([], []), FakeProfiles()
        yield uow

    snapshot = await FiService(factory).build_snapshot("u1")
    assert snapshot.total_assets == Decimal(500)
