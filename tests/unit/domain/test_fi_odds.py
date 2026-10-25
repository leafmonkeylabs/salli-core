"""
The wealth manager's planning figures: capital-market assumptions as user
data, guaranteed income and spending phases, the FI number gross of tax on
withdrawals, cash earning the pack's yield, and a seeded Monte Carlo
(domain/fi/cma.py, plan.py, montecarlo.py; docs/baseline.md). Every figure
is made up; XA is a user-assigned code, no country's.
"""

from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from salli.domain.baseline import fi, timelines
from salli.domain.fi import cma, montecarlo
from salli.domain.fi import plan as fi_plan
from salli.domain.fi.assumptions import PLACEHOLDERS
from tests.baseline_ledger import USER, Ledger
from tests.golden import taxed

#: The withdrawal rate the placeholder pack's returns sustain.
SWR = PLACEHOLDERS["safe_withdrawal_rate"].value

AS_OF = dt.date(2031, 6, 30)


def pack(**over: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "format": "salli.cma/1",
        "name": "XA reference",
        "version": "2031-06",
        "asset_classes": {
            "equity": {
                "label": "Equity",
                "real_return": {"value": "0.05", "source": "XA statistics", "date": "2031-05-31"},
                "volatility": {"value": "0.18", "source": "XA statistics", "date": "2031-05-31"},
            },
            "bonds": {
                "label": "Bonds",
                "real_return": {"value": "0.01", "source": "XA statistics", "date": "2031-05-31"},
                "volatility": {"value": "0.06", "source": "XA statistics", "date": "2031-05-31"},
            },
        },
        "correlations": [
            {"a": "equity", "b": "bonds", "value": "0.2", "source": "XA", "date": "2031-05-31"}
        ],
        "cash_yield": {"value": "0.01", "source": "XA bank", "date": "2031-05-31"},
        "mix": {"equity": "0.6", "bonds": "0.4"},
    }
    doc.update(over)
    return doc


def books() -> Ledger:
    """Rent of 1,500 a month, a salary of 4,000, 10,000 of cash: taxed's household."""
    return taxed.ledger()


def with_pack(ledger: Ledger, doc: dict[str, Any]) -> None:
    ledger.uow.cma_packs.rows.append(
        {
            "id": "p1",
            "user_id": USER,
            "name": doc["name"],
            "version": doc["version"],
            "content": doc,
            "content_hash": cma.content_hash(doc),
            "is_active": True,
            "created_at": None,
            "activated_at": None,
        }
    )


# ── The pack ─────────────────────────────────────────────────────────────────


def test_a_pack_gives_its_mix_expected_return_and_volatility() -> None:
    p = cma.parse(pack())
    assert p.expected_return == Decimal("0.034")
    # √(0.6²·0.18² + 0.4²·0.06² + 2·0.6·0.4·0.2·0.18·0.06)
    assert p.volatility.quantize(Decimal("0.0001")) == Decimal("0.1152")


@pytest.mark.parametrize(
    ("over", "says"),
    [
        ({"format": "salli.cma/2"}, "format"),
        ({"mix": {"equity": "0.6"}}, "sum to 1"),
        ({"mix": {"gold": "1"}}, "not one of the asset classes"),
        ({"cash_yield": {"value": "0.01", "date": "2031-05-31"}}, "cash_yield.source"),
        ({"cash_yield": {"value": 0.01, "source": "x", "date": "2031-05-31"}}, "decimal string"),
    ],
)
def test_a_pack_that_is_wrong_says_why(over: dict[str, Any], says: str) -> None:
    with pytest.raises(ValueError, match=says):
        cma.parse(pack(**over))


