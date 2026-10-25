"""Bank reconciliation against a real database: a statement's closing
balance against the cleared postings, completed only at a difference of
zero, and the cleared flag the one change a closed month's posting takes."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.application.services.reconciliation_service import Reconciled, ReconciliationService
from salli.domain.accounting.models import Direction
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _legs(debit: str, credit: str, amount: str) -> list[dict[str, object]]:
    return [
        {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(amount)},
        {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(amount)},
    ]


async def test_a_statement_reconciles_only_at_a_difference_of_zero(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("kofi", {"base_currency": "GHS"})
    ledger = LedgerService(uow_factory, today=lambda: dt.date(2031, 3, 10))
    bank = await ledger.add_account("kofi", "1000", "Bank", "asset")
    pay = await ledger.add_account("kofi", "4000", "Pay", "income")
    food = await ledger.add_account("kofi", "5000", "Food", "expense")
    await ledger.add_entry("kofi", "2031-01-31", "Pay", "manual", _legs(bank, pay, "900"))
    await ledger.add_entry("kofi", "2031-02-03", "Market", "manual", _legs(food, bank, "40"))
    await ledger.add_entry("kofi", "2031-02-27", "Not yet", "manual", _legs(food, bank, "15"))
    # The month is closed: clearing is still allowed.
    await ledger.set_lock_date("kofi", "2031-02-28")

    service = ReconciliationService(uow_factory)
    status = await service.add_statement(
        "kofi",
        account_id=bank,
        period_start="2031-02-01",
        period_end="2031-02-28",
        opening_balance=Decimal("900"),
        closing_balance=Decimal("860"),
    )
    assert (status["cleared_total"], status["difference"]) == ("900.00", "-40.00")
    [market] = [p for p in status["postings"] if p["description"] == "Market"]
    assert market["amount"] == "-40.00"

    with pytest.raises(ValueError, match="difference of zero"):
        await service.complete("kofi", status["statement_id"], "session")
    with pytest.raises(ValueError, match="Not a posting"):
        await service.clear("kofi", status["statement_id"], ["elsewhere"])

    cleared = await service.clear("kofi", status["statement_id"], [market["posting_id"]])
    assert cleared is not None and cleared["difference"] == "0.00"
    done = await service.complete("kofi", status["statement_id"], "session")
    assert done is not None and done["reconciliation"]["completed_by"] == "session"
    assert done["reconciliation"]["cleared_total"] == "860.00"

    with pytest.raises(Reconciled):
        await service.clear("kofi", status["statement_id"], [market["posting_id"]], False)
    [listed] = await service.list_statements("kofi")
    assert listed["reconciliation"] is not None
