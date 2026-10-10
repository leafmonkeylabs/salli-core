"""Unit tests for agent tools — verify shape and policy invariants."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.application.services.tax_service import NoTaxRulesError
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.agents.tools import make_tools, set_current_user
from salli.domain.taxrules.explain import UnknownLine
from tests.fakes import FakeProfiles
from tests.tax_views import computation_view


@pytest.fixture(autouse=True)
def _act_as_the_seeded_user():
    """The tools read the user from a context variable with no default; the
    fixtures below seed their data as "u1"."""
    set_current_user("u1")


# ── Fakes ──────────────────────────────────────────────────────────────────────


class FakeLedgerRepo:
    def __init__(self, entries=None, accounts=None):
        self._entries = list(entries or [])
        self._accounts = list(accounts or [])

    async def get_accounts(self, user_id, include_inactive=False):
        return [a for a in self._accounts if a.user_id == user_id]

    async def get_entries(self, user_id, from_date=None, to_date=None):
        return [e for e in self._entries if e.user_id == user_id]


class FakeUoW:
    def __init__(self, ledger_repo):
        self.ledger = ledger_repo
        self.user_profiles = FakeProfiles()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class FakeTax:
    """TaxService, as far as the tools call it."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def compute_tax(self, user_id, **kwargs):
        self.calls.append(("compute_tax", {"user_id": user_id, **kwargs}))
        if self.fail:
            raise self.fail
        return computation_view()

    async def explain(self, user_id, line_key, **kwargs):
        self.calls.append(("explain", {"user_id": user_id, "line_key": line_key, **kwargs}))
        if line_key == "nowhere":
            raise UnknownLine("nowhere", ["allowance", "tax"])
        if self.fail:
            raise self.fail
        return {"line": {"key": line_key, "amount": "3000"}, "inputs": [], "provenance": "p"}


def _services(tax: FakeTax | None = None):
    income = Decimal("30000")
    salary = Account(
        id=str(uuid.uuid4()),
        user_id="u1",
        code="4001",
        name="Salary",
        type="income",
        currency="EUR",
    )
    entry = StoredJournalEntry(
        id=str(uuid.uuid4()),
        user_id="u1",
        entry_date="2031-04-01",
        description="test",
        source="manual",
        postings=[
            Posting(account_id="bank", direction=Direction.DEBIT, amount=income, currency="EUR"),
            Posting(
                account_id=salary.id, direction=Direction.CREDIT, amount=income, currency="EUR"
            ),
        ],
    )
    repo = FakeLedgerRepo(entries=[entry], accounts=[salary])

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(repo)

    return LedgerService(uow_factory), tax or FakeTax()


def _tool(name: str, tax: FakeTax | None = None):
    ledger_svc, tax_svc = _services(tax)
    return next(t for t in make_tools(ledger_svc, tax_svc) if t.name == name)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_the_read_tools_are_the_ledger_and_the_users_own_tax():
    ledger_svc, tax_svc = _services()
    assert [t.name for t in make_tools(ledger_svc, tax_svc)] == [
        "get_trial_balance",
        "get_accounts",
        "get_tax_computation",
        "explain_tax_line",
    ]


async def test_get_accounts_returns_list():
    result = await _tool("get_accounts").ainvoke({})
    assert len(result["accounts"]) == 1
    assert result["accounts"][0]["type"] == "income"


async def test_get_trial_balance_nets_to_zero():
    result = await _tool("get_trial_balance").ainvoke({})
    assert "trial_balance" in result
    assert Decimal(result["net"]) == Decimal(0)


async def test_the_computation_is_read_only_and_for_the_signed_in_user():
    tax = FakeTax()
    await _tool("get_tax_computation", tax).ainvoke({"year": "2031", "country": "XZ"})
    assert tax.calls == [
        (
            "compute_tax",
            {"user_id": "u1", "country": "XZ", "year": "2031", "answers": None, "persist": False},
        )
    ]


async def test_the_computation_is_lines_with_their_expressions_and_sources():
    result = await _tool("get_tax_computation").ainvoke({})
    assert result["rule_set_version"] == 2
    assert [ln["key"] for ln in result["lines"]][-1] == "balance"
    tax = next(ln for ln in result["lines"] if ln["key"] == "tax")
    assert tax["expr"].startswith("line.tax.band_1.tax")
    assert result["inputs"][0] == {
        "role": "income",
        "label": "Income",
        "kind": "income",
        "total": "25000",
    }
    assert (result["net"], result["tax_payable"], result["refund_due"]) == (
        "3000.00",
        "3000.00",
        "0.00",
    )
    assert "Never recompute" in result["how_to_read"]
    assert "explain_tax_line" in result["how_to_read"]
    assert "Salli doesn't vouch" in result["provenance"]


async def test_every_figure_is_a_string_never_a_float():
    result = await _tool("get_tax_computation").ainvoke({})

    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                yield from walk(v)
        elif isinstance(value, list):
            for v in value:
                yield from walk(v)
        else:
            yield value

    assert not [v for v in walk(result) if isinstance(v, float)]


