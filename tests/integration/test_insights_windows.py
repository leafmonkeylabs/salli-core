"""Insights read only their window, and answer exactly as reading everything
did: a five-year ledger took over a second per call."""

from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction
from salli.domain.reports import insights
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

TODAY = dt.date(2026, 10, 9)


async def test_windowed_insights_answer_as_the_whole_ledger_does(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD"})
    ledger = LedgerService(uow_factory)
    bank = await ledger.add_account("u1", "1000", "Checking", "asset")
    card = await ledger.add_account("u1", "2000", "Card", "liability")
    euros = await ledger.add_account("u1", "1100", "Euro account", "asset", "EUR")
    food = await ledger.add_account("u1", "5000", "Food", "expense")
    salary = await ledger.add_account("u1", "4000", "Salary", "income")
    rng = random.Random(3)
    day = dt.date(2021, 10, 1)
    while day <= TODAY:
        await ledger.add_entry(
            "u1",
            day.isoformat(),
            "ACME PAYROLL",
            "manual",
            [
                {"account_id": bank, "direction": Direction.DEBIT, "amount": Decimal("3000.00")},
                {"account_id": salary, "direction": Direction.CREDIT, "amount": Decimal("3000.00")},
            ],
        )
        spent = Decimal(rng.randint(100, 900)) + Decimal("0.37")
        await ledger.add_entry(
            "u1",
            (day + dt.timedelta(days=9)).isoformat(),
            "GROCER",
            "manual",
            [
                {"account_id": food, "direction": Direction.DEBIT, "amount": spent},
                {"account_id": card, "direction": Direction.CREDIT, "amount": spent},
            ],
        )
        # A euro transfer at an exact but long rate: the SQL sum must not round.
        await ledger.add_entry(
            "u1",
            (day + dt.timedelta(days=12)).isoformat(),
            "TO EUROS",
            "manual",
            [
                {
                    "account_id": euros,
                    "direction": Direction.DEBIT,
                    "amount": Decimal("100.01"),
                    "currency": "EUR",
                    "fx_rate": Decimal("1.08345678"),
                },
                {
                    "account_id": bank,
                    "direction": Direction.CREDIT,
                    "amount": Decimal("100.01"),
                    "currency": "EUR",
                    "fx_rate": Decimal("1.08345678"),
                },
            ],
        )
        day = (day.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    await ledger.deactivate_account("u1", euros)  # closed, and still owned

    service = InsightsService(uow_factory, today=lambda: TODAY)
    async with uow_factory() as uow:
        accounts = await uow.ledger.get_accounts("u1", include_inactive=True)
        everything = await uow.ledger.get_entries("u1")

    window = insights.last_months(TODAY, 24)
    full = insights.net_worth_series(everything, accounts, window)
    served = (await service.net_worth("u1", months=24))["points"]
    assert [p["net_worth"] for p in served] == [
        str(p.net_worth.quantize(Decimal("0.01"))) for p in full
    ]

    # Twelve full months, then this month so far: what is dated after today
    # (October's groceries, on the 10th) hasn't happened yet.
    so_far = [e for e in everything if e.entry_date <= TODAY.isoformat()]
    flows = insights.cash_flow(so_far, accounts, insights.last_months(TODAY, 13))
    served_flows = (await service.cash_flow("u1", months=12))["months"]
    assert [m["net"] for m in served_flows] == [str(f.net.quantize(Decimal("0.01"))) for f in flows]

    lines = insights.spending(everything, accounts, insights.last_months(TODAY, 3))
    served_lines = (await service.spending("u1", months=3))["lines"]
    assert [line["total"] for line in served_lines] == [
        str(line.total.quantize(Decimal("0.01"))) for line in lines
    ]

    # The forecast's balances: each account's totals per currency, summed in SQL.
    async with uow_factory() as uow:
        totals = await uow.ledger.posting_totals("u1", [bank, euros])
    expected: dict[tuple[str, str], list[Decimal]] = {}
    for entry in everything:
        for p in entry.postings:
            if p.account_id in (bank, euros):
                signed = Decimal(p.direction.value) * p.amount
                pair = expected.setdefault((p.account_id, p.currency), [Decimal(0), Decimal(0)])
                pair[0] += signed
                pair[1] += signed * p.fx_rate
    assert {(a, c): [amount, base] for a, c, amount, base in totals} == expected

    # Summed to a day, they leave out what is dated after it.
    cutoff = "2024-06-30"
    async with uow_factory() as uow:
        to_day = await uow.ledger.posting_totals("u1", [bank], to_date=cutoff)
    upto: dict[tuple[str, str], list[Decimal]] = {}
    for entry in everything:
        for p in entry.postings:
            if p.account_id == bank and entry.entry_date <= cutoff:
                signed = Decimal(p.direction.value) * p.amount
                pair = upto.setdefault((p.account_id, p.currency), [Decimal(0), Decimal(0)])
                pair[0] += signed
                pair[1] += signed * p.fx_rate
    assert {(a, c): [amount, base] for a, c, amount, base in to_day} == upto


async def test_the_record_of_money_in_and_out_begins_with_its_first_unreversed_entry(
    uow_factory,
):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u2", {"base_currency": "NOK"})
        await uow.user_profiles.upsert("u3", {"base_currency": "NOK"})
    ledger = LedgerService(uow_factory)
    bank = await ledger.add_account("u2", "1000", "Bank", "asset")
    equity = await ledger.add_account("u2", "3000", "Equity", "equity")
    food = await ledger.add_account("u2", "5000", "Food", "expense")
    other_bank = await ledger.add_account("u3", "1000", "Bank", "asset")
    other_food = await ledger.add_account("u3", "5000", "Food", "expense")

    def legs(debit: str, credit: str, amount: str) -> list[dict[str, object]]:
        return [
            {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(amount)},
            {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(amount)},
        ]

    await ledger.add_entry("u2", "2026-01-31", "Opening", "manual", legs(bank, equity, "900"))
    mistake = await ledger.add_entry("u2", "2026-02-10", "OOPS", "manual", legs(food, bank, "5"))
    await ledger.reverse_entry("u2", mistake)
    await ledger.add_entry("u2", "2026-04-02", "GROCER", "manual", legs(food, bank, "20"))
    await ledger.add_entry(
        "u3", "2025-01-01", "GROCER", "manual", legs(other_food, other_bank, "1")
    )

    async with uow_factory() as uow:
        # Not the opening balance (no income or expense), not the reversed
        # mistake or its reversal, not another user's.
        assert await uow.ledger.first_flow_date("u2") == "2026-04-02"
        assert await uow.ledger.first_flow_date("u2", to_date="2026-03-31") is None
        assert await uow.ledger.first_flow_date("u3") == "2025-01-01"
