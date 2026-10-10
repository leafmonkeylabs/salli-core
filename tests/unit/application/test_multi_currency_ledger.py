"""
A ledger kept in any currency, with accounts held in others.

Covers the rules every way into the ledger follows: amounts in the owner's base
currency are at par; amounts in another currency carry the rate the bank used
or the published one, and are refused when there is neither; the base currency
cannot change once anything is stored in it; and a tax pack only computes for a
ledger kept in its own currency.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.ports import FxQuote, FxRatePort, FxUnavailableError
from salli.application.services.ledger_service import LedgerService
from salli.application.services.tax_service import TaxPackCurrencyError, TaxService
from salli.application.services.user_profile_service import (
    BaseCurrencyLockedError,
    UserProfileService,
)
from salli.domain.accounting.models import Account, Direction
from salli.domain.currency import UnknownCurrencyError
from tests.fakes import FakeProfiles
from tests.unit.application.test_ledger_service import FakeLedgerRepo, FakeTaxComputationRepo

USER = "u1"


class Ledger(FakeLedgerRepo):
    async def get_account(self, user_id: str, account_id: str) -> Account | None:
        account = self._accounts.get(account_id)
        return account if account and account.user_id == user_id else None

    async def update_account(self, user_id: str, account_id: str, **fields) -> None:
        current = self._accounts[account_id]
        self._accounts[account_id] = current.model_copy(update=fields)


class Rates(FxRatePort):
    def __init__(self, table: dict[tuple[str, str], str]) -> None:
        self.table = table
        self.asked: list[tuple[str, str, str]] = []

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        self.asked.append((from_currency, to_currency, on_date))
        if (from_currency, to_currency) not in self.table:
            raise FxUnavailableError(f"No {from_currency}→{to_currency} rate")
        return FxQuote(
            rate=Decimal(self.table[from_currency, to_currency]), source="ecb", as_of=on_date
        )


def _setup(base: str = "EUR", rates: dict[tuple[str, str], str] | None = None):
    repo = Ledger()
    profiles = FakeProfiles(base)

    class UoW:
        def __init__(self) -> None:
            self.ledger = repo
            self.tax_computations = FakeTaxComputationRepo()
            self.user_profiles = profiles

    @asynccontextmanager
    async def uow_factory():
        yield UoW()

    fx = Rates(rates or {})
    return LedgerService(uow_factory, fx=fx), repo, fx, profiles, uow_factory


def _leg(account_id: str, direction: Direction, amount: str, **extra) -> dict:
    return {"account_id": account_id, "direction": direction, "amount": Decimal(amount), **extra}


@pytest.mark.asyncio
async def test_accounts_open_in_the_base_currency_unless_another_is_named():
    svc, repo, *_ = _setup("EUR")
    cash = await svc.add_account(USER, "1000", "Cash", "asset")
    usd = await svc.add_account(USER, "1100", "Dollar account", "asset", currency="usd")
    assert repo._accounts[cash].currency == "EUR"
    assert repo._accounts[usd].currency == "USD"
    with pytest.raises(UnknownCurrencyError):
        await svc.add_account(USER, "1200", "Bad", "asset", currency="XYZ")


@pytest.mark.asyncio
async def test_amounts_without_a_currency_are_in_the_base_currency_at_par():
    svc, repo, fx, *_ = _setup("EUR")
    await svc.add_entry(
        USER,
        "2026-10-01",
        "Lunch",
        "manual",
        [_leg("food", Direction.DEBIT, "12.5"), _leg("cash", Direction.CREDIT, "12.5")],
    )
    [entry] = repo._entries
    assert {(p.currency, p.fx_rate, p.fx_rate_source) for p in entry.postings} == {
        ("EUR", Decimal(1), None)
    }
    assert fx.asked == []


@pytest.mark.asyncio
async def test_a_foreign_amount_gets_the_published_rate_for_the_entrys_date():
    svc, repo, fx, *_ = _setup("EUR", {("USD", "EUR"): "0.89397"})
    await svc.add_entry(
        USER,
        "2026-10-02",
        "Invoice paid",
        "manual",
        [
            _leg("usd-bank", Direction.DEBIT, "1000", currency="USD"),
            _leg("income", Direction.CREDIT, "1000", currency="USD"),
        ],
    )
    [entry] = repo._entries
    assert {(p.fx_rate, p.fx_rate_source) for p in entry.postings} == {(Decimal("0.89397"), "ecb")}
    assert fx.asked[0] == ("USD", "EUR", "2026-10-02")
    assert sum(p.base_signed for p in entry.postings) == 0


@pytest.mark.asyncio
async def test_the_rate_the_bank_used_wins_over_the_published_one():
    svc, repo, fx, *_ = _setup("EUR", {("USD", "EUR"): "0.89397"})
    await svc.add_entry(
        USER,
        "2026-10-02",
        "Card payment abroad",
        "manual",
        [
            _leg("travel", Direction.DEBIT, "80", currency="USD", fx_rate=Decimal("0.9123")),
            _leg("card", Direction.CREDIT, "80", currency="USD", fx_rate=Decimal("0.9123")),
        ],
    )
    [entry] = repo._entries
    assert {(p.fx_rate, p.fx_rate_source) for p in entry.postings} == {(Decimal("0.9123"), "user")}
    assert fx.asked == []


@pytest.mark.asyncio
async def test_no_rate_means_no_entry_rather_than_one_at_par():
    svc, repo, *_ = _setup("EUR", {})
    with pytest.raises(FxUnavailableError):
        await svc.add_entry(
            USER,
            "2026-10-02",
            "Rupee transfer",
            "manual",
            [
                _leg("lkr-bank", Direction.DEBIT, "50000", currency="LKR"),
                _leg("income", Direction.CREDIT, "50000", currency="LKR"),
            ],
        )
    assert repo._entries == []


@pytest.mark.asyncio
async def test_a_base_amount_cannot_carry_an_exchange_rate():
    svc, *_ = _setup("EUR")
    with pytest.raises(ValueError, match="rate of 1"):
        await svc.add_entry(
            USER,
            "2026-10-02",
            "x",
            "manual",
            [
                _leg("a", Direction.DEBIT, "10", currency="EUR", fx_rate=Decimal("1.1")),
                _leg("b", Direction.CREDIT, "10", currency="EUR", fx_rate=Decimal("1.1")),
            ],
        )


@pytest.mark.asyncio
async def test_a_foreign_account_shows_its_own_balance_and_its_book_value():
    svc, repo, *_ = _setup("EUR", {("USD", "EUR"): "0.9"})
    usd = await svc.add_account(USER, "1100", "Dollar account", "asset", currency="USD")
    income = await svc.add_account(USER, "4000", "Income", "income")
    for day, amount in (("2026-10-01", "1000"), ("2026-10-02", "500")):
        await svc.add_entry(
            USER,
            day,
            "Paid",
            "manual",
            [
                _leg(usd, Direction.DEBIT, amount, currency="USD"),
                _leg(income, Direction.CREDIT, amount, currency="USD"),
            ],
        )
    overview = await svc.get_account_overview(USER, usd)
    assert overview["account"]["currency"] == "USD"
    assert overview["balance"] == "1500.00"  # what the bank shows
    assert overview["base_currency"] == "EUR"
    assert overview["current_balance"] == "1350.00"  # its value in the ledger
    assert [t["running_balance_native"] for t in overview["transactions"]] == ["1000.00", "1500.00"]


@pytest.mark.asyncio
async def test_a_yen_ledger_has_no_decimals_anywhere():
    svc, *_ = _setup("JPY")
    cash = await svc.add_account(USER, "1000", "Cash", "asset")
    food = await svc.add_account(USER, "5000", "Food", "expense")
    await svc.add_entry(
        USER,
        "2026-10-01",
        "Ramen",
        "manual",
        [_leg(food, Direction.DEBIT, "1200"), _leg(cash, Direction.CREDIT, "1200")],
    )
    overview = await svc.get_account_overview(USER, food)
    assert overview["current_balance"] == "1200"
    assert overview["balance"] == "1200"


@pytest.mark.asyncio
async def test_an_accounts_currency_only_changes_while_it_has_no_entries():
    svc, repo, *_ = _setup("EUR", {("USD", "EUR"): "0.9"})
    usd = await svc.add_account(USER, "1100", "Dollar account", "asset", currency="USD")
    other = await svc.add_account(USER, "1200", "Spare", "asset")
    income = await svc.add_account(USER, "4000", "Income", "income")
    await svc.update_account(USER, other, "1200", "Spare", "asset", currency="GBP")
    assert repo._accounts[other].currency == "GBP"
    await svc.add_entry(
        USER,
        "2026-10-01",
        "Paid",
        "manual",
        [
            _leg(usd, Direction.DEBIT, "10", currency="USD"),
            _leg(income, Direction.CREDIT, "10", currency="USD"),
        ],
    )
    with pytest.raises(ValueError, match="can't change"):
        await svc.update_account(USER, usd, "1100", "Dollar account", "asset", currency="EUR")
    # Leaving the currency out keeps it.
    await svc.update_account(USER, usd, "1100", "Renamed", "asset")
    assert (repo._accounts[usd].name, repo._accounts[usd].currency) == ("Renamed", "USD")


# ── the base currency itself ──────────────────────────────────────────────────


def _profile_service(profiles: FakeProfiles, uow_factory, default: str = "USD"):
    from unittest.mock import MagicMock

    return UserProfileService(
        uow_factory,
        ledger_service=MagicMock(),
        fi_service=MagicMock(),
        document_service=MagicMock(),
        default_currency=default,
    )


class _ProfileRepo(FakeProfiles):
    """Starts with no rows, like a fresh instance."""

    async def get(self, user_id: str):
        return self.rows.get(user_id)

    async def base_currency(self, user_id: str) -> str:
        return self.rows[user_id]["base_currency"]


def _profiles_uow(profiles: FakeProfiles):
    class UoW:
        user_profiles = profiles

    @asynccontextmanager
    async def uow_factory():
        yield UoW()

    return uow_factory


@pytest.mark.asyncio
async def test_a_new_profile_gets_the_named_currency_or_the_instances_default():
    profiles = _ProfileRepo()
    svc = _profile_service(profiles, _profiles_uow(profiles), default="SGD")
    await svc.ensure_user("a", "a@example.com", may_create=True)
    await svc.ensure_user("b", "b@example.com", may_create=True, base_currency="jpy")
    assert profiles.rows["a"]["base_currency"] == "SGD"
    assert profiles.rows["b"]["base_currency"] == "JPY"


@pytest.mark.asyncio
async def test_the_base_currency_changes_freely_until_something_is_stored_in_it():
    profiles = _ProfileRepo()
    svc = _profile_service(profiles, _profiles_uow(profiles))
    await svc.ensure_user(USER, None, may_create=True)
    assert await svc.set_base_currency(USER, "eur") == "EUR"

    profiles.has_data = True
    assert await svc.set_base_currency(USER, "EUR") == "EUR"  # no change is always fine
    with pytest.raises(BaseCurrencyLockedError, match="kept in EUR"):
        await svc.set_base_currency(USER, "GBP")
    assert profiles.rows[USER]["base_currency"] == "EUR"


@pytest.mark.asyncio
async def test_a_tax_pack_only_computes_for_a_ledger_in_its_own_currency():
    *_, uow_factory = _setup("EUR")
    with pytest.raises(
        TaxPackCurrencyError, match="computes in LKR, but this ledger is kept in EUR"
    ):
        await TaxService(uow_factory).compute_tax(USER, "2025/26")
