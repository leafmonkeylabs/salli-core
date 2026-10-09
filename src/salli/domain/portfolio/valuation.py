"""
What a holding is worth on a date. Pure: its transactions, its closing prices,
and the exchange rates the caller found in; a valuation out.

The price is the latest one known on or before the date, of two kinds:

  a close  a closing price recorded for the holding's symbol in its currency
           (by the user, or by a provider when the user asked for a refresh);
  a trade  the price of one of the holding's own buys or sales: what someone
           actually paid that day.

On a day with both, the close wins: it is the day's last word. A price quoted
before a split is adjusted to the units after it (divided by the split ratio),
to the 18 places a price has.

    value      = quantity × price
    value_base = value × the rate into the base currency on the price's date

A trade carries its own rate. A close's rate is the caller's to find (see
`rate_dates`), and may not exist: a currency the published sources do not
cover, on a day too far back for the ones that only have today's.

Nothing here makes a number up. With no price at all, a holding is carried at
what it cost, as an unpriced asset conventionally is; with a price but no rate
for its date, its value in its own currency stands and its base value is
carried at cost. Either way the valuation says so (`priced`, `converted`).
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from salli.domain.portfolio.lots import (
    EXACT,
    PLACES,
    TRADES,
    Position,
    Transaction,
    split_factor,
)

_STEP = Decimal(1).scaleb(-PLACES)

#: The source a trade's price is reported under.
TRADE = "trade"


@dataclass(frozen=True)
class Close:
    """A closing price for the holding's symbol, in the holding's currency."""

    on: date
    price: Decimal
    source: str


@dataclass(frozen=True)
class Quote:
    """A price as it was quoted: on its day, before any later split."""

    on: date
    price: Decimal
    source: str
    #: A trade's own rate into the base currency; None for a close.
    fx_rate: Decimal | None


@dataclass(frozen=True)
class Valuation:
    on: date
    quantity: Decimal
    cost: Decimal
    cost_base: Decimal
    #: The price used, as quoted; None when there is none.
    quote: Quote | None
    #: That price per unit held on `on` (adjusted for splits since).
    price: Decimal | None
    #: The rate into the base currency on the price's date, if known.
    fx_rate: Decimal | None
    #: In the holding's currency: quantity × price, or the cost when unpriced.
    value: Decimal
    #: In the base currency: value × fx_rate, or the base cost when unpriced
    #: or when there is no rate.
    value_base: Decimal

    @property
    def priced(self) -> bool:
        """Whether `value` is at a price rather than at cost."""
        return self.price is not None

    @property
    def converted(self) -> bool:
        """Whether `value_base` is at a rate rather than at cost."""
        return self.price is not None and self.fx_rate is not None

    @property
    def unrealised(self) -> Decimal:
        with localcontext(EXACT):
            return self.value - self.cost

    @property
    def unrealised_base(self) -> Decimal:
        with localcontext(EXACT):
            return self.value_base - self.cost_base


class Pricing:
    """A holding's prices, ready to say which applies on any date."""

    def __init__(self, transactions: Iterable[Transaction], closes: Iterable[Close]) -> None:
        self._transactions = list(transactions)
        # Ranked within a day: trades in the order recorded, then the close.
        ranked: list[tuple[tuple[date, int, int], Quote]] = [
            ((tx.on, 0, tx.seq), Quote(tx.on, tx.price, TRADE, tx.fx_rate))
            for tx in self._transactions
            # A trade at no price (shares given away, say) is not a price.
            if tx.kind in TRADES and tx.price > 0
        ]
        ranked += [((c.on, 1, 0), Quote(c.on, c.price, c.source, None)) for c in closes]
        ranked.sort(key=lambda pair: pair[0])
        self._quotes = [quote for _, quote in ranked]
        self._dates = [quote.on for quote in self._quotes]

    def quote(self, on: date) -> Quote | None:
        """The latest price quoted on or before `on`."""
        index = bisect_right(self._dates, on)
        return self._quotes[index - 1] if index else None

    def value(self, on: date, position: Position, rates: Mapping[date, Decimal]) -> Valuation:
        """`position`, held on `on`, at the price that applies then. `rates`
        are the rates into the base currency the caller found, by date; a
        close's is looked up there."""
        quote = self.quote(on)
        if quote is None:
            return Valuation(
                on=on,
                quantity=position.quantity,
                cost=position.cost,
                cost_base=position.cost_base,
                quote=None,
                price=None,
                fx_rate=None,
                value=position.cost,
                value_base=position.cost_base,
            )
        rate = quote.fx_rate if quote.fx_rate is not None else rates.get(quote.on)
        with localcontext(EXACT):
            factor = split_factor(self._transactions, quote.on, on)
            price = quote.price if factor == 1 else (quote.price / factor).quantize(_STEP)
            value = position.quantity * price
            value_base = value * rate if rate is not None else position.cost_base
        return Valuation(
            on=on,
            quantity=position.quantity,
            cost=position.cost,
            cost_base=position.cost_base,
            quote=quote,
            price=price,
            fx_rate=rate,
            value=value,
            value_base=value_base,
        )

    def rate_dates(self, dates: Iterable[date]) -> set[date]:
        """The days whose rates a valuation on each of `dates` needs: those
        of the closes it would use (a trade has its own)."""
        needed: set[date] = set()
        for on in dates:
            quote = self.quote(on)
            if quote is not None and quote.fx_rate is None:
                needed.add(quote.on)
        return needed
