"""
Subscriptions and their reports over HTTP.

Each typed response must carry exactly what the subscription service returns:
amounts as decimal strings in the base currency's precision, a null where a
subscription has no account or an alert has no amounts, and the tolerance as
the decimal-string fraction it is stored as.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from salli.application.services.subscription_service import SubscriptionService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.interfaces.api.routers import subscriptions as router
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"
TODAY = "2026-03-20"
STREAMING = {
    "name": "Streaming",
    "amount": 2990,
    "frequency": "monthly",
    "next_due_date": "2026-01-05",
    "account_id": "streaming",
}
GYM = {"name": "Gym", "amount": 5000, "frequency": "monthly", "next_due_date": "2026-03-01"}


class _Today(datetime.date):
    @classmethod
    def today(cls) -> datetime.date:
        return datetime.date.fromisoformat(TODAY)


@pytest.fixture
def uow(mock_services, monkeypatch) -> FakeRecordsUoW:
    monkeypatch.setattr(router, "datetime", SimpleNamespace(date=_Today))
    uow = FakeRecordsUoW()
    uow.ledger.accounts = [
        Account(
            id="streaming",
            user_id=USER,
            code="5100",
            name="Streaming",
            type="expense",
            currency="LKR",
        ),
        Account(id="cash", user_id=USER, code="1000", name="Cash", type="asset", currency="LKR"),
    ]
    uow.ledger.entries = [_charge("2026-01-05", "2990"), _charge("2026-02-05", "3490")]
    mock_services.subscription = SubscriptionService(lambda: uow)
    return uow


def _charge(entry_date: str, amount: str) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=f"e-{entry_date}",
        user_id=USER,
        entry_date=entry_date,
        description="charge",
        source="statement",
        postings=[
            Posting(
                account_id="streaming",
                direction=Direction.DEBIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
            Posting(
                account_id="cash",
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
        ],
    )


async def _create(client, subscription: dict) -> str:
    r = await client.post("/v1/subscriptions/", json=subscription, headers=AUTH)
    assert r.status_code == 201
    return r.json()["id"]


async def test_a_subscription_reads_back_as_the_service_returns_it(client, mock_services, uow):
    streaming_id = await _create(client, STREAMING)
    gym_id = await _create(client, GYM)

    r = await client.get(f"/v1/subscriptions/{streaming_id}", headers=AUTH)
    assert r.status_code == 200
    streaming = r.json()
    assert streaming == await mock_services.subscription.get_subscription(USER, streaming_id)
    assert (streaming["amount"], streaming["currency"], streaming["frequency"]) == (
        "2990.00",
        "LKR",
        "monthly",
    )
    assert (streaming["grace_days"], streaming["amount_tolerance_pct"]) == (5, "0.05")

    gym = (await client.get(f"/v1/subscriptions/{gym_id}", headers=AUTH)).json()
    assert gym["account_id"] is None

    r = await client.get("/v1/subscriptions/", headers=AUTH)
    assert r.json() == {"subscriptions": [streaming, gym]}


async def test_an_update_answers_that_it_was_applied(client, mock_services, uow):
    subscription_id = await _create(client, STREAMING)

    r = await client.patch(
        f"/v1/subscriptions/{subscription_id}", json={"amount": 3490}, headers=AUTH
    )
    assert (r.status_code, r.json()) == (200, {"updated": True})
    subscription = (await client.get(f"/v1/subscriptions/{subscription_id}", headers=AUTH)).json()
    assert subscription["amount"] == "3490.00"


async def test_a_report_shows_matches_and_alerts(client, mock_services, uow):
    subscription_id = await _create(client, STREAMING)

    r = await client.get(f"/v1/subscriptions/{subscription_id}/report", headers=AUTH)
    assert r.status_code == 200
    report = r.json()
    assert report == await mock_services.subscription.get_report(USER, subscription_id, TODAY)
    assert (report["subscription_id"], report["currency"]) == (subscription_id, "LKR")
    assert [(m["entry_date"], m["amount"]) for m in report["matches"]] == [
        ("2026-01-05", "2990.00"),
        ("2026-02-05", "3490.00"),
    ]
    price_change, missed = report["alerts"]
    assert (price_change["kind"], price_change["expected_amount"]) == ("price_change", "2990.00")
    assert price_change["actual_amount"] == "3490.00"
    assert (missed["kind"], missed["expected_amount"], missed["actual_amount"]) == (
        "missed_charge",
        None,
        None,
    )


async def test_all_reports_cover_every_active_subscription(client, mock_services, uow):
    await _create(client, STREAMING)
    gym_id = await _create(client, GYM)

    r = await client.get("/v1/subscriptions/reports", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body == {"reports": await mock_services.subscription.get_all_reports(USER, TODAY)}
    gym = body["reports"][1]
    assert (gym["subscription_id"], gym["matches"]) == (gym_id, [])
    assert [a["kind"] for a in gym["alerts"]] == ["missed_charge"]


@pytest.mark.parametrize("path", ["/v1/subscriptions/nope", "/v1/subscriptions/nope/report"])
async def test_a_missing_subscription_is_not_found(client, uow, path):
    assert (await client.get(path, headers=AUTH)).status_code == 404
