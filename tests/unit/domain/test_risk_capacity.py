"""Risk capacity beside tolerance, and the investment policy's drift report."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from salli.domain.portfolio import policy as ips
from salli.domain.risk import capacity


def test_capacity_scores_the_four_measures_and_scales_over_those_present():
    strong = capacity.compute(Decimal(8), Decimal("0.05"), 20, Decimal("0.05"))
    assert (strong.score, strong.category, strong.missing) == (100, "aggressive", ())
    thin = capacity.compute(Decimal("0.5"), Decimal("0.6"), 1, Decimal("0.5"))
    assert (thin.score, thin.category) == (0, "conservative")
    # Without a horizon: three measures, 15 + 25 + 18 of 75.
    partial = capacity.compute(Decimal(4), Decimal("0.02"), None, Decimal("0.15"))
    assert partial.missing == ("horizon",) and partial.score == 77


def test_income_variation_needs_three_months():
    assert capacity.income_variation([Decimal(100), Decimal(100)]) is None
    assert capacity.income_variation([Decimal(100)] * 3) == 0


def test_the_profile_is_the_lower_of_tolerance_and_capacity():
    assert capacity.profile("aggressive", "balanced") == "balanced"
    assert capacity.profile("conservative", "aggressive") == "conservative"
    assert capacity.profile(None, "balanced") == "balanced"


POLICY = {
    "targets": [
        {"asset_class": "equity", "target": "0.6", "band": "0.05"},
        {"asset_class": "fixed_income", "target": "0.4", "band": "0.05"},
    ],
    "rebalancing": {"rule": "both", "every_months": 12},
    "horizon_years": 15,
    "review_on": "2027-01-01",
}


def test_a_policy_needs_targets_that_add_up():
    with pytest.raises(ValidationError, match="add up to 1"):
        ips.Policy.model_validate({"targets": [{"asset_class": "equity", "target": "0.5"}]})
    with pytest.raises(ValidationError, match="every_months"):
        ips.Policy.model_validate({**POLICY, "rebalancing": {"rule": "calendar"}})


def test_drift_against_the_policy_with_bands_and_the_rebalancing_rule():
    policy = ips.Policy.model_validate(POLICY)
    report = ips.drift(
        policy,
        {"equity": Decimal(7000), "fixed_income": Decimal(2500), "cash": Decimal(500)},
        adopted_on=dt.date(2026, 1, 15),
        today=dt.date(2026, 10, 25),
    )
    classes = {c["asset_class"]: c for c in report["classes"]}  # type: ignore[index]
    assert classes["equity"]["drift_pct"] == Decimal("0.1000")
    assert classes["equity"]["outside_band"] is True
    assert classes["equity"]["to_target"] == Decimal("-1000.00")
    assert classes["cash"]["in_policy"] is False
    assert report["rebalance_due"] is True and report["review_due"] is False
    inside = ips.drift(
        policy,
        {"equity": Decimal(6200), "fixed_income": Decimal(3800)},
        adopted_on=dt.date(2026, 1, 15),
        today=dt.date(2027, 1, 15),
    )
    # Inside the bands, but a year has passed and the review date has come.
    assert inside["rebalance_due"] is True and inside["review_due"] is True


def test_an_equity_target_above_the_profiles_band_is_flagged():
    policy = ips.Policy.model_validate(POLICY)
    assert ips.equity_check(policy, "balanced")["above_profile"] is False
    assert ips.equity_check(policy, "conservative")["above_profile"] is True


def test_classes_come_from_the_taxonomy_and_sub_classes_roll_up():
    with pytest.raises(ValidationError):
        ips.Policy.model_validate({"targets": [{"asset_class": "stocks", "target": "1"}]})
    with pytest.raises(ValidationError, match="not both"):
        ips.Policy.model_validate(
            {
                "targets": [
                    {"asset_class": "equity", "target": "0.5"},
                    {"asset_class": "equity.international", "target": "0.5"},
                ]
            }
        )
    policy = ips.Policy.model_validate(
        {
            "targets": [
                {"asset_class": "equity.domestic", "target": "0.3"},
                {"asset_class": "equity.international", "target": "0.3"},
                {"asset_class": "fixed_income", "target": "0.4"},
            ]
        }
    )
    report = ips.drift(
        policy,
        {
            "equity.domestic": Decimal(300),
            "equity.international": Decimal(300),
            "fixed_income.government": Decimal(400),
        },
        adopted_on=dt.date(2026, 1, 1),
        today=dt.date(2026, 2, 1),
    )
    rows = {c["asset_class"]: c for c in report["classes"]}  # type: ignore[index]
    assert rows["fixed_income"]["current_pct"] == Decimal("0.4000")
    # Sub-classes of equity count toward the profile's band together.
    assert ips.equity_check(policy, "conservative")["equity_target"] == Decimal("0.6")


def test_a_look_through_allocation_is_checked():
    assert ips.check_allocation({"equity": "0.6", "fixed_income": "0.4"}) == {
        "equity": Decimal("0.6"),
        "fixed_income": Decimal("0.4"),
    }
    with pytest.raises(ValueError, match="add up to 1"):
        ips.check_allocation({"equity": "0.6"})
    with pytest.raises(ValueError, match="not an asset class"):
        ips.check_allocation({"stocks": "1"})


def test_lots_are_picked_losses_first_then_the_smallest_gain():
    lots = [
        {"lot_id": "a", "quantity": Decimal(10), "value": Decimal(1000), "cost": Decimal(400)},
        {"lot_id": "b", "quantity": Decimal(10), "value": Decimal(1000), "cost": Decimal(1200)},
        {"lot_id": "c", "quantity": Decimal(10), "value": Decimal(1000), "cost": Decimal(900)},
    ]
    picked, gain = ips.lots_to_sell(Decimal(1500), lots, Decimal("0.01"))
    assert [p["lot_id"] for p in picked] == ["b", "c"]
    assert picked[1]["quantity"] == Decimal(5)
    # −200 on b, then half of c's 100.
    assert gain == Decimal("-150.00")


def test_need_is_the_return_the_plan_requires():
    # 100,000 now and 1,000 a month reach 400,000 in 15 years at about 3.6%.
    required = capacity.required_return(Decimal(100000), Decimal(1000), Decimal(400000), 15)
    assert required is not None and Decimal("0.03") < required < Decimal("0.045")
    assert capacity.need_category(required) == "balanced"
    assert capacity.required_return(Decimal(0), Decimal(10), Decimal(10**9), 5) is None
    assert capacity.need_category(None) == "aggressive"
    # Dependents are a capacity measure.
    assert capacity.compute(None, None, None, None, 4).breakdown == {"dependents": 5}


def test_every_tolerance_item_sits_in_one_factor():
    from salli.domain.risk import engine

    items = [i for group in engine.FACTORS.values() for i in group]
    assert sorted(items) == sorted(["drawdown_reaction", *engine.ITEMS])
