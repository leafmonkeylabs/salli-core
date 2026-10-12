"""
A holding's link to the investment account that holds it (decision lab 3b,
decision 17): set on `PATCH /v1/portfolio/{id}` (or when adding one), read
back on the holding, refused for an account that isn't the caller's own
investment account, and removed with null.
"""

from __future__ import annotations

from salli.application.services.portfolio_service import PortfolioService
from salli.domain.accounting.models import Account
from tests.fakes import FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"
FUND = {"symbol": "FUND", "name": "My index fund", "asset_class": "equity"}


def _uow(mock_services) -> FakeRecordsUoW:
    uow = FakeRecordsUoW("CAD")
    for id_, code, type_, role in (
        ("brk", "1300", "asset", "investment"),
        ("chk", "1000", "asset", "cash"),
        ("card", "2000", "liability", None),
    ):
        uow.ledger.accounts.append(
            Account(
                id=id_,
                user_id=USER,
                code=code,
                name=id_.title(),
                type=type_,  # type: ignore[arg-type]
                currency="CAD",
                asset_role=role,  # type: ignore[arg-type]
            )
        )
    mock_services.portfolio = PortfolioService(lambda: uow)
    return uow


async def _create(client, holding: dict) -> str:
    r = await client.post("/v1/portfolio/", json=holding, headers=AUTH)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_a_holding_links_to_its_investment_account_and_unlinks(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, FUND)
    assert (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()[
        "account_id"
    ] is None

    r = await client.patch(f"/v1/portfolio/{holding_id}", json={"account_id": "brk"}, headers=AUTH)
    assert (r.status_code, r.json()) == (200, {"updated": True})
    assert (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()[
        "account_id"
    ] == "brk"

    # Another field leaves the link as it is; null removes it.
    await client.patch(f"/v1/portfolio/{holding_id}", json={"name": "Fund"}, headers=AUTH)
    assert (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()[
        "account_id"
    ] == "brk"
    await client.patch(f"/v1/portfolio/{holding_id}", json={"account_id": None}, headers=AUTH)
    assert (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()[
        "account_id"
    ] is None


async def test_a_holding_can_be_linked_when_it_is_added(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, {**FUND, "account_id": "brk"})
    holding = (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()
    assert holding["account_id"] == "brk"


async def test_only_an_investment_account_holds_a_holding(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, FUND)
    for account, says in (("chk", "role cash"), ("card", "liability account")):
        r = await client.patch(
            f"/v1/portfolio/{holding_id}", json={"account_id": account}, headers=AUTH
        )
        assert r.status_code == 422
        assert says in r.json()["detail"]
        assert "--asset-role investment" in r.json()["detail"]


async def test_someone_elses_account_is_not_found(client, mock_services):
    _uow(mock_services)
    holding_id = await _create(client, FUND)
    r = await client.patch(
        f"/v1/portfolio/{holding_id}", json={"account_id": "not-mine"}, headers=AUTH
    )
    assert r.status_code == 404
    holding = (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()
    assert holding["account_id"] is None
