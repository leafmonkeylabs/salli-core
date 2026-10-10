"""
Converting into the base currency: the one rule every entry point follows.

A posting in the owner's base currency has a rate of 1, always. A posting in any
other currency needs a rate into the base: the one the caller gives (the rate
the bank actually used, from a statement or a receipt) or, failing that, the
published rate for the entry's date. If there is neither, the entry is refused
with FxUnavailableError. Booking 100 USD at a rate of 1 into a yen ledger
would put a number in it that is wrong by the exchange rate, and nothing would
ever flag it.
"""

from __future__ import annotations

from decimal import Decimal

from salli.application.ports import FxRatePort, FxUnavailableError


async def rate_to_base(
    fx: FxRatePort | None,
    currency: str,
    base: str,
    on_date: str,
    given: object = None,
) -> tuple[Decimal, str | None]:
    """(rate, source) converting `currency` into `base` on `on_date`.

    `given` is a rate the caller already has; it wins over any lookup and is
    recorded with source "user". Both currency codes must already be
    normalized (`currency.normalize_currency`).
    """
    if currency == base:
        if given is not None and Decimal(str(given)) != 1:
            raise ValueError(f"An amount in the base currency ({base}) has an exchange rate of 1")
        return Decimal(1), None
    if given is not None:
        rate = Decimal(str(given))
        if rate <= 0:
            raise ValueError("An exchange rate must be positive")
        return rate, "user"
    if fx is None:
        raise FxUnavailableError(f"No exchange-rate source for {currency}→{base}; give the rate")
    quote = await fx.rate(currency, base, on_date)
    return quote.rate, quote.source
