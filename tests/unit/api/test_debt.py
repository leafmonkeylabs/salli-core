"""
Debts over HTTP.

Each typed response must carry exactly what the debt service returns: amounts
as decimal strings in the base currency's precision, and the APR as the
decimal string it is stored as (a rate, not money).
"""

from __future__ import annotations

from salli.application.services.debt_service import DebtService
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"
CARD = {"name": "Card", "principal": 1000, "apr": 0.24, "minimum_payment": 100}


def _uow(mock_services, base_currency: str = "LKR") -> FakeRecordsUoW:
    uow = FakeRecordsUoW(base_currency)
    mock_services.debt = DebtService(lambda: uow)
    return uow


async def _create(client, debt: dict) -> str:
    r = await client.post("/v1/debt/", json=debt, headers=AUTH)
    assert r.status_code == 201
    return r.json()["id"]


async def test_a_debt_reads_back_as_the_service_returns_it(client, mock_services):
    _uow(mock_services)
    debt_id = await _create(client, CARD)

    r = await client.get(f"/v1/debt/{debt_id}", headers=AUTH)
    assert r.status_code == 200
    debt = r.json()
    assert debt == await mock_services.debt.get_debt(USER, debt_id)
    assert (debt["currency"], debt["principal"], debt["minimum_payment"]) == (
        "LKR",
        "1000.00",
        "100.00",
    )
    assert debt["apr"] == "0.24"

    r = await client.get("/v1/debt/", headers=AUTH)
    assert r.json() == {"debts": [debt]}


async def test_an_update_answers_that_it_was_applied(client, mock_services):
    _uow(mock_services)
    debt_id = await _create(client, CARD)

    r = await client.patch(f"/v1/debt/{debt_id}", json={"is_active": False}, headers=AUTH)
    assert (r.status_code, r.json()) == (200, {"updated": True})
    assert (await client.get("/v1/debt/", headers=AUTH)).json() == {"debts": []}
    r = await client.get("/v1/debt/", params={"active_only": False}, headers=AUTH)
    assert [d["is_active"] for d in r.json()["debts"]] == [False]


async def test_the_payoff_plan_is_the_services_plan(client, mock_services):
    _uow(mock_services)
    await _create(client, CARD)

    r = await client.get(
        "/v1/debt/payoff-plan",
        params={"strategy": "snowball", "extra_monthly_payment": 50},
        headers=AUTH,
    )
    assert r.status_code == 200
    plan = r.json()
    assert plan == await mock_services.debt.get_payoff_plan(USER, 50, "snowball")
    assert (plan["strategy"], plan["currency"], plan["months_to_payoff"]) == (
        "snowball",
        "LKR",
        8,
    )
    assert plan["schedule"][0] == {
        "month": 1,
        "debt_name": "Card",
        "payment": "150.00",
        "principal_paid": "130.00",
        "interest_paid": "20.00",
        "remaining_balance": "870.00",
    }


async def test_a_plan_with_nothing_owed_states_zero_in_the_currencys_precision(
    client, mock_services
):
    """The engine's total for no debts is a bare 0; an amount always carries
    its currency's decimals, so it reads "0.00", like every other total."""
    _uow(mock_services)
    plan = (await client.get("/v1/debt/payoff-plan", headers=AUTH)).json()
    assert plan == {
        "strategy": "avalanche",
        "currency": "LKR",
        "months_to_payoff": 0,
        "total_interest_paid": "0.00",
        "schedule": [],
    }

    _uow(mock_services, base_currency="KWD")
    plan = (await client.get("/v1/debt/payoff-plan", headers=AUTH)).json()
    assert plan["total_interest_paid"] == "0.000"


async def test_a_plan_that_never_finishes_has_no_payoff_month(client, mock_services):
    _uow(mock_services)
    # The minimum payment never covers the interest.
    await _create(client, {**CARD, "minimum_payment": 10})

    plan = (await client.get("/v1/debt/payoff-plan", headers=AUTH)).json()
    assert plan["months_to_payoff"] is None
    assert plan["schedule"][-1]["month"] == 600


async def test_a_missing_debt_is_not_found(client, mock_services):
    _uow(mock_services)
    assert (await client.get("/v1/debt/nope", headers=AUTH)).status_code == 404


async def test_money_sent_as_a_string_is_kept_exactly(client, mock_services):
    # As a JSON number this would go through a float and lose its last digits.
    _uow(mock_services)
    debt_id = await _create(
        client,
        {
            "name": "Mortgage",
            "principal": "12345678901234567.89",
            "apr": "0.0725",
            "minimum_payment": "1500.10",
        },
    )
    debt = (await client.get(f"/v1/debt/{debt_id}", headers=AUTH)).json()
    assert (debt["principal"], debt["minimum_payment"]) == ("12345678901234567.89", "1500.10")
