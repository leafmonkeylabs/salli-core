"""
`GET /v1/baseline` over HTTP: the real service over the household ledger
(tests/golden/household.py), so the typed response is what it computes.
"""

from __future__ import annotations

import pytest

from salli.application.services.baseline_service import BaselineService
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

USER = "test-user-1"


def _household_of(user: str) -> FakeUoW:
    """The household's books, as `user`'s."""
    uow = h.uow()
    uow.ledger.accounts = [a.model_copy(update={"user_id": user}) for a in uow.ledger.accounts]
    uow.ledger.entries = [e.model_copy(update={"user_id": user}) for e in uow.ledger.entries]
    for row in uow.debts.rows.values():
        row["user_id"] = user
    return uow


@pytest.fixture
def uow(mock_services) -> FakeUoW:
    books = _household_of(USER)
    mock_services.baseline = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)
    return books


async def test_the_baseline_says_the_definitions_behind_every_figure(client, uow):
    r = await client.get("/v1/baseline", params={"horizon_years": 2}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()

    assert (body["as_of"], body["currency"]) == ("2026-10-11", "EUR")
    assert body["months_observed"] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]
    assert body["flows"]["monthly_income"] == "4000.00"
    assert body["flows"]["monthly_expenses"] == "2037.09"
    assert body["rates"] == [
        {"currency": "USD", "rate": "0.86", "source": "ecb", "as_of": "2026-10-09"}
    ]
    roles = {b["account_id"]: b["role"] for b in body["balances"]}
    assert (roles["brk"], roles["flat"], roles["card"]) == (
        "investment",
        "other_asset",
        "liability",
    )
    assert body["totals"]["net_worth"] == "335901.47"
    assert [(d["debt_id"], d["source"]) for d in body["debts"]] == [
        ("debt-car", "account"),
        ("debt-student", "declared"),
    ]
    assert body["placeholders"] == ["real_return", "safe_withdrawal_rate", "inflation"]
    # The as-of month and the twelve after it, every day of them.
    assert (body["cash"]["start"], body["cash"]["end"]) == ("2026-10-11", "2027-10-31")
    assert len(body["cash"]["month_ends"]) == 13
    assert len(body["cash"]["daily"]) == 386
    # The as-of point, then each month's end to two years after the as-of month.
    assert len(body["monthly"]["points"]) == 1 + 2 * 12 + 1
    assert body["monthly"]["points"][0]["net_worth"] == body["totals"]["net_worth"]

    # Without the day-by-day series, its month-ends and lowest point stay.
    lean = (await client.get("/v1/baseline", params={"daily": False}, headers=AUTH)).json()
    assert lean["cash"]["daily"] is None
    assert lean["cash"]["lowest"] == body["cash"]["lowest"]
    # Reading it stored nothing.
    assert uow.fi_scores.rows == []


async def test_a_past_day_is_read_and_a_future_one_refused(client, uow):
    r = await client.get("/v1/baseline", params={"as_of": "2026-06-30"}, headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["as_of"] == "2026-06-30"
    # As of June 30th, May is the last full month: April and May observed.
    assert body["months_observed"] == ["2026-04", "2026-05"]

    r = await client.get("/v1/baseline", params={"as_of": "2026-10-12"}, headers=AUTH)
    assert r.status_code == 422
    assert "after today" in r.json()["detail"]


@pytest.mark.parametrize("years", [0, 51])
async def test_a_horizon_is_one_to_fifty_years(client, uow, years):
    r = await client.get("/v1/baseline", params={"horizon_years": years}, headers=AUTH)
    assert r.status_code == 422


async def test_someone_elses_books_are_not_in_yours(client, mock_services):
    """The household belongs to someone else: the caller's baseline is empty."""
    books = _household_of("someone-else")
    mock_services.baseline = BaselineService(books.factory(), fx=h.fx(), today=lambda: h.AS_OF)

    body = (await client.get("/v1/baseline", headers=AUTH)).json()
    assert body["balances"] == [] and body["debts"] == []
    assert body["months_observed"] == []
    assert body["totals"]["net_worth"] == "0.00"
