"""The price history a user keeps, read as market data: no network, ever."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from salli.application.market_data import StoredPriceHistory, symbol_key
from salli.application.ports import PriceQuote, PriceUnavailableError
from tests.fakes import FakeHoldingPrices


async def _history() -> StoredPriceHistory:
    prices = FakeHoldingPrices()
    for on, close, currency in (
        ("2026-10-01", "10", "USD"),
        ("2026-10-02", "11", "EUR"),
        ("2026-10-05", "12", "USD"),
    ):
        await prices.upsert(
            "u1",
            {
                "symbol": "VOO",
                "price_date": on,
                "close": Decimal(close),
                "currency": currency,
                "source": "user",
            },
        )
    return StoredPriceHistory(prices, "u1")


async def test_the_latest_close_on_or_before_a_day_in_a_currency():
    history = await _history()
    assert await history.latest(" voo") == PriceQuote(
        "VOO", date(2026, 10, 5), Decimal(12), "USD", "user"
    )
    assert (await history.latest("VOO", on_or_before=date(2026, 10, 4))).close == 11
    assert (await history.latest("VOO", currency="USD", on_or_before=date(2026, 10, 4))).close == 10


async def test_no_close_is_unavailable_not_zero():
    history = await _history()
    with pytest.raises(PriceUnavailableError, match="No price recorded for VOO on or before"):
        await history.latest("VOO", on_or_before=date(2026, 9, 30))
    with pytest.raises(PriceUnavailableError):
        await StoredPriceHistory(FakeHoldingPrices(), "u1").latest("VOO")


async def test_history_is_oldest_first_within_the_range():
    history = await _history()
    closes = await history.history("VOO", date(2026, 10, 2), date(2026, 10, 5))
    assert [q.close for q in closes] == [11, 12]


def test_symbols_match_whatever_case_they_were_typed_in():
    assert symbol_key("  brk.b ") == "BRK.B"
