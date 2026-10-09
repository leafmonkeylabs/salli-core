"""
Money in a real database: every currency stored at its own scale, the base
currency recorded per user, and existing users kept on what their data was.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from salli.domain.accounting.models import Account, Direction, JournalEntry, Posting
from salli.migrations.support import CORE_SCRIPT_LOCATION, upgrade
from tests.integration.pg import _sync, requires_postgres, scalar, scratch_database

pytestmark = requires_postgres


async def _user(uow_factory, user_id: str, base: str) -> None:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(user_id, {"base_currency": base})


async def _account(uow_factory, user_id: str, code: str, currency: str) -> str:
    async with uow_factory() as uow:
        return await uow.ledger.save_account(
            user_id,
            Account(
                id=f"{user_id}-{code}",
                user_id=user_id,
                code=code,
                name=code,
                type="asset",
                currency=currency,
            ),
        )


async def _post(uow_factory, user_id: str, legs: list[tuple[str, Direction, str, str, str]]):
    entry = JournalEntry(
        entry_date="2026-10-01",
        description="x",
        source="manual",
        postings=[
            Posting(
                account_id=account,
                direction=direction,
                amount=Decimal(amount),
                currency=currency,
                fx_rate=Decimal(rate),
            )
            for account, direction, amount, currency, rate in legs
        ],
    )
    async with uow_factory() as uow:
        return await uow.ledger.save_entry(user_id, entry)


def _rows(db: str, entry_id: str) -> list[tuple]:
    engine = create_engine(_sync(db))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select currency, amount_minor, base_amount_minor from postings"
                " where entry_id = :e order by direction desc"
            ),
            {"e": entry_id},
        ).all()
    engine.dispose()
    return [tuple(r) for r in rows]


async def test_each_currency_is_stored_at_its_own_scale(db, uow_factory):
    await _user(uow_factory, "yen", "JPY")
    a, b = (
        await _account(uow_factory, "yen", "1", "JPY"),
        await _account(uow_factory, "yen", "2", "JPY"),
    )
    entry_id = await _post(
        uow_factory,
        "yen",
        [(a, Direction.DEBIT, "1200", "JPY", "1"), (b, Direction.CREDIT, "1200", "JPY", "1")],
    )
    assert _rows(db, entry_id) == [("JPY", 1200, 1200), ("JPY", 1200, 1200)]

    await _user(uow_factory, "dinar", "KWD")
    c, d = (
        await _account(uow_factory, "dinar", "1", "KWD"),
        await _account(uow_factory, "dinar", "2", "KWD"),
    )
    entry_id = await _post(
        uow_factory,
        "dinar",
        [(c, Direction.DEBIT, "1.234", "KWD", "1"), (d, Direction.CREDIT, "1.234", "KWD", "1")],
    )
    assert _rows(db, entry_id) == [("KWD", 1234, 1234), ("KWD", 1234, 1234)]

    async with uow_factory() as uow:
        [stored] = await uow.ledger.get_entries("dinar")
    assert {p.amount for p in stored.postings} == {Decimal("1.234")}


async def test_a_foreign_posting_stores_its_own_amount_and_the_base_one(db, uow_factory):
    # 1,000 USD into a euro ledger at 0.89397 → EUR 893.97.
    await _user(uow_factory, "euro", "EUR")
    usd = await _account(uow_factory, "euro", "1", "USD")
    income = await _account(uow_factory, "euro", "2", "EUR")
    entry_id = await _post(
        uow_factory,
        "euro",
        [
            (usd, Direction.DEBIT, "1000", "USD", "0.89397"),
            (income, Direction.CREDIT, "1000", "USD", "0.89397"),
        ],
    )
    assert _rows(db, entry_id) == [("USD", 100000, 89397), ("USD", 100000, 89397)]


async def test_an_entry_needs_its_owners_base_currency(db, uow_factory):
    with pytest.raises(ValueError, match="no profile"):
        await _post(
            uow_factory,
            "nobody",
            [("x", Direction.DEBIT, "1", "USD", "1"), ("y", Direction.CREDIT, "1", "USD", "1")],
        )


async def test_a_new_profile_must_name_its_currency(db, uow_factory):
    async with uow_factory() as uow:
        with pytest.raises(ValueError, match="needs a base_currency"):
            await uow.user_profiles.upsert("someone", {"email": "a@example.com"})
    engine = create_engine(_sync(db))
    with pytest.raises(Exception, match="base_currency"), engine.begin() as conn:
        conn.execute(
            text(
                "insert into user_profiles (id, mcp_enabled, daily_briefing_enabled, created_at, updated_at)"
                " values ('x', false, false, now(), now())"
            )
        )
    engine.dispose()


async def test_financial_data_is_anything_stored_in_the_base_currency(db, uow_factory):
    await _user(uow_factory, "u", "EUR")
    async with uow_factory() as uow:
        assert await uow.user_profiles.has_financial_data("u") is False
    await _account(uow_factory, "u", "1", "EUR")
    async with uow_factory() as uow:
        assert await uow.user_profiles.has_financial_data("u") is True
        assert await uow.user_profiles.base_currency("u") == "EUR"


def test_existing_users_are_kept_on_rupees(monkeypatch):
    """Upgrading a database that predates base currencies keeps every user's
    data meaning what it meant: their profiles, and profiles created for anyone
    who owns data but never had one, are LKR."""
    with scratch_database() as url:
        monkeypatch.setenv("DATABASE_URL", url)
        upgrade(CORE_SCRIPT_LOCATION, "core_0001_baseline")
        engine = create_engine(_sync(url))
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into user_profiles (id, mcp_enabled, daily_briefing_enabled, created_at, updated_at)"
                    " values ('with-profile', false, false, now(), now())"
                )
            )
            conn.execute(
                text(
                    "insert into accounts (id, user_id, code, name, type, currency, is_active, created_at)"
                    " values ('a1', 'no-profile', '1000', 'Cash', 'asset', 'LKR', true, now())"
                )
            )
        engine.dispose()

        upgrade(CORE_SCRIPT_LOCATION)

        assert (
            scalar(url, "select base_currency from user_profiles where id = 'with-profile'")
            == "LKR"
        )
        assert (
            scalar(url, "select base_currency from user_profiles where id = 'no-profile'") == "LKR"
        )
        assert scalar(url, "select count(*) from user_profiles") == 2
