"""InsightsService: the ledger's insights in the base currency, as the API serves them."""

from __future__ import annotations

import datetime as dt
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from salli.application.services.insights_service import InsightsService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeProfiles

ACCOUNTS = [
    Account(id="bank", user_id="u", code="1000", name="Checking", type="asset", currency="EUR"),
    Account(id="salary", user_id="u", code="4000", name="Salary", type="income", currency="EUR"),
    Account(id="tv", user_id="u", code="5100", name="Streaming", type="expense", currency="EUR"),
    Account(id="gym", user_id="u", code="5200", name="Gym", type="expense", currency="EUR"),
]


def _entry(id_: str, day: str, debit: str, credit: str, amount: str, description: str):
    leg = {"amount": Decimal(amount), "currency": "EUR"}
    return StoredJournalEntry(
        id=id_,
        user_id="u",
        entry_date=day,
        description=description,
        source="statement",
        postings=[
            Posting(account_id=debit, direction=Direction.DEBIT, **leg),
            Posting(account_id=credit, direction=Direction.CREDIT, **leg),
        ],
    )


ENTRIES = [
    _entry("s1", "2026-09-25", "bank", "salary", "3000", "ACME GMBH SALARY"),
    *(
        _entry(f"n{i}", day, "tv", "bank", "12.99", f"NETFLIX.COM {i}")
        for i, day in enumerate(["2026-07-08", "2026-08-08", "2026-09-08", "2026-10-08"])
    ),
    *(
        _entry(f"g{i}", day, "gym", "bank", "39", "FITX STUDIO")
        for i, day in enumerate(["2026-08-01", "2026-09-01", "2026-10-01"])
    ),
]


def _subscription(**kw: Any) -> dict[str, Any]:
    return {
        "id": "sub1",
        "name": "Video",
        "amount_minor": 1299,
        "frequency": "monthly",
        "next_due_date": "2026-10-12",
        "account_id": "tv",
        "grace_days": 5,
        "amount_tolerance_pct": "0.05",
        **kw,
    }


def _service(subscriptions: list[dict[str, Any]]) -> InsightsService:
    uow = SimpleNamespace(
        ledger=SimpleNamespace(
            get_accounts=AsyncMock(return_value=ACCOUNTS),
            get_entries=AsyncMock(return_value=ENTRIES),
        ),
        user_profiles=FakeProfiles("EUR"),
        recurring_subscriptions=SimpleNamespace(list=AsyncMock(return_value=subscriptions)),
    )

    @asynccontextmanager
    async def factory():
        yield uow

    return InsightsService(factory, today=lambda: dt.date(2026, 10, 9))


async def test_money_is_served_as_strings_in_the_base_currency():
    flow = await _service([]).cash_flow("u", months=2)
    assert flow == {
        "currency": "EUR",
        "months": [
            {
                "month": "2026-09",
                "income": "3000.00",
                "expenses": "51.99",
                "net": "2948.01",
                "savings_rate": "0.9827",
            },
            {
                "month": "2026-10",
                "income": "0.00",
                "expenses": "51.99",
                "net": "-51.99",
                "savings_rate": None,
            },
        ],
    }


async def test_spending_lines_carry_shares_and_each_month():
    spent = await _service([]).spending("u", months=1, by="account")
    assert spent["months"] == ["2026-10"]
    assert [(line["key"], line["total"], line["share"]) for line in spent["lines"]] == [
        ("Gym", "39.00", "0.7501"),
        ("Streaming", "12.99", "0.2499"),
    ]
    assert spent["lines"][0]["by_month"] == {"2026-10": "39.00"}


async def test_net_worth_points_end_each_month():
    worth = await _service([]).net_worth("u", months=2)
    assert [p["net_worth"] for p in worth["points"]] == ["2883.03", "2831.04"]


async def test_a_recurring_payment_a_subscription_matches_is_tracked():
    found = await _service([_subscription()]).recurring("u")
    by_payee = {r["payee"]: r for r in found["items"]}
    assert set(by_payee) == {"Netflix", "Fitx Studio"}
    netflix = by_payee["Netflix"]
    assert (netflix["tracked"], netflix["subscription_id"]) == (True, "sub1")
    assert (netflix["typical_amount"], netflix["currency"], netflix["cadence"]) == (
        "12.99",
        "EUR",
        "monthly",
    )
    assert (by_payee["Fitx Studio"]["tracked"], by_payee["Fitx Studio"]["subscription_id"]) == (
        False,
        None,
    )


async def test_a_subscription_named_after_the_payee_covers_it_even_unmatched():
    # Declared against the wrong account and amount: the engine matches none of
    # its charges, but it is plainly the same subscription.
    named = _subscription(id="sub2", name="FitX", account_id=None, amount_minor=999)
    found = await _service([named]).recurring("u")
    fitx = next(r for r in found["items"] if r["payee"] == "Fitx Studio")
    assert (fitx["tracked"], fitx["subscription_id"]) == (True, "sub2")


async def test_the_forecast_carries_cash_forward_without_counting_a_subscription_twice():
    # Netflix is both seen in the ledger and declared (sub1): one charge a month.
    result = await _service([_subscription()]).forecast("u", days=30)
    assert (result["start"], result["end"], result["currency"]) == (
        "2026-10-09",
        "2026-11-08",
        "EUR",
    )
    assert result["today"] == "2831.04"
    assert [(f["date"], f["description"], f["amount"]) for f in result["flows"]] == [
        ("2026-11-01", "Fitx Studio", "-39.00"),
        ("2026-11-08", "Netflix", "-12.99"),
    ]
    assert (result["end_balance"], result["lowest"], result["lowest_date"]) == (
        "2779.05",
        "2779.05",
        "2026-11-08",
    )
    [bank] = result["accounts"]
    assert (bank["account_id"], bank["name"], bank["currency"]) == ("bank", "Checking", "EUR")


async def test_a_declared_subscription_the_ledger_has_not_shown_is_forecast_too():
    spotify = _subscription(
        id="sub3", name="Spotify", account_id=None, amount_minor=999, next_due_date="2026-10-20"
    )
    result = await _service([spotify]).forecast("u", days=30)
    declared = [f for f in result["flows"] if f["source"] == "subscription"]
    assert [(f["date"], f["amount"], f["account_id"]) for f in declared] == [
        ("2026-10-20", "-9.99", None)
    ]