def test_an_active_pack_sets_the_return_and_cash_earns_its_yield() -> None:
    plain = books().baseline(AS_OF)
    ledger = books()
    with_pack(ledger, pack())
    held = ledger.baseline(AS_OF)
    assert held.assumptions.real_return.value == Decimal("0.034")
    assert "XA reference" in held.assumptions.real_return.source
    assert "real_return" not in held.assumptions.placeholders
    a = timelines.monthly(plain, 1).points[-1].cash
    b = timelines.monthly(held, 1).points[-1].cash
    assert b > a  # a year's 1% on what cash holds
    # Without a pack, cash earns nothing and the placeholder pack is labelled.
    assert plain.assumptions.cma.placeholder
    assert plain.assumptions.cash_yield == 0


# ── The FI number: gross of tax, less guaranteed income, by phase ───────────


def test_the_fi_number_is_grossed_up_by_the_withdrawal_role() -> None:
    ledger = books()
    doc = copy.deepcopy(taxed.RULES)
    doc["roles"].append({"key": "withdrawal", "kind": "income", "label": "Withdrawals"})
    doc["lines"][0]["expr"] = "max(0, role.salary + role.withdrawal - role.pension)"
    ledger.uow.tax_rule_sets.active[:] = [taxed.rules_row(doc)]
    baseline = ledger.baseline(AS_OF)
    # 18,000 a year to spend: G − 20% × (G − 12,000) = 18,000, so G = 19,500.
    assert fi.gross_up(baseline, Decimal(18000)) == Decimal("19500.00")
    assert fi.fi_number(baseline) == Decimal("19500.00") / SWR
    assert fi.withdrawal_tax(baseline)["status"] == "computed"
    # Without the role it isn't, and says so.
    plain = books().baseline(AS_OF)
    assert fi.fi_number(plain) == Decimal(18000) / SWR
    assert fi.withdrawal_tax(plain)["status"] == "not_computed"


def test_withdrawals_are_taxed_beside_guaranteed_income_with_a_tax_role() -> None:
    """An annuity of 1,000 a month taxed under an income role uses the whole
    12,000 relief, so the withdrawal is taxed at 20% from its first unit:
    18,000 − 12,000 = 6,000 to fund, G × 0.8 = 6,000, G = 7,500 (the
    withdrawal alone, within the relief, would have been 6,000)."""
    ledger = books()
    doc = copy.deepcopy(taxed.RULES)
    doc["roles"] += [
        {"key": "withdrawal", "kind": "income", "label": "Withdrawals"},
        {"key": "annuity", "kind": "income", "label": "Annuities"},
    ]
    doc["lines"][0]["expr"] = "max(0, role.salary + role.withdrawal + role.annuity - role.pension)"
    ledger.uow.tax_rule_sets.active[:] = [taxed.rules_row(doc)]
    stream = {"name": "Annuity", "start": "2031-01", "monthly": "1000", "tax_role": "annuity"}
    ledger.uow.user_profiles.rows.setdefault(USER, {})["fi_plan"] = {"income_streams": [stream]}
    baseline = ledger.baseline(AS_OF)
    assert fi.taxed_income(baseline, "2031-06", {}) == {"annuity": Decimal(12000)}
    assert fi.gross_up(baseline, Decimal(6000)) == Decimal("6000.00")
    assert fi.gross_up(baseline, Decimal(6000), {"annuity": Decimal(12000)}) == Decimal("7500.00")
    assert fi.fi_number(baseline) == Decimal("7500.00") / SWR


def test_a_pension_steps_the_number_down_and_comes_into_cash() -> None:
    ledger = books()
    ledger.uow.user_profiles.rows.setdefault(USER, {})["fi_plan"] = {
        "income_streams": [
            {"name": "Pension", "start": "2041-01", "monthly": "500", "lump_sum": "20000"}
        ]
    }
    baseline = ledger.baseline(AS_OF)
    timeline = fi.full_timeline(baseline)
    numbers = fi.fi_numbers(baseline, timeline.points)
    assert numbers[0] == Decimal(18000) / SWR
    at = next(i for i, p in enumerate(timeline.points) if p.month == "2041-01")
    assert numbers[at] == Decimal(12000) / SWR  # 1,000 a month left to fund
    plain = fi.full_timeline(books().baseline(AS_OF))
    gained = timeline.points[at].cash - plain.points[at].cash
    assert gained == Decimal(20500)


