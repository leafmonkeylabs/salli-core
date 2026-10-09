"""Connecting a bank, mapping its accounts, and syncing them — against a real database."""

from __future__ import annotations

import base64
import datetime as dt
import os
from decimal import Decimal
from typing import Any

import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.application.ports import (
    BankConnector,
    BankLinkError,
    BankSnapshot,
    RemoteAccount,
    RemoteTransaction,
)
from salli.application.services.bank_connection_service import (
    BankConnectionService,
    BankConnectionsUnavailable,
)
from salli.application.services.ledger_service import LedgerService
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

KEYS = "1:" + base64.b64encode(os.urandom(32)).decode()
CREDENTIAL = "https://user:secret@bridge.test/simplefin"


class FakeBank(BankConnector):
    provider = "fake"

    def __init__(self) -> None:
        self.starts: list[dt.datetime | None] = []
        self.fail = False

    async def link(self, setup: str) -> str:
        if setup != "good-token":
            raise BankLinkError("bad token")
        return CREDENTIAL

    async def fetch(self, credential, start, balances_only=False) -> BankSnapshot:
        assert credential == CREDENTIAL  # the sealed credential opened intact
        if self.fail:
            raise BankLinkError("access revoked")
        self.starts.append(start)
        return BankSnapshot(
            accounts=[
                RemoteAccount("chk", "Checking", "Chase", "USD", Decimal("1520.42"), None),
                RemoteAccount("sav", "Savings", "Chase", "USD", Decimal("90.00"), None),
                RemoteAccount("miles", "Miles", "Chase", "https://x/miles", Decimal("5000"), None),
            ],
            transactions=[]
            if balances_only
            else [
                RemoteTransaction("t1", "chk", "2026-10-08", Decimal("-12.50"), "UBER *TRIP"),
                RemoteTransaction("t2", "chk", "2026-10-07", Decimal("2500.00"), "ACME PAYROLL"),
                RemoteTransaction("t3", "sav", "2026-10-07", Decimal("5.00"), "INTEREST"),
            ],
            warnings=["Chase needs you to sign in again"],
        )


class Importer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, user_id, rows, *, bank, account_id):
        self.calls.append({"rows": rows, "bank": bank, "account_id": account_id})
        return {"queued": len(rows)}


@pytest.fixture
async def setup(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
    bank, importer = FakeBank(), Importer()
    service = BankConnectionService(uow_factory, KeyRing(KEYS), {"fake": bank}, importer)
    return service, bank, importer, uow_factory


async def test_connect_map_and_sync(setup):
    service, bank, importer, uow_factory = setup
    connected = await service.connect("u1", "fake", "good-token")
    assert connected["warnings"] == ["Chase needs you to sign in again"]

    [connection] = await service.list("u1")
    assert connection["name"] == "Chase"
    assert "credential_sealed" not in connection
    assert {a["remote_id"]: a["balance"] for a in connection["accounts"]} == {
        "chk": Decimal("1520.42"),
        "sav": Decimal("90.00"),
        "miles": None,  # a custom currency has no money balance
    }
    async with uow_factory() as uow:
        secret = await uow.bank_connections.get_secret("u1", connection["id"])
    assert CREDENTIAL not in str(secret["credential_sealed"])  # sealed, not stored in the clear

    checking = await service.map_account("u1", connection["id"], "chk", create=True)
    with pytest.raises(ValueError, match="not a currency"):
        await service.map_account("u1", connection["id"], "miles", create=True)

    result = await service.sync("u1", connection["id"])
    assert [c["account_id"] for c in importer.calls] == [checking]  # savings is not mapped
    rows = importer.calls[0]["rows"]
    assert [(r.bank_ref, r.amount, r.credit_flag, r.currency) for r in rows] == [
        ("t1", Decimal("12.50"), False, "USD"),
        ("t2", Decimal("2500.00"), True, "USD"),
    ]
    assert importer.calls[0]["bank"] == "Chase · Checking"
    assert result["unmapped"] == ["Savings", "Miles"]

    # The next sync overlaps the last one by a week; the importer drops what it has seen.
    await service.sync("u1", connection["id"])
    [connection] = await service.list("u1")
    assert bank.starts[-1] < connection["last_synced_at"] - dt.timedelta(days=6)


async def test_an_account_must_be_mapped_to_one_in_its_currency(setup):
    service, _, _, uow_factory = setup
    await service.connect("u1", "fake", "good-token")
    [connection] = await service.list("u1")
    euros = await LedgerService(uow_factory).add_account(
        "u1", "1100", "Euro account", "asset", "EUR"
    )
    with pytest.raises(ValueError, match="same currency"):
        await service.map_account("u1", connection["id"], "chk", euros)


async def test_a_failed_sync_is_recorded_and_reported(setup):
    service, bank, _, _ = setup
    await service.connect("u1", "fake", "good-token")
    [connection] = await service.list("u1")
    bank.fail = True
    with pytest.raises(BankLinkError):
        await service.sync("u1", connection["id"])
    [connection] = await service.list("u1")
    assert (connection["status"], connection["last_error"]) == ("error", "access revoked")


async def test_disconnecting_forgets_the_credential(setup):
    service, _, _, _ = setup
    await service.connect("u1", "fake", "good-token")
    [connection] = await service.list("u1")
    assert await service.disconnect("u1", connection["id"])
    assert await service.list("u1") == []


async def test_no_encryption_key_means_no_bank_connection(uow_factory):
    service = BankConnectionService(uow_factory, KeyRing(""), {"fake": FakeBank()})
    with pytest.raises(BankConnectionsUnavailable):
        await service.connect("u1", "fake", "good-token")
