"""
Salli's MCP tools, in-process, on the golden households (tests/golden/).

Each household's books are the golden fixtures' in-memory unit of work, and
the services are the real ones, on the household's own date, so a tool here
answers exactly what Salli's MCP server answers that person. Only reads are
offered: the benchmark asks questions, it never changes the books.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest import mock

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

#: The read tools an agent is given: what a person's questions about their
#: money need, and nothing that writes.
TOOLS = (
    "get_overview",
    "search_entries",
    "get_accounts",
    "get_trial_balance",
    "get_cash_flow",
    "get_spending",
    "get_net_worth_history",
    "get_recurring_payments",
    "get_cash_forecast",
    "get_safe_to_spend",
    "get_signals",
    "get_baseline",
    "get_payoff_plan",
    "get_fi_projections",
    "get_fi_assumptions",
    "get_tax_computation",
    "explain_tax_line",
    "list_decision_templates",
    "start_decision",
    "get_scenario_schema",
    "run_scenario",
    "compare_options",
    "list_principles",
    "check_principles",
)


class _Services(SimpleNamespace):
    """The services the read tools use; the rest (documents, budgets, the
    briefing, ...) are absent, as no tool offered here reaches them."""

    def __getattr__(self, name: str) -> Any:
        return None


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
        """The tools' names, descriptions and input schemas."""
        listed = await self._server.list_tools()
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in listed
            if t.name in TOOLS
        ]

    async def call(self, tool: str, args: dict[str, Any] | None = None) -> Any:
        """What the tool answers, as JSON-ready data."""
        if tool not in TOOLS:
            return {"error": f"{tool} is not a tool here"}
        with mock.patch.object(mcp_server, "_current_user_id", return_value=self.user):
            try:
                _, structured = await self._server.call_tool(tool, args or {})
            except Exception as exc:  # a bad call is the agent's to fix
                return {"error": str(exc)}
        return json.loads(json.dumps(structured, default=str))
