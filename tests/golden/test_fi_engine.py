"""
Golden tests for the FI ("Freedom") engine — hand-computed scenarios.

These exist because the engine shipped with zero test coverage, and the units it
returns were consequently misread by a client: a 0.5 fraction (50%) was rendered
as "0.5%". Assertions here pin the UNITS as much as the arithmetic — every ratio
the engine returns is a 0..1 fraction, and only the scores are 0..100.
"""

from decimal import Decimal

from salli.domain.fi import engine
from salli.domain.fi.models import FinancialSnapshot, FiPack, FireStrategy

# A pack with round numbers so expected values can be computed by hand.
PACK = FiPack(
    version="test-1",
    safe_withdrawal_rate=Decimal("0.04"),
    emergency_fund_target_months=6,
    expected_real_return=Decimal("0.05"),
    expected_inflation=Decimal("0.05"),
    savings_rate_for_full_score=Decimal("0.50"),
    weights={
        "savings_rate": Decimal("0.25"),
        "emergency_fund": Decimal("0.15"),
        "fi_progress": Decimal("0.35"),
        "debt": Decimal("0.10"),
        "goals": Decimal("0.15"),
    },
)


def _snapshot(**over) -> FinancialSnapshot:
    base = dict(
        monthly_income=Decimal("100000"),
        monthly_expenses=Decimal("50000"),
        liquid_savings=Decimal("300000"),
        investments=Decimal("0"),
        total_assets=Decimal("300000"),
        total_liabilities=Decimal("0"),
        goal_progress=None,
    )
    base.update(over)
    return FinancialSnapshot(**base)  # type: ignore[arg-type]


def _strategy(**over) -> FireStrategy:
    base = dict(
        version=1,
        fire_style="standard",
        swr=Decimal("0.04"),
        return_conservative=Decimal("0.06"),
        return_base=Decimal("0.10"),
        return_growth=Decimal("0.14"),
        target_monthly_expenses=None,
        target_age=None,
        buckets=[],
        ai_rationale="",
        theories_applied=[],
        created_at="",
        is_initial=True,
    )
    base.update(over)
    return FireStrategy(**base)  # type: ignore[arg-type]


# ── Units: every ratio is a FRACTION, not a percentage ────────────────────────
#
# income 100,000, expenses 50,000 → surplus 50,000 → savings_rate = 0.5 (= 50%).
# The bug this guards: a client reading 0.5 and printing "0.5%".


def test_savings_rate_is_a_fraction_not_a_percentage():
    score = engine.compute(_snapshot(), PACK)
    assert score.savings_rate == Decimal("0.5")
    assert score.savings_rate < Decimal(1)


def test_debt_to_asset_is_a_fraction():
    score = engine.compute(
        _snapshot(total_assets=Decimal("400000"), total_liabilities=Decimal("100000")), PACK
    )
    assert score.debt_to_asset == Decimal("0.25")


# ── FI number = target annual expenses / SWR ──────────────────────────────────
#
# 50,000/mo → 600,000/yr; at 4% → 15,000,000 (the classic 25x).


def test_fi_number_is_annual_expenses_over_swr():
    score = engine.compute(_snapshot(), PACK)
    assert score.annual_expenses == Decimal("600000")
    assert score.fi_number == Decimal("15000000")
    assert score.swr == Decimal("0.04")


def test_fi_number_uses_the_supplied_swr_not_the_pack():
    """The 81.2M-vs-92.8M defect: two paths, two rates. One rate now wins."""
    score = engine.compute(_snapshot(), PACK, swr=Decimal("0.035"))
    # 600,000 / 0.035
    assert score.fi_number == Decimal("600000") / Decimal("0.035")
    assert score.swr == Decimal("0.035")


def test_target_monthly_expenses_moves_the_target_only():
    score = engine.compute(_snapshot(), PACK, target_monthly_expenses=Decimal("40000"))
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
    score = engine.compute(snap, PACK)
    # 1,000,000 + 500,000 − 500,000 = 1,000,000 — the house is excluded.
    assert score.fi_asset_base == Decimal("1000000")
    assert score.net_worth == Decimal("8500000")
    assert score.progress_to_fi == Decimal("1000000") / Decimal("15000000")


def test_progress_is_unclamped_so_past_fi_is_visible():
    snap = _snapshot(liquid_savings=Decimal("30000000"), total_assets=Decimal("30000000"))
    score = engine.compute(snap, PACK)
    assert score.progress_to_fi == Decimal(2)  # 200% of a 15M target
    # …while the *component score* still clamps at 100.
    fi_comp = next(c for c in score.components if c.key == "fi_progress")
    assert fi_comp.score == Decimal("100.00")


# ── Component scores and weight renormalisation ───────────────────────────────


def test_component_scores_are_zero_to_hundred():
    score = engine.compute(_snapshot(), PACK)
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
    score = engine.compute(_snapshot(), PACK)
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
    score = engine.compute(_snapshot(goal_progress=Decimal("0.5")), PACK)
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
    score = engine.compute(snap, PACK, swr=Decimal("0.04"))
    assert score.savings_rate == Decimal("0.5")
    by_key = {c.key: c for c in score.components}
    assert by_key["savings_rate"].score == Decimal("100.00")
    assert by_key["debt"].score == Decimal("100.00")
    assert score.overall_score == Decimal("61.01")
    assert score.grade == "Strong"


