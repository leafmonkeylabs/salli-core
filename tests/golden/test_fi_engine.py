"""
Golden tests for the FI ("Freedom") engine — hand-computed scenarios.

These exist because the engine shipped with zero test coverage, and the units it
returns were consequently misread by a client: a 0.5 fraction (50%) was rendered
as "0.5%". Assertions here pin the UNITS as much as the arithmetic — every ratio
the engine returns is a 0..1 fraction, and only the scores are 0..100.

Everything is in real terms, as the engine is. The withdrawal rate is passed
explicitly (the pack holds no assumption any more), with the same round figure
the old test pack carried, so every hand-computed figure below is unchanged.
The amounts are in no particular currency: the engine never looks at it.

When FI is reached is no longer walked by this engine: it comes from the
baseline's monthly timeline, where cash, investments and debts are kept apart
(domain/baseline/fi.py; tests/unit/domain/test_baseline_fi.py and
tests/golden/test_household_fi.py), and the caller passes the month in. What
a purchase costs is a scenario now (tests/golden/test_household_scenarios.py),
so the engine's own purchase costing, its yearly and monthly walks and its
projection are gone, and with them the tests that pinned them against each
other.
"""

from decimal import Decimal

from salli.domain.fi import engine
from salli.domain.fi.models import FinancialSnapshot, FiPack

# A pack with round numbers so expected values can be computed by hand.
PACK = FiPack(
    version="test-1",
    emergency_fund_target_months=6,
    savings_rate_for_full_score=Decimal("0.50"),
    weights={
        "savings_rate": Decimal("0.25"),
        "emergency_fund": Decimal("0.15"),
        "fi_progress": Decimal("0.35"),
        "debt": Decimal("0.10"),
        "goals": Decimal("0.15"),
    },
)

#: The withdrawal rate these scenarios assume.
SWR = Decimal("0.04")


def _score(snapshot: FinancialSnapshot, **over) -> object:
    return engine.compute(snapshot, PACK, **{"swr": SWR, **over})


def _snapshot(**over) -> FinancialSnapshot:
    base = dict(
        monthly_income=Decimal("100000"),
        monthly_expenses=Decimal("50000"),
        liquid_savings=Decimal("300000"),
        investments=Decimal("0"),
        total_assets=Decimal("300000"),
        total_liabilities=Decimal("0"),
        goal_progress=None,
        currency="PHP",
    )
    base.update(over)
    return FinancialSnapshot(**base)  # type: ignore[arg-type]


# ── Units: every ratio is a FRACTION, not a percentage ────────────────────────
#
# income 100,000, expenses 50,000 → surplus 50,000 → savings_rate = 0.5 (= 50%).
# The bug this guards: a client reading 0.5 and printing "0.5%".


def test_savings_rate_is_a_fraction_not_a_percentage():
    score = _score(_snapshot())
    assert score.savings_rate == Decimal("0.5")
    assert score.savings_rate < Decimal(1)


def test_debt_to_asset_is_a_fraction():
    score = _score(_snapshot(total_assets=Decimal("400000"), total_liabilities=Decimal("100000")))
    assert score.debt_to_asset == Decimal("0.25")


# ── FI number = target annual expenses / SWR ──────────────────────────────────
#
# 50,000/mo → 600,000/yr; at 4% → 15,000,000 (the classic 25x).


def test_fi_number_is_annual_expenses_over_swr():
    score = _score(_snapshot())
    assert score.annual_expenses == Decimal("600000")
    assert score.fi_number == Decimal("15000000")
    assert score.swr == Decimal("0.04")


def test_fi_number_uses_the_supplied_swr():
    """The 81.2M-vs-92.8M defect: two paths, two rates. One rate now wins, and
    the pack has none of its own to fall back on."""
    score = _score(_snapshot(), swr=Decimal("0.035"))
    # 600,000 / 0.035
    assert score.fi_number == Decimal("600000") / Decimal("0.035")
    assert score.swr == Decimal("0.035")


def test_target_monthly_expenses_moves_the_target_only():
    score = _score(_snapshot(), target_monthly_expenses=Decimal("40000"))
    assert score.annual_expenses == Decimal("480000")
    assert score.fi_number == Decimal("12000000")
    # Contribution basis is untouched: still actual income − actual expenses.
    assert score.monthly_surplus == Decimal("50000")


# ── Progress measures the FI asset base, not total net worth ──────────────────


def test_progress_uses_investable_assets_net_of_debt():
    snap = _snapshot(
        liquid_savings=Decimal("1000000"),
        investments=Decimal("500000"),
        total_assets=Decimal("9000000"),  # includes e.g. a house
        total_liabilities=Decimal("500000"),
    )
    score = _score(snap)
    # 1,000,000 + 500,000 − 500,000 = 1,000,000 — the house is excluded.
    assert score.fi_asset_base == Decimal("1000000")
    assert score.net_worth == Decimal("8500000")
    assert score.progress_to_fi == Decimal("1000000") / Decimal("15000000")


