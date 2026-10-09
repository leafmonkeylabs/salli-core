import pytest

from salli.application.ports import EntitlementPolicy
from tests.unit.api.conftest import AUTH

# ── POST /fi/simulate-purchase ────────────────────────────────────────────────


def _impact() -> dict:
    """Everything FiService.simulate_purchase returns."""
    return {
        "amount": "450000.00",
        "currency": "LKR",
        "fi_number": "54000000",
        "fi_asset_base_before": "1200000.00",
        "monthly_surplus": "60000.00",
        "baseline_months_to_fi": 404,
        "payable_from_liquid": True,
        "emergency_months_before": "8.00",
        "emergency_months_after_cash": "5.75",
        "emergency_fund_target_months": 6,
        "options": [
            {
                "key": "cash",
                "label": "Pay in full",
                "total_cost": "450000.00",
                "interest_cost": "0.00",
                "monthly_payment": None,
                "term_months": None,
                "months_to_fi": 412,
                "months_delay": 8,
                "exceeds_monthly_surplus": False,
            }
        ],
        "cheapest_option_key": "cash",
        "is_stale": False,
        "data_as_of": "2026-07-23",
        "stale_after_days": 45,
        "real_return_used": "0.0462962962962962962962962963",
        "swr": "0.04",
    }


@pytest.mark.asyncio
async def test_simulate_purchase_parses_money_as_decimal(client, mock_services):
    """Money crosses the wire as a string and must reach the service as Decimal."""
    from decimal import Decimal

    mock_services.fi.simulate_purchase.return_value = _impact()

    r = await client.post(
        "/fi/simulate-purchase",
        json={"amount": "450000", "term_months": 12, "annual_interest_rate": "0.18"},
        headers=AUTH,
    )

    assert r.status_code == 200
    assert r.json()["cheapest_option_key"] == "cash"

    args, kwargs = mock_services.fi.simulate_purchase.call_args
    amount = args[1]
    assert isinstance(amount, Decimal), f"money reached the service as {type(amount).__name__}"
    assert amount == Decimal("450000")
    assert kwargs["annual_interest_rate"] == Decimal("0.18")
    assert kwargs["term_months"] == 12


@pytest.mark.asyncio
async def test_simulate_purchase_rejects_a_percentage_as_a_rate(client, mock_services):
    """18 instead of 0.18 would overstate the finance cost ~100x — reject at the edge."""
    r = await client.post(
        "/fi/simulate-purchase",
        json={"amount": "450000", "term_months": 12, "annual_interest_rate": "18"},
        headers=AUTH,
    )
    assert r.status_code == 422
    mock_services.fi.simulate_purchase.assert_not_called()


@pytest.mark.asyncio
async def test_simulate_purchase_rejects_negative_and_bad_terms(client, mock_services):
    for body in (
        {"amount": "-1"},
        {"amount": "450000", "term_months": 0},
        {"amount": "450000", "term_months": 601},
        {"amount": "not a number"},
    ):
        r = await client.post("/fi/simulate-purchase", json=body, headers=AUTH)
        assert r.status_code == 422, body
    mock_services.fi.simulate_purchase.assert_not_called()