async def test_no_active_rules_is_an_answer_saying_what_to_do():
    tax = FakeTax(fail=NoTaxRulesError("no_rule_set", "You have no tax rules for XZ. Add them."))
    result = await _tool("get_tax_computation", tax).ainvoke({})
    assert result == {"error": "You have no tax rules for XZ. Add them."}


async def test_explain_tax_line_passes_the_line_through():
    tax = FakeTax()
    result = await _tool("explain_tax_line", tax).ainvoke({"line_key": "tax"})
    assert result["line"]["key"] == "tax"
    assert tax.calls[0][1]["line_key"] == "tax"


async def test_explain_tax_line_names_the_lines_there_are_for_an_unknown_one():
    result = await _tool("explain_tax_line").ainvoke({"line_key": "nowhere"})
    assert "no line 'nowhere'" in result["error"] and "allowance, tax" in result["error"]


# ── can_i_afford / get_freedom_snapshot — the affordability tools ──────────────
#
# The engine's arithmetic is covered in tests/golden and tests/properties. What
# matters at this layer is that the tool refuses bad input rather than passing it
# to the money path, and that it surfaces staleness instead of hiding it.


class FakeFiService:
    """Records what the tool passed through, and echoes a canned impact."""

    def __init__(self, is_stale: bool = False):
        self.calls: list[dict] = []
        self._is_stale = is_stale

    async def simulate_purchase(self, user_id, amount, *, term_months=None, annual_interest_rate=0):
        self.calls.append(
            {
                "user_id": user_id,
                "amount": amount,
                "term_months": term_months,
                "annual_interest_rate": annual_interest_rate,
            }
        )
        return {
            "amount": str(amount),
            "is_stale": self._is_stale,
            "data_as_of": "2026-03-01" if self._is_stale else "2026-07-20",
            "options": [{"key": "cash", "months_delay": 9}],
        }

    async def get_or_compute_score(self, user_id):
        return {"overall_score": "61.01", "grade": "Strong"}


def _manager_tool(name: str, fi_svc=None):
    from salli.domain.agents.tools import make_manager_tools, set_current_user

    set_current_user("u1")
    tools = make_manager_tools(None, None, None, fi_svc=fi_svc)
    return next(t for t in tools if t.name == name)


def test_affordability_tools_are_registered():
    """`make_manager_tools` previously took no fi_svc, so the agent could not
    discuss Freedom at all. Guard against that regressing."""
    from salli.domain.agents.tools import make_manager_tools

    names = {t.name for t in make_manager_tools(None, None, None, fi_svc=FakeFiService())}
    assert "can_i_afford" in names
    assert "get_freedom_snapshot" in names


@pytest.mark.asyncio
async def test_can_i_afford_passes_decimal_amount_through():
    fi = FakeFiService()
    tool = _manager_tool("can_i_afford", fi)

    await tool.ainvoke({"amount": "450000", "term_months": 12, "annual_interest_rate": "0.18"})

    assert fi.calls[0]["amount"] == Decimal("450000")
    assert fi.calls[0]["annual_interest_rate"] == Decimal("0.18")
    assert fi.calls[0]["term_months"] == 12


@pytest.mark.asyncio
async def test_can_i_afford_rejects_a_percentage_mistaken_for_a_fraction():
    """
    18 instead of 0.18 would overstate the finance cost ~100x. Reject rather than
    compute — the same reason FireStrategySchema bounds its rates.
    """
    fi = FakeFiService()
    tool = _manager_tool("can_i_afford", fi)

    result = await tool.ainvoke(
        {"amount": "450000", "term_months": 12, "annual_interest_rate": "18"}
    )

    assert "error" in result
    assert fi.calls == []  # never reached the money path


@pytest.mark.asyncio
async def test_can_i_afford_rejects_unparseable_and_negative_amounts():
    fi = FakeFiService()
    tool = _manager_tool("can_i_afford", fi)

    assert "error" in await tool.ainvoke({"amount": "a lot"})
    assert "error" in await tool.ainvoke({"amount": "-100"})
    assert fi.calls == []


@pytest.mark.asyncio
async def test_can_i_afford_surfaces_staleness_to_the_model():
    """The refusal is the model's job, but it can only refuse if it is told."""
    tool = _manager_tool("can_i_afford", FakeFiService(is_stale=True))

    result = await tool.ainvoke({"amount": "450000"})

    assert result["is_stale"] is True
    assert result["data_as_of"] == "2026-03-01"


@pytest.mark.asyncio
async def test_freedom_tools_degrade_without_the_service():
    for name in ("can_i_afford", "get_freedom_snapshot"):
        tool = _manager_tool(name, None)
        payload = {"amount": "1000"} if name == "can_i_afford" else {}
        result = await tool.ainvoke(payload)
        assert "error" in result
