"""
"Export my data" includes what extensions hold about the user, after Salli's
own keys — and is complete without any extension at all.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from salli.application.services.data_portability_service import DataPortabilityService

pytestmark = pytest.mark.asyncio


def _service(exporters=(), statements=(), banks=()):
    # profile, ledger, tax, budget, debt, portfolio, subscription, insurance,
    # fi, advisor, documents, reminders
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    svcs = [AsyncMock() for _ in range(12)]
    svcs[1].get_entries.return_value = []
    svcs[2].get_latest_computation.return_value = None

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(
            statements=SimpleNamespace(export=AsyncMock(return_value=statements)),
            bank_connections=SimpleNamespace(list=AsyncMock(return_value=banks)),
        )

    return DataPortabilityService(uow, *svcs, exporters=exporters)


async def test_without_extensions_the_export_is_salli_only():
    data = await _service().export_all("u1")
    assert data["user_id"] == "u1"
    assert "bug_reports" not in data


async def test_extension_data_is_appended_after_salli_keys():
    async def export(user_id):
        return {"extension_rows": [user_id]}

    data = await _service([export]).export_all("u1")

    assert data["extension_rows"] == ["u1"]
    assert list(data)[-1] == "extension_rows"


async def test_statements_and_their_transactions_are_exported():
    # Deleting the account removes them, so the export carries them too.
    from decimal import Decimal

    from salli.domain.parsing.models import ParsedTransaction, RawRow

    row = RawRow("2026-10-13", "COFFEE", Decimal("4.5"), False, "USD", "FIT-1")
    txn = ParsedTransaction(row, "", "checking", id="t1", dedup_status="discarded")
    data = await _service(statements=[{"id": "s1", "transactions": [txn]}]).export_all("u1")
    [statement] = data["statements"]
    [exported] = statement["transactions"]
    assert (statement["id"], exported["id"], exported["amount"]) == ("s1", "t1", "4.50")
    assert exported["dedup_status"] == "discarded"


async def test_bank_connections_are_exported_without_credentials():
    from decimal import Decimal

    bank = {
        "id": "b1",
        "name": "Chase",
        "accounts": [{"remote_id": "a1", "account_id": "checking", "balance": Decimal("12.5")}],
    }
    data = await _service(banks=[bank]).export_all("u1")
    [exported] = data["bank_connections"]
    assert exported["accounts"][0] == {
        "remote_id": "a1",
        "account_id": "checking",
        "balance": "12.5",
    }
    assert "credential_sealed" not in exported