@pytest.mark.asyncio
async def test_simulate_purchase_needs_auth(client, mock_services):
    r = await client.post("/fi/simulate-purchase", json={"amount": "450000"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_simulate_purchase_is_not_metered(client, mock_services):
    """
    Pure engine math with no LLM call. Metering it would teach users not to ask
    the one question the product exists to answer.
    """
    mock_services.fi.simulate_purchase.return_value = _impact()

    r = await client.post("/fi/simulate-purchase", json={"amount": "450000"}, headers=AUTH)

    assert r.status_code == 200
    mock_services.usage.charge.assert_not_called()


# ── Typed responses ───────────────────────────────────────────────────────────


def _score() -> dict:
    """A score as FiService computes and stores it: `str(Decimal)` throughout."""
    return {
        "pack_version": "1.0.0",
        "overall_score": "54.25",
        "grade": "On track",
        "monthly_income": "333333.3333333333333333333333",
        "monthly_expenses": "150000.00",
        "monthly_surplus": "183333.3333333333333333333333",
        "savings_rate": "0.5500000000000000000000000000",
        "swr": "0.04",
        "annual_expenses": "1800000.0",
        "fi_number": "4.500000E+7",
        "net_worth": "2500000.00",
        "fi_asset_base": "1200000.00",
        "progress_to_fi": "0.02666666666666666666666666667",
        "emergency_fund_months": "6.666666666666666666666666667",
        "debt_to_asset": "0",
        "projected_fi_years": "13",
        "currency": "LKR",
        "components": [
            {
                "key": "savings_rate",
                "label": "Savings rate",
                "score": "100.00",
                "weight": "0.30",
                "detail": "Saving 55.00% of income",
            }
        ],
        "projected_fi_date": "2039-10-09",
        "inputs_hash": "9f86d081",
    }


async def test_score_amounts_leave_as_plain_decimals_in_the_currency(client, mock_services):
    """An exact quotient renders as "4.500000E+7" from Decimal; an amount never
    leaves the API like that, nor with more decimals than its currency has."""
    mock_services.fi.get_or_compute_score.return_value = _score()

    body = (await client.get("/v1/fi/score", headers=AUTH)).json()

    assert body["fi_number"] == "45000000.00"
    assert body["monthly_income"] == "333333.33"
    assert body["annual_expenses"] == "1800000.00"
    # Ratios are not money: as computed.
    assert body["savings_rate"] == "0.5500000000000000000000000000"


async def test_a_score_stored_by_an_earlier_version_still_reads(client, mock_services):
    legacy = _score()
    for key in ("currency", "swr", "annual_expenses", "fi_asset_base", "inputs_hash"):
        del legacy[key]
    mock_services.fi.get_or_compute_score.return_value = legacy

    r = await client.get("/v1/fi/score", headers=AUTH)

    assert r.status_code == 200
    body = r.json()
    # In the base currency, which cannot change once anything is stored in it.
    assert body["currency"] == "LKR"
    # What it lacks stays absent rather than turning up as null.
    assert not {"swr", "annual_expenses", "fi_asset_base", "inputs_hash"} & body.keys()


async def test_score_history_says_what_currency_it_is_in(client, mock_services):
    mock_services.fi.get_score_history.return_value = [
        {"score": 54.25, "net_worth": "2500000.5", "created_at": "2026-10-01T06:00:00+00:00"},
        {"score": 50.0, "net_worth": None, "created_at": "2026-09-01T06:00:00+00:00"},
    ]

    body = (await client.get("/v1/fi/score/history", headers=AUTH)).json()

    assert body["currency"] == "LKR"
    assert [h["net_worth"] for h in body["history"]] == ["2500000.50", None]


def _projections(currency: str) -> dict:
    """As FiService.get_projections returns them: cents, and the raw FI number."""
    return {
        "currency": currency,
        "points": [
            {"year": 0, "conservative": "1200000.00", "base": "1200000.00", "growth": "1200000.00"},
            {"year": 1, "conservative": "1500000.00", "base": "1530000.00", "growth": "1560000.00"},
        ],
        "fi_number": "3.00000E+7",
        "swr": "0.04",
        "fire_year_conservative": 21,
        "fire_year_base": 17,
        "fire_year_growth": 14,
        "current_portfolio": "1200000",
        "real_returns": {"conservative": "0.0094", "base": "0.0472", "growth": "0.0849"},
        "expected_inflation": "0.05",
    }


async def test_projections_are_at_the_currency_precision(client, mock_services):
    mock_services.fi.get_projections.return_value = _projections("JPY")

    body = (await client.get("/v1/fi/projections", headers=AUTH)).json()

    assert body["fi_number"] == "30000000"
    assert body["points"][1] == {
        "year": 1,
        "conservative": "1500000",
        "base": "1530000",
        "growth": "1560000",
    }


class _WithholdingView:
    """Withholds the growth scenario and says so, as a deployment's policy may."""

    def shape(self, surface, payload):
        shaped = {k: v for k, v in payload.items() if k != "fire_year_growth"}
        shaped["points"] = [{k: v for k, v in p.items() if k != "growth"} for p in shaped["points"]]
        return {**shaped, "growth_locked": True}


class _WithholdingPolicy(EntitlementPolicy):
    async def for_user(self, user_id, email=None):
        return _WithholdingView()


async def test_what_a_policy_withholds_stays_out_and_what_it_adds_comes_through(
    client, mock_services
):
    mock_services.fi.get_projections.return_value = _projections("LKR")
    mock_services.entitlements = _WithholdingPolicy()

    body = (await client.get("/v1/fi/projections", headers=AUTH)).json()

    assert "fire_year_growth" not in body
    assert all("growth" not in p for p in body["points"])
    assert body["growth_locked"] is True


async def test_a_strategy_stored_by_an_earlier_version_reads_as_stored(client, mock_services):
    stored = {
        "version": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "fire_style": "lean",
        "swr": 0.04,
        "buckets": [],
    }
    mock_services.fi.get_strategy.return_value = stored

    r = await client.get("/v1/fi/strategy", headers=AUTH)

    assert r.json() == stored


async def test_purchase_amounts_are_at_the_currency_precision(client, mock_services):
    impact = _impact()
    impact["fi_number"] = "5.4000000E+7"
    mock_services.fi.simulate_purchase.return_value = impact

    r = await client.post("/v1/fi/simulate-purchase", json={"amount": "450000"}, headers=AUTH)

    body = r.json()
    assert body["fi_number"] == "54000000.00"
    assert body["options"][0]["monthly_payment"] is None
