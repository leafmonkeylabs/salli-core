"""
Salli's MCP tools, in-process, on the golden households (tests/golden/).

Each household's books are the golden fixtures' in-memory unit of work, and
the services are the real ones, on the household's own date, so a tool here
answers exactly what Salli's MCP server answers that person, through the
server's own handler. Every tool is listed, as to any client, on a
connection that may only read: the server's gate refuses a change, so the
benchmark never changes the books. A tool whose service the households
don't have (documents, budgets, the briefing, ...) says so as an error.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest import mock

from mcp import types
from mcp.server.fastmcp import FastMCP

from salli.application.services.baseline_service import BaselineService
from salli.application.services.debt_service import DebtService
from salli.application.services.decision_service import DecisionService
from salli.application.services.fi_service import FiService
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.reminder_service import ReminderService
from salli.application.services.scenario_service import ScenarioService
from salli.application.services.tax_rule_service import TaxRuleService
from salli.application.services.tax_service import TaxService
from salli.application.services.template_service import TemplateService
from salli.interfaces.api import mcp_server
from tests import baseline_ledger
from tests.fakes import FakeFx, FakeUoW
from tests.golden import household as h
from tests.golden import renting, taxed


class _Absent:
    """A service the golden households don't have: any use of it fails the
    tool, as one with nothing to answer from."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, method: str) -> Any:
        def absent(*args: Any, **kwargs: Any) -> Any:
            raise mcp_server.ToolFailure(
                "not_enough_data", f"The benchmark's households have no {self._name}"
            )

        return absent


class _Services(SimpleNamespace):
    """The services the households have (books, baseline, plans, decisions,
    tax); the rest are absent."""

    def __getattr__(self, name: str) -> Any:
        return _Absent(name)


def _services(uow: FakeUoW, fx: FakeFx, as_of: dt.date) -> SimpleNamespace:
    def today() -> dt.date:
        return as_of

    factory = uow.factory()
    baselines = BaselineService(factory, fx=fx, today=today)
    scenarios = ScenarioService(factory, baselines=baselines)
    principles = PrincipleService(factory, scenarios)
    rules = TaxRuleService(factory, fx=fx)
    return _Services(
        ledger=LedgerService(factory, fx=fx, today=today),
        baseline=baselines,
        insights=InsightsService(factory, today=today, baselines=baselines),
        fi=FiService(factory, baselines=baselines, today=today),
        reminders=ReminderService(factory),
        debt=DebtService(factory, baselines=baselines, today=today),
        scenarios=scenarios,
        principles=principles,
        templates=TemplateService(scenarios, principles),
        decisions=DecisionService(factory, scenarios, principles),
        tax_rules=rules,
        tax=TaxService(factory, rules, clock=today),
    )


def _household() -> tuple[str, SimpleNamespace]:
    return h.USER, _services(h.uow(), h.fx(), h.AS_OF)


def _ledger(make: Callable[[], baseline_ledger.Ledger], as_of: dt.date) -> Any:
    def books() -> tuple[str, SimpleNamespace]:
        ledger = make()
        return baseline_ledger.USER, _services(ledger.uow, FakeFx(ledger.rates), as_of)

    return books


#: Each household: its books, by name, as questions.yaml names them.
HOUSEHOLDS: dict[str, Callable[[], tuple[str, SimpleNamespace]]] = {
    "household": _household,
    "renting": _ledger(renting.ledger, renting.AS_OF),
    "taxed": _ledger(taxed.ledger, taxed.AS_OF),
}


class Salli:
    """One household's Salli, as an MCP client sees it: its read tools, each
    answering as the MCP server does."""

    def __init__(self, household: str) -> None:
        self.household = household
        self.user, services = HOUSEHOLDS[household]()
        self._server: FastMCP = mcp_server.build_mcp_server(services, "https://salli.test")
        self.instructions = self._server.instructions or ""

    async def tools(self) -> list[dict[str, Any]]:
        """Every tool's name, description and input schema, as listed."""
        listed = await self._server.list_tools()
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in listed
        ]

    async def call(self, tool: str, args: dict[str, Any] | None = None) -> Any:
        """What the tool answers, as a client gets it, as JSON-ready data: a
        failure as its `error` (a refused change's code is `scope`)."""
        handler = self._server._mcp_server.request_handlers[types.CallToolRequest]  # pyright: ignore[reportPrivateUsage]
        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name=tool, arguments=args or {}),
        )
        with (
            mock.patch.object(mcp_server, "_current_user_id", return_value=self.user),
            mock.patch.object(mcp_server, "_current_scopes", return_value=["mcp:read"]),
        ):
            result = (await handler(request)).root
        assert isinstance(result, types.CallToolResult)
        if result.structuredContent is not None:
            return json.loads(json.dumps(result.structuredContent, default=str))
        text = " ".join(c.text for c in result.content if isinstance(c, types.TextContent))
        return {"error": {"message": text}} if result.isError else text
