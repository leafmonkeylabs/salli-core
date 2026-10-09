"""
An account's tax role must be one its owner's tax packs declare.

LedgerService checks it where a role is set: on a new account, and on an edit
that changes it. An edit that keeps the role it has never fails on it, so a
user who moves country can still rename their old accounts.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.ledger_service import LedgerService, UnknownTaxRoleError
from salli.application.services.tax_service import _build_ledger_view
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26

USER = "u1"


class _Ledger:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}

    async def save_account(self, user_id: str, account: Account) -> str:
        self.accounts[account.id] = account
        return account.id

    async def get_account(self, user_id: str, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    async def get_entries(self, user_id: str, from_date=None, to_date=None) -> list[Any]:
        return []

    async def update_account(self, user_id: str, account_id: str, **fields: Any) -> None:
        self.accounts[account_id] = self.accounts[account_id].model_copy(update=fields)


class _Profiles:
    def __init__(self, residency: str | None) -> None:
        self.residency = residency

    async def get(self, user_id: str) -> dict[str, Any]:
        return {"id": user_id, "base_currency": "LKR", "tax_residency": self.residency}

    async def base_currency(self, user_id: str) -> str:
        return "LKR"


def _service(residency: str | None) -> tuple[LedgerService, _Ledger, _Profiles]:
    ledger, profiles = _Ledger(), _Profiles(residency)

    class _UoW:
        pass

    uow = _UoW()
    uow.ledger = ledger  # type: ignore[attr-defined]
    uow.user_profiles = profiles  # type: ignore[attr-defined]

    @asynccontextmanager
    async def factory():
        yield uow

    return LedgerService(factory), ledger, profiles


async def test_a_sri_lankan_resident_may_use_sri_lankan_roles():
    svc, ledger, _ = _service("LK")
    for role in ("apit_credit", "ait_credit", "foreign_tax_credit", "qualifying_payment"):
        account_id = await svc.add_account(USER, role, role, "asset", tax_role=role)
        assert ledger.accounts[account_id].tax_role == role


async def test_a_role_another_country_or_no_pack_declares_is_refused():
    svc, ledger, _ = _service("GB")
    with pytest.raises(UnknownTaxRoleError, match="no tax pack for the United Kingdom"):
        await svc.add_account(USER, "4110", "APIT Receivable", "asset", tax_role="apit_credit")
    assert ledger.accounts == {}

    svc, _, _ = _service("LK")
    with pytest.raises(UnknownTaxRoleError, match="tax packs for Sri Lanka"):
        await svc.add_account(USER, "1", "x", "asset", tax_role="paye_credit")


async def test_with_no_residency_any_pack_s_role_will_do():
    """The roles such a user could always use; no country is assumed for them."""
    svc, _, _ = _service(None)
    await svc.add_account(USER, "4110", "APIT Receivable", "asset", tax_role="apit_credit")
    with pytest.raises(UnknownTaxRoleError, match="any tax pack"):
        await svc.add_account(USER, "1", "x", "asset", tax_role="paye_credit")
    assert await svc.allowed_tax_roles(USER) == LK_2025_26.tax_roles


async def test_an_account_without_a_role_needs_no_pack():
    svc, ledger, _ = _service("US")
    account_id = await svc.add_account(USER, "1100", "Cash", "asset")
    assert ledger.accounts[account_id].tax_role is None


async def test_an_edit_that_keeps_the_role_never_fails_on_it():
    svc, ledger, profiles = _service("LK")
    account_id = await svc.add_account(USER, "4110", "APIT", "asset", tax_role="apit_credit")

    profiles.residency = "GB"  # they moved
    await svc.update_account(
        USER, account_id, "4110", "APIT Receivable (old job)", "asset", tax_role="apit_credit"
    )
    assert ledger.accounts[account_id].name == "APIT Receivable (old job)"

    with pytest.raises(UnknownTaxRoleError):
        await svc.update_account(
            USER, account_id, "4110", "APIT", "asset", tax_role="foreign_tax_credit"
        )


# ── The engine reads only the roles the computing pack declares ──────────────


def _entry(debit: str, credit: str, amount: str) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=str(uuid.uuid4()),
        user_id=USER,
        entry_date="2025-06-01",
        description="",
        source="manual",
        postings=[
            Posting(
                account_id=debit,
                direction=Direction.DEBIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
            Posting(
                account_id=credit,
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
        ],
    )


def test_a_role_the_pack_does_not_declare_is_not_credited():
    from dataclasses import replace

    salary = Account(id="s", user_id=USER, code="4100", name="S", type="income", currency="LKR")
    apit = Account(
        id="a",
        user_id=USER,
        code="4110",
        name="A",
        type="asset",
        currency="LKR",
        tax_role="apit_credit",
    )
    entries = [_entry("bank", "s", "3000000"), _entry("a", "clearing", "100000")]

    assert _build_ledger_view(entries, [salary, apit], LK_2025_26).apit_withheld == Decimal(
        "100000"
    )
    without_apit = replace(LK_2025_26, withholding_kinds=LK_2025_26.withholding_kinds[1:])
    assert _build_ledger_view(entries, [salary, apit], without_apit).apit_withheld == 0
    # With no pack to ask, every role the engine knows counts, as before.
    assert _build_ledger_view(entries, [salary, apit]).apit_withheld == Decimal("100000")
