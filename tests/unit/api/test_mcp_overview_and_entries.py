"""
What an agent starts from: where the user stands in one call
(get_overview), the entries it can find with Salli's totals
(search_entries), every tool saying whether it only reads, and an entry a
retry never books twice.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.domain.accounting.models import Direction, Posting, StoredJournalEntry
from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services():
    services = MagicMock()
    for name in ("ledger", "baseline", "insights", "fi", "reminders"):
        setattr(services, name, AsyncMock())
    services.ledger.base_currency.return_value = "EUR"
    audit = SimpleNamespace(log=AsyncMock())
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    uow.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=uow)
    services.audit = audit
    return services


async def _call(services, tool: str, args: dict):
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value="u1"):
        _, structured = await server.call_tool(tool, args)
    return structured


async def test_every_tool_says_whether_it_only_reads(services):
    tools = await mcp_server.build_mcp_server(services, "https://api.test").list_tools()
    unsaid = [t.name for t in tools if t.annotations is None or t.annotations.readOnlyHint is None]
    assert unsaid == []
    hints = {t.name: t.annotations for t in tools}
    for read in ("get_overview", "search_entries", "get_safe_to_spend", "run_scenario"):
        assert hints[read].readOnlyHint is True, read
    for write in ("post_journal_entry", "create_reminder", "record_decision", "save_memory"):
        assert hints[write].readOnlyHint is False, write
    assert hints["delete_document"].destructiveHint is True
    assert hints["create_reminder"].destructiveHint is False
    assert "Start here" in (next(t for t in tools if t.name == "get_overview").description or "")


async def test_the_overview_is_salli_s_figures_in_one_call(services):
    services.baseline.build.return_value = SimpleNamespace(
        as_of=dt.date(2026, 10, 25),
        currency="EUR",
        net_worth=Decimal("48210.456"),
        savings=Decimal("9000"),
        latest_entry="2026-10-24",
    )
    services.insights.safe_to_spend.return_value = {
        "amount": "412.30",
        "cash_today": "2310.00",
        "until": "2026-10-31",
        "low_point": "912.30",
        "low_point_date": "2026-10-30",
        "committed": [{"description": "Rent"}],
    }
    services.insights.signals.return_value = {
        "signals": [{"kind": "price_change", "title": "A subscription got dearer", "detail": "…"}]
    }
    services.fi.compute_score.return_value = {
        "projected_fi_month": "2041-03",
        "progress_to_fi": "0.18",
        "status": "ok",
        "months_observed": 14,
        "assumptions": {"status": "placeholder"},
    }
    services.reminders.list_reminders.return_value = [
        {"kind": "File the return", "due_date": "2026-11-15", "source_domain": "tax_rules"},
        {"kind": "Renew the lease", "due_date": "2027-03-01", "source_domain": None},
    ]

    overview = await _call(services, "get_overview", {})

    assert overview == {
        "as_of": "2026-10-25",
        "currency": "EUR",
        "net_worth": "48210.46",
        "cash": "2310.00",
        "savings": "9000.00",
        "free_until_payday": {
            "amount": "412.30",
            "until": "2026-10-31",
            "low_point": "912.30",
            "low_point_date": "2026-10-30",
        },
        "signals": [{"kind": "price_change", "title": "A subscription got dearer"}],
        "fi": {
            "status": "ok",
            "months_observed": 14,
            "month": "2041-03",
            "progress": "0.18",
            "assumptions": "placeholder",
        },
        "due": [{"kind": "File the return", "due_date": "2026-11-15", "source": "tax_rules"}],
        "data_as_of": "2026-10-24",
        "is_stale": False,
    }
    services.reminders.list_reminders.assert_awaited_once_with("u1", "pending")
    services.fi.record_score.assert_not_called()  # a read stores no score

    services.baseline.build.return_value.latest_entry = "2026-08-01"
    assert (await _call(services, "get_overview", {}))["is_stale"] is True

    # Under two full months of flows, the score's month and progress say nothing.
    services.fi.compute_score.return_value |= {"status": "not_enough_data", "months_observed": 1}
    assert (await _call(services, "get_overview", {}))["fi"] == {
        "status": "not_enough_data",
        "months_observed": 1,
        "month": None,
        "progress": None,
        "assumptions": "placeholder",
    }


async def test_entries_are_found_with_totals_over_every_match(services, refused):
    entry = StoredJournalEntry(
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
    services.ledger.search_entries.return_value = {
        "entries": [entry],
        "matches": 7,
        "totals": [{"account_type": "expense", "currency": "EUR", "net": "61.20"}],
        "amounts_in": "EUR",
        "next_cursor": "MjAyNi0xMC0yNHxlMQ==",
    }

    found = await _call(
        services,
        "search_entries",
        {"text": "bakery", "min_amount": "5", "limit": 1000, "cursor": "abc"},
    )

    services.ledger.search_entries.assert_awaited_once_with(
        "u1",
        text="bakery",
        account_id=None,
        from_date=None,
        to_date=None,
        min_amount=Decimal("5"),
        max_amount=None,
        limit=200,  # at most 200 a page
        cursor="abc",
    )
    assert found["entries"] == [
        {
            "id": "e1",
            "date": "2026-10-24",
            "description": "Corner Bakery",
            "reversed_by": None,
            "postings": [
                {"account_id": "food", "side": "debit", "amount": "8.40", "currency": "EUR"},
                {"account_id": "cash", "side": "credit", "amount": "8.40", "currency": "EUR"},
            ],
        }
    ]
    assert found["matches"] == 7
    assert found["totals"] == [{"account_type": "expense", "currency": "EUR", "net": "61.20"}]
    assert found["next_cursor"] == "MjAyNi0xMC0yNHxlMQ=="

    vague = await refused(_call(services, "search_entries", {"max_amount": "about ten"}))
    assert vague["problems"] == [{"path": "max_amount", "message": "not a decimal string"}]
    services.ledger.search_entries.side_effect = ValueError("That cursor is not one a search gave")
    cursor = await refused(_call(services, "search_entries", {"cursor": "nonsense"}))
    assert cursor == {
        "code": "invalid_input",
        "message": "That cursor is not one a search gave",
        "retryable": False,
    }


async def test_an_entry_sent_again_with_its_client_ref_is_booked_once(services, refused):
    args = {
        "entry_date": "2026-10-24",
        "description": "Corner Bakery",
        "debit_account_id": "food",
        "credit_account_id": "cash",
        "amount": "8.40",
        "client_ref": "chat-7-entry-1",
    }
    services.ledger.add_entry_once.return_value = ("e1", True)
    assert await _call(services, "post_journal_entry", args) == {"entry_id": "e1", "posted": True}
    assert services.ledger.add_entry_once.await_args.args[-1] == "chat-7-entry-1"
    services.ledger.add_entry.assert_not_called()
    assert services.audit.log.await_count == 1

    services.ledger.add_entry_once.return_value = ("e1", False)
    assert await _call(services, "post_journal_entry", args) == {
        "entry_id": "e1",
        "posted": False,
        "already_posted": True,
    }
    # Booking nothing still answers the call: audited as succeeded.
    assert [c.args[3] for c in services.audit.log.await_args_list] == ["succeeded"] * 2

    too_long = await refused(
        _call(services, "post_journal_entry", {**args, "client_ref": "x" * 181})
    )
    assert too_long["message"] == "client_ref is 1 to 180 characters"
