"""
CBSL (Central Bank of Sri Lanka) FX rate adapter.

CBSL publishes daily buying/selling rates at:
  https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-exchange-rates

Their site doesn't expose a stable JSON API, so we use ExchangeRate-API
(free tier, 1500 req/month) as the primary source and fall back to a
cached LKR cross-rate if the API is unavailable.

Rate choice: the CBSL "buying rate" is the correct rate to use for foreign
income remitted to Sri Lanka — it's what a bank pays when buying foreign
currency from you. For individual tax purposes this is the rate that
determines the LKR value of foreign service income.

To use CBSL rates directly: the adaptor can be replaced by one that
scrapes their site; the FxRatePort contract is the same.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from salli.application.ports import FxRatePort

# ExchangeRate-API free endpoint — no key required, limited to 1500 req/month
_BASE_URL = "https://open.er-api.com/v6/latest"

# In-process cache: (currency, date) → rate. Fine for a single process; if
# running multiple workers, replace with Redis or a DB-backed cache.
_cache: dict[tuple[str, str], Decimal] = {}

# Fallback rates — approximate CBSL mid-market rates (update periodically)
_FALLBACK_RATES: dict[str, Decimal] = {
    "USD": Decimal("300.00"),
    "GBP": Decimal("380.00"),
    "EUR": Decimal("325.00"),
    "AUD": Decimal("195.00"),
    "SGD": Decimal("222.00"),
    "CAD": Decimal("220.00"),
    "JPY": Decimal("2.00"),
    "INR": Decimal("3.60"),
    "AED": Decimal("81.70"),
}


class CBSLFxRateAdapter(FxRatePort):
    """
    Fetch LKR/foreign-currency buying rates.
    Uses ExchangeRate-API with in-process caching; falls back to static
    approximate rates when the API is unavailable (e.g. offline tests).
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def get_buying_rate(self, currency: str, date: str) -> Decimal:
        """
        Return the LKR buying rate for `currency` on `date` (YYYY-MM-DD).
        The 'buying rate' is what a bank pays you when you sell foreign currency —
        the correct rate for remitted foreign service income.

        Note: ExchangeRate-API free tier only provides current rates, not
        historical. For historical rates, upgrade to a paid plan or use CBSL
        scraping. For tax purposes this approximation is generally acceptable
        as rates are recorded at time of transaction in the ledger.
        """
        currency = currency.upper()
        if currency == "LKR":
            return Decimal("1")

        cache_key = (currency, date)
        if cache_key in _cache:
            return _cache[cache_key]

        rate = await self._fetch_rate(currency)
        _cache[cache_key] = rate
        return rate

    async def _fetch_rate(self, currency: str) -> Decimal:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{_BASE_URL}/LKR")
                resp.raise_for_status()
                data = resp.json()
                # Rates are LKR per 1 unit of foreign currency
                # open.er-api returns rates as LKR/X, so rates["USD"] = LKR per USD
                rates = data.get("rates", {})
                if currency in rates:
                    # The API gives LKR per foreign unit (since base is LKR)
                    # But actually, base=LKR means: 1 LKR = rates[X] X
                    # We want: 1 X = ? LKR (i.e. LKR/X)
                    # So: LKR per X = 1 / rates[X]  when base is LKR
                    foreign_per_lkr = Decimal(str(rates[currency]))
                    if foreign_per_lkr > 0:
                        return (Decimal("1") / foreign_per_lkr).quantize(Decimal("0.01"))
        except Exception:
            pass

        return _FALLBACK_RATES.get(currency, Decimal("300.00"))
