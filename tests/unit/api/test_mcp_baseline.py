"""
The MCP tools for the baseline and the figures built on it: `get_baseline`,
and the bounds `get_payoff_plan` keeps as the API does, because the service
checks them. And an account's asset role, on create and update. (What a
purchase costs is a scenario now: tests/unit/api/test_mcp_scenarios.py.)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.debt_service import DebtService
from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account
from salli.interfaces.api import mcp_server
from tests.golden import household as h

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services():
    uow = h.uow()
    today = lambda: h.AS_OF  # noqa: E731
    baselines = BaselineService(uow.factory(), fx=h.fx(), today=today)
    services = MagicMock()
    services.baseline = baselines
    services.fi = FiService(uow.factory(), baselines=baselines, today=today)
    services.debt = DebtService(uow.factory(), baselines=baselines, today=today)
    services.ledger = AsyncMock()
    audit = SimpleNamespace(log=AsyncMock())
    unit = MagicMock()
    unit.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    unit.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=unit)
    services.uow = uow
    return services


async def _call(services, tool: str, args: dict):
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value=h.USER):
        _, structured = await server.call_tool(tool, args)
    return structured


async def test_the_baseline_is_salli_s_with_its_definitions(services, refused):
    body = await _call(services, "get_baseline", {})
    assert body["as_of"] == "2026-10-11"
    assert body["months_observed"][0] == "2026-04"
    assert body["rates"][0]["source"] == "ecb"
    # Compact for an agent: month-ends and the lowest point, not every day.
    assert body["cash"]["daily"] is None
    assert len(body["cash"]["month_ends"]) == 13
    assert len(body["monthly"]["points"]) == 1 + 10 * 12 + 1
    assert services.uow.fi_scores.rows == []

    past = await _call(services, "get_baseline", {"as_of": "2026-06-30", "horizon_years": 1})
    assert past["as_of"] == "2026-06-30"
    for args, said in (
        ({"as_of": "2026-12-01"}, "after today"),
        ({"as_of": "soon"}, "as_of is a date"),
        ({"horizon_years": 70}, "horizon"),
    ):
        error = await refused(_call(services, "get_baseline", args))
        assert said in error["message"]
        assert (error["code"], error["retryable"]) == ("invalid_input", False)


@pytest.mark.parametrize("extra", ["-50", "nothing", "NaN"])
async def test_an_extra_payment_out_of_bounds_is_refused(services, refused, extra):
    error = await refused(_call(services, "get_payoff_plan", {"extra_monthly_payment": extra}))
    assert error["code"] == "invalid_input"
    assert "extra" in error["message"].lower()


async def test_the_payoff_plan_is_on_calendar_months(services):
    plan = await _call(services, "get_payoff_plan", {"extra_monthly_payment": "100"})
    assert (plan["first_month"], plan["debt_free_month"]) == ("2026-11", "2029-09")


async def test_an_account_is_created_and_changed_with_its_asset_role(services):
    services.ledger.add_account.return_value = "new"
    services.ledger.base_currency.return_value = "EUR"
    created = await _call(
        services,
        "create_account",
        {
            "code": "1600",
            "name": "Index funds",
            "account_type": "asset",
            "asset_role": "investment",
        },
    )
    assert created["created"] is True
    assert services.ledger.add_account.await_args.kwargs["asset_role"] == "investment"
    await _call(
        services,
        "create_account",
        {"code": "1700", "name": "Rainy day", "account_type": "asset", "asset_role": "savings"},
    )
    assert services.ledger.add_account.await_args.kwargs["asset_role"] == "savings"

    existing = Account(
        id="flat", user_id=h.USER, code="1500", name="Flat", type="asset", currency="EUR"
    )
    services.ledger.get_account.side_effect = [
        existing,
        existing.model_copy(update={"asset_role": "other"}),
    ]
    changed = await _call(services, "update_account", {"account_id": "flat", "asset_role": "other"})
    assert (changed["updated"], changed["asset_role"]) == (True, "other")
    kwargs = services.ledger.update_account.await_args.kwargs
    assert (kwargs["code"], kwargs["name"], kwargs["type"], kwargs["asset_role"]) == (
        "1500",
        "Flat",
        "asset",
        "other",
    )


async def test_an_account_that_is_not_the_users_is_not_changed(services, refused):
    services.ledger.get_account.side_effect = None
    services.ledger.get_account.return_value = None  # not theirs, or nowhere
    error = await refused(
        _call(services, "update_account", {"account_id": "x", "asset_role": "other"})
    )
    assert error == {"code": "not_found", "message": "Account not found: x", "retryable": False}
    services.ledger.update_account.assert_not_awaited()
