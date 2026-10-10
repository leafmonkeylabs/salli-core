"""
Golden tests for the FI ("Freedom") engine — hand-computed scenarios.

These exist because the engine shipped with zero test coverage, and the units it
returns were consequently misread by a client: a 0.5 fraction (50%) was rendered
as "0.5%". Assertions here pin the UNITS as much as the arithmetic — every ratio
the engine returns is a 0..1 fraction, and only the scores are 0..100.

Everything is in real terms, as the engine is. The withdrawal rate and the real
return are passed explicitly (the pack holds no assumption any more), with the
same round figures the old test pack carried, so every hand-computed figure
below is unchanged. The amounts are in no particular currency: the engine never
looks at it.
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

#: The withdrawal rate and base real return these scenarios assume.
SWR = Decimal("0.04")
REAL = Decimal("0.05")
#: Real returns per scenario, around REAL.
RATES = {"conservative": Decimal("0.03"), "base": REAL, "growth": Decimal("0.07")}


def _score(snapshot: FinancialSnapshot, **over) -> object:
    return engine.compute(snapshot, PACK, **{"swr": SWR, "annual_real_return": REAL, **over})


def _impact(snapshot: FinancialSnapshot, amount: Decimal, **over):
    return engine.simulate_purchase(
        snapshot, PACK, amount, **{"swr": SWR, "annual_real_return": REAL, **over}
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


# ── Real terms, and future money from the user's inflation ───────────────────
#
# Changed expectation: this section used to check that a projection run with
# the strategy's NOMINAL returns converted at 5% inflation trailed the same run
# at 0% inflation. Projections now take real returns directly, so there is no
# conversion to test there. What is pinned instead is that the user's inflation
# only ever changes how the same real projection is shown in future money.


def test_projection_in_future_money_is_the_real_one_grown_by_inflation():
    snap = _snapshot()
    real = engine.project_portfolio(snap, RATES, horizon_years=10)
    both = engine.project_portfolio(snap, RATES, horizon_years=10, inflation=Decimal("0.03"))

    assert all(p.nominal is None for p in real)
    for r, b in zip(real, both, strict=True):
        # The real walk is untouched by inflation.
        assert (r.conservative, r.base, r.growth) == (b.conservative, b.base, b.growth)
        assert b.nominal is not None
        factor = Decimal("1.03") ** r.year
        assert b.nominal.base == (r.base * factor).quantize(Decimal("0.01"))
    # Today is today in both.
    assert both[0].nominal is not None and both[0].nominal.base == both[0].base
    # With positive inflation, a future amount is more money than today's.
    assert both[-1].nominal is not None and both[-1].nominal.growth > both[-1].growth


def test_future_money_is_rounded_to_the_cent():
    # 1,000 × 1.03² = 1,060.90 exactly; × 1.025³ = 1,076.890625 → 1,076.89.
    assert engine.in_future_money(Decimal("1000"), Decimal("0.03"), 2) == Decimal("1060.90")
    assert engine.in_future_money(Decimal("1000"), Decimal("0.025"), 3) == Decimal("1076.89")
    assert engine.in_future_money(Decimal("1000"), Decimal("0.03"), 0) == Decimal("1000.00")


def test_higher_real_returns_reach_further():
    pts = engine.project_portfolio(_snapshot(), RATES, horizon_years=10)
    assert pts[-1].conservative < pts[-1].base < pts[-1].growth


# ── Years-to-FI agrees with the projected series ──────────────────────────────


def test_years_to_target_matches_where_the_projection_crosses():
    """
    The defect this pins: years-to-FI and the chart were separate
    implementations with different bases, rates and compounding, and disagreed
    (measured 14 vs 12 on one snapshot).
    """
    snap = _snapshot()
    score = _score(snap, annual_real_return=RATES["base"])
    points = engine.project_portfolio(snap, RATES, horizon_years=60)

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
    score = _score(snap)
    assert score.fi_number == Decimal(0)
    assert score.savings_rate == Decimal(0)
    assert score.projected_fi_years is None
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


# ── simulate_purchase — hand-checked purchase scenarios ───────────────────────
#
# Round figures so they are legible: 250,000 income, 200,000 expenses (50,000
# monthly surplus), 600,000 liquid, 900,000 invested, 400,000 owed → FI asset
# base 1,100,000.


def _buyer(**over) -> FinancialSnapshot:
    base = dict(
        monthly_income=Decimal("250000"),
        monthly_expenses=Decimal("200000"),
        liquid_savings=Decimal("600000"),
        investments=Decimal("900000"),
        total_assets=Decimal("1500000"),
        total_liabilities=Decimal("400000"),
        goal_progress=None,
        currency="KES",
    )
    base.update(over)
    return FinancialSnapshot(**base)  # type: ignore[arg-type]


def test_purchase_is_costed_in_months_of_freedom():
    impact = _impact(_buyer(), Decimal("450000"))

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
    impact = _impact(_buyer(), Decimal("450000"))

    assert impact.payable_from_liquid is True  # 600,000 ≥ 450,000
    assert impact.emergency_months_before == Decimal("3.00")  # 600k / 200k
    assert impact.emergency_months_after_cash == Decimal("0.75")  # 150k / 200k
    assert impact.emergency_fund_target_months == 6
    assert impact.emergency_months_after_cash < impact.emergency_fund_target_months


def test_purchase_beyond_liquid_savings_is_flagged():
    impact = _impact(_buyer(), Decimal("900000"))
    assert impact.payable_from_liquid is False  # 600,000 < 900,000
    assert impact.emergency_months_after_cash < 0  # honestly negative, not clamped


def test_installments_cost_more_in_total_and_in_freedom():
    impact = _impact(
        _buyer(),
        Decimal("450000"),
        term_months=12,
        annual_interest_rate=Decimal("0.18"),
    )
    cash, inst = impact.options[0], impact.options[1]

    assert inst.term_months == 12
    assert inst.monthly_payment == Decimal("41256.00")  # 18% / 12 months on 450k
    assert inst.total_cost > cash.total_cost
    assert inst.interest_cost == Decimal("45071.96")
    # Cash is never the dearer option in absolute money.
    assert impact.cheapest_option_key == "cash"


def test_installment_exceeding_surplus_is_flagged():
    """A payment larger than the monthly surplus is cash-flow negative, not just slow."""
    impact = _impact(
        _buyer(),
        Decimal("450000"),
        term_months=6,  # ~78k/month against a 50k surplus
        annual_interest_rate=Decimal("0.18"),
    )
    inst = impact.options[1]
    assert inst.monthly_payment is not None and inst.monthly_payment > impact.monthly_surplus
    assert inst.exceeds_monthly_surplus is True


def test_no_installment_option_unless_a_term_is_given():
    impact = _impact(_buyer(), Decimal("450000"))
    assert [o.key for o in impact.options] == ["cash"]


def test_unreachable_target_reports_none_not_zero():
    """
    No surplus and no return means FI is not reachable. The delay must be None —
    reporting 0 would tell the user the purchase is free.
    """
    broke = _buyer(monthly_income=Decimal("200000"), monthly_expenses=Decimal("200000"))
    impact = _impact(broke, Decimal("450000"), annual_real_return=Decimal("0"))
    assert impact.baseline_months_to_fi is None
    assert impact.options[0].months_delay is None
    assert impact.cheapest_option_key is None


def test_staleness_is_carried_through_untouched():
    impact = _impact(_buyer(), Decimal("450000"), data_as_of="2026-03-01", is_stale=True)
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
        (SWR, None),
        (Decimal("0.035"), None),
        (Decimal("0.04"), Decimal("150000")),
        (Decimal("0.05"), Decimal("300000")),
    ):
        score = _score(snap, swr=swr, target_monthly_expenses=target_expenses)
        impact = _impact(snap, Decimal("450000"), swr=swr, target_monthly_expenses=target_expenses)
        assert impact.fi_number == score.fi_number, f"diverged at swr={swr}, exp={target_expenses}"
        assert impact.fi_asset_base_before == score.fi_asset_base
        assert impact.monthly_surplus == score.monthly_surplus


def test_purchase_baseline_agrees_with_the_headline_years():
    """
    The baseline month count must reconcile with `projected_fi_years`, which is
    what the dashboard shows. ceil(months / 12) == years, always.
    """
    snap = _buyer()
    score = _score(snap)
    impact = _impact(snap, Decimal("450000"))

    assert score.projected_fi_years is not None
    assert impact.baseline_months_to_fi is not None
    ceil_years = -(-impact.baseline_months_to_fi // 12)
    assert ceil_years == int(score.projected_fi_years)
