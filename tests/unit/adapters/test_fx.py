"""Exchange rates: real sources, tried in order, and never a made-up number."""

from __future__ import annotations

import datetime
import json
from decimal import Decimal

import httpx
import pytest

from salli.adapters.fx.chain import FxRates
from salli.adapters.fx.frankfurter import FrankfurterFxRates
from salli.adapters.fx.open_er_api import OpenErApiFxRates
from salli.application.fx import rate_to_base
from salli.application.ports import FxQuote, FxRatePort, FxUnavailableError

TODAY = datetime.date.today().isoformat()


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


# ── ECB via Frankfurter ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ecb_rate_comes_back_exact_with_the_day_it_is_for():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/2026-10-04"
        assert request.url.params["base"] == "USD"
        assert request.url.params["symbols"] == "EUR"
        # A Sunday: the ECB answers with Friday's rate, and says so.
        body = '{"amount":1.0,"base":"USD","date":"2026-10-02","rates":{"EUR":0.89397}}'
        return httpx.Response(200, text=body)

    quote = await FrankfurterFxRates(transport=_transport(handler)).rate("USD", "EUR", "2026-10-04")
    assert quote == FxQuote(rate=Decimal("0.89397"), source="ecb", as_of="2026-10-02")


@pytest.mark.asyncio
async def test_a_currency_the_ecb_does_not_publish_is_unavailable_not_wrong():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text='{"message":"not found"}')

    with pytest.raises(FxUnavailableError, match="publishes no USD/LKR"):
        await FrankfurterFxRates(transport=_transport(handler)).rate("USD", "LKR", "2026-10-08")


@pytest.mark.asyncio
async def test_an_unreachable_ecb_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(FxUnavailableError, match="unreachable"):
        await FrankfurterFxRates(transport=_transport(handler)).rate("USD", "EUR", "2026-10-08")


# ── exchangerate-api.com ──────────────────────────────────────────────────────


def _open_er_body(rates: dict[str, str]) -> str:
    updated = int(datetime.datetime(2026, 10, 9, 0, 2, tzinfo=datetime.UTC).timestamp())
    return json.dumps(
        {"result": "success", "base_code": "USD", "time_last_update_unix": updated}
    ).replace("}", ', "rates": {' + ", ".join(f'"{k}": {v}' for k, v in rates.items()) + "}}")


@pytest.mark.asyncio
async def test_todays_rate_for_a_currency_only_the_wide_feed_has():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v6/latest/USD"
        return httpx.Response(200, text=_open_er_body({"LKR": "330.503569", "EUR": "0.89"}))

    quote = await OpenErApiFxRates(transport=_transport(handler)).rate("USD", "LKR", TODAY)
    assert quote.rate == Decimal("330.503569")
    assert quote.source == "exchangerate-api.com"
    assert quote.as_of == "2026-10-09"


@pytest.mark.asyncio
async def test_todays_rate_is_never_passed_off_as_last_years():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not be called
        raise AssertionError("asked the network for a rate it cannot have")

    with pytest.raises(FxUnavailableError, match="only today's rates"):
        await OpenErApiFxRates(transport=_transport(handler)).rate("USD", "LKR", "2025-01-15")


# ── the chain ─────────────────────────────────────────────────────────────────


class _Provider(FxRatePort):
    def __init__(self, answer: Decimal | None, source: str) -> None:
        self.answer, self.source, self.calls = answer, source, 0

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        self.calls += 1
        if self.answer is None:
            raise FxUnavailableError(f"{self.source} has no {from_currency}/{to_currency}")
        return FxQuote(rate=self.answer, source=self.source, as_of=on_date)


@pytest.mark.asyncio
async def test_providers_are_tried_in_order_and_the_first_answer_wins():
    ecb, wide = _Provider(None, "ecb"), _Provider(Decimal("330.5"), "wide")
    quote = await FxRates([ecb, wide]).rate("usd", "lkr", "2026-10-08")
    assert (quote.rate, quote.source) == (Decimal("330.5"), "wide")
    assert ecb.calls == wide.calls == 1


@pytest.mark.asyncio
async def test_a_rate_is_asked_for_once_per_day():
    provider = _Provider(Decimal("0.9"), "ecb")
    rates = FxRates([provider])
    await rates.rate("USD", "EUR", "2026-10-08")
    await rates.rate("USD", "EUR", "2026-10-08")
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_a_currency_against_itself_is_one_without_asking_anyone():
    provider = _Provider(Decimal("9"), "ecb")
    quote = await FxRates([provider]).rate("EUR", "EUR", "2026-10-08")
    assert (quote.rate, quote.source) == (Decimal(1), "identity")
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_when_nobody_has_a_rate_the_answer_is_an_error_saying_why():
    with pytest.raises(FxUnavailableError, match="No USD→LKR rate for 2026-10-08: ecb has no"):
        await FxRates([_Provider(None, "ecb")]).rate("USD", "LKR", "2026-10-08")


# ── the rule every entry point follows ────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_base_currency_is_always_at_par():
    assert await rate_to_base(None, "LKR", "LKR", "2026-10-08") == (Decimal(1), None)
    with pytest.raises(ValueError, match="rate of 1"):
        await rate_to_base(None, "LKR", "LKR", "2026-10-08", given="2")


@pytest.mark.asyncio
async def test_a_given_rate_wins_and_is_recorded_as_the_users():
    provider = _Provider(Decimal("300"), "ecb")
    assert await rate_to_base(provider, "USD", "LKR", "2026-10-08", given="298.10") == (
        Decimal("298.10"),
        "user",
    )
    assert provider.calls == 0
    with pytest.raises(ValueError, match="positive"):
        await rate_to_base(provider, "USD", "LKR", "2026-10-08", given="0")


@pytest.mark.asyncio
async def test_a_missing_rate_is_looked_up_and_never_assumed():
    assert await rate_to_base(_Provider(Decimal("300"), "ecb"), "USD", "LKR", "2026-10-08") == (
        Decimal("300"),
        "ecb",
    )
    with pytest.raises(FxUnavailableError):
        await rate_to_base(None, "USD", "LKR", "2026-10-08")
