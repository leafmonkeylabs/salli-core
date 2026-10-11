from salli.application.ports import EntitlementPolicy
from tests.unit.api.conftest import AUTH

# POST /fi/simulate-purchase is gone: what a purchase costs is a scenario
# (POST /v1/scenarios/compare, cash against instalments), whose figures come
# from the same baseline timeline FI's do (tests/unit/api/test_scenarios_api.py).


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
        "projected_fi_months": 156,
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
        "projected_fi_month": "2039-10",
        "as_of": "2026-10-09",
        "inputs_hash": "9f86d081",
    }


async def test_score_amounts_leave_as_plain_decimals_in_the_currency(client, mock_services):
    """An exact quotient renders as "4.500000E+7" from Decimal; an amount never
    leaves the API like that, nor with more decimals than its currency has."""
    mock_services.fi.compute_score.return_value = _score()

    body = (await client.get("/v1/fi/score", headers=AUTH)).json()

    assert body["fi_number"] == "45000000.00"
    assert body["monthly_income"] == "333333.33"
    assert body["annual_expenses"] == "1800000.00"
    # Ratios are not money: to four places, and months of savings to two.
    assert (body["savings_rate"], body["progress_to_fi"]) == ("0.5500", "0.0267")
    assert (body["debt_to_asset"], body["emergency_fund_months"]) == ("0.0000", "6.67")


async def test_reading_the_score_computes_it_and_recomputing_records_it(client, mock_services):
    """A read computes and stores nothing; only the explicit recompute records
    a score in the history. The FI date is a month."""
    mock_services.fi.compute_score.return_value = _score()
    mock_services.fi.record_score.return_value = _score()

    body = (await client.get("/v1/fi/score", headers=AUTH)).json()
    assert (body["projected_fi_months"], body["projected_fi_month"]) == (156, "2039-10")
    assert "projected_fi_date" not in body and "projected_fi_years" not in body
    mock_services.fi.record_score.assert_not_awaited()

    await client.post("/v1/fi/score/recompute", headers=AUTH)
    mock_services.fi.record_score.assert_awaited_once_with("test-user-1")


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
        "fi_by": {
            "conservative": {"months": 252, "month": "2047-10"},
            "base": {"months": 204, "month": "2043-10"},
            "growth": {"months": 168, "month": "2040-10"},
        },
        "current_portfolio": "1200000",
        "real_returns": {"conservative": "0.02", "base": "0.04", "growth": "0.06"},
        "terms": "real_and_nominal",
        "inflation": "0.02",
        "nominal_returns": {"conservative": "0.0404", "base": "0.0608", "growth": "0.0812"},
    }


async def test_projections_are_at_the_currency_precision(client, mock_services):
    data = _projections("JPY")
    data["points"][1]["nominal"] = {
        "conservative": "1530000.00",
        "base": "1560600.00",
        "growth": "1591200.00",
        "fi_number": "30600000.00",
    }
    mock_services.fi.get_projections.return_value = data

    body = (await client.get("/v1/fi/projections", headers=AUTH)).json()

    assert body["fi_number"] == "30000000"
    assert body["points"][1] == {
        "year": 1,
        "conservative": "1500000",
        "base": "1530000",
        "growth": "1560000",
        # In that year's money, from the user's inflation, at the same precision.
        "nominal": {
            "conservative": "1530000",
            "base": "1560600",
            "growth": "1591200",
            "fi_number": "30600000",
        },
    }
    assert body["terms"] == "real_and_nominal"
    assert body["inflation"] == "0.02"


class _WithholdingView:
    """Withholds the growth scenario and says so, as a deployment's policy may."""

    def shape(self, surface, payload):
        shaped = {k: v for k, v in payload.items() if k != "fi_by"}
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

    assert "fi_by" not in body
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
