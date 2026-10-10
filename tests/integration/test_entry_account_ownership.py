"""A journal entry posts only to the caller's own accounts.

Postings reference accounts by id alone, and nothing checked whose account an
id was: user B could post against user A's accounts through the API, the MCP
server or the CLI, and the entry landed in A's ledger. Each surface is driven
here against a real database, so the check that matters (the repository's) is
the one exercised.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from salli.application.ports import AccountNotFound
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
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
        alice_cash=await ledger.add_account("alice", "1000", "Cash", "asset"),
        bob_cash=await ledger.add_account("bob", "1000", "Cash", "asset"),
        bob_income=await ledger.add_account("bob", "4000", "Salary", "income"),
    )


def _postings(debit: str, credit: str) -> list[dict[str, object]]:
    return [
        {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(50)},
        {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(50)},
    ]


async def _nothing_posted(ledger: LedgerService) -> None:
    assert await ledger.get_entries("alice") == []
    assert await ledger.get_entries("bob") == []


async def test_the_service_refuses_another_users_account(ledgers):
    with pytest.raises(AccountNotFound) as refused:
        await ledgers.ledger.add_entry(
            "bob",
            "2026-10-10",
            "Into Alice's cash",
            "manual",
            _postings(ledgers.alice_cash, ledgers.bob_income),
        )
    # Named like an account that doesn't exist: nothing about Alice's ledger.
    assert refused.value.account_ids == (ledgers.alice_cash,)
    assert str(refused.value) == f"Account not found: {ledgers.alice_cash}"
    await _nothing_posted(ledgers.ledger)

    with pytest.raises(AccountNotFound):
        await ledgers.ledger.add_entry(
            "bob", "2026-10-10", "Nowhere", "manual", _postings("made-up", ledgers.bob_income)
        )
    await _nothing_posted(ledgers.ledger)


async def test_the_api_refuses_it_and_still_posts_to_your_own(ledgers):
    from salli.interfaces.api.deps import get_current_user, get_services
    from salli.interfaces.api.main import create_app

    def caller(request: Request) -> str:
        return request.headers["authorization"].removeprefix("Bearer ")

    app = create_app()
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(ledger=ledgers.ledger)
    app.dependency_overrides[get_current_user] = caller

    def body(debit: str, credit: str) -> dict[str, object]:
        return {
            "entry_date": "2026-10-10",
            "description": "Salary",
            "postings": [
                {"account_id": debit, "direction": 1, "amount": "50.00"},
                {"account_id": credit, "direction": -1, "amount": "50.00"},
            ],
        }

    bob = {"Authorization": "Bearer bob"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/v1/entries/", json=body(ledgers.alice_cash, ledgers.bob_income), headers=bob
        )
        assert r.status_code == 404, r.json()
        assert r.headers["content-type"].startswith("application/problem+json")
        assert r.json()["detail"] == f"Account not found: {ledgers.alice_cash}"
        await _nothing_posted(ledgers.ledger)

        r = await client.post(
            "/v1/entries/", json=body(ledgers.bob_cash, ledgers.bob_income), headers=bob
        )
        assert r.status_code == 201
    [entry] = await ledgers.ledger.get_entries("bob")
    assert {p.account_id for p in entry.postings} == {ledgers.bob_cash, ledgers.bob_income}
    assert await ledgers.ledger.get_entries("alice") == []


async def test_the_mcp_tool_refuses_it(ledgers):
    from salli.interfaces.api import mcp_server

    services = MagicMock()
    services.ledger = ledgers.ledger
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with (
        patch.object(mcp_server, "_current_user_id", return_value="bob"),
        patch.object(mcp_server, "_log_audit", AsyncMock()) as audit,
    ):
        _, result = await server.call_tool(
            "post_journal_entry",
            {
                "entry_date": "2026-10-10",
                "description": "Into Alice's cash",
                "debit_account_id": ledgers.alice_cash,
                "credit_account_id": ledgers.bob_income,
                "amount": "50.00",
            },
        )
    assert result == {"error": f"Could not post entry: Account not found: {ledgers.alice_cash}"}
    audit.assert_not_awaited()  # nothing happened, so nothing is logged as done
    await _nothing_posted(ledgers.ledger)
