"""
An account's tax role must be one the user's own tax rule sets declare.

Salli has no roles of its own: a rule set's `roles` are what its accounts may
carry. LedgerService checks it where a role is set: on a new account, and on an
edit that changes it. An edit that keeps the role an account has never fails on
it, so an account whose role no rule set in use declares any more (its version
was superseded) can still be renamed; validating a rule set warns about it
instead (tests/integration/test_tax_rule_service.py).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from salli.application.services.ledger_service import LedgerService, UnknownTaxRoleError
from salli.domain.accounting.models import Account

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
        return {"id": user_id, "base_currency": "EUR", "tax_residency": self.residency}

    async def base_currency(self, user_id: str) -> str:
        return "EUR"


class _RuleSets:
    def __init__(self, roles: set[str]) -> None:
        self.roles = roles

    async def declared_roles(self, user_id: str) -> set[str]:
        return set(self.roles) if user_id == USER else set()


def _service(
    own_roles: set[str] | None = None, residency: str | None = "GB"
) -> tuple[LedgerService, _Ledger, _RuleSets]:
    ledger, rule_sets = _Ledger(), _RuleSets(own_roles or set())

    class _UoW:
        pass

    uow = _UoW()
    uow.ledger = ledger  # type: ignore[attr-defined]
    uow.user_profiles = _Profiles(residency)  # type: ignore[attr-defined]
    uow.tax_rule_sets = rule_sets  # type: ignore[attr-defined]

    @asynccontextmanager
    async def factory():
        yield uow

    return LedgerService(factory), ledger, rule_sets


async def test_a_role_the_users_rule_sets_declare_is_allowed_wherever_they_live():
    for residency in ("GB", None):
        svc, ledger, _ = _service({"paye_withheld", "salary"}, residency)
        account_id = await svc.add_account(USER, "1450", "PAYE", "asset", tax_role="paye_withheld")
        assert ledger.accounts[account_id].tax_role == "paye_withheld"
        assert await svc.allowed_tax_roles(USER) == ("paye_withheld", "salary")


async def test_any_other_role_is_refused_saying_which_there_are():
    svc, ledger, _ = _service({"salary"})
    with pytest.raises(UnknownTaxRoleError, match=r"'apit_credit' .* \(salary\)"):
        await svc.add_account(USER, "4110", "Withheld", "asset", tax_role="apit_credit")
    assert ledger.accounts == {}


async def test_with_no_rule_sets_there_are_no_roles_at_all():
    """Salli has none of its own: what used to be built in is gone."""
    svc, _, _ = _service(set())
    assert await svc.allowed_tax_roles(USER) == ()
    for role in ("apit_credit", "fsi_income", "qualifying_payment"):
        with pytest.raises(UnknownTaxRoleError, match="none of your tax rule sets declares any"):
            await svc.add_account(USER, "1", "x", "asset", tax_role=role)


async def test_an_account_without_a_role_needs_no_rule_set():
    svc, ledger, _ = _service(set())
    account_id = await svc.add_account(USER, "1100", "Cash", "asset")
    assert ledger.accounts[account_id].tax_role is None


async def test_an_edit_that_keeps_the_role_never_fails_on_it():
    svc, ledger, rule_sets = _service({"salary", "withheld"})
    account_id = await svc.add_account(USER, "1450", "Withheld", "asset", tax_role="withheld")

    rule_sets.roles = {"salary"}  # the version declaring it was superseded
    await svc.update_account(
        USER, account_id, "1450", "Withheld (old job)", "asset", tax_role="withheld"
    )
    assert ledger.accounts[account_id].name == "Withheld (old job)"

    with pytest.raises(UnknownTaxRoleError):
        await svc.update_account(USER, account_id, "1450", "Withheld", "asset", tax_role="other")
