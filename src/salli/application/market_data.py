"""
The market data Salli keeps itself: the closing prices a user records.

`StoredPriceHistory` is the MarketDataPort every valuation reads. It answers
from what is stored and never reaches the network. A provider's prices get
here only when the user asks for a refresh (PortfolioService.refresh_prices),
which stores what the provider said under the provider's name, so a read never
fetches a price nobody asked for.

It is built on the price repository port rather than on a database, which is
why it lives here and not among the adapters; the SQL repository is the
adapter.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from salli.application.ports import (
    HoldingPriceRepository,
    MarketDataPort,
    PriceQuote,
    PriceUnavailableError,
)


def symbol_key(symbol: str) -> str:
    """How a symbol is stored and matched: trimmed and upper case, so "voo"
    and "VOO " are the same holding's prices."""
    return symbol.strip().upper()


def _quote(row: dict[str, Any]) -> PriceQuote:
    return PriceQuote(
        symbol=row["symbol"],
        on=date.fromisoformat(row["price_date"]),
        close=Decimal(row["close"]),
        currency=row["currency"],
        source=row["source"],
    )


class StoredPriceHistory(MarketDataPort):
    """One user's recorded closes."""

    def __init__(self, prices: HoldingPriceRepository, user_id: str) -> None:
        self._prices = prices
        self._user_id = user_id

    async def latest(
        self, symbol: str, *, currency: str | None = None, on_or_before: date | None = None
    ) -> PriceQuote:
        end = on_or_before.isoformat() if on_or_before else None
        rows = await self._prices.list(self._user_id, symbol_key(symbol), end=end)
        if currency is not None:
            rows = [row for row in rows if row["currency"] == currency]
        if not rows:
            when = f" on or before {on_or_before}" if on_or_before else ""
            raise PriceUnavailableError(f"No price recorded for {symbol_key(symbol)}{when}")
        return _quote(rows[-1])

    async def history(self, symbol: str, start: date, end: date) -> list[PriceQuote]:
        rows = await self._prices.list(
            self._user_id, symbol_key(symbol), start.isoformat(), end.isoformat()
        )
        return [_quote(row) for row in rows]