def test_progress_is_unclamped_so_past_fi_is_visible():
    snap = _snapshot(liquid_savings=Decimal("30000000"), total_assets=Decimal("30000000"))
    score = _score(snap)
    assert score.progress_to_fi == Decimal(2)  # 200% of a 15M target
    # …while the *component score* still clamps at 100.
    fi_comp = next(c for c in score.components if c.key == "fi_progress")
    assert fi_comp.score == Decimal("100.00")


# ── Component scores and weight renormalisation ───────────────────────────────


def test_component_scores_are_zero_to_hundred():
    score = _score(_snapshot())
    by_key = {c.key: c for c in score.components}
    # savings_rate 0.5 / 0.50 → full marks
    assert by_key["savings_rate"].score == Decimal("100.00")
    # liquid 300,000 / expenses 50,000 = 6 months / 6 target → full marks
    assert by_key["emergency_fund"].score == Decimal("100.00")
    # no liabilities → (1 − 0) × 100
    assert by_key["debt"].score == Decimal("100.00")
    # 300,000 / 15,000,000 = 2%
    assert by_key["fi_progress"].score == Decimal("2.00")


def test_weights_renormalise_when_goals_absent():
    score = _score(_snapshot())
    assert {c.key for c in score.components} == {
        "savings_rate",
        "emergency_fund",
        "fi_progress",
        "debt",
    }
    # 0.25/0.85, 0.15/0.85, 0.35/0.85, 0.10/0.85 → sums to 1
    assert sum((c.weight for c in score.components), Decimal(0)) == Decimal("1.00")
    by_key = {c.key: c for c in score.components}
    assert by_key["savings_rate"].weight == Decimal("0.29")
    assert by_key["fi_progress"].weight == Decimal("0.41")


def test_goals_component_included_when_present():
    score = _score(_snapshot(goal_progress=Decimal("0.5")))
    by_key = {c.key: c for c in score.components}
    assert by_key["goals"].score == Decimal("50.00")
    # All five weights present → the raw pack weights, no renormalisation.
    assert by_key["savings_rate"].weight == Decimal("0.25")


# ── The exact score the user reported: regression case ────────────────────────
#
# Reported: "Strong" 61/100 while the UI showed "Savings rate 0.5%" and
# component savings_rate 100. Reconstructed:
#   savings_rate  0.5/0.50×100  = 100.00  × 0.25/0.85 = 29.41
#   emergency     clamped       = 100.00  × 0.15/0.85 = 17.65
#   fi_progress   0.0531×100    =   5.31  × 0.35/0.85 =  2.19
#   debt          (1−0)×100     = 100.00  × 0.10/0.85 = 11.76
#                                                     = 61.01 → "Strong"
# Proof the engine was right and only the display was wrong.


def test_reported_sixty_one_reconstructs_exactly():
    snap = _snapshot(
        monthly_income=Decimal("541334"),
        monthly_expenses=Decimal("270667"),
        liquid_savings=Decimal("4310000"),
        investments=Decimal("0"),
        total_assets=Decimal("4310000"),
        total_liabilities=Decimal("0"),
    )
    score = _score(snap)
    assert score.savings_rate == Decimal("0.5")
    by_key = {c.key: c for c in score.components}
    assert by_key["savings_rate"].score == Decimal("100.00")
    assert by_key["debt"].score == Decimal("100.00")
    assert score.overall_score == Decimal("61.01")
    assert score.grade == "Strong"


# ── The FI month is the caller's ──────────────────────────────────────────────


def test_the_fi_month_is_the_one_the_caller_passes():
    """Was walked here, at the real return, the whole asset base compounding
    together. Now the baseline's monthly timeline finds it and the score
    carries it through unchanged."""
    assert _score(_snapshot(), projected_fi_months=197).projected_fi_months == 197
    assert _score(_snapshot()).projected_fi_months is None


# ── Empty-ledger edge case ────────────────────────────────────────────────────


def test_empty_ledger_reports_no_fi_date_rather_than_zero_years():
    snap = _snapshot(
        monthly_income=Decimal(0),
        monthly_expenses=Decimal(0),
        liquid_savings=Decimal(0),
        total_assets=Decimal(0),
    )
    score = _score(snap)
    assert score.fi_number == Decimal(0)
    assert score.savings_rate == Decimal(0)
    assert score.projected_fi_months is None
    assert score.grade == "Just starting"


# ── Pack integrity ───────────────────────────────────────────────────────────


def test_shipped_pack_weights_sum_to_one():
    from salli.domain.fi.packs import registry

    pack = registry.get_pack()
    assert sum(pack.weights.values(), Decimal(0)) == Decimal(1)


def test_the_shipped_pack_holds_no_planning_assumption():
    """The withdrawal rate, returns and inflation are the user's, or labelled
    placeholders (domain/fi/assumptions.py), never the pack's."""
    from dataclasses import fields

    names = {f.name for f in fields(FiPack)}
    assert not names & {"safe_withdrawal_rate", "expected_real_return", "expected_inflation"}
