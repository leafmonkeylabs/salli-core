"""
The baseline built from a real database: each user's from their own books
only, as of a day (nothing dated after it read), with a linked debt counted
once and an account's role as stored.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.debt_service import DebtService
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from tests.fakes import FakeFx
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]

AS_OF = dt.date(2026, 9, 15)


def _legs(debit: str, credit: str, amount: str, **kw: object) -> list[dict[str, object]]:
    return [
        {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(amount), **kw},
        {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(amount), **kw},
    ]


async def _books(uow_factory, user: str) -> dict[str, str]:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(user, {"base_currency": "ZAR"})
    ledger = LedgerService(uow_factory, fx=FakeFx({("USD", "ZAR", None): (Decimal("17.5"), "x")}))
    ids = {
        "bank": await ledger.add_account(user, "1000", "Bank", "asset"),
        "usd": await ledger.add_account(user, "1100", "Dollars", "asset", currency="USD"),
        "funds": await ledger.add_account(user, "1300", "Funds", "asset", asset_role="investment"),
        "loan": await ledger.add_account(user, "2100", "Loan", "liability"),
        "equity": await ledger.add_account(user, "3000", "Equity", "equity"),
        "pay": await ledger.add_account(user, "4000", "Pay", "income"),
        "food": await ledger.add_account(user, "5000", "Food", "expense"),
    }
    add = ledger.add_entry
    await add(user, "2026-06-30", "Opening", "manual", _legs(ids["bank"], ids["equity"], "10000"))
    await add(user, "2026-06-30", "Opening", "manual", _legs(ids["funds"], ids["equity"], "50000"))
    await add(user, "2026-06-30", "Opening", "manual", _legs(ids["equity"], ids["loan"], "30000"))
    await add(
        user,
        "2026-06-30",
        "Opening",
        "manual",
        _legs(ids["usd"], ids["equity"], "100", currency="USD", fx_rate=Decimal("18")),
    )
    for month in ("2026-07", "2026-08", "2026-09"):
        await add(user, f"{month}-01", "PAY", "statement", _legs(ids["bank"], ids["pay"], "20000"))
        await add(user, f"{month}-05", "SHOP", "statement", _legs(ids["food"], ids["bank"], "6000"))
    # After the as-of date: never part of the baseline as of it.
    await add(user, "2026-09-20", "PAY", "statement", _legs(ids["bank"], ids["pay"], "99999"))
    return ids


async def test_a_users_baseline_is_their_own_books_as_of_the_day(uow_factory):
    alice = await _books(uow_factory, "alice")
    await _books(uow_factory, "bob")
    await DebtService(uow_factory).add_debt(
        "alice",
        {
            "name": "Loan",
            "principal": "31000",
            "apr": "0.11",
            "minimum_payment": "900",
            "account_id": alice["loan"],
        },
    )
    fx = FakeFx({("USD", "ZAR", AS_OF.isoformat()): (Decimal("17.25"), "sarb", "2026-09-15")})
    baseline = await BaselineService(uow_factory, fx=fx, today=lambda: AS_OF).build("alice")

    assert {b.account_id for b in baseline.balances} <= set(alice.values())
    by_id = {b.account_id: b for b in baseline.balances}
    # 10,000 + 2 × (20,000 − 6,000) + 20,000 − 6,000 in September: the 99,999
    # on the 20th isn't counted.
    assert by_id[alice["bank"]].value == Decimal("52000.00")
    # 100 USD at the published 17.25, not the 18 it was booked at.
    assert by_id[alice["usd"]].value == Decimal("1725.00")
    assert by_id[alice["funds"]].role == "investment"
    assert baseline.flows.months == ("2026-07", "2026-08")
    assert (baseline.flows.income, baseline.flows.expenses) == (Decimal(20000), Decimal(6000))
    # The linked loan is the account's 30,000, counted once.
    [loan] = baseline.debts
    assert (loan.source, loan.balance) == ("account", Decimal("30000.00"))
    assert baseline.total_liabilities == Decimal("30000.00")
    assert fx.asked == [("USD", "ZAR", "2026-09-15")]

    bob = await BaselineService(uow_factory, fx=fx, today=lambda: AS_OF).build("bob")
    assert bob.debts == ()
    assert not {b.account_id for b in bob.balances} & set(alice.values())
