"""
Goal progress is derived from allocations, never typed in.

The old `current_amount` was a number the user entered and had to maintain by
hand — and since neither client ever exposed the field, every goal made in the
app sat at 0% forever while both UIs claimed progress came from the ledger.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Direction, Posting, StoredJournalEntry
from tests.fakes import FakeProfiles


class FakeLedgerRepo:
    def __init__(self, entries):
        self._entries = entries

    async def get_accounts(self, user_id):
        return []

    async def get_entries(self, user_id, from_date=None, to_date=None):
        return self._entries


class FakeGoalRepo:
    def __init__(self, goals, allocations):
        self._goals = goals
        self._allocations = allocations

    async def list(self, user_id, active_only=True):
        return self._goals

    async def list_allocations(self, user_id, goal_id=None):
        if goal_id:
            return [a for a in self._allocations if a["goal_id"] == goal_id]
        return self._allocations


class FakeUoW:
    def __init__(self, ledger, goals):
        self.ledger = ledger
        self.goals = goals
        self.user_profiles = FakeProfiles()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _balance_entry(account_id: str, amount: str) -> StoredJournalEntry:
    return StoredJournalEntry(
        id="e1",
        user_id="u1",
        entry_date="2026-01-01",
        description="opening balance",
        source="manual",
        postings=[
            Posting(
                account_id=account_id,
                direction=Direction.DEBIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
            Posting(
                account_id="equity",
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
        ],
    )


def _goal(goal_id: str, target: str, priority: int = 2) -> dict:
    return {
        "id": goal_id,
        "name": goal_id,
        "kind": "custom",
        "target_amount_minor": int(Decimal(target) * 100),
        "current_amount_minor": 0,
        "priority": priority,
        "target_date": None,
    }


def _service(goals, allocations, balance="1000000"):
    ledger = FakeLedgerRepo([_balance_entry("sav", balance)])
    repo = FakeGoalRepo(goals, allocations)

    @asynccontextmanager
    async def factory():
        yield FakeUoW(ledger, repo)

    return FiService(factory)


def _alloc(goal_id: str, amount: str, account: str = "sav") -> dict:
    return {
        "goal_id": goal_id,
        "account_id": account,
        "allocated_minor": int(Decimal(amount) * 100),
    }


@pytest.mark.asyncio
async def test_a_goal_with_no_allocation_reads_zero_not_a_typed_number():
    svc = _service([_goal("house", "2000000")], [])
    (view,) = await svc.list_goals("u1")
    assert view["current_amount"] == "0.00"
    assert view["allocated_amount"] == "0.00"
    assert view["progress"] == 0.0


@pytest.mark.asyncio
async def test_progress_comes_from_the_account_balance():
    svc = _service([_goal("house", "2000000")], [_alloc("house", "600000")])
    (view,) = await svc.list_goals("u1")
    assert view["current_amount"] == "600000.00"
    assert view["progress"] == pytest.approx(0.30)


@pytest.mark.asyncio
async def test_one_account_backing_two_goals():
    """The case this was built for."""
    svc = _service(
        [_goal("house", "2000000", priority=1), _goal("fund", "400000", priority=2)],
        [_alloc("house", "600000"), _alloc("fund", "400000")],
    )
    views = {v["name"]: v for v in await svc.list_goals("u1")}
    assert views["house"]["current_amount"] == "600000.00"
    assert views["fund"]["current_amount"] == "400000.00"
    assert views["fund"]["progress"] == 1.0


@pytest.mark.asyncio
async def test_priority_decides_who_stays_funded_when_the_balance_falls():
    svc = _service(
        [_goal("house", "2000000", priority=1), _goal("fund", "400000", priority=2)],
        [_alloc("house", "600000"), _alloc("fund", "400000")],
        balance="500000",
    )
    views = {v["name"]: v for v in await svc.list_goals("u1")}
    assert views["house"]["current_amount"] == "500000.00"
    assert views["house"]["shortfall"] == "100000.00"
    assert views["fund"]["current_amount"] == "0.00"
    assert views["fund"]["shortfall"] == "400000.00"


@pytest.mark.asyncio
async def test_progress_never_exceeds_the_target():
    svc = _service([_goal("house", "300000")], [_alloc("house", "900000")])
    (view,) = await svc.list_goals("u1")
    assert view["current_amount"] == "300000.00"
    assert view["progress"] == 1.0


@pytest.mark.asyncio
async def test_money_amounts_are_consistently_formatted():
    """Apportioned amounts carry cents while exact ones do not, so without
    normalising a goal could report "500000.00" beside a bare "0"."""
    svc = _service(
        [_goal("a", "1000000", priority=1), _goal("b", "1000000", priority=2)],
        [_alloc("a", "600000"), _alloc("b", "600000")],
        balance="600000",
    )
    for view in await svc.list_goals("u1"):
        for key in ("target_amount", "current_amount", "allocated_amount", "shortfall"):
            assert view[key].count(".") == 1 and len(view[key].split(".")[1]) == 2, (
                f"{key}={view[key]!r}"
            )
