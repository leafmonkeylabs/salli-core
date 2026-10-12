"""
A holding's account in a real database: core_0020, the foreign key that keeps
it pointing at an account, and the checks that keep each user's link to their
own investment accounts (decision lab 3b, decision 17).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from salli.application.ports import AccountNotFound
from salli.application.services.ledger_service import LedgerService
from salli.application.services.portfolio_service import PortfolioService
from salli.migrations.support import CORE_SCRIPT_LOCATION, alembic_config, upgrade
from tests.integration.pg import _sync, requires_postgres, scalar, scratch_database

pytestmark = requires_postgres

_BEFORE = "core_0019_notifications"


def _execute(url: str, *statements: str) -> None:
    engine = create_engine(_sync(url))
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
    engine.dispose()


def _column(url: str) -> int:
    return scalar(
        url,
        "select count(*) from information_schema.columns"
        " where table_name = 'holdings' and column_name = 'account_id'",
    )


_HOLDING = (
    "insert into holdings (id, user_id, symbol, name, asset_class, currency, cost_basis_minor,"
    " current_value_minor, is_active, created_at, updated_at)"
    " values ('h', 'u', 'FND', 'Fund', 'equity', 'ZAR', 0, 0, true, now(), now())"
)


def test_core_0020_adds_the_link_unset_and_reverses(monkeypatch):
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION, _BEFORE)
        _execute(url, _HOLDING)
        assert _column(url) == 0
        upgrade(CORE_SCRIPT_LOCATION)
        assert _column(url) == 1
        # Existing holdings are linked to nothing: a person links them.
        assert scalar(url, "select account_id from holdings where id = 'h'") is None

        command.downgrade(alembic_config(CORE_SCRIPT_LOCATION), _BEFORE)
        assert _column(url) == 0
        upgrade(CORE_SCRIPT_LOCATION)
        assert _column(url) == 1


def test_a_link_points_at_an_account_that_exists(db):
    _execute(db, _HOLDING)
    with pytest.raises(Exception, match="holdings_account_id_fkey"):
        _execute(db, "update holdings set account_id = 'gone' where id = 'h'")


@pytest.fixture
async def books(uow_factory) -> SimpleNamespace:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("thandi", {"base_currency": "ZAR"})
        await uow.user_profiles.upsert("arjun", {"base_currency": "INR"})
    ledger = LedgerService(uow_factory)
    portfolio = PortfolioService(uow_factory)
    return SimpleNamespace(
        portfolio=portfolio,
        brokerage=await ledger.add_account(
            "thandi", "1300", "Brokerage", "asset", asset_role="investment"
        ),
        bank=await ledger.add_account("thandi", "1000", "Bank", "asset"),
        arjuns=await ledger.add_account("arjun", "1300", "Demat", "asset", asset_role="investment"),
        holding=await portfolio.add_holding(
            "thandi", {"symbol": "FND", "name": "My fund", "asset_class": "equity"}
        ),
    )


async def test_a_holding_links_to_its_owners_investment_account(books):
    svc = books.portfolio
    await svc.update_holding("thandi", books.holding, {"account_id": books.brokerage})
    assert (await svc.get_holding("thandi", books.holding) or {})["account_id"] == books.brokerage

    # Another change keeps it; null unlinks it.
    await svc.update_holding("thandi", books.holding, {"name": "Fund"})
    assert (await svc.get_holding("thandi", books.holding) or {})["account_id"] == books.brokerage
    await svc.update_holding("thandi", books.holding, {"account_id": None})
    assert (await svc.get_holding("thandi", books.holding) or {})["account_id"] is None


async def test_a_holding_never_links_to_someone_elses_or_a_cash_account(books):
    svc = books.portfolio
    with pytest.raises(AccountNotFound):
        await svc.update_holding("thandi", books.holding, {"account_id": books.arjuns})
    with pytest.raises(ValueError, match="role cash"):
        await svc.update_holding("thandi", books.holding, {"account_id": books.bank})
    assert (await svc.get_holding("thandi", books.holding) or {})["account_id"] is None
