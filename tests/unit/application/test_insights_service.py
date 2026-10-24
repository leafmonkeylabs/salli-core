"""InsightsService: the ledger's insights in the base currency, as the API serves them."""

from __future__ import annotations

import datetime as dt
import sys
from decimal import Decimal
from typing import Any

from salli.application.services.insights_service import InsightsService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeUoW

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


def _service(
    subscriptions: list[dict[str, Any]], statements: list[dict[str, Any]] | None = None
) -> InsightsService:
    uow = FakeUoW("EUR")
    uow.ledger.accounts = list(ACCOUNTS)
    uow.ledger.entries = list(ENTRIES)
    for row in subscriptions:
        uow.recurring_subscriptions.rows[row["id"]] = {**row, "user_id": "u", "is_active": True}
    uow.statements.statements = list(statements or [])
    return InsightsService(uow.factory(), today=lambda: dt.date(2026, 10, 9))


async def test_money_is_served_as_strings_in_the_base_currency():
    flow = await _service([]).cash_flow("u", months=2)
    assert flow == {
        "currency": "EUR",
        "months": [
            {
                "month": "2026-08",
                "income": "0.00",
                "expenses": "51.99",
                "net": "-51.99",
                "savings_rate": None,
                "complete": True,
                "observed": True,
            },
            {
                "month": "2026-09",
                "income": "3000.00",
                "expenses": "51.99",
                "net": "2948.01",
                "savings_rate": "0.9827",
                "complete": True,
                "observed": True,
            },
            {
                "month": "2026-10",
                "income": "0.00",
                "expenses": "51.99",
                "net": "-51.99",
                "savings_rate": None,
                "complete": False,
                "observed": False,
            },
        ],
        # Over the two full months: (3,000 in, 103.98 out) / 2.
        "average": {
            "months_observed": ["2026-08", "2026-09"],
            "income": "1500.00",
            "expenses": "51.99",
            "net": "1448.01",
            "savings_rate": "0.9653",
        },
    }


