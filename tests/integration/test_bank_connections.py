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


async def test_development_sign_in_means_no_bank_connection(uow_factory):
    # Anyone can name any user id then, so no one's bank may be read.
    service = BankConnectionService(
        uow_factory, KeyRing(KEYS), {"fake": FakeBank()}, Importer(), auth_is_real=False
    )
    assert not service.available
    with pytest.raises(BankConnectionsUnavailable, match="development sign-in"):
        await service.connect("u1", "fake", "good-token")
    with pytest.raises(BankConnectionsUnavailable):
        await service.sync("u1", "any")


async def test_the_scheduler_syncs_what_is_due_and_a_failure_stops_nothing(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u2", {"base_currency": "USD"})
    good, bad, importer = FakeBank(), FakeBank(), Importer()
    service = BankConnectionService(
        uow_factory, KeyRing(KEYS), {"good": good, "bad": bad}, importer
    )
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
    await service.connect("u1", "bad", "good-token")
    fine = (await service.connect("u2", "good", "good-token"))["id"]
    bad.fail = True  # its access is revoked after connecting

    counts = await service.sync_due()
    assert counts == {"due": 2, "synced": 1, "failed": 1, "skipped": 0}
    assert len(good.starts) == 2  # connecting, then the sync

    # Just attempted, both: neither is due for 12 hours, and the failed one
    # is retried only once a day.
    assert await service.due() == []
    later = BankConnectionService(
        uow_factory,
        KeyRing(KEYS),
        {"good": good, "bad": bad},
        importer,
        clock=lambda: dt.datetime.now(dt.UTC) + dt.timedelta(hours=13),
    )
    assert [c for _, c in await later.due()] == [fine]
    next_day = BankConnectionService(
        uow_factory,
        KeyRing(KEYS),
        {"good": good, "bad": bad},
        importer,
        clock=lambda: dt.datetime.now(dt.UTC) + dt.timedelta(hours=25),
    )
    assert {u for u, _ in await next_day.due()} == {"u1", "u2"}


# ── What review found ─────────────────────────────────────────────────────────


async def test_an_expense_account_cannot_take_a_bank_feed(setup):
    service, _, _, uow_factory = setup
    await service.connect("u1", "fake", "good-token")
    [connection] = await service.list("u1")
    food = await LedgerService(uow_factory).add_account("u1", "5000", "Food", "expense")
    with pytest.raises(ValueError, match="expense account"):
        await service.map_account("u1", connection["id"], "chk", food)


class FailingImporter(Importer):
    def __init__(self, failing: dict[str, Exception]) -> None:
        super().__init__()
        self.failing = failing

    async def __call__(self, user_id, rows, *, bank, account_id):
        if account_id in self.failing:
            raise self.failing[account_id]
        return await super().__call__(user_id, rows, bank=bank, account_id=account_id)


@pytest.mark.parametrize("failure", [ValueError("No active account"), RuntimeError("db down")])
async def test_one_accounts_failure_is_noted_and_the_rest_imported(uow_factory, failure):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
    bank, importer = FakeBank(), FailingImporter({})
    service = BankConnectionService(uow_factory, KeyRing(KEYS), {"fake": bank}, importer)
    connection = (await service.connect("u1", "fake", "good-token"))["id"]
    checking = await service.map_account("u1", connection, "chk", create=True)
    savings = await service.map_account("u1", connection, "sav", create=True)
    importer.failing = {checking: failure}

    result = await service.sync("u1", connection)

    assert [c["account_id"] for c in importer.calls] == [savings]
    [connection_row] = await service.list("u1")
    accounts = {a["remote_id"]: a for a in connection_row["accounts"]}
    assert accounts["chk"]["notes"].startswith("Could not import")
    assert accounts["chk"]["last_imported_at"] is None  # tried again next time
    assert accounts["sav"]["last_imported_at"] is not None
    assert connection_row["last_synced_at"] is not None
    assert connection_row["status"] == "attention" and "Checking" in connection_row["last_error"]
    assert any(a["notes"] for a in result["accounts"])


async def test_a_second_sync_while_one_runs_is_refused(uow_factory):
    import asyncio

    from salli.application.services.bank_connection_service import SyncInProgress

    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})

    class SlowBank(FakeBank):
        async def fetch(self, credential, start, balances_only=False):
            await asyncio.sleep(0.3)
            return await super().fetch(credential, start, balances_only)

    importer = Importer()
    service = BankConnectionService(uow_factory, KeyRing(KEYS), {"fake": SlowBank()}, importer)
    connection = (await service.connect("u1", "fake", "good-token"))["id"]
    await service.map_account("u1", connection, "chk", create=True)

    outcomes = await asyncio.gather(
        service.sync("u1", connection), service.sync("u1", connection), return_exceptions=True
    )
    assert sum(isinstance(o, SyncInProgress) for o in outcomes) == 1
    assert len(importer.calls) == 1  # each transaction queued once
    await service.sync("u1", connection)  # released afterwards


