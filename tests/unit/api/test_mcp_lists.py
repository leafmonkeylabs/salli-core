"""
What the MCP server reads and does beside the API: the lists of budgets,
debts, goals and reminders, a budget's summary by its id, an entry by its
id and its reversal once the person said yes; and a personal access token
as a read-only bearer for a headless agent.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.application.services.personal_access_token_service import VerifiedToken
from salli.domain.accounting.models import Direction, Posting, StoredJournalEntry
from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services():
    services = MagicMock()
    for name in ("ledger", "budget", "debt", "fi", "reminders", "tokens", "mcp_oauth"):
        setattr(services, name, AsyncMock())
    audit = SimpleNamespace(log=AsyncMock())
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    uow.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=uow)
    return services


async def _call(services, tool: str, args: dict):
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value="u1"):
        _, structured = await server.call_tool(tool, args)
    return structured


async def test_the_lists_are_the_services_own(services):
    services.budget.list_budgets.return_value = [{"id": "b1", "period_start": "2026-10-01"}]
    services.debt.list_debts.return_value = [{"id": "d1", "name": "Car loan"}]
    services.fi.list_goals.return_value = [{"id": "g1", "name": "A new roof"}]
    services.reminders.list_reminders.return_value = [{"id": "r1", "kind": "Renew the lease"}]

    assert (await _call(services, "list_budgets", {}))["budgets"][0]["id"] == "b1"
    debts = await _call(services, "list_debts", {"include_closed": True})
    assert debts["debts"] == [{"id": "d1", "name": {"untrusted_text": "Car loan"}}]
    services.debt.list_debts.assert_awaited_once_with("u1", False)
    goals = await _call(services, "list_goals", {})
    assert goals["goals"][0]["name"] == {"untrusted_text": "A new roof"}
    await _call(services, "list_reminders", {"status": "pending"})
    services.reminders.list_reminders.assert_awaited_once_with("u1", "pending")


async def test_a_budget_summary_is_the_one_asked_for(services, refused):
    services.budget.get_summary.return_value = {"budget_id": "b2", "lines": []}
    assert (await _call(services, "get_budget_summary", {"budget_id": "b2"}))["budget_id"] == "b2"
    services.budget.get_summary.assert_awaited_once_with("u1", "b2")
    services.budget.list_budgets.assert_not_called()
    services.budget.get_summary.return_value = None
    gone = await refused(_call(services, "get_budget_summary", {"budget_id": "nope"}))
    assert gone["code"] == "not_found"


async def test_an_entry_is_read_and_reversed_only_once_the_person_said_yes(services, refused):
    services.ledger.get_entry.return_value = StoredJournalEntry(
        id="e1",
        user_id="u1",
        entry_date="2026-10-24",
        description="Corner Bakery",
        source="manual",
        postings=[
            Posting(
                account_id="food", direction=Direction.DEBIT, amount=Decimal("8.4"), currency="EUR"
            ),
            Posting(
                account_id="cash", direction=Direction.CREDIT, amount=Decimal("8.4"), currency="EUR"
            ),
        ],
    )
    entry = await _call(services, "get_entry", {"entry_id": "e1"})
    assert entry["description"] == {"untrusted_text": "Corner Bakery"}
    assert [p["amount"] for p in entry["postings"]] == ["8.40", "8.40"]

    unconfirmed = await refused(
        _call(services, "reverse_entry", {"entry_id": "e1", "reason": "Booked twice"})
    )
    assert unconfirmed["code"] == "invalid_input"
    services.ledger.reverse_entry.assert_not_called()

    services.ledger.reverse_entry.return_value = "e2"
    done = await _call(
        services,
        "reverse_entry",
        {"entry_id": "e1", "reason": "Booked twice", "confirmed_by_user": True},
    )
    assert done == {"entry_id": "e1", "reversed_by": "e2"}
    services.ledger.reverse_entry.assert_awaited_once_with("u1", "e1", "Booked twice")


async def test_a_personal_access_token_reads_and_never_writes(services):
    verifier = mcp_server.SalliTokenVerifier(services.mcp_oauth, services.tokens)
    services.tokens.verify.return_value = VerifiedToken("u1", "nightly agent", frozenset())
    services.mcp_oauth.is_mcp_enabled.return_value = True
    token = await verifier.verify_token("salli_pat_abc")
    assert token is not None
    assert (token.subject, token.client_id, token.scopes) == ("u1", "pat:nightly agent", [])
    services.mcp_oauth.verify_access_token.assert_not_called()

    services.mcp_oauth.is_mcp_enabled.return_value = False
    assert await verifier.verify_token("salli_pat_abc") is None
    services.tokens.verify.return_value = None
    services.mcp_oauth.is_mcp_enabled.return_value = True
    assert await verifier.verify_token("salli_pat_revoked") is None
