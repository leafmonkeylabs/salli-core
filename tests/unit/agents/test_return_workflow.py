"""Unit tests for the return preparation workflow (no LLM calls)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.agent_service import AgentService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.tax_service import TaxService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.agents.return_workflow import ReturnState, _finalize, _map_to_cages
from tests.fakes import FakeProfiles

# ── Fakes (shared with test_tools.py) ─────────────────────────────────────────


class FakeLedgerRepo:
    def __init__(self, entries=None, accounts=None):
        self._entries = list(entries or [])
        self._accounts = list(accounts or [])

    async def save_account(self, user_id, account):
        self._accounts.append(account)
        return account.id

    async def get_accounts(self, user_id, include_inactive=False):
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


def _make_services(income: Decimal = Decimal("4_000_000")):
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

    return LedgerService(uow_factory), TaxService(uow_factory)


# ── Pure node tests (no LangGraph graph execution) ────────────────────────────


def _make_tax_computation():
    from salli.domain.tax.engine import compute
    from salli.domain.tax.models import LedgerView
    from salli.domain.tax.packs.registry import get_pack

    pack = get_pack("LK", "2025/26")
    view = LedgerView(
        total_income=Decimal("4_000_000"),
        foreign_service_income=Decimal(0),
        apit_withheld=Decimal(0),
        ait_withheld=Decimal(0),
        foreign_tax_paid=Decimal(0),
        qualifying_payments=Decimal(0),
    )
    return compute(view, pack)


def test_map_to_cages_keys():
    tc = _make_tax_computation()
    state = ReturnState(user_id="u1", year="2025/26", tax_computation=tc)
    result = _map_to_cages(state)
    draft = result["draft_return"]

    for key in (
        "cage_1a_employment_income",
        "cage_2a_personal_relief",
        "cage_3a_taxable_income",
        "cage_3b_tax_before_credits",
        "cage_4a_apit_withheld",
        "cage_5a_tax_payable",
        "pack_version",
        "year",
    ):
        assert key in draft, f"Missing cage: {key}"


def test_map_to_cages_values_match_engine():
    tc = _make_tax_computation()
    state = ReturnState(user_id="u1", year="2025/26", tax_computation=tc)
    result = _map_to_cages(state)
    draft = result["draft_return"]

    assert Decimal(draft["cage_5a_tax_payable"]) == tc.tax_payable
    assert Decimal(draft["cage_3a_taxable_income"]) == tc.taxable_income


def test_map_to_cages_no_computation():
    state = ReturnState(user_id="u1", year="2025/26", tax_computation=None)
    result = _map_to_cages(state)
    assert "error" in result


def test_finalize_approved():
    tc = _make_tax_computation()
    state = ReturnState(
        user_id="u1",
        year="2025/26",
        tax_computation=tc,
        review_decision="approve",
        draft_return={"cage_5a_tax_payable": str(tc.tax_payable)},
    )
    result = _finalize(state)
    assert result["worksheet"]["status"] == "ready_to_submit"
    assert "instructions" in result["worksheet"]
    assert not result.get("error")


def test_finalize_rejected():
    tc = _make_tax_computation()
    state = ReturnState(
        user_id="u1",
        year="2025/26",
        tax_computation=tc,
        review_decision="reject",
        draft_return={},
    )
    result = _finalize(state)
    assert not result["worksheet"]
    assert "error" in result


def test_finalize_edit_not_approved():
    tc = _make_tax_computation()
    state = ReturnState(
        user_id="u1",
        year="2025/26",
        tax_computation=tc,
        review_decision="edit",
        draft_return={},
    )
    result = _finalize(state)
    assert not result["worksheet"]
    assert "error" in result


# ── AgentService basic construction test ──────────────────────────────────────


def test_agent_service_constructs():
    ledger_svc, tax_svc = _make_services()
    svc = AgentService(ledger_svc, tax_svc)
    # Agents are lazily built — just verify construction doesn't crash
    assert svc._agents == {}
    assert svc._workflow is None


def test_agent_service_lazy_agent_build():
    """_get_agent() should build the agent on first call without crashing."""
    import os

    # If no ANTHROPIC_API_KEY is set, ChatAnthropic construction may fail.
    # We check the env and skip if not available.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set — skipping live agent build")

    ledger_svc, tax_svc = _make_services()
    svc = AgentService(ledger_svc, tax_svc)
    agent = svc._get_agent()
    assert agent is not None
