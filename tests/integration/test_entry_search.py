"""Finding entries, and booking one once, against a real database: the
store filters, pages and sums, so an agent never adds anything up."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

from salli.application.ports import EntryRefTaken
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _postings(debit: str, credit: str, amount: str, currency: str | None = None):
    return [
        {
            "account_id": debit,
            "direction": Direction.DEBIT,
            "amount": Decimal(amount),
            "currency": currency,
        },
        {
            "account_id": credit,
            "direction": Direction.CREDIT,
            "amount": Decimal(amount),
            "currency": currency,
        },
    ]


@pytest.fixture
async def books(uow_factory) -> SimpleNamespace:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("ana", {"base_currency": "EUR"})
        await uow.user_profiles.upsert("ben", {"base_currency": "EUR"})
    ledger = LedgerService(uow_factory)
    cash = await ledger.add_account("ana", "1000", "Cash", "asset")
    food = await ledger.add_account("ana", "5000", "Food", "expense")
    pay = await ledger.add_account("ana", "4000", "Salary", "income")
    for day, what, amount in [
        ("2026-09-02", "Corner Bakery", "8.40"),
        ("2026-09-20", "CORNER BAKERY 100%", "12.10"),
        ("2026-10-03", "Market", "40.00"),
        ("2026-10-05", "Corner Bakery", "3.50"),
    ]:
        await ledger.add_entry("ana", day, what, "manual", _postings(food, cash, amount))
    await ledger.add_entry("ana", "2026-10-01", "Salary", "manual", _postings(cash, pay, "2500"))
    ben_cash = await ledger.add_account("ben", "1000", "Cash", "asset")
    ben_food = await ledger.add_account("ben", "5000", "Food", "expense")
    await ledger.add_entry(
        "ben", "2026-10-05", "Corner Bakery", "manual", _postings(ben_food, ben_cash, "99")
    )
    return SimpleNamespace(ledger=ledger, cash=cash, food=food, pay=pay)


async def test_text_finds_any_case_newest_first_with_totals_over_every_page(books):
    first = await books.ledger.search_entries("ana", text="corner bakery", limit=2)
    assert [e.description for e in first["entries"]] == ["Corner Bakery", "CORNER BAKERY 100%"]
    assert first["matches"] == 3  # never Ben's
    assert first["totals"] == [
        {"account_type": "asset", "currency": "EUR", "net": "-24.00"},
        {"account_type": "expense", "currency": "EUR", "net": "24.00"},
    ]
    rest = await books.ledger.search_entries(
        "ana", text="corner bakery", limit=2, cursor=first["next_cursor"]
    )
    assert [e.entry_date for e in rest["entries"]] == ["2026-09-02"]
    assert rest["next_cursor"] is None and rest["totals"] == first["totals"]

    # % and _ are only themselves.
    assert (await books.ledger.search_entries("ana", text="100%"))["matches"] == 1
    assert (await books.ledger.search_entries("ana", text="_"))["matches"] == 0
    with pytest.raises(ValueError):
        await books.ledger.search_entries("ana", cursor="nonsense")


async def test_account_dates_and_amounts_narrow_it_and_the_account_s_net_is_the_total(books):
    found = await books.ledger.search_entries(
        "ana", account_id=books.cash, from_date="2026-10-01", min_amount=Decimal("10")
    )
    assert [e.description for e in found["entries"]] == ["Market", "Salary"]
    assert found["totals"] == [{"account_type": "asset", "currency": "EUR", "net": "2460.00"}]

    small = await books.ledger.search_entries(
        "ana", account_id=books.food, max_amount=Decimal("8.40")
    )
    assert [e.description for e in small["entries"]] == ["Corner Bakery", "Corner Bakery"]
    assert small["amounts_in"] == "EUR"


async def test_a_client_ref_books_an_entry_once(books):
    postings = _postings(books.food, books.cash, "8.40")
    entry_id, posted = await books.ledger.add_entry_once(
        "ana", "2026-10-24", "Bakery", postings, "r-1"
    )
    again, posted_again = await books.ledger.add_entry_once(
        "ana", "2026-10-24", "Bakery", postings, "r-1"
    )
    assert (posted, posted_again, again) == (True, False, entry_id)
    assert (await books.ledger.search_entries("ana", text="Bakery", from_date="2026-10-24"))[
        "matches"
    ] == 1
    stored = await books.ledger.get_entry("ana", entry_id)
    assert stored is not None and stored.external_ref == "client-ref:r-1"


async def test_retries_sent_at_once_book_one_entry(books):
    postings = _postings(books.food, books.cash, "8.40")
    booked = await asyncio.gather(
        *(
            books.ledger.add_entry_once("ana", "2026-10-24", "Bakery", postings, "r-2")
            for _ in range(4)
        )
    )
    assert len({entry_id for entry_id, _ in booked}) == 1
    assert sorted(posted for _, posted in booked) == [False, False, False, True]
    # The database is what holds it: a second entry with the ref is refused.
    with pytest.raises(EntryRefTaken):
        await books.ledger.add_entry(
            "ana", "2026-10-24", "Bakery", "manual", postings, external_ref="client-ref:r-2"
        )
    # A reference a person typed may repeat, as before.
    for _ in range(2):
        await books.ledger.add_entry(
            "ana", "2026-10-24", "Bakery", "manual", postings, external_ref="receipt-7"
        )
