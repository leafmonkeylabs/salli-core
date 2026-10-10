"""Exporting a real database's ledger, closed accounts included, and loading it in Beancount."""

from __future__ import annotations

from decimal import Decimal

from beancount import loader

from salli.application.services.data_portability_service import DataPortabilityService
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres


async def test_the_whole_ledger_exports_and_loads(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "EUR"})
    ledger = LedgerService(uow_factory)
    bank = await ledger.add_account("u1", "1000", "Bank", "asset")
    food = await ledger.add_account("u1", "5000", "Food", "expense")
    old = await ledger.add_account("u1", "5900", "Old", "expense")
    for account, amount in ((food, "12.50"), (old, "3.00")):
        await ledger.add_entry(
            "u1",
            "2026-10-01",
            "Spend",
            "manual",
            [
                {"account_id": account, "direction": Direction.DEBIT, "amount": Decimal(amount)},
                {"account_id": bank, "direction": Direction.CREDIT, "amount": Decimal(amount)},
            ],
        )
    await ledger.deactivate_account("u1", old)

    export = DataPortabilityService(uow_factory, *([None] * 12))
    text = await export.export_plaintext("u1", "beancount")
    entries, errors, options = loader.load_string(text)
    assert errors == []
    assert options["operating_currency"] == ["EUR"]
    assert "Expenses:Old" in text and 'salli-status: "inactive"' in text
