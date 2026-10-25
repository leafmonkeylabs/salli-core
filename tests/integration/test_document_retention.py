"""How long a document is kept, against a real database: a retention period
the person chose keeps it until then, and an entry citing it keeps it while
no retention period has passed."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.services.document_service import DocumentRetained, DocumentService
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


class _Storage:
    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        return f"{user_id}/{key}"


async def test_a_retained_or_cited_document_is_not_deleted(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("noor", {"base_currency": "AED"})
    day = [dt.date(2031, 1, 10)]
    docs = DocumentService(uow_factory, _Storage(), today=lambda: day[0])  # type: ignore[arg-type]

    loose = await docs.save_document("noor", "Note", "text")
    receipt = (await docs.save_file("noor", "receipt.pdf", b"%PDF"))["id"]
    ledger = LedgerService(uow_factory)
    cash = await ledger.add_account("noor", "1000", "Cash", "asset")
    food = await ledger.add_account("noor", "5000", "Food", "expense")
    legs = [
        {"account_id": food, "direction": Direction.DEBIT, "amount": Decimal("9")},
        {"account_id": cash, "direction": Direction.CREDIT, "amount": Decimal("9")},
    ]
    await ledger.add_entry("noor", "2031-01-09", "Lunch", "manual", legs, external_ref=receipt)

    with pytest.raises(DocumentRetained, match="cites"):
        await docs.delete_document("noor", receipt)
    await docs.delete_document("noor", loose)

    async with uow_factory() as uow:
        await uow.user_profiles.upsert("noor", {"document_retention_years": 6})
    kept = (await docs.save_file("noor", "invoice.pdf", b"%PDF"))["id"]
    stored = await docs.get_document("noor", kept)
    assert stored is not None and stored["retain_until"] == "2037-01-10"
    with pytest.raises(DocumentRetained, match="2037-01-10"):
        await docs.delete_document("noor", kept)
    day[0] = dt.date(2037, 1, 10)
    await docs.delete_document("noor", kept)