# ── Real vs nominal returns ───────────────────────────────────────────────────


def test_real_return_strips_inflation():
    # (1.10 / 1.05) − 1 = 0.047619...
    r = engine.real_return(Decimal("0.10"), Decimal("0.05"))
    assert r.quantize(Decimal("0.0001")) == Decimal("0.0476")


def test_zero_inflation_leaves_return_unchanged():
    assert engine.real_return(Decimal("0.10"), Decimal("0")) == Decimal("0.10")


def test_projection_uses_real_returns_so_it_is_slower_than_nominal():
    snap = _snapshot()
    strat = _strategy()
    real_pack = PACK
    no_inflation = FiPack(**{**PACK.__dict__, "expected_inflation": Decimal("0")})

    real_pts = engine.project_portfolio(snap, strat, real_pack, horizon_years=10)
    nominal_pts = engine.project_portfolio(snap, strat, no_inflation, horizon_years=10)
    # Same contributions, but inflation-adjusted growth must trail nominal growth.
    assert real_pts[-1].base < nominal_pts[-1].base


# ── Years-to-FI agrees with the projected series ──────────────────────────────


def test_years_to_target_matches_where_the_projection_crosses():
    """
    The defect this pins: years-to-FI and the chart were separate
    implementations with different bases, rates and compounding, and disagreed
    (measured 14 vs 12 on one snapshot).
    """
    snap = _snapshot()
    strat = _strategy()
    rates = engine.scenario_real_returns(strat, PACK)
    score = engine.compute(snap, PACK, swr=strat.swr, annual_real_return=rates["base"])
    points = engine.project_portfolio(snap, strat, PACK, horizon_years=60)

    crossing = next(p.year for p in points if p.base >= score.fi_number)
    assert score.projected_fi_years is not None
    assert int(score.projected_fi_years) == crossing


def test_years_to_target_zero_when_already_past_target():
    assert engine.years_to_target(
        Decimal("200"), Decimal("10"), Decimal("0.05"), Decimal("100")
    ) == Decimal(0)


def test_years_to_target_none_when_no_target_yet():
    """An empty ledger has no FI number; "0 years" would claim the user is FI."""
    assert engine.years_to_target(Decimal(0), Decimal(0), Decimal("0.05"), Decimal(0)) is None


def test_years_to_target_none_when_unreachable():
    assert (
        engine.years_to_target(
            Decimal("1"), Decimal(0), Decimal(0), Decimal("1000000"), max_years=5
        )
        is None
    )


# ── Empty-ledger edge case ────────────────────────────────────────────────────


def test_empty_ledger_reports_no_fi_date_rather_than_zero_years():
    snap = _snapshot(
        monthly_income=Decimal(0),
        monthly_expenses=Decimal(0),
        liquid_savings=Decimal(0),
        total_assets=Decimal(0),
    )
    score = engine.compute(snap, PACK)
    assert score.fi_number == Decimal(0)
    assert score.savings_rate == Decimal(0)
    assert score.projected_fi_years is None
    assert score.grade == "Just starting"


# ── Pack integrity ───────────────────────────────────────────────────────────


def test_shipped_pack_weights_sum_to_one():
    from salli.domain.fi.packs import registry

    pack = registry.get_pack()
    assert sum(pack.weights.values(), Decimal(0)) == Decimal(1)


# ── simulate_purchase — hand-checked purchase scenarios ───────────────────────
#
# Scenarios use a realistic Sri Lankan professional so the figures are legible:
# LKR 250,000 income, 200,000 expenses (50,000 monthly surplus), 600,000 liquid,
# 900,000 invested, 400,000 owed → FI asset base 1,100,000.


def _buyer(**over) -> FinancialSnapshot:
    base = dict(
        monthly_income=Decimal("250000"),
        monthly_expenses=Decimal("200000"),
        liquid_savings=Decimal("600000"),
        investments=Decimal("900000"),
        total_assets=Decimal("1500000"),
        total_liabilities=Decimal("400000"),
        goal_progress=None,
    )
    base.update(over)
    return FinancialSnapshot(**base)  # type: ignore[arg-type]


def test_purchase_is_costed_in_months_of_freedom():
    impact = engine.simulate_purchase(_buyer(), PACK, Decimal("450000"))

    # FI number = 200,000 × 12 / 0.04 = 60,000,000
    assert impact.fi_number == Decimal("60000000")
    assert impact.fi_asset_base_before == Decimal("1100000.00")  # 600k + 900k − 400k
    assert impact.monthly_surplus == Decimal("50000.00")
    # A real delay, expressed in months — not a vague "this will slow you down".
    cash = impact.options[0]
    assert cash.months_delay is not None and cash.months_delay > 0
    assert cash.total_cost == Decimal("450000.00")
    assert cash.interest_cost == Decimal("0.00")


