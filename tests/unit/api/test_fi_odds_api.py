"""The odds, the FI plan and capital-market assumptions over HTTP: query
options reach the service as Decimals and a Guardrails, and each answer is
the service's, through its response model."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from salli.application.services.fi_service import FiService
from salli.domain.fi.montecarlo import Guardrails
from tests.baseline_ledger import USER
from tests.golden import taxed
from tests.unit.api.conftest import AUTH
from tests.unit.domain.test_fi_odds import pack


async def _odds() -> dict:
    ledger = taxed.ledger()
    svc = FiService(ledger.uow.factory(), baselines=ledger.service(dt.date(2031, 6, 30)))
    return await svc.odds(USER, horizon_years=30, paths=50)


async def test_the_odds_take_their_options_from_the_query(client, mock_services):
    mock_services.fi.odds.return_value = await _odds()
    r = await client.get(
        "/v1/fi/odds?retire_month=2040-01&paths=50&seed=3&guardrail_band=0.2", headers=AUTH
    )
    assert r.status_code == 200, r.text
    kwargs = mock_services.fi.odds.await_args.kwargs
    assert kwargs["retire_month"] == "2040-01"
    assert (kwargs["paths"], kwargs["seed"]) == (50, 3)
    assert kwargs["guardrails"] == Guardrails(Decimal("0.2"), Decimal("0.1"))
    assert r.json()["cma"]["placeholder"] is True
    bad = await client.get("/v1/fi/odds?retire_month=2040-13", headers=AUTH)
    assert bad.status_code == 422


async def test_packs_are_imported_activated_and_the_service_checks_them():
    ledger = taxed.ledger()
    svc = FiService(ledger.uow.factory(), baselines=ledger.service(dt.date(2031, 6, 30)))
    stored = await svc.import_cma_pack(USER, pack())
    again = await svc.import_cma_pack(USER, pack())
    assert stored["id"] == again["id"] and not stored["is_active"]
    listed = await svc.activate_cma_pack(USER, stored["id"])
    assert [p["is_active"] for p in listed["packs"]] == [True]
    odds = await svc.odds(USER, horizon_years=30, paths=50)
    assert odds["cma"]["name"] == "XA reference"
    assert "volatility" not in odds["placeholders"]
    plan = await svc.set_plan(
        USER, {"income_streams": [{"name": "Annuity", "start": "2045-01", "monthly": "300"}]}
    )
    assert plan["income_streams"][0]["monthly"] == "300"