async def test_an_account_mapped_later_gets_the_first_syncs_window(setup):
    service, bank, _, _ = setup
    connection = (await service.connect("u1", "fake", "good-token"))["id"]
    await service.map_account("u1", connection, "chk", create=True)
    await service.sync("u1", connection)
    # Savings is mapped only now: the next sync reaches back 90 days for it,
    # not a week before checking's last import.
    await service.map_account("u1", connection, "sav", create=True)
    await service.sync("u1", connection)
    assert bank.starts[-1] < dt.datetime.now(dt.UTC) - dt.timedelta(days=80)


async def test_an_institution_error_holds_the_marker_and_is_shown(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})

    class TroubledBank(FakeBank):
        async def fetch(self, credential, start, balances_only=False):
            snapshot = await super().fetch(credential, start, balances_only)
            return BankSnapshot(
                snapshot.accounts, snapshot.transactions, snapshot.warnings, frozenset({"chk"})
            )

    service = BankConnectionService(
        uow_factory, KeyRing(KEYS), {"fake": TroubledBank()}, Importer()
    )
    connection = (await service.connect("u1", "fake", "good-token"))["id"]
    await service.map_account("u1", connection, "chk", create=True)
    result = await service.sync("u1", connection)
    [row] = await service.list("u1")
    [checking] = [a for a in row["accounts"] if a["remote_id"] == "chk"]
    assert checking["last_imported_at"] is None  # the same days are fetched again
    assert row["status"] == "attention"
    assert row["warnings"] == ["Chase needs you to sign in again"]
    assert any("reported a problem" in n for a in result["accounts"] for n in a["notes"])


async def test_a_failed_first_read_keeps_the_claimed_credential(uow_factory):
    # The token is claimed once; a failed balances fetch lost the credential.
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
    bank, importer = FakeBank(), Importer()
    service = BankConnectionService(uow_factory, KeyRing(KEYS), {"fake": bank}, importer)
    bank.fail = True
    connected = await service.connect("u1", "fake", "good-token")
    assert connected["error"] == "access revoked"
    [row] = await service.list("u1")
    assert (row["status"], row["last_error"]) == ("error", "access revoked")

    bank.fail = False
    await service.sync("u1", connected["id"])  # finishes without a new token
    [row] = await service.list("u1")
    assert row["status"] == "attention" and {a["remote_id"] for a in row["accounts"]} == {
        "chk",
        "sav",
        "miles",
    }


async def test_a_long_bank_label_fits_its_column(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
        await uow.statements.save_statement(
            user_id="u1",
            statement_id="s1",
            bank="I" * 100 + " · " + "N" * 100,
            period_start="2026-10-01",
            period_end="2026-10-01",
            transactions=[],
        )
    async with uow_factory() as uow:
        statement = await uow.statements.get_statement("u1", "s1")
    assert statement is not None and len(statement["bank"]) == 100


async def test_feed_rows_carry_the_providers_ids(setup):
    service, _, importer, _ = setup
    connection = (await service.connect("u1", "fake", "good-token"))["id"]
    await service.map_account("u1", connection, "chk", create=True)
    await service.sync("u1", connection)
    assert {(r.ref_kind, r.ref_source) for r in importer.calls[0]["rows"]} == {("id", "feed:fake")}
