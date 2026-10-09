"""SimpleFIN: claiming a setup token, and reading accounts as the protocol defines them."""

from __future__ import annotations

import base64
import datetime as dt
from decimal import Decimal

import httpx
import pytest

from salli.adapters.banks.simplefin import SimpleFinConnector
from salli.application.ports import BankLinkError

CLAIM = "https://bridge.test/simplefin/claim/abc"
TOKEN = base64.b64encode(CLAIM.encode()).decode()
ACCESS = "https://user:pa55@bridge.test/simplefin"

ACCOUNT_SET = """{
  "errlist": [{"code": "con.auth", "msg": "Chase needs you to sign in again\\u0007", "conn_id": "c1"}],
  "connections": [{"conn_id": "c1", "name": "Chase", "org_id": "o1", "sfin_url": "https://x"}],
  "accounts": [
    {
      "id": "acct-1", "name": "Checking", "conn_id": "c1", "currency": "USD",
      "balance": "1520.42", "available-balance": "1500.00", "balance-date": 1791504000,
      "transactions": [
        {"id": "t1", "posted": 1791417600, "amount": "-12.50", "description": "UBER *TRIP"},
        {"id": "t2", "posted": 1791331200, "amount": "2500.00", "description": "ACME PAYROLL"},
        {"id": "t3", "posted": 0, "amount": "-3.00", "description": "PENDING THING", "pending": true}
      ]
    },
    {
      "id": "acct-2", "name": "Airline Miles", "conn_id": "c1",
      "currency": "https://bridge.test/currencies/miles",
      "balance": "52000", "balance-date": 1791504000
    }
  ]
}"""


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def test_a_setup_token_is_claimed_once_for_an_access_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert (request.method, str(request.url)) == ("POST", CLAIM)
        return httpx.Response(200, text=ACCESS + "\n")

    assert await SimpleFinConnector(transport=_transport(handler)).link(TOKEN) == ACCESS


async def test_a_used_token_says_it_may_be_compromised():
    connector = SimpleFinConnector(transport=_transport(lambda r: httpx.Response(403)))
    with pytest.raises(BankLinkError, match="already used"):
        await connector.link(TOKEN)


@pytest.mark.parametrize(
    "bad", ["not base64 !!", base64.b64encode(b"http://insecure.test").decode()]
)
async def test_a_token_that_is_not_one_is_refused_without_a_request(bad):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made")

    with pytest.raises(BankLinkError):
        await SimpleFinConnector(transport=_transport(handler)).link(bad)


async def test_accounts_and_settled_transactions_are_read_exactly():
    start = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/simplefin/accounts"
        assert request.url.params["start-date"] == str(int(start.timestamp()))
        assert request.url.params["version"] == "2"
        # The credentials travel as Basic Auth, never in the URL.
        assert request.url.userinfo == b""
        assert (
            request.headers["authorization"] == "Basic " + base64.b64encode(b"user:pa55").decode()
        )
        return httpx.Response(200, text=ACCOUNT_SET)

    snapshot = await SimpleFinConnector(transport=_transport(handler)).fetch(ACCESS, start)
    checking, miles = snapshot.accounts
    assert (checking.name, checking.institution, checking.currency) == ("Checking", "Chase", "USD")
    assert checking.balance == Decimal("1520.42")
    assert miles.currency.startswith("https://")  # a custom currency, kept as given
    assert [(t.remote_id, t.amount, t.posted) for t in snapshot.transactions] == [
        ("t1", Decimal("-12.50"), "2026-10-08"),
        ("t2", Decimal("2500.00"), "2026-10-07"),
    ]  # the pending one is left until it settles
    assert snapshot.warnings == ["Chase needs you to sign in again"]  # sanitized


@pytest.mark.parametrize(("status", "message"), [(403, "revoked"), (402, "subscription")])
async def test_revoked_or_unpaid_access_is_reported(status, message):
    connector = SimpleFinConnector(transport=_transport(lambda r: httpx.Response(status)))
    with pytest.raises(BankLinkError, match=message):
        await connector.fetch(ACCESS, None)
