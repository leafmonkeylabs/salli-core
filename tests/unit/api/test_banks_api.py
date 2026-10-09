"""/v1/bank-connections over HTTP."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.ports import BankLinkError
from salli.application.services.bank_connection_service import BankConnectionsUnavailable
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 10, 9, 8, 30, tzinfo=UTC)
_CONNECTION = {
    "id": "c1",
    "provider": "simplefin",
    "name": "Chase",
    "status": "active",
    "last_error": None,
    "last_synced_at": _NOW,
    "created_at": _NOW,
    "accounts": [
        {
            "remote_id": "chk",
            "name": "Checking",
            "institution": "Chase",
            "currency": "USD",
            "balance": Decimal("1520.4"),
            "balance_date": _NOW,
            "account_id": "acc-1",
        },
        {
            "remote_id": "miles",
            "name": "Miles",
            "institution": "Chase",
            "currency": "https://bridge.test/miles",
            "balance": None,
            "balance_date": None,
            "account_id": None,
        },
    ],
}


@pytest.fixture
def banks(mock_services):
    service = MagicMock()
    service.available = True
    service.providers = ["simplefin"]
    for method in ("list", "connect", "map_account", "sync", "disconnect", "due", "sync_due"):
        setattr(service, method, AsyncMock())
    mock_services.bank_connections = service
    return service


async def test_connections_list_with_balances_in_their_currency(client, banks):
    banks.list.return_value = [_CONNECTION]
    body = (await client.get("/v1/bank-connections", headers=AUTH)).json()
    assert (body["available"], body["providers"]) == (True, ["simplefin"])
    checking, miles = body["connections"][0]["accounts"]
    assert (checking["balance"], checking["account_id"]) == ("1520.40", "acc-1")
    assert (miles["balance"], miles["account_id"]) == (None, None)  # not a currency


async def test_connecting_hands_over_the_setup_token_once(client, banks):
    banks.connect.return_value = {"id": "c1", "warnings": ["Chase needs you to sign in again"]}
    r = await client.post(
        "/v1/bank-connections",
        json={"provider": "simplefin", "setup_token": "aHR0cHM6Ly9..."},
        headers=AUTH,
    )
    assert r.status_code == 201
    assert r.json()["warnings"] == ["Chase needs you to sign in again"]
    banks.connect.assert_awaited_once_with("test-user-1", "simplefin", "aHR0cHM6Ly9...", None)


@pytest.mark.parametrize(
    ("error", "code"),
    [(BankLinkError("token already used"), 400), (BankConnectionsUnavailable("no key"), 503)],
)
async def test_a_connection_that_cannot_be_made_says_why(client, banks, error, code):
    banks.connect.side_effect = error
    r = await client.post(
        "/v1/bank-connections", json={"provider": "simplefin", "setup_token": "t"}, headers=AUTH
    )
    assert r.status_code == code
    assert r.json()["detail"] == str(error)


async def test_mapping_an_unknown_bank_account_is_not_found(client, banks):
    banks.map_account.side_effect = KeyError("nope")
    r = await client.put(
        "/v1/bank-connections/c1/accounts/nope", json={"create": True}, headers=AUTH
    )
    assert r.status_code == 404


async def test_a_bank_account_in_another_currency_cannot_be_mapped(client, banks):
    banks.map_account.side_effect = ValueError("Checking is in USD but that account is in EUR")
    r = await client.put(
        "/v1/bank-connections/c1/accounts/chk", json={"account_id": "eur"}, headers=AUTH
    )
    assert r.status_code == 422


async def test_a_sync_reports_what_it_queued(client, banks):
    banks.sync.return_value = {
        "accounts": [
            {
                "remote_id": "chk",
                "name": "Checking",
                "statement_id": "st1",
                "queued": 5,
                "duplicates": 2,
            }
        ],
        "unmapped": ["Savings"],
        "warnings": [],
    }
    body = (await client.post("/v1/bank-connections/c1/sync", headers=AUTH)).json()
    assert body["accounts"][0]["queued"] == 5 and body["unmapped"] == ["Savings"]


async def test_a_refused_sync_is_a_bad_gateway(client, banks):
    banks.sync.side_effect = BankLinkError("access revoked")
    r = await client.post("/v1/bank-connections/c1/sync", headers=AUTH)
    assert (r.status_code, r.json()["detail"]) == (502, "access revoked")


async def test_disconnecting_what_is_not_there_is_not_found(client, banks):
    banks.disconnect.return_value = False
    r = await client.delete("/v1/bank-connections/nope", headers=AUTH)
    assert r.status_code == 404


async def test_the_scheduler_needs_the_cron_secret(client, app, banks):
    from types import SimpleNamespace

    from salli.config import get_settings

    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(cron_secret="s3cret")
    banks.due.return_value = [("u1", "c1"), ("u2", "c2")]
    assert (await client.post("/v1/bank-connections/cron/sync-due")).status_code == 401
    r = await client.post("/v1/bank-connections/cron/sync-due", headers={"X-Cron-Secret": "s3cret"})
    assert (r.status_code, r.json()) == (202, {"due": 2, "scheduled": True})
    banks.sync_due.assert_awaited_once()
