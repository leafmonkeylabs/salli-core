"""
ExchangeRate-API's open-access rates (https://www.exchangerate-api.com/docs/free).

Keyless, and covers 160-odd currencies, including many the ECB does not publish
(the Sri Lankan rupee among them). But it only has *today's* rates, refreshed
once a day. A rate for a date more than a week back would be today's market
passed off as that day's, so those are refused (FxUnavailableError) rather
than answered.

Its terms ask for attribution wherever its rates are shown; every posting
converted with one records "exchangerate-api.com" as its source.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal

import httpx

from salli.application.ports import FxQuote, FxRatePort, FxUnavailableError

_URL = "https://open.er-api.com/v6/latest/{base}"
_MAX_AGE_DAYS = 7


class OpenErApiFxRates(FxRatePort):
    source = "exchangerate-api.com"

    def __init__(self, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._timeout = timeout
        self._transport = transport

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        age = (datetime.date.today() - datetime.date.fromisoformat(on_date)).days
        if age > _MAX_AGE_DAYS:
            raise FxUnavailableError(
                f"exchangerate-api.com has only today's rates, not {on_date}'s"
            )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(_URL.format(base=from_currency))
        except httpx.HTTPError as exc:
            raise FxUnavailableError(f"exchangerate-api.com unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise FxUnavailableError(f"exchangerate-api.com answered HTTP {resp.status_code}")
        data = json.loads(resp.text, parse_float=Decimal)
        if data.get("result") != "success":
            raise FxUnavailableError(f"exchangerate-api.com has no {from_currency} rates")
        value = data.get("rates", {}).get(to_currency)
        if value is None:
            raise FxUnavailableError(f"exchangerate-api.com has no {from_currency}/{to_currency}")
        as_of = datetime.datetime.fromtimestamp(int(data["time_last_update_unix"]), datetime.UTC)
        return FxQuote(rate=Decimal(value), source=self.source, as_of=as_of.date().isoformat())