def test_the_engine_reports_an_emergency_fund_breach():
    """
    Paying cash here leaves under one month of expenses against a 6-month target.
    Affordability is not only about the FI date — this is the part a user needs
    loudest, and it is deterministic, not a judgement the LLM should make.
    """
    impact = engine.simulate_purchase(_buyer(), PACK, Decimal("450000"))

    assert impact.payable_from_liquid is True  # 600,000 ≥ 450,000
    assert impact.emergency_months_before == Decimal("3.00")  # 600k / 200k
    assert impact.emergency_months_after_cash == Decimal("0.75")  # 150k / 200k
    assert impact.emergency_fund_target_months == 6
    assert impact.emergency_months_after_cash < impact.emergency_fund_target_months


def test_purchase_beyond_liquid_savings_is_flagged():
    impact = engine.simulate_purchase(_buyer(), PACK, Decimal("900000"))
    assert impact.payable_from_liquid is False  # 600,000 < 900,000
    assert impact.emergency_months_after_cash < 0  # honestly negative, not clamped


def test_installments_cost_more_in_total_and_in_freedom():
    impact = engine.simulate_purchase(
        _buyer(),
        PACK,
        Decimal("450000"),
        term_months=12,
        annual_interest_rate=Decimal("0.18"),
    )
    cash, inst = impact.options[0], impact.options[1]

    assert inst.term_months == 12
    assert inst.monthly_payment == Decimal("41256.00")  # 18% / 12 months on 450k
    assert inst.total_cost > cash.total_cost
    assert inst.interest_cost == Decimal("45071.96")
    # Cash is never the dearer option in absolute rupees.
    assert impact.cheapest_option_key == "cash"


def test_installment_exceeding_surplus_is_flagged():
    """A payment larger than the monthly surplus is cash-flow negative, not just slow."""
    impact = engine.simulate_purchase(
        _buyer(),
        PACK,
        Decimal("450000"),
        term_months=6,  # ~78k/month against a 50k surplus
        annual_interest_rate=Decimal("0.18"),
    )
    inst = impact.options[1]
    assert inst.monthly_payment is not None and inst.monthly_payment > impact.monthly_surplus
    assert inst.exceeds_monthly_surplus is True


def test_no_installment_option_unless_a_term_is_given():
    impact = engine.simulate_purchase(_buyer(), PACK, Decimal("450000"))
    assert [o.key for o in impact.options] == ["cash"]


def test_unreachable_target_reports_none_not_zero():
    """
    No surplus and no return means FI is not reachable. The delay must be None —
    reporting 0 would tell the user the purchase is free.
    """
    broke = _buyer(monthly_income=Decimal("200000"), monthly_expenses=Decimal("200000"))
    impact = engine.simulate_purchase(
        broke, PACK, Decimal("450000"), annual_real_return=Decimal("0")
    )
    assert impact.baseline_months_to_fi is None
    assert impact.options[0].months_delay is None
    assert impact.cheapest_option_key is None


def test_staleness_is_carried_through_untouched():
    impact = engine.simulate_purchase(
        _buyer(), PACK, Decimal("450000"), data_as_of="2026-03-01", is_stale=True
    )
    assert impact.data_as_of == "2026-03-01"
    assert impact.is_stale is True


def test_purchase_and_score_agree_on_the_fi_number():
    """
    `simulate_purchase` and `compute` must derive an IDENTICAL Freedom number from
    the same inputs.

    This is the audit's headline bug in miniature: the FI number was once computed
    in two places with different withdrawal rates, and the page showed 81.2M in one
    panel and 92.8M in another. Any new surface that re-derives the target is a
    place for those to drift apart again, so pin them equal — including when a
    strategy overrides the SWR and the target expenses.
    """
    snap = _buyer()
    for swr, target_expenses in (
        (None, None),
        (Decimal("0.035"), None),
        (Decimal("0.04"), Decimal("150000")),
        (Decimal("0.05"), Decimal("300000")),
    ):
        score = engine.compute(snap, PACK, swr=swr, target_monthly_expenses=target_expenses)
        impact = engine.simulate_purchase(
            snap, PACK, Decimal("450000"), swr=swr, target_monthly_expenses=target_expenses
        )
        assert impact.fi_number == score.fi_number, f"diverged at swr={swr}, exp={target_expenses}"
        assert impact.fi_asset_base_before == score.fi_asset_base
        assert impact.monthly_surplus == score.monthly_surplus


def test_purchase_baseline_agrees_with_the_headline_years():
    """
    The baseline month count must reconcile with `projected_fi_years`, which is
    what the dashboard shows. ceil(months / 12) == years, always.
    """
    snap = _buyer()
    score = engine.compute(snap, PACK)
    impact = engine.simulate_purchase(snap, PACK, Decimal("450000"))

    assert score.projected_fi_years is not None
    assert impact.baseline_months_to_fi is not None
    ceil_years = -(-impact.baseline_months_to_fi // 12)
    assert ceil_years == int(score.projected_fi_years)
