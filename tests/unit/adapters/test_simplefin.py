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


async def _public(host: str, port: int) -> list[str]:
    """Every test host resolves to a public address."""
    return ["93.184.216.34"]


async def test_a_setup_token_is_claimed_once_for_an_access_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert (request.method, str(request.url)) == ("POST", CLAIM)
        return httpx.Response(200, text=ACCESS + "\n")

    assert (
        await SimpleFinConnector(transport=_transport(handler), resolver=_public).link(TOKEN)
        == ACCESS
    )


async def test_a_used_token_says_it_may_be_compromised():
    connector = SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(403)), resolver=_public
    )
    with pytest.raises(BankLinkError, match="already used"):
        await connector.link(TOKEN)


@pytest.mark.parametrize(
    "bad", ["not base64 !!", base64.b64encode(b"http://insecure.test").decode()]
)
async def test_a_token_that_is_not_one_is_refused_without_a_request(bad):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made")

    with pytest.raises(BankLinkError):
        await SimpleFinConnector(transport=_transport(handler), resolver=_public).link(bad)


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

    snapshot = await SimpleFinConnector(transport=_transport(handler), resolver=_public).fetch(
        ACCESS, start
    )
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
    connector = SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(status)), resolver=_public
    )
    with pytest.raises(BankLinkError, match=message):
        await connector.fetch(ACCESS, None)


async def test_an_answer_that_is_not_an_account_set_is_refused_or_passed_over():
    garbled = SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(200, text="<html>")), resolver=_public
    )
    with pytest.raises(BankLinkError, match="not JSON"):
        await garbled.fetch(ACCESS, None)
    odd = '{"accounts": [42, {"id": "a", "currency": "USD", "balance": "1"}], "errlist": "x"}'
    snapshot = await SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(200, text=odd)), resolver=_public
    ).fetch(ACCESS, None)
    assert [a.remote_id for a in snapshot.accounts] == ["a"] and snapshot.warnings == []


# ── What review found ─────────────────────────────────────────────────────────


def _never(request: httpx.Request) -> httpx.Response:  # pragma: no cover
    raise AssertionError("no request should be made")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.0.9", "192.168.1.1", "169.254.169.254", "::1", "fd00::1",
     "::ffff:127.0.0.1"],
)  # fmt: skip
async def test_a_setup_token_pointing_inside_the_network_is_refused(address):
    async def resolves(host: str, port: int) -> list[str]:
        return [address]

    connector = SimpleFinConnector(transport=_transport(_never), resolver=resolves)
    with pytest.raises(BankLinkError, match="not on the public internet"):
        await connector.link(TOKEN)


async def test_an_ip_literal_inside_the_network_is_refused_without_resolving():
    token = base64.b64encode(b"https://127.0.0.1:8443/claim").decode()
    connector = SimpleFinConnector(transport=_transport(_never), resolver=_public)
    with pytest.raises(BankLinkError, match="not on the public internet"):
        await connector.link(token)


async def test_an_access_url_inside_the_network_is_refused_too():
    async def resolves(host: str, port: int) -> list[str]:
        return ["10.0.0.5"] if host == "internal.test" else ["93.184.216.34"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="https://u:p@internal.test/simplefin")

    connector = SimpleFinConnector(transport=_transport(handler), resolver=resolves)
    with pytest.raises(BankLinkError, match="not on the public internet"):
        await connector.link(TOKEN)
    with pytest.raises(BankLinkError, match="not on the public internet"):
        await connector.fetch("https://u:p@internal.test/simplefin", None)


async def test_a_failure_to_connect_says_nothing_about_the_network():
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[Errno 61] Connection refused to 93.184.216.34:8443")

    connector = SimpleFinConnector(transport=_transport(refused), resolver=_public)
    with pytest.raises(BankLinkError) as error:
        await connector.link(TOKEN)
    assert str(error.value) == "Could not reach SimpleFIN"


async def test_a_claim_url_with_a_trailing_newline_or_a_bad_url_is_a_link_error():
    # `echo url | base64` adds a newline: httpx.InvalidURL is no HTTPError,
    # so it was a 500.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=ACCESS)

    connector = SimpleFinConnector(transport=_transport(handler), resolver=_public)
    newline = base64.b64encode((CLAIM + "\n").encode()).decode()
    assert await connector.link(newline) == ACCESS
    broken = base64.b64encode(b"https://bridge.test:99999999/claim").decode()
    with pytest.raises(BankLinkError):
        await connector.link(broken)


async def test_an_answer_past_the_size_cap_is_refused(monkeypatch):
    from salli.adapters.banks import simplefin

    monkeypatch.setattr(simplefin, "MAX_BODY_BYTES", 1000)
    connector = SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(200, text="x" * 5000)), resolver=_public
    )
    with pytest.raises(BankLinkError, match="more than Salli reads"):
        await connector.fetch(ACCESS, None)


async def test_basic_auth_credentials_are_percent_decoded():
    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            request.headers["authorization"] == "Basic " + base64.b64encode(b"us@r:p/ss").decode()
        )
        return httpx.Response(200, text='{"accounts": []}')

    connector = SimpleFinConnector(transport=_transport(handler), resolver=_public)
    await connector.fetch("https://us%40r:p%2Fss@bridge.test/simplefin", None)


async def test_a_payload_missing_an_id_is_a_link_error_not_a_missing_connection():
    broken = '{"accounts": [{"name": "Checking", "currency": "USD", "balance": "1"}]}'
    connector = SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(200, text=broken)), resolver=_public
    )
    with pytest.raises(BankLinkError, match="can't read"):
        await connector.fetch(ACCESS, None)


async def test_currencies_are_normalised_once_and_troubled_accounts_named():
    data = ACCOUNT_SET.replace('"currency": "USD"', '"currency": " usd "')
    connector = SimpleFinConnector(
        transport=_transport(lambda r: httpx.Response(200, text=data)), resolver=_public
    )
    snapshot = await connector.fetch(ACCESS, None)
    checking, miles = snapshot.accounts
    assert checking.currency == "USD"
    assert miles.currency == "https://bridge.test/currencies/miles"  # kept as given
    # Chase's errlist entry (con.auth) marks both its accounts as troubled.
    assert snapshot.troubled == {"acct-1", "acct-2"}
