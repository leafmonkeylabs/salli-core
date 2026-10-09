"""
Whose tax pack, which year.

A user's tax is computed with their country's pack: their tax residency, or,
while they have not set one, the one country whose packs compute in their base
currency (a rupee ledger keeps being Sri Lanka's, as it always was). With no
year named, the latest year Salli can compute for them.
"""

from __future__ import annotations

import datetime
import uuid
from contextlib import asynccontextmanager
from typing import Any

import pytest

from salli.application.services.reminder_service import ReminderService
from salli.application.services.tax_service import (
    NoTaxPackError,
    TaxService,
    jurisdiction_of,
)
from salli.domain.agents.return_workflow import ReturnState, _gather
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from tests.fakes import FakeProfiles

USER = "u1"


def test_whose_packs_compute_a_users_tax():
    lk = jurisdiction_of({"base_currency": "USD", "tax_residency": "LK"})
    assert (lk.country, lk.source) == ("LK", "tax_residency")
    # No residency: the one country whose packs compute in the base currency.
    rupees = jurisdiction_of({"base_currency": "LKR", "tax_residency": None})
    assert (rupees.country, rupees.source) == ("LK", "base_currency")
    # Otherwise nobody: no country is assumed.
    dollars = jurisdiction_of({"base_currency": "USD"})
    assert (dollars.country, dollars.source) == (None, None)
    # A residency always wins, a pack for it or not.
    us = jurisdiction_of({"base_currency": "LKR", "tax_residency": "US"})
    assert (us.country, us.source) == ("US", "tax_residency")
    assert jurisdiction_of(None).country is None


class _Computations:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], Any] = {}

    async def save(self, user_id, computation) -> str:
        self.rows[(user_id, computation.pack_year)] = computation
        return str(uuid.uuid4())

    async def get_latest(self, user_id, year):
        return self.rows.get((user_id, year))

    async def list_computation_keys(self):
        return list(self.rows)


class _Ledger:
    async def get_entries(self, user_id, from_date=None, to_date=None):
        return []

    async def get_accounts(self, user_id, include_inactive=False):
        return []


def _service(base: str = "LKR", residency: str | None = None):
    profiles = FakeProfiles(base)
    if residency:
        profiles.rows[USER] = {"tax_residency": residency}
    computations = _Computations()

    class _UoW:
        user_profiles = profiles
        tax_computations = computations
        ledger = _Ledger()
        reminders: Any = None

    uow = _UoW()

    @asynccontextmanager
    async def factory():
        yield uow

    return TaxService(factory), profiles, computations, uow, factory


async def test_with_no_year_the_latest_year_salli_can_compute():
    svc, *_ = _service()
    assert await svc.pack(USER) is LK_2025_26
    assert await svc.default_year(USER) == "2025/26"
    result = await svc.compute_tax(USER)
    assert (result.pack_country, result.pack_year) == ("LK", "2025/26")


async def test_a_named_year_salli_has_no_pack_for_is_not_found():
    svc, *_ = _service()
    with pytest.raises(KeyError):
        await svc.compute_tax(USER, "2026/27")


async def test_a_country_without_a_pack_says_so():
    svc, *_ = _service(residency="US")
    with pytest.raises(NoTaxPackError, match="no tax pack for the United States"):
        await svc.compute_tax(USER)


async def test_no_country_means_no_computation_and_nothing_stored():
    svc, *_ = _service(base="EUR")
    with pytest.raises(NoTaxPackError, match="doesn't know where you are taxed"):
        await svc.pack(USER)
    assert await svc.get_latest_computation(USER) is None


async def test_the_current_tax_year_is_the_users_countrys():
    svc, *_ = _service(residency="LK")
    where, current = await svc.current_tax_year(USER, datetime.date(2026, 10, 9))
    assert (where.country, where.source) == ("LK", "tax_residency")
    assert current is not None
    assert (current.year.label, current.pack, current.latest) == ("2026/27", None, LK_2025_26)


async def test_a_stored_computation_is_redone_with_the_country_it_was_made_for():
    """A user who has since moved still has their Sri Lankan years recomputed
    with Sri Lanka's pack, not refused for having no GB pack."""
    svc, profiles, computations, *_ = _service(residency="LK")
    await svc.compute_tax(USER)
    profiles.rows[USER] = {"tax_residency": "GB"}

    [row] = await svc.recompute_stored(apply=False)

    assert "error" not in row
    assert row["year"] == "2025/26"


# ── The filing calendar is the user's pack's ─────────────────────────────────


class _Reminders:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str]] = []

    async def list_reminders(self, user_id, status=None):
        return [{"kind": kind} for kind, _ in self.rows]

    async def create_reminder(self, user_id, reminder_id, kind, due_date):
        self.rows.append((kind, due_date))


async def test_the_filing_calendar_is_seeded_from_the_users_pack():
    svc, _, _, uow, factory = _service()
    uow.reminders = _Reminders()

    created = await ReminderService(factory, tax_svc=svc).seed_filing_calendar(USER)

    assert len(created) == 5
    # The dates Sri Lankans always got for 2025/26.
    assert sorted(uow.reminders.rows) == [
        ("installment_1_2025/26", "2025-08-15"),
        ("installment_2_2025/26", "2025-11-15"),
        ("installment_3_2025/26", "2026-02-15"),
        ("installment_4_2025/26", "2025-05-15"),
        ("return_due_2025/26", "2026-11-30"),
    ]
    # Seeding again adds nothing.
    assert await ReminderService(factory, tax_svc=svc).seed_filing_calendar(USER) == []


# ── The return workflow prepares the user's year ─────────────────────────────


class _LedgerService:
    async def list_accounts(self, user_id):
        return []

    async def get_entries(self, user_id, from_date=None, to_date=None):
        return []


async def test_the_return_is_prepared_for_the_latest_year_by_default():
    svc, *_ = _service()
    state = await _gather(ReturnState(user_id=USER), _LedgerService(), svc)
    assert state.get("year") == "2025/26"
    assert "error" not in state


async def test_no_worksheet_without_a_mapped_return_form():
    svc, *_ = _service(residency="US")
    state = await _gather(ReturnState(user_id=USER), _LedgerService(), svc)
    assert "no tax pack for the United States" in state["error"]
