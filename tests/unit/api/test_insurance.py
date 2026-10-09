"""
Insurance policies, coverage targets and the coverage report over HTTP.

Each typed response must carry exactly what the insurance service returns:
amounts as decimal strings in the base currency's precision beside the
`currency` they are in.
"""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from salli.application.services.insurance_service import InsuranceService
from salli.interfaces.api.routers import insurance as router
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"
TODAY = "2026-03-20"
LIFE = {
    "name": "Term life",
    "policy_type": "life",
    "provider": "Insurer",
    "coverage_amount": 2000000,
    "premium_amount": 1250.5,
    "premium_frequency": "monthly",
    "expiry_date": "2026-03-30",
}


class _Today(datetime.date):
    @classmethod
    def today(cls) -> datetime.date:
        return datetime.date.fromisoformat(TODAY)


@pytest.fixture
def uow(mock_services, monkeypatch) -> FakeRecordsUoW:
    monkeypatch.setattr(router, "datetime", SimpleNamespace(date=_Today))
    uow = FakeRecordsUoW()
    mock_services.insurance = InsuranceService(lambda: uow)
    return uow


async def _create(client, policy: dict) -> str:
    r = await client.post("/v1/insurance/policies", json=policy, headers=AUTH)
    assert r.status_code == 201
    return r.json()["id"]


async def _set_target(client, policy_type: str, amount: float) -> str:
    r = await client.put(
        "/v1/insurance/targets",
        json={"policy_type": policy_type, "target_amount": amount},
        headers=AUTH,
    )
    assert r.status_code == 200
    return r.json()["id"]


async def test_a_policy_reads_back_as_the_service_returns_it(client, mock_services, uow):
    policy_id = await _create(client, LIFE)

    r = await client.get(f"/v1/insurance/policies/{policy_id}", headers=AUTH)
    assert r.status_code == 200
    policy = r.json()
    assert policy == await mock_services.insurance.get_policy(USER, policy_id)
    assert (policy["currency"], policy["coverage_amount"], policy["premium_amount"]) == (
        "LKR",
        "2000000.00",
        "1250.50",
    )

    r = await client.get("/v1/insurance/policies", headers=AUTH)
    assert r.json() == {"policies": [policy]}


async def test_an_update_answers_that_it_was_applied(client, mock_services, uow):
    policy_id = await _create(client, LIFE)

    r = await client.patch(
        f"/v1/insurance/policies/{policy_id}", json={"premium_amount": 1300}, headers=AUTH
    )
    assert (r.status_code, r.json()) == (200, {"updated": True})
    policy = (await client.get(f"/v1/insurance/policies/{policy_id}", headers=AUTH)).json()
    assert policy["premium_amount"] == "1300.00"


async def test_a_target_is_set_once_per_policy_type(client, mock_services, uow):
    target_id = await _set_target(client, "life", 4000000)
    assert await _set_target(client, "life", 5000000) == target_id

    r = await client.get("/v1/insurance/targets", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"targets": await mock_services.insurance.list_targets(USER)}
    assert r.json() == {
        "targets": [
            {
                "id": target_id,
                "policy_type": "life",
                "currency": "LKR",
                "target_amount": "5000000.00",
            }
        ]
    }


async def test_the_report_shows_gaps_missing_cover_and_what_expires_soon(
    client, mock_services, uow
):
    await _create(client, LIFE)
    await _set_target(client, "life", 5000000)
    await _set_target(client, "health", 1000000)

    r = await client.get("/v1/insurance/report", headers=AUTH)
    assert r.status_code == 200
    report = r.json()
    assert report == await mock_services.insurance.get_report(USER, TODAY)
    assert report == {
        "currency": "LKR",
        "lines": [
            {
                "policy_type": "life",
                "target_amount": "5000000.00",
                "actual_coverage": "2000000.00",
                "gap": "3000000.00",
            },
            {
                "policy_type": "health",
                "target_amount": "1000000.00",
                "actual_coverage": "0.00",
                "gap": "1000000.00",
            },
        ],
        "missing_types": ["health"],
        "expiring_soon": [
            {
                "policy_name": "Term life",
                "policy_type": "life",
                "expiry_date": "2026-03-30",
                "days_until_expiry": 10,
            }
        ],
    }


async def test_a_missing_policy_is_not_found(client, uow):
    assert (await client.get("/v1/insurance/policies/nope", headers=AUTH)).status_code == 404
