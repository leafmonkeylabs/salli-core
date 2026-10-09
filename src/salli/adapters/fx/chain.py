"""
The exchange rates Salli uses: several providers, tried in order.

The ECB comes first because its rates are historical and official; the wider
but today-only feed fills the gaps. A rate between a currency and itself is 1
without asking anyone. Nothing here ever invents a rate: if no provider has
one, the caller gets FxUnavailableError and can ask the user for it.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from decimal import Decimal

from salli.application.ports import FxQuote, FxRatePort, FxUnavailableError
from salli.domain.currency import normalize_currency

_CACHE_SIZE = 4096


class FxRates(FxRatePort):
    def __init__(self, providers: Sequence[FxRatePort]) -> None:
        self._providers = list(providers)
        self._cache: OrderedDict[tuple[str, str, str], FxQuote] = OrderedDict()

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        source, target = normalize_currency(from_currency), normalize_currency(to_currency)
        if source == target:
            return FxQuote(rate=Decimal(1), source="identity", as_of=on_date)

        key = (source, target, on_date)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        reasons: list[str] = []
        for provider in self._providers:
            try:
                quote = await provider.rate(source, target, on_date)
            except FxUnavailableError as exc:
                reasons.append(str(exc))
                continue
            self._cache[key] = quote
            if len(self._cache) > _CACHE_SIZE:
                self._cache.popitem(last=False)
            return quote
        raise FxUnavailableError(
            f"No {source}→{target} rate for {on_date}"
            + (f": {'; '.join(reasons)}" if reasons else "")
        )


def default_fx_rates() -> FxRates:
    from salli.adapters.fx.frankfurter import FrankfurterFxRates
    from salli.adapters.fx.open_er_api import OpenErApiFxRates

    return FxRates([FrankfurterFxRates(), OpenErApiFxRates()])