def test_spending_phases_go_by_age() -> None:
    plan = fi_plan.parse(
        {
            "spending_phases": [
                {"from_age": 60, "monthly": "2000"},
                {"from_age": 75, "monthly": "1200"},
            ]
        },
        dt.date(1980, 3, 15),
    )
    assert plan.phase_spending("2040-02") is None
    assert plan.phase_spending("2040-03") == Decimal(2000)
    assert plan.phase_spending("2055-03") == Decimal(1200)
    with pytest.raises(ValueError, match="same age"):
        fi_plan.parse({"spending_phases": [{"from_age": 60, "monthly": "1"}] * 2})


# ── The Monte Carlo ──────────────────────────────────────────────────────────


def test_the_odds_are_reproducible_and_ordered() -> None:
    baseline = books().baseline(AS_OF)
    one = montecarlo.plan_odds(baseline, horizon_years=40, paths=200, seed=7)
    two = montecarlo.plan_odds(baseline, horizon_years=40, paths=200, seed=7)
    other = montecarlo.plan_odds(baseline, horizon_years=40, paths=200, seed=8)
    assert one == two
    assert one["percentiles"] != other["percentiles"]
    for year in one["percentiles"]:  # type: ignore[union-attr]
        assert Decimal(year["p10"]) <= Decimal(year["p50"]) <= Decimal(year["p90"])
    assert "volatility" in one["placeholders"]  # type: ignore[operator]
    assert one["retire_month"] == one["fi_month"]


def test_the_horizon_rate_is_exact_without_volatility() -> None:
    # Level returns of 0: a pool lasts 25 years at 4% exactly.
    assert montecarlo.sustainable_rate([Decimal(0)] * 300) == Decimal("0.04")
    rails = montecarlo.plan_odds(
        books().baseline(AS_OF),
        horizon_years=40,
        paths=100,
        guardrails=montecarlo.Guardrails(),
    )["guardrails"]
    assert rails is not None


def test_investing_against_a_debt_is_a_share_of_paths() -> None:
    sure = montecarlo.beats(Decimal("0.05"), Decimal(0), 60, Decimal("0.02"), paths=50)
    never = montecarlo.beats(Decimal("0.01"), Decimal(0), 60, Decimal("0.08"), paths=50)
    mixed = montecarlo.beats(Decimal("0.04"), Decimal("0.15"), 120, Decimal("0.04"), paths=400)
    assert (sure, never) == (Decimal(1), Decimal(0))
    assert Decimal("0.2") < mixed < Decimal("0.8")


def test_draws_have_fat_tails_at_the_packs_volatility() -> None:
    """Student-t draws, scaled to the volatility: a yearly 0.12 is a monthly
    0.12/√12 ≈ 0.0346 whatever the tails; with 5 degrees of freedom, moves
    beyond four of those are far more common than a normal's 0.006%."""
    paths = montecarlo.draws(Decimal(0), Decimal("0.12"), 120, 100, 3)
    assert paths == montecarlo.draws(Decimal(0), Decimal("0.12"), 120, 100, 3)
    flat = [float(r) for path in paths for r in path]
    sd = (sum(r * r for r in flat) / len(flat)) ** 0.5
    assert 0.032 < sd < 0.037
    beyond = sum(abs(r) > 4 * 0.0346 for r in flat) / len(flat)
    assert beyond > 0.001
    thin = montecarlo.draws(Decimal(0), Decimal("0.12"), 120, 100, 3, Decimal(100))
    assert sum(abs(float(r)) > 4 * 0.0346 for p in thin for r in p) / len(flat) < beyond


