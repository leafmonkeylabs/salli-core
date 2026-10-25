"""
The investment policy statement, its drift report and the risk profile over
HTTP; holdings' cost method and expense ratios; the insurance needs analysis.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from salli.application.services.insurance_service import InsuranceService
from salli.application.services.investment_policy_service import InvestmentPolicyService
from salli.application.services.portfolio_service import PortfolioService
from tests.fakes import FakeRecords, FakeRecordsUoW
from tests.unit.api.conftest import AUTH

USER = "test-user-1"


class _Baselines:
    """What the risk profile and the needs analysis read from a baseline."""

    async def build(self, user_id: str) -> SimpleNamespace:
        month = SimpleNamespace
        return SimpleNamespace(
            currency="LKR",
            liquid=Decimal(8000),
            total_liabilities=Decimal(20000),
            balances=(SimpleNamespace(role="investment", owned=Decimal(12000)),),
            debts=(
                SimpleNamespace(
                    source="account", balance=Decimal(20000), minimum_payment=Decimal(600)
                ),
            ),
            flows=SimpleNamespace(
                income=Decimal(4000),
                expenses=Decimal(2000),
                by_month=tuple(month(income=Decimal(4000)) for _ in range(6)),
            ),
        )


def _wire(mock_services) -> FakeRecordsUoW:
    uow = FakeRecordsUoW()
    uow.goals = FakeRecords(is_active=True)
    mock_services.portfolio = PortfolioService(lambda: uow)
    mock_services.investment_policy = InvestmentPolicyService(
        lambda: uow, mock_services.portfolio, _Baselines()
    )
    mock_services.insurance = InsuranceService(lambda: uow, baselines=_Baselines())
    return uow


POLICY = {
    "targets": [
        {"asset_class": "equity", "target": "0.8", "band": "0.05"},
        {"asset_class": "bond", "target": "0.2", "band": "0.05"},
    ],
    "horizon_years": 20,
    "objectives": "Retire early",
    "review_on": "2030-01-01",
}


async def test_a_policy_is_kept_as_versions_and_drift_is_reported_beside_the_profile(
    client, mock_services
):
    uow = _wire(mock_services)
    await uow.user_profiles.upsert(USER, {"risk_score": 80, "risk_category": "aggressive"})
    for holding in (
        {
            "symbol": "EQ",
            "name": "Equity fund",
            "asset_class": "equity",
            "current_value": "6000",
            "expense_ratio": "0.002",
        },
        {"symbol": "BD", "name": "Bond fund", "asset_class": "bond", "current_value": "4000"},
    ):
        assert (await client.post("/v1/portfolio/", json=holding, headers=AUTH)).status_code == 201

    assert (await client.get("/v1/ips", headers=AUTH)).status_code == 404
    r = await client.post("/v1/ips", json=POLICY, headers=AUTH)
    assert r.status_code == 201 and r.json()["version"] == 1
    r = await client.post("/v1/ips", json={**POLICY, "objectives": "Later"}, headers=AUTH)
    assert r.json()["version"] == 2
    versions = (await client.get("/v1/ips/versions", headers=AUTH)).json()["versions"]
    assert [v["content"]["objectives"] for v in versions] == ["Retire early", "Later"]
    bad = {**POLICY, "targets": [{"asset_class": "equity", "target": "0.5"}]}
    assert (await client.post("/v1/ips", json=bad, headers=AUTH)).status_code == 422

    drift = (await client.get("/v1/ips/drift", headers=AUTH)).json()
    equity = next(c for c in drift["classes"] if c["asset_class"] == "equity")
    assert (equity["drift_pct"], equity["outside_band"], equity["to_target"]) == (
        "-0.2000",
        True,
        "2000.00",
    )
    assert drift["rebalance_due"] is True
    profile = drift["risk_profile"]
    # Capacity: 4 months (15), steady income (25), 20 years (25), 15% (18): 83.
    assert profile["capacity"]["score"] == 83 and profile["profile"] == "aggressive"
    assert drift["equity_check"]["above_profile"] is False

    summary = (await client.get("/v1/portfolio/summary", headers=AUTH)).json()
    assert summary["target_source"] == "policy"
    assert [a["asset_class"] for a in summary["alerts"]] == ["bond", "equity"]
    assert summary["costs"] == {
        "weighted_expense_ratio": "0.002000",
        "yearly_cost": "12.00",
        "value_covered": "6000.00",
        "without_ratio": ["BD"],
    }


async def test_a_cautious_tolerance_makes_the_profile_and_flags_the_policy(client, mock_services):
    uow = _wire(mock_services)
    await uow.user_profiles.upsert(USER, {"risk_score": 20, "risk_category": "conservative"})
    await client.post("/v1/ips", json=POLICY, headers=AUTH)
    drift = (await client.get("/v1/ips/drift", headers=AUTH)).json()
    assert drift["risk_profile"]["profile"] == "conservative"
    assert drift["equity_check"] == {
        "equity_target": "0.8",
        "profile": "conservative",
        "profile_equity_max": "0.40",
        "above_profile": True,
    }


async def test_a_holdings_cost_method_and_expense_ratio(client, mock_services):
    _wire(mock_services)
    r = await client.post(
        "/v1/portfolio/",
        json={"symbol": "X", "name": "X", "asset_class": "equity", "cost_method": "average"},
        headers=AUTH,
    )
    holding_id = r.json()["id"]
    holding = (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()
    assert (holding["cost_method"], holding["cost_method_source"]) == ("average", "holding")
    await client.patch(f"/v1/portfolio/{holding_id}", json={"cost_method": None}, headers=AUTH)
    holding = (await client.get(f"/v1/portfolio/{holding_id}", headers=AUTH)).json()
    assert (holding["cost_method"], holding["cost_method_source"]) == ("fifo", "default")
    r = await client.patch(
        f"/v1/portfolio/{holding_id}", json={"expense_ratio": "1.5"}, headers=AUTH
    )
    assert r.status_code == 422


async def test_the_insurance_needs_analysis_is_figures(client, mock_services):
    uow = _wire(mock_services)
    await uow.goals.save(
        USER, {"name": "House", "target_amount_minor": 1_000_000, "current_amount_minor": 400_000}
    )
    r = await client.get("/v1/insurance/needs?replacement_years=5", headers=AUTH)
    assert r.status_code == 200
    # 4,000 × 12 × 5 + 20,000 + 6,000 − (8,000 + 12,000).
    assert r.json() == {
        "currency": "LKR",
        "replacement_years": 5,
        "income_replacement": "240000.00",
        "debts": "20000.00",
        "goals": "6000.00",
        "assets": "20000.00",
        "life_cover_need": "246000.00",
        "life_cover_held": "0.00",
        "life_cover_gap": "246000.00",
        "income_protection_monthly": "2000.00",
    }
