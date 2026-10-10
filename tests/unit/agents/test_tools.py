"""Unit tests for agent tools — verify shape and policy invariants."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.application.services.tax_service import TaxService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.agents.tools import make_tools, set_current_user
from tests.fakes import FakeProfiles


@pytest.fixture(autouse=True)
def _act_as_the_seeded_user():
    """The tools read the user from a context variable with no default; the
    fixtures below seed their data as "u1"."""
    set_current_user("u1")


# ── Fake repos (same pattern as service tests) ────────────────────────────────


class FakeLedgerRepo:
    def __init__(self, entries=None, accounts=None):
        self._entries = list(entries or [])
        self._accounts = list(accounts or [])

    async def save_account(self, user_id, account):
        self._accounts.append(account)
        return account.id

    async def get_accounts(self, user_id):
        return [a for a in self._accounts if a.user_id == user_id]

    async def save_entry(self, user_id, entry):
        return str(uuid.uuid4())

    async def get_entries(self, user_id, from_date=None, to_date=None):
        result = [e for e in self._entries if e.user_id == user_id]
        if from_date:
            result = [e for e in result if e.entry_date >= from_date]
        if to_date:
            result = [e for e in result if e.entry_date <= to_date]
        return result


class FakeTaxComputationRepo:
    def __init__(self):
        self._store = {}

    async def save(self, user_id, computation):
        self._store[(user_id, computation.pack_year)] = computation
        return str(uuid.uuid4())

    async def get_latest(self, user_id, year):
        return self._store.get((user_id, year))


class FakeUoW:
    def __init__(self, ledger_repo, tax_repo):
        self.ledger = ledger_repo
        self.tax_computations = tax_repo
        self.user_profiles = FakeProfiles()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _make_services_with_income(income: Decimal = Decimal("3_000_000")):
    salary_acc = Account(
        id=str(uuid.uuid4()),
        user_id="u1",
        code="4001",
        name="Employment Income",
        type="income",
        currency="LKR",
    )
    entry = StoredJournalEntry(
        id=str(uuid.uuid4()),
        user_id="u1",
        entry_date="2025-04-01",
        description="test",
        source="manual",
        postings=[
            Posting(account_id="bank", direction=Direction.DEBIT, amount=income, currency="LKR"),
            Posting(
                account_id=salary_acc.id, direction=Direction.CREDIT, amount=income, currency="LKR"
            ),
        ],
    )
    ledger_repo = FakeLedgerRepo(entries=[entry], accounts=[salary_acc])
    tax_repo = FakeTaxComputationRepo()

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(ledger_repo, tax_repo)

    ledger_svc = LedgerService(uow_factory)
    tax_svc = TaxService(uow_factory)
    return ledger_svc, tax_svc


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_accounts_returns_list():
    from salli.domain.agents.tools import set_current_user

    set_current_user("u1")
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    get_accounts = next(t for t in tools if t.name == "get_accounts")

    result = await get_accounts.ainvoke({})
    assert "accounts" in result
    assert len(result["accounts"]) == 1
    assert result["accounts"][0]["type"] == "income"


@pytest.mark.asyncio
async def test_get_trial_balance_keys():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    get_tb = next(t for t in tools if t.name == "get_trial_balance")

    result = await get_tb.ainvoke({"user_id": "u1"})
    assert "trial_balance" in result
    assert "net" in result


@pytest.mark.asyncio
async def test_get_trial_balance_net_is_zero():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    get_tb = next(t for t in tools if t.name == "get_trial_balance")

    result = await get_tb.ainvoke({"user_id": "u1"})
    assert Decimal(result["net"]) == Decimal(0)


@pytest.mark.asyncio
async def test_get_tax_computation_keys():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    get_tax = next(t for t in tools if t.name == "get_tax_computation")

    result = await get_tax.ainvoke({"year": "2025/26", "user_id": "u1"})
    for key in (
        "year",
        "pack_version",
        "gross_income",
        "taxable_income",
        "tax_payable",
        "band_workings",
    ):
        assert key in result, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_get_tax_computation_all_values_strings():
    """Tool must return string representations of Decimal values (LLM-safe)."""
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    get_tax = next(t for t in tools if t.name == "get_tax_computation")

    result = await get_tax.ainvoke({"year": "2025/26", "user_id": "u1"})
    # All monetary values should be strings, not Decimal (JSON-safe)
    for key in ("gross_income", "taxable_income", "tax_payable", "tax_before_credits"):
        assert isinstance(result[key], str), f"{key} should be str, got {type(result[key])}"


@pytest.mark.asyncio
async def test_get_tax_computation_below_relief():
    """Income below relief → tax_payable should be '0'."""
    ledger_svc, tax_svc = _make_services_with_income(income=Decimal("1_000_000"))
    tools = make_tools(ledger_svc, tax_svc)
    get_tax = next(t for t in tools if t.name == "get_tax_computation")

    result = await get_tax.ainvoke({"year": "2025/26", "user_id": "u1"})
    assert Decimal(result["tax_payable"]) == Decimal(0)


def test_list_tax_packs():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    list_packs = next(t for t in tools if t.name == "list_tax_packs")

    result = list_packs.invoke({})
    assert "packs" in result
    keys = {(p["country"], p["year"]) for p in result["packs"]}
    assert ("LK", "2025/26") in keys


def test_explain_tax_band_valid():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    explain = next(t for t in tools if t.name == "explain_tax_band")

    result = explain.invoke({"band_index": 0, "year": "2025/26"})
    assert "rate" in result
    assert "rate_pct" in result
    assert result["band_index"] == 0


def test_explain_tax_band_out_of_range():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    explain = next(t for t in tools if t.name == "explain_tax_band")

    result = explain.invoke({"band_index": 99, "year": "2025/26"})
    assert "error" in result


@pytest.mark.asyncio
async def test_get_tax_computation_unknown_year():
    ledger_svc, tax_svc = _make_services_with_income()
    tools = make_tools(ledger_svc, tax_svc)
    get_tax = next(t for t in tools if t.name == "get_tax_computation")

    with pytest.raises(KeyError):
        await get_tax.ainvoke({"year": "1999/00", "user_id": "u1"})


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
