"""The API names the user's tax year from their pack, and computes the latest
year Salli can when a client names none."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock

from salli.application.services.tax_service import NoTaxPackError, TaxJurisdiction
from salli.domain.tax.models import CurrentTaxYear, TaxYear
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_onboarding import USER, _portability_service

_LK = TaxJurisdiction("LK", "tax_residency", "LK", "LKR")


async def test_the_current_year_is_the_users_countrys(client, mock_services):
    mock_services.tax.current_tax_year.return_value = (
        _LK,
        CurrentTaxYear(
            year=TaxYear("LK", "2026/27", datetime.date(2026, 4, 1), datetime.date(2027, 3, 31)),
            pack=None,
            latest=LK_2025_26,
        ),
    )
    r = await client.get("/v1/tax/current-year", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "country": "LK",
        "country_source": "tax_residency",
        "year": "2026/27",
        "start": "2026-04-01",
        "end": "2027-03-31",
        "has_pack": False,
        "latest_year": "2025/26",
    }


async def test_without_a_country_the_current_year_is_unknown(client, mock_services):
    mock_services.tax.current_tax_year.return_value = (
        TaxJurisdiction(None, None, None, "USD"),
        None,
    )
    body = (await client.get("/v1/tax/current-year", headers=AUTH)).json()
    assert body == {
        "country": None,
        "country_source": None,
        "year": None,
        "start": None,
        "end": None,
        "has_pack": False,
        "latest_year": None,
    }


async def test_compute_and_latest_leave_the_year_to_the_service(client, mock_services):
    mock_services.tax.get_latest_computation.return_value = None
    await client.get("/v1/tax/latest", headers=AUTH)
    mock_services.tax.get_latest_computation.assert_awaited_once_with("test-user-1", None)

    await client.get("/v1/tax/latest", params={"year": "2025/26"}, headers=AUTH)
    assert mock_services.tax.get_latest_computation.await_args.args == ("test-user-1", "2025/26")


async def test_no_pack_for_the_user_is_a_problem_of_its_own(client, mock_services):
    mock_services.tax.compute_tax.side_effect = NoTaxPackError(
        "Salli has no tax pack for United States yet."
    )
    r = await client.post("/v1/tax/compute", headers=AUTH)
    assert r.status_code == 422
    body = r.json()
    assert (body["type"], body["title"]) == ("/problems/no-tax-pack", "No tax pack")
    assert "United States" in body["detail"]


async def test_seeding_reminders_leaves_the_year_to_the_service(client, mock_services):
    mock_services.reminders = AsyncMock()
    mock_services.reminders.seed_filing_calendar.return_value = []
    await client.post("/v1/reminders/seed", headers=AUTH)
    mock_services.reminders.seed_filing_calendar.assert_awaited_once_with("test-user-1", None)


async def test_the_exports_legacy_key_holds_the_year_it_is_named_after():
    service = _portability_service()
    by_year = {"2025/26": {"pack_year": "2025/26", "tax_payable": "1.00"}}

    async def latest(user_id, year=None):
        return by_year.get(year)

    service._tax.get_latest_computation.side_effect = latest
    document = await service.export_all(USER)
    assert document["tax_computation_2025_26"] == by_year["2025/26"]
    assert document["tax_computations"] == [by_year["2025/26"]]
