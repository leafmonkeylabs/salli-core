"""Currency rounding, unrealised exchange gains and the books' start, against
a real database: a converted entry balances exactly in the base currency
(core_0001's trigger agrees), revaluation is computed and posted only when
asked, and the opening balances land on the day the books start."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.ports import FxQuote, FxUnavailableError
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


class _Rates:
    """Kroner into the base currency: 2.0 in March, 2.5 from April."""

    async def rate(self, currency: str, base: str, on_date: str) -> FxQuote:
        if currency != "NOK":
            raise FxUnavailableError(currency)
        return FxQuote(
            rate=Decimal("2.5") if on_date >= "2031-04-01" else Decimal("2.0"),
            source="test",
            as_of=on_date,
        )


async def _ledger(uow_factory) -> LedgerService:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("ines", {"base_currency": "NZD"})
    return LedgerService(uow_factory, fx=_Rates(), today=lambda: dt.date(2031, 6, 1))


async def test_rounding_goes_to_fx_rounding_and_the_entry_balances(uow_factory):
    ledger = await _ledger(uow_factory)
    nok = await ledger.add_account("ines", "1100", "Kroner", "asset", currency="NOK")
    a = await ledger.add_account("ines", "5000", "Food", "expense")
    b = await ledger.add_account("ines", "5100", "Fun", "expense")
    legs = [
        {
            "account_id": a,
            "direction": Direction.DEBIT,
            "amount": Decimal("1.00"),
            "currency": "NOK",
            "fx_rate": Decimal("1.005"),
        },
        {
            "account_id": b,
            "direction": Direction.DEBIT,
            "amount": Decimal("1.00"),
            "currency": "NOK",
            "fx_rate": Decimal("1.005"),
        },
        {
            "account_id": nok,
            "direction": Direction.CREDIT,
            "amount": Decimal("2.00"),
            "currency": "NOK",
            "fx_rate": Decimal("1.005"),
        },
    ]
    entry = await ledger.get_entry(
        "ines", await ledger.add_entry("ines", "2031-03-02", "Split", "manual", legs)
    )
    assert entry is not None
    rounding = [p for p in entry.postings if p.fx_rate_source == "rounding"]
    assert [(p.amount, p.currency, p.direction) for p in rounding] == [
        (Decimal("0.01"), "NZD", Direction.CREDIT)
    ]
    codes = {x.id: x.code for x in await ledger.list_accounts("ines")}
    assert codes[rounding[0].account_id] == "fx_rounding"
    # And its reversal balances too.
    await ledger.reverse_entry("ines", entry.id, "test")


async def test_unrealised_fx_is_computed_and_posted_only_when_asked(uow_factory):
    ledger = await _ledger(uow_factory)
    nok = await ledger.add_account("ines", "1100", "Kroner", "asset", currency="NOK")
    equity = await ledger.add_account("ines", "3000", "Opening", "equity")
    await ledger.add_entry(
        "ines",
        "2031-03-01",
        "In",
        "manual",
        [
            {
                "account_id": nok,
                "direction": Direction.DEBIT,
                "amount": Decimal("100"),
                "currency": "NOK",
            },
            {"account_id": equity, "direction": Direction.CREDIT, "amount": Decimal("200")},
        ],
    )
    march = await ledger.unrealised_fx("ines", "2031-03-31")
    assert (march["total"], march["unposted"]) == ("0.00", "0.00")
    april = await ledger.unrealised_fx("ines", "2031-04-30")
    assert (april["total"], april["posted"], april["unposted"]) == ("50.00", "0.00", "50.00")
    assert april["lines"][0]["cost"] == "200.00" and april["lines"][0]["value"] == "250.00"

    with pytest.raises(ValueError, match="last day"):
        await ledger.post_fx_revaluation("ines", "2031-04-15")
    assert await ledger.post_fx_revaluation("ines", "2031-04-30") is not None
    after = await ledger.unrealised_fx("ines", "2031-04-30")
    assert (after["posted"], after["unposted"]) == ("50.00", "0.00")
    assert await ledger.post_fx_revaluation("ines", "2031-04-30") is None


async def test_reports_before_the_books_start_say_so(uow_factory):
    ledger = await _ledger(uow_factory)
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("ines", {"books_start": dt.date(2031, 3, 1)})
    assert await ledger.books_note("ines", "2031-03-01") == []
    [note] = await ledger.books_note("ines", "2031-02-01")
    assert "2031-03-01" in note
