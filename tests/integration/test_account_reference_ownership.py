"""A parent account, a subscription and a budget line point only at the
caller's own accounts.

Each stored whatever account id it was given, so user B's row could point into
user A's ledger, and a refusal from the database's foreign key told B whether
an id existed at all. Driven against a real database, where those foreign keys
are.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from salli.application.ports import AccountNotFound
from salli.application.services.budget_service import BudgetService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.subscription_service import SubscriptionService
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


@pytest.fixture
async def ledgers(uow_factory) -> SimpleNamespace:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("alice", {"base_currency": "USD"})
        await uow.user_profiles.upsert("bob", {"base_currency": "USD"})
    ledger = LedgerService(uow_factory)
    return SimpleNamespace(
        ledger=ledger,
        alice_food=await ledger.add_account("alice", "5000", "Food", "expense"),
        bob_food=await ledger.add_account("bob", "5000", "Food", "expense"),
    )


def _subscription(account_id: str | None) -> dict[str, object]:
    return {
        "name": "Streaming",
        "amount": "12.99",
        "frequency": "monthly",
        "next_due_date": "2026-11-01",
        "account_id": account_id,
    }


@pytest.mark.parametrize("parent", ["alice", "made-up"])
async def test_an_account_cannot_sit_under_someone_elses(ledgers, parent):
    parent_id = ledgers.alice_food if parent == "alice" else "made-up"

    with pytest.raises(AccountNotFound) as refused:
        await ledgers.ledger.add_account("bob", "5100", "Groceries", "expense", parent_id=parent_id)

    # Another user's account and one that doesn't exist read the same.
    assert str(refused.value) == f"Account not found: {parent_id}"
    assert [a.code for a in await ledgers.ledger.list_accounts("bob")] == ["5000"]


async def test_an_account_can_sit_under_your_own(ledgers):
    child = await ledgers.ledger.add_account(
        "bob", "5100", "Groceries", "expense", parent_id=ledgers.bob_food
    )

    account = await ledgers.ledger.get_account("bob", child)
    assert account is not None and account.parent_id == ledgers.bob_food


async def test_a_subscription_cannot_watch_someone_elses_account(uow_factory, ledgers):
    subscriptions = SubscriptionService(uow_factory)

    with pytest.raises(AccountNotFound):
        await subscriptions.add_subscription("bob", _subscription(ledgers.alice_food))
    with pytest.raises(AccountNotFound):
        await subscriptions.add_subscription("bob", _subscription("made-up"))
    assert await subscriptions.list_subscriptions("bob", active_only=False) == []

    mine = await subscriptions.add_subscription("bob", _subscription(ledgers.bob_food))
    with pytest.raises(AccountNotFound):
        await subscriptions.update_subscription("bob", mine, {"account_id": ledgers.alice_food})

    stored = await subscriptions.get_subscription("bob", mine)
    assert stored is not None and stored["account_id"] == ledgers.bob_food


async def test_a_subscription_needs_no_account(uow_factory, ledgers):
    subscriptions = SubscriptionService(uow_factory)

    mine = await subscriptions.add_subscription("bob", _subscription(None))
    await subscriptions.update_subscription("bob", mine, {"name": "Streaming HD"})

    stored = await subscriptions.get_subscription("bob", mine)
    assert stored is not None
    assert (stored["name"], stored["account_id"]) == ("Streaming HD", None)


async def test_a_budget_line_cannot_be_on_someone_elses_account(uow_factory, ledgers):
    budgets = BudgetService(uow_factory)
    theirs = [{"account_id": ledgers.alice_food, "limit_amount": "300"}]
    mine = [{"account_id": ledgers.bob_food, "limit_amount": "300"}]

    with pytest.raises(AccountNotFound):
        await budgets.create_budget("bob", "2026-10-01", "2026-10-31", mine + theirs)
    assert await budgets.list_budgets("bob") == []

    budget_id = await budgets.create_budget("bob", "2026-10-01", "2026-10-31", mine)
    with pytest.raises(AccountNotFound):
        await budgets.update_budget("bob", budget_id, {"lines": theirs})

    stored = await budgets.get_budget("bob", budget_id)
    assert stored is not None
    assert [line["account_id"] for line in stored["lines"]] == [ledgers.bob_food]
