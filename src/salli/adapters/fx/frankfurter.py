"""
ECB reference rates, through Frankfurter (https://frankfurter.dev).

Free, keyless, and historical back to 1999, for the 30-odd currencies the
European Central Bank publishes. The ECB publishes once per working day, so a
weekend or holiday gets the last working day's rate, and the quote's `as_of`
says which day that was. A currency the ECB does not publish is a 404, which
becomes FxUnavailableError so the next provider can try.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx

from salli.application.ports import FxQuote, FxRatePort, FxUnavailableError

_URL = "https://api.frankfurter.dev/v1/{date}"


class FrankfurterFxRates(FxRatePort):
    source = "ecb"

    def __init__(self, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._timeout = timeout
        self._transport = transport

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(
                    _URL.format(date=on_date),
                    params={"base": from_currency, "symbols": to_currency},
                )
        except httpx.HTTPError as exc:
            raise FxUnavailableError(f"ECB rates unreachable: {exc}") from exc
        if resp.status_code == 404:
            raise FxUnavailableError(f"The ECB publishes no {from_currency}/{to_currency} rate")
        if resp.status_code != 200:
            raise FxUnavailableError(f"ECB rates answered HTTP {resp.status_code}")
        # Decimal straight from the text: a rate never passes through a float.
        data = json.loads(resp.text, parse_float=Decimal)
        value = data.get("rates", {}).get(to_currency)
        if value is None:
            raise FxUnavailableError(f"The ECB publishes no {from_currency}/{to_currency} rate")
        return FxQuote(rate=Decimal(value), source=self.source, as_of=str(data["date"]))
