"""
Investments in a real database: transactions keep their quantities, prices and
rates exactly, go with their holding, and existing holdings come through the
migration in their owner's base currency.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from salli.application.services.portfolio_service import PortfolioService
from salli.migrations.support import CORE_SCRIPT_LOCATION, upgrade
from tests.integration.pg import _sync, requires_postgres, scalar, scratch_database

pytestmark = requires_postgres

USER = "investor"


async def _profile(uow_factory, base: str, user: str = USER) -> None:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(user, {"base_currency": base})


async def _holding(svc: PortfolioService, currency: str | None = None) -> str:
    return await svc.add_holding(
        USER, {"symbol": "ETH", "name": "Ether", "asset_class": "crypto", "currency": currency}
    )


async def test_a_transaction_keeps_its_numbers_exactly(uow_factory):
    await _profile(uow_factory, "LKR")
    svc = PortfolioService(uow_factory)
    holding = await _holding(svc, "USD")
    buy = await svc.add_transaction(
        USER,
        holding,
        {
            "kind": "buy",
            "date": "2026-01-05",
            # A wei more than 0.123456789012345678 ether would not fit; this does.
            "quantity": "0.123456789012345678",
            "price": "2512.000000000000000001",
            "fees": "1.25",
            "fx_rate": "0.000000000000000001",
        },
    )
    assert buy is not None
    sale = await svc.add_transaction(
        USER,
        holding,
        {
            "kind": "sell",
            "date": "2026-02-05",
            "quantity": "0.1",
            "price": "3000",
            "fx_rate": "300.5",
            "lots": [{"lot_id": buy, "quantity": "0.1"}],
        },
    )

    [first, second] = await svc.list_transactions(USER, holding) or []
    assert (first["quantity"], first["price"], first["fx_rate"], first["fees"]) == (
        "0.123456789012345678",
        "2512.000000000000000001",
        "0.000000000000000001",
        "1.25",
    )
    assert (second["id"], second["lots"]) == (sale, [{"lot_id": buy, "quantity": "0.1"}])
    lots = await svc.get_lots(USER, holding)
    assert lots is not None and lots["quantity"] == "0.023456789012345678"

    async with uow_factory() as uow:
        [row, _] = await uow.holding_transactions.list(USER, holding)
    assert row["quantity"] == Decimal("0.123456789012345678")
    assert isinstance(row["quantity"], Decimal) and isinstance(row["fx_rate"], Decimal)


async def test_a_holdings_transactions_go_with_it(uow_factory):
    await _profile(uow_factory, "USD")
    svc = PortfolioService(uow_factory)
    holding = await _holding(svc)
    await svc.add_transaction(
        USER, holding, {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1"}
    )
    await svc.delete_holding(USER, holding)
    async with uow_factory() as uow:
        assert await uow.holding_transactions.list(USER) == []


async def test_deleting_an_account_deletes_its_transactions(uow_factory):
    await _profile(uow_factory, "USD")
    svc = PortfolioService(uow_factory)
    holding = await _holding(svc)
    await svc.add_transaction(
        USER, holding, {"kind": "split", "date": "2026-01-05", "ratio": "2:1"}
    )
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all(USER)
    assert counts["holding_transactions"] == 1
    async with uow_factory() as uow:
        assert await uow.holding_transactions.list(USER) == []


async def test_the_database_refuses_a_transaction_missing_what_its_kind_needs(db, uow_factory):
    await _profile(uow_factory, "USD")
    holding = await _holding(PortfolioService(uow_factory))
    engine = create_engine(_sync(db))
    with pytest.raises(Exception, match="ck_holding_transactions_fields"), engine.begin() as conn:
        conn.execute(
            text(
                "insert into holding_transactions (id, user_id, holding_id, kind,"
                " transaction_date, quantity, fees_minor, withholding_tax_minor, lots, fx_rate,"
                " created_at, updated_at) values ('t', :u, :h, 'buy', '2026-01-05', 1, 0, 0,"
                " '[]', 1, now(), now())"
            ),
            {"u": USER, "h": holding},
        )
    engine.dispose()


def test_existing_holdings_are_in_their_owners_base_currency(monkeypatch):
    """Upgrading a database with holdings in it: each gets its owner's base
    currency, which their declared figures were always in."""
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION, "core_0008_jurisdiction")
        engine = create_engine(_sync(url))
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into user_profiles (id, base_currency, mcp_enabled,"
                    " daily_briefing_enabled, created_at, updated_at)"
                    " values ('euro', 'EUR', false, false, now(), now())"
                )
            )
            for holding, owner in (("h1", "euro"), ("h2", "orphan")):
                conn.execute(
                    text(
                        "insert into holdings (id, user_id, symbol, name, asset_class,"
                        " cost_basis_minor, current_value_minor, is_active, created_at,"
                        " updated_at) values (:id, :owner, 'VOO', 'S&P 500', 'equity',"
                        " 100000, 125000, true, now(), now())"
                    ),
                    {"id": holding, "owner": owner},
                )
        engine.dispose()

        upgrade(CORE_SCRIPT_LOCATION)

        assert scalar(url, "select currency from holdings where id = 'h1'") == "EUR"
        assert scalar(url, "select currency from holdings where id = 'h2'") == "LKR"
        assert scalar(url, "select current_value_minor from holdings where id = 'h1'") == 125000
        assert scalar(url, "select count(*) from holding_transactions") == 0


async def test_a_days_price_is_kept_once_and_exactly(uow_factory):
    await _profile(uow_factory, "USD")
    svc = PortfolioService(uow_factory)
    await _holding(svc, "USD")
    first = await svc.set_price(
        USER, {"symbol": "eth", "close": "2512.000000000000000001", "date": "2026-10-01"}
    )
    second = await svc.set_price(USER, {"symbol": "ETH", "close": "2600", "date": "2026-10-01"})
    await svc.set_price(USER, {"symbol": "ETH", "close": "2700", "date": "2026-10-02"})
    assert first == second
    assert [(p["date"], p["close"]) for p in await svc.list_prices(USER, "ETH")] == [
        ("2026-10-02", "2700"),
        ("2026-10-01", "2600"),
    ]
    assert [p["close"] for p in await svc.list_prices(USER, "ETH", end="2026-10-01")] == ["2600"]
    await svc.set_price(
        USER, {"symbol": "ETH", "close": "0.000000000000000001", "date": "2026-10-03"}
    )
    assert (await svc.list_prices(USER, "ETH"))[0]["close"] == "0.000000000000000001"

    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all(USER)
    assert counts["holding_prices"] == 3


async def test_another_users_prices_are_theirs(uow_factory):
    await _profile(uow_factory, "USD")
    await _profile(uow_factory, "USD", user="neighbour")
    svc = PortfolioService(uow_factory)
    price = await svc.set_price(USER, {"symbol": "ETH", "close": "1", "currency": "USD"})
    assert await svc.list_prices("neighbour") == []
    assert await svc.delete_price("neighbour", price) is False
    assert await svc.delete_price(USER, price) is True


@pytest.fixture
def upgraded_with_a_holding(monkeypatch):
    """A database with a holding declared before investments existed, then
    upgraded: synchronous, because migrations run their own event loop."""
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION, "core_0004_categorization_rules")
        engine = create_engine(_sync(url))
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into user_profiles (id, base_currency, mcp_enabled,"
                    " daily_briefing_enabled, created_at, updated_at)"
                    " values (:u, 'EUR', false, false, now(), now())"
                ),
                {"u": USER},
            )
            conn.execute(
                text(
                    "insert into holdings (id, user_id, symbol, name, asset_class,"
                    " cost_basis_minor, current_value_minor, is_active, created_at,"
                    " updated_at) values ('h1', :u, 'VWCE', 'All-World', 'equity',"
                    " 100000, 125050, true, now(), now())"
                ),
                {"u": USER},
            )
        engine.dispose()
        upgrade(CORE_SCRIPT_LOCATION)
        yield url


async def test_a_holding_from_before_reads_as_it_did(upgraded_with_a_holding):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from salli.application.unit_of_work import UnitOfWork

    engine = create_async_engine(upgraded_with_a_holding, connect_args={"statement_cache_size": 0})
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    svc = PortfolioService(lambda: UnitOfWork(sessions))
    try:
        holding = await svc.get_holding(USER, "h1")
        summary = await svc.get_summary(USER)
    finally:
        await engine.dispose()
    assert holding is not None
    assert (holding["currency"], holding["cost_basis"], holding["current_value"]) == (
        "EUR",
        "1000.00",
        "1250.50",
    )
    assert (holding["tracking"], holding["native"]["currency"]) == ("declared", "EUR")
    assert (summary["total_value"], summary["total_gain"]) == ("1250.50", "250.50")
