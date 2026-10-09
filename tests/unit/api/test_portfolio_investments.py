"""
Transactions, lots, prices and performance over HTTP.

Each typed response carries exactly what the portfolio service returns: money
as decimal strings in its currency's precision, quantities, prices and rates
as exact decimal strings, never JSON numbers. A history that cannot have
happened, or a foreign amount with no rate, is a 422; anything missing a 404.
"""

from __future__ import annotations

from datetime import date

from salli.application.services.portfolio_service import PortfolioService
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH
from tests.unit.application.test_portfolio_transactions import Rates

USER = "test-user-1"


def _service(mock_services, base: str = "LKR", rates=None) -> PortfolioService:
    uow = FakeRecordsUoW(base)
    mock_services.portfolio = PortfolioService(
        lambda: uow, fx=Rates(rates), today=lambda: date(2026, 10, 9)
    )
    return mock_services.portfolio


async def _holding(client, currency: str | None = None) -> str:
    body = {"symbol": "VOO", "name": "S&P 500", "asset_class": "equity"}
    if currency:
        body["currency"] = currency
    r = await client.post("/v1/portfolio/", json=body, headers=AUTH)
    assert r.status_code == 201
    return r.json()["id"]


async def _transaction(client, holding_id: str, **body) -> str:
    r = await client.post(f"/v1/portfolio/{holding_id}/transactions", json=body, headers=AUTH)
    assert r.status_code == 201, r.json()
    return r.json()["id"]


async def test_a_transaction_round_trips(client, mock_services):
    svc = _service(mock_services)
    h = await _holding(client)
    buy = await _transaction(
        client, h, kind="buy", date="2026-01-05", quantity="10.5", price="100.25", fees="4.99"
    )

    r = await client.get(f"/v1/portfolio/{h}/transactions/{buy}", headers=AUTH)
    assert r.status_code == 200
    tx = r.json()
    assert tx == await svc.get_transaction(USER, h, buy)
    assert {k: tx[k] for k in ("kind", "quantity", "price", "fees", "total", "currency")} == {
        "kind": "buy",
        "quantity": "10.5",
        "price": "100.25",
        "fees": "4.99",
        # 10.5 × 100.25 + 4.99.
        "total": "1057.62",
        "currency": "LKR",
    }
    r = await client.get(f"/v1/portfolio/{h}/transactions", headers=AUTH)
    assert r.json() == {"transactions": [tx]}

    r = await client.patch(
        f"/v1/portfolio/{h}/transactions/{buy}", json={"quantity": "11"}, headers=AUTH
    )
    assert (r.status_code, r.json()) == (200, {"id": buy})
    tx = (await client.get(f"/v1/portfolio/{h}/transactions/{buy}", headers=AUTH)).json()
    assert tx["quantity"] == "11"

    r = await client.delete(f"/v1/portfolio/{h}/transactions/{buy}", headers=AUTH)
    assert r.status_code == 204
    r = await client.get(f"/v1/portfolio/{h}/transactions/{buy}", headers=AUTH)
    assert r.status_code == 404


async def test_a_sale_of_more_than_was_held_is_a_422(client, mock_services):
    _service(mock_services)
    h = await _holding(client)
    await _transaction(client, h, kind="buy", date="2026-01-05", quantity="1", price="1")
    r = await client.post(
        f"/v1/portfolio/{h}/transactions",
        json={"kind": "sell", "date": "2026-01-06", "quantity": "2", "price": "1"},
        headers=AUTH,
    )
    assert r.status_code == 422
    assert r.json()["type"] == "/problems/invalid"
    assert "only 1 are held" in r.json()["detail"]


async def test_a_foreign_transaction_without_a_rate_says_to_send_one(client, mock_services):
    _service(mock_services, "LKR")
    h = await _holding(client, "USD")
    r = await client.post(
        f"/v1/portfolio/{h}/transactions",
        json={"kind": "buy", "date": "2025-01-05", "quantity": "1", "price": "1"},
        headers=AUTH,
    )
    assert r.status_code == 422
    assert r.json()["type"] == "/problems/fx-rate-unavailable"
    # With the rate the broker used, it is recorded.
    await _transaction(
        client, h, kind="buy", date="2025-01-05", quantity="1", price="1", fx_rate="298.5"
    )


async def test_malformed_transactions_are_422s(client, mock_services):
    _service(mock_services)
    h = await _holding(client)
    for body in (
        {"kind": "split", "date": "2026-01-05", "ratio": "two for one"},
        {"kind": "buy", "date": "2026-02-30", "quantity": "1", "price": "1"},
        {"kind": "buy", "date": "2026-01-05", "quantity": "NaN", "price": "1"},
        {"kind": "gift", "date": "2026-01-05"},
        {"kind": "dividend", "date": "2026-01-05", "amount": "1", "quantity": "3"},
    ):
        r = await client.post(f"/v1/portfolio/{h}/transactions", json=body, headers=AUTH)
        assert r.status_code == 422, body