def test_a_pack_sets_the_degrees_of_freedom_else_a_placeholder() -> None:
    tails = {"value": "8", "source": "XA statistics", "date": "2031-05-31"}
    assert cma.parse(pack(degrees_of_freedom=tails)).tails == Decimal(8)
    assert cma.parse(pack()).tails == cma.TAILS
    with pytest.raises(ValueError, match="degrees_of_freedom.value must be from 3 to 100"):
        cma.parse(pack(degrees_of_freedom={**tails, "value": "2"}))
    ledger = books()
    with_pack(ledger, pack(degrees_of_freedom=tails))
    odds = montecarlo.plan_odds(ledger.baseline(AS_OF), horizon_years=10, paths=20)
    assert "degrees_of_freedom" not in odds["placeholders"]  # type: ignore[operator]
    assert odds["cma"]["degrees_of_freedom"] == "8"  # type: ignore[index]
    plain = montecarlo.plan_odds(books().baseline(AS_OF), horizon_years=10, paths=20)
    assert "degrees_of_freedom" in plain["placeholders"]  # type: ignore[operator]


def test_a_pack_history_is_resampled_from_one_source() -> None:
    from salli.domain.fi import returns

    history = tuple(Decimal("0.01") if k % 2 else Decimal("-0.005") for k in range(36))
    source = returns.ReturnSource(
        Decimal("0.05"), Decimal("0.1"), cma.TAILS, "pack", Decimal("0.0012"), history
    )
    assert source.method == "bootstrap"
    # The history's own mean a year, less the expense ratio.
    assert source.mean == Decimal("0.0025") * 12 - Decimal("0.0012")
    paths = source.monthly(30, 3, 1)
    assert all(len(p) == 30 for p in paths)
    # Every draw is a month of the history less a twelfth of the costs.
    allowed = {r - Decimal("0.0001") for r in history}
    assert {r for p in paths for r in p} <= allowed
    assert source.monthly(30, 3, 1) == paths


def test_a_category_runs_at_its_own_inflation_in_todays_money() -> None:
    plan = fi_plan.parse(
        {
            "spending_phases": [
                {"from_age": 60, "monthly": "3000", "categories": {"housing": "1000"}}
            ],
            "category_inflation": {"housing": {"value": "0.0506", "source": "a test"}},
        },
        dt.date(1970, 1, 15),
    )
    # 1.0506 / 1.02 = 1.03 a year, twelve years on.
    added = fi_plan.category_uplift(plan, "2038-10", "2026-10", Decimal("0.02"), {})
    assert added.quantize(Decimal("0.01")) == (
        Decimal(1000) * (Decimal("1.03") ** 12 - 1)
    ).quantize(Decimal("0.01"))
    # The pack's figure where the plan has none; nothing without inflation.
    bare = fi_plan.parse(
        {
            "spending_phases": [
                {"from_age": 60, "monthly": "3000", "categories": {"housing": "1000"}}
            ]
        },
        dt.date(1970, 1, 15),
    )
    assert fi_plan.category_uplift(bare, "2038-10", "2026-10", Decimal("0.02"), {}) == 0
    assert (
        fi_plan.category_uplift(bare, "2038-10", "2026-10", None, {"housing": Decimal("0.05")}) == 0
    )
    assert (
        fi_plan.category_uplift(
            bare, "2038-10", "2026-10", Decimal("0.02"), {"housing": Decimal("0.0506")}
        )
        == added
    )
    with pytest.raises(ValueError, match="more than"):
        fi_plan.parse(
            {
                "spending_phases": [
                    {"from_age": 60, "monthly": "10", "categories": {"housing": "11"}}
                ]
            }
        )


def test_debt_payments_leave_the_fi_spending_and_the_emergency_fund_is_held_out() -> None:
    baseline = books().baseline(AS_OF)
    assert fi.debt_service(baseline) == sum(
        (d.already_paid for d in baseline.debts if d.balance > 0), Decimal(0)
    )
    living = fi.spending(baseline) - fi.debt_service(baseline)
    assert fi.reserve(baseline) == living * 6
    point = fi.full_timeline(baseline).points[0]
    assert fi.asset_base(point, fi.reserve(baseline)) == fi.asset_base(point) - fi.reserve(baseline)
