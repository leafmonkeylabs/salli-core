"""
The MCP tools for the person's holdings (decision lab 3b): `list_holdings`
gives each by the person's own id, symbol and name; `link_holding` links one
to the investment account that holds it, or unlinks it, and refuses an
account that isn't the person's own investment account. And the scenario
tools' descriptions say how holdings go into a scenario, and what an agent
may and may not say about them.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.application.services.portfolio_service import PortfolioService
from salli.domain.accounting.models import Account
from salli.interfaces.api import mcp_server
from tests.fakes import FakeRecordsUoW

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("experimental_on")]

USER = "amara"


@pytest.fixture
def services():
    uow = FakeRecordsUoW("NGN")
    for id_, role in (("brk", "investment"), ("bank", "cash")):
        uow.ledger.accounts.append(
            Account(
                id=id_,
                user_id=USER,
                code=id_,
                name=id_.title(),
                type="asset",
                currency="NGN",
                asset_role=role,  # type: ignore[arg-type]
            )
        )
    services = MagicMock()
    services.portfolio = PortfolioService(lambda: uow)
    services.ledger = AsyncMock()
    audit = SimpleNamespace(log=AsyncMock())
    unit = MagicMock()
    unit.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    unit.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=unit)
    services.uow = uow
    services.audit = audit
    return services


async def _call(services, tool: str, args: dict):
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value=USER):
        _, structured = await server.call_tool(tool, args)
    return structured


async def _fund(services) -> str:
    return await services.portfolio.add_holding(
        USER, {"symbol": "FND", "name": "My savings fund", "asset_class": "equity"}
    )


async def test_holdings_are_listed_as_the_person_named_them(services):
    fund = await _fund(services)
    listed = await _call(services, "list_holdings", {})
    (holding,) = listed["holdings"]
    name = holding["name"]["untrusted_text"]
    assert (holding["id"], holding["symbol"], name, holding["account_id"]) == (
        fund,
        "FND",
        "My savings fund",
        None,
    )


async def test_a_holding_links_to_its_investment_account_and_unlinks(services):
    fund = await _fund(services)
    linked = await _call(services, "link_holding", {"holding_id": fund, "account_id": "brk"})
    assert linked == {"holding_id": fund, "account_id": "brk", "updated": True}
    assert (await services.portfolio.get_holding(USER, fund))["account_id"] == "brk"
    services.audit.log.assert_awaited()

    await _call(services, "link_holding", {"holding_id": fund, "account_id": None})
    assert (await services.portfolio.get_holding(USER, fund))["account_id"] is None


async def test_a_link_to_anything_but_the_persons_investment_account_is_refused(services, refused):
    fund = await _fund(services)
    cash = await refused(
        _call(services, "link_holding", {"holding_id": fund, "account_id": "bank"})
    )
    assert cash["code"] == "invalid_input" and "role cash" in cash["message"]
    theirs = await refused(
        _call(services, "link_holding", {"holding_id": fund, "account_id": "nope"})
    )
    assert (theirs["code"], theirs["message"]) == ("not_found", "Account not found: nope")
    missing = await refused(
        _call(services, "link_holding", {"holding_id": "x", "account_id": "brk"})
    )
    assert (missing["code"], missing["message"]) == ("not_found", "Holding not found: x")
    assert (await services.portfolio.get_holding(USER, fund))["account_id"] is None


async def test_the_tools_say_what_an_agent_may_say_about_holdings(services):
    tools = {
        t.name: " ".join((t.description or "").split())
        for t in await mcp_server.build_mcp_server(services, "https://api.test").list_tools()
    }
    assert (
        "never suggest buying or selling one, never compare them as investments"
        in tools["list_holdings"]
    )
    assert "get their go-ahead" in tools["link_holding"]
    # How holdings go into a scenario: in the schema get_scenario_schema gives.
    assert "how tax, holdings and assets go into one" in tools["get_scenario_schema"]
    guide = mcp_server.SCENARIO_GUIDE
    assert "a `sell` sells part of one" in guide
    assert "Fees are the user's own figure: never assume one" in guide
    assert "forecasts no price" in guide