async def test_anything_missing_is_a_404(client, mock_services):
    _service(mock_services)
    h = await _holding(client)
    body = {"kind": "buy", "date": "2026-01-05", "quantity": "1", "price": "1"}
    for method, path, json in (
        ("POST", "/v1/portfolio/nope/transactions", body),
        ("GET", "/v1/portfolio/nope/transactions", None),
        ("GET", f"/v1/portfolio/{h}/transactions/nope", None),
        ("PATCH", f"/v1/portfolio/{h}/transactions/nope", {"price": "2"}),
        ("DELETE", f"/v1/portfolio/{h}/transactions/nope", None),
        ("GET", "/v1/portfolio/nope/lots", None),
        ("GET", "/v1/portfolio/nope/performance", None),
        ("DELETE", "/v1/portfolio/prices/nope", None),
    ):
        r = await client.request(method, path, json=json, headers=AUTH)
        assert r.status_code == 404, (method, path)


async def test_lots_read_back_as_the_service_returns_them(client, mock_services):
    svc = _service(mock_services, "LKR")
    h = await _holding(client, "USD")
    first = await _transaction(
        client, h, kind="buy", date="2026-01-05", quantity="10", price="100", fx_rate="300"
    )
    await _transaction(
        client,
        h,
        kind="sell",
        date="2026-03-05",
        quantity="4",
        price="120",
        fees="1",
        fx_rate="305",
        lots=[{"lot_id": first, "quantity": "4"}],
    )
    r = await client.get(f"/v1/portfolio/{h}/lots", headers=AUTH)
    assert r.status_code == 200
    lots = r.json()
    assert lots == await svc.get_lots(USER, h)
    [sale] = lots["sales"]
    # 480 − 1 − 400 = 79 USD; in rupees 479 × 305 − 400 × 300 = 26,095.
    assert (sale["gain"], sale["gain_base"]) == ("79.00", "26095.00")
    assert (lots["quantity"], lots["cost"], lots["cost_base"]) == ("6", "600.00", "180000.00")


async def test_prices_are_recorded_listed_and_deleted(client, mock_services):
    svc = _service(mock_services)
    await _holding(client)
    r = await client.post(
        "/v1/portfolio/prices",
        json={"symbol": "voo", "close": "512.123456", "date": "2026-10-08"},
        headers=AUTH,
    )
    assert r.status_code == 201
    quote_id = r.json()["id"]
    r = await client.get("/v1/portfolio/prices", params={"symbol": "VOO"}, headers=AUTH)
    assert r.json() == {"prices": await svc.list_prices(USER, "VOO")}
    [price] = r.json()["prices"]
    assert (price["symbol"], price["close"], price["currency"], price["date"]) == (
        "VOO",
        "512.123456",
        "LKR",
        "2026-10-08",
    )
    assert (
        await client.delete(f"/v1/portfolio/prices/{quote_id}", headers=AUTH)
    ).status_code == 204
    assert (await client.get("/v1/portfolio/prices", headers=AUTH)).json() == {"prices": []}


async def test_a_price_for_an_unheld_symbol_needs_its_currency(client, mock_services):
    _service(mock_services)
    r = await client.post(
        "/v1/portfolio/prices", json={"symbol": "BTC", "close": "1"}, headers=AUTH
    )
    assert r.status_code == 422


async def test_performance_for_a_period_and_for_one_holding(client, mock_services):
    svc = _service(mock_services)
    h = await _holding(client)
    await _transaction(client, h, kind="buy", date="2026-01-05", quantity="10", price="10")
    await _transaction(client, h, kind="buy", date="2026-03-05", quantity="5", price="12")
    await _transaction(client, h, kind="sell", date="2026-06-05", quantity="15", price="11")
    await _transaction(
        client, h, kind="dividend", date="2026-04-01", amount="3", withholding_tax="0.45"
    )

    params = {"from_date": "2026-01-01", "to_date": "2026-12-31"}
    r = await client.get("/v1/portfolio/performance", params=params, headers=AUTH)
    assert r.status_code == 200
    report = r.json()
    assert report == await svc.get_performance(USER, "2026-01-01", "2026-12-31")
    figures = report["portfolio"]
    assert (figures["realised_gain"], figures["dividends"], figures["net_income"]) == (
        "5.00",
        "3.00",
        "2.55",
    )
    assert figures["total_return"] == "7.55"

    r = await client.get(f"/v1/portfolio/{h}/performance", params=params, headers=AUTH)
    assert r.status_code == 200
    assert [x["holding_id"] for x in r.json()["holdings"]] == [h]

    r = await client.get(
        "/v1/portfolio/performance",
        params={"from_date": "2026-12-31", "to_date": "2026-01-01"},
        headers=AUTH,
    )
    assert r.status_code == 422


async def test_the_old_paths_still_reach_the_new_routes(client, mock_services):
    _service(mock_services)
    h = await _holding(client)
    r = await client.get(f"/portfolio/{h}/transactions", headers=AUTH)
    assert (r.status_code, r.headers.get("Deprecation")) == (200, "true")