async def test_the_average_is_over_the_full_months_observed_and_no_earlier():
    # The ledger's first income or expense is in July: twelve months asked
    # for, three observed (July to September), and October not yet over.
    flow = await _service([]).cash_flow("u", months=12)
    assert [m["month"] for m in flow["months"] if m["observed"]] == [
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert flow["average"]["months_observed"] == ["2026-07", "2026-08", "2026-09"]
    # (3,000 in; 12.99 + 51.99 + 51.99 out) / 3.
    assert (flow["average"]["income"], flow["average"]["expenses"]) == ("1000.00", "38.99")
    # The average and the months it is over agree, to the cent.
    observed = [m for m in flow["months"] if m["observed"]]
    total = sum(Decimal(m["net"]) for m in observed)
    assert Decimal(flow["average"]["net"]) == (total / len(observed)).quantize(Decimal("0.01"))


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


async def test_a_subscription_named_after_the_payee_covers_it_at_another_price():
    # Tied to the gym account, so its own matching takes these charges; the
    # amount is wrong, but it is plainly named after the payee.
    named = _subscription(id="sub2", name="FitX", account_id="gym", amount_minor=999)
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


async def test_matching_alone_does_not_make_one_subscription_cover_another():
    # Disney+ is tied to the streaming account, so the engine matched every
    # charge there: Netflix read as "tracked by Disney Plus".
    disney = _subscription(id="sub3", name="Disney Plus", amount_minor=799)
    netflix = next(
        r for r in (await _service([disney]).recurring("u"))["items"] if r["payee"] == "Netflix"
    )
    assert (netflix["tracked"], netflix["subscription_id"]) == (False, None)
    # A name alone, with no charge of its own matched, covers nothing either.
    unmatched = _subscription(id="sub4", name="FitX", account_id=None, amount_minor=999)
    fitx = next(
        r
        for r in (await _service([unmatched]).recurring("u"))["items"]
        if r["payee"] == "Fitx Studio"
    )
    assert fitx["tracked"] is False


async def test_a_yearly_subscription_does_not_cover_a_monthly_payment():
    yearly = _subscription(id="sub5", frequency="yearly")
    netflix = next(
        r for r in (await _service([yearly]).recurring("u"))["items"] if r["payee"] == "Netflix"
    )
    assert netflix["tracked"] is False


async def test_a_malformed_subscription_is_left_out_of_the_forecast_with_a_note():
    # A bad frequency (stored before it was checked) failed the whole forecast.
    bad = _subscription(id="bad", name="Old Thing", frequency="Fortnightly", account_id=None)
    result = await _service([bad]).forecast("u", days=30)
    assert any(n.startswith("Old Thing: left out") for n in result["notes"])


async def test_an_account_whose_balance_cant_be_known_is_left_out_and_said(monkeypatch):
    # Dollars posted to the euro account in a euro ledger: its balance in
    # euros was computed by skipping them, silently wrong.
    foreign = StoredJournalEntry(
        id="x1",
        user_id="u",
        entry_date="2026-10-01",
        description="ODD DOLLARS",
        source="statement",
        postings=[
            Posting(
                account_id="bank",
                direction=Direction.DEBIT,
                amount=Decimal(10),
                currency="USD",
                fx_rate=Decimal("0.9"),
            ),
            Posting(
                account_id="salary",
                direction=Direction.CREDIT,
                amount=Decimal(10),
                currency="USD",
                fx_rate=Decimal("0.9"),
            ),
        ],
    )
    accounts = [*ACCOUNTS[1:], ACCOUNTS[0].model_copy(update={"currency": "GBP"})]
    monkeypatch.setattr(sys.modules[__name__], "ACCOUNTS", accounts)
    monkeypatch.setattr(sys.modules[__name__], "ENTRIES", [*ENTRIES, foreign])
    result = await _service([]).forecast("u", days=30)
    assert result["accounts"] == []
    assert any(n.startswith("Checking: its balance in GBP can't be known") for n in result["notes"])


async def test_safe_to_spend_is_the_low_point_before_money_comes_in():
    # No salary rhythm in this ledger, so it looks 30 days ahead: FitX on
    # Nov 1 is committed; Netflix on Nov 8 falls on the last day, outside.
    # Netflix is all its spending, and scheduled: no everyday spending, and a
    # tenth of a usual month's 38.99 kept back.
    result = await _service([_subscription()]).safe_to_spend("u")
    assert (result["amount"], result["cash_today"], result["until"]) == (
        "2788.14",
        "2831.04",
        "2026-11-08",
    )
    assert (result["everyday_spending"], result["cushion"]) == ("0.00", "3.90")
    assert result["next_income"] is None
    assert [(f["date"], f["description"], f["amount"]) for f in result["committed"]] == [
        ("2026-11-01", "Fitx Studio", "-39.00")
    ]


async def test_cash_set_aside_for_a_goal_is_not_free_to_spend():
    service = _service([_subscription()])
    uow = service._uow_factory()
    uow.goals.goals = [{"id": "trip", "priority": 1}, {"id": "old", "priority": 2}]
    uow.goals.allocations = [
        {"goal_id": "trip", "account_id": "bank", "allocated_minor": 50000},
        # A goal that is gone or archived holds nothing back.
        {"goal_id": "gone", "account_id": "bank", "allocated_minor": 99999},
    ]
    result = await service.safe_to_spend("u")
    assert result["held_for_goals"] == "500.00"
    assert result["amount"] == "2288.14"
    # The amount is the low point less the cushion and the goals' cash.
    assert (result["low_point"], result["cushion"]) == ("2792.04", "3.90")
    # One figure: scenarios and principle checks read the baseline's, the same.
    from decimal import Decimal

    from salli.domain.baseline import timelines

    baseline = await service._baselines.build("u", dt.date(2026, 10, 9))
    assert timelines.safe_to_spend(baseline).amount == Decimal("2288.14")


async def test_signals_point_at_new_recurring_charges_nobody_tracks():
    result = await _service([]).signals("u")
    kinds = {(s["kind"], s["title"]) for s in result["signals"]}
    assert ("new_recurring", "New recurring payment: Fitx Studio") in kinds
    assert all(s["severity"] in ("high", "medium", "info") for s in result["signals"])
