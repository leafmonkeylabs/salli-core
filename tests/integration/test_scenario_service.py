"""
Scenarios against a real database: a user's scenario runs on their own
books, another user's account or debt named in a change is not found (as one
that doesn't exist is), and running one stores nothing.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.ports import AccountNotFound, DebtNotFound
from salli.application.services.baseline_service import BaselineService
from salli.application.services.debt_service import DebtService
from salli.application.services.scenario_service import ScenarioService
from tests.fakes import FakeFx
from tests.integration.pg import requires_postgres
from tests.integration.test_baseline_service import AS_OF, _books

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _scenarios(uow_factory) -> ScenarioService:
    fx = FakeFx({("USD", "ZAR", AS_OF.isoformat()): (Decimal("17.25"), "sarb", "2026-09-15")})
    return ScenarioService(uow_factory, BaselineService(uow_factory, fx=fx, today=lambda: AS_OF))


async def _debt(uow_factory, user: str) -> str:
    return await DebtService(uow_factory).add_debt(
        user, {"name": "Card", "principal": "5000", "apr": "0.2", "minimum_payment": "250"}
    )


async def test_a_scenario_runs_on_the_users_own_books_and_stores_nothing(uow_factory):
    alice = await _books(uow_factory, "alice")
    debt = await _debt(uow_factory, "alice")
    async with uow_factory() as uow:
        entries_before = len(await uow.ledger.get_entries("alice"))
    result = await _scenarios(uow_factory).run(
        "alice",
        {
            "schema": "salli.scenario/1",
            "changes": [
                {
                    "type": "one_off",
                    "date": "2026-10-01",
                    "amount": "-1500.00",
                    "account": alice["bank"],
                    "label": "Fridge",
                },
                {
                    "type": "extra_debt_payment",
                    "debt": debt,
                    "monthly": "100",
                    "from": "2026-10-01",
                },
            ],
        },
    )
    assert result["as_of"] == AS_OF.isoformat() and result["currency"] == "ZAR"
    # The fridge, and twelve extra payments of 100 (October to September).
    assert result["cash"]["at_end"]["delta"] == "-2700.00"
    card = next(d for d in result["debts"]["items"] if d["debt_id"] == debt)
    assert Decimal(card["total_interest"]["delta"]) < 0
    async with uow_factory() as uow:
        assert len(await uow.ledger.get_entries("alice")) == entries_before
        assert await uow.fi_scores.get_latest("alice") is None


async def test_another_users_account_or_debt_is_not_found(uow_factory):
    await _books(uow_factory, "alice")
    bob = await _books(uow_factory, "bob")
    bobs_debt = await _debt(uow_factory, "bob")
    scenarios = _scenarios(uow_factory)

    def doc(change: dict) -> dict:
        return {"schema": "salli.scenario/1", "changes": [change]}

    spend = {"type": "one_off", "date": "2026-10-01", "amount": "-1.00", "label": "x"}
    with pytest.raises(AccountNotFound) as theirs:
        await scenarios.run("alice", doc({**spend, "account": bob["bank"]}))
    with pytest.raises(AccountNotFound) as missing:
        await scenarios.run(
            "alice", doc({**spend, "account": "00000000-0000-0000-0000-000000000000"})
        )
    assert str(theirs.value).startswith("Account not found: ")
    assert str(missing.value).startswith("Account not found: ")

    extra = {"type": "extra_debt_payment", "monthly": "1", "from": "2026-10-01"}
    with pytest.raises(DebtNotFound):
        await scenarios.run("alice", doc({**extra, "debt": bobs_debt}))
    with pytest.raises(DebtNotFound):
        await scenarios.compare(
            "alice",
            [
                {"schema": "salli.scenario/1", "label": "A"},
                {**doc({**extra, "debt": bobs_debt}), "label": "B"},
            ],
        )
    assert dt.date(2026, 9, 15) == AS_OF
