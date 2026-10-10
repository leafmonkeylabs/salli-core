"""
Parity: the rule-set engine reproduces the built-in Sri Lanka 2025/26 pack
figure for figure.

DELETED IN PHASE 3, with the built-in pack, the old engine and the fixture
fixtures/lk_2025_26_parity.json (docs/design/country-neutral-core.md). Until
then it is the proof that a rule set can carry exactly what salli.domain.tax
computes today: every golden case, and a few thousand random ledgers, must give
the same figures from both engines, compared with Decimal `==` (exact value,
no tolerance).

The fixture is the one place real-country data appears in this package's
tests, and it is a copy of the pack, not a reviewed statement of the law.
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from salli.domain.tax.engine import compute
from salli.domain.tax.models import LedgerView, TaxComputation, TaxPack
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.domain.taxrules.engine import CompiledRuleSet, RuleSetResult, compile_rule_set, evaluate
from salli.domain.taxrules.validate import validate

FIXTURE = Path(__file__).parent / "fixtures" / "lk_2025_26_parity.json"

#: Each LedgerView field, and the role its total is given as.
ROLES = {
    "total_income": "total_income",
    "foreign_service_income": "foreign_service_income",
    "apit_withheld": "apit_withheld",
    "ait_withheld": "ait_withheld",
    "foreign_tax_paid": "foreign_tax_paid",
    "qualifying_payments": "qualifying_payments",
}

#: Each TaxComputation figure, and the rule-set line that must equal it.
#: Band workings are compared band by band below: band N's `taxable_in_band`
#: is line `general.band_N.amount` and its `tax` is `general.band_N.tax`; a
#: band the old engine never reached must be zero in both lines.
LINES = {
    "gross_income": "gross",
    "foreign_service_income": "foreign_service_income",
    "regular_income": "regular_income",
    "personal_relief_applied": "personal_relief",
    "qp_deduction": "qualifying_payments",
    "taxable_income": "taxable_income",
    "fsi_tax": "fsi_tax",
    "tax_before_credits": "tax_before_credits",
    "apit_credit": "apit",
    "ait_credit": "ait",
    "foreign_tax_credit": "foreign_tax_credit",
    "total_credits": "total_credits",
}
#: And the two that are the result's rather than a line's.
RESULT = {"tax_payable": "tax_payable", "refund_due": "refund_due"}


def fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def rule_set_for(pack: TaxPack) -> CompiledRuleSet:
    """The fixture for `pack`. The golden tests vary one figure of the stock
    pack (the qualifying-payment cap), and that one figure only."""
    doc = fixture()
    if pack != LK_2025_26:
        assert replace(pack, qualifying_payment_cap=LK_2025_26.qualifying_payment_cap) == LK_2025_26
        (block,) = [b for b in doc["blocks"] if b["key"] == "qualifying_payments"]
        block["cap"] = format(pack.qualifying_payment_cap, "f")
    return compile_rule_set(doc)


STOCK = rule_set_for(LK_2025_26)


def run(compiled: CompiledRuleSet, ledger: LedgerView) -> RuleSetResult:
    return evaluate(compiled, {role: getattr(ledger, field) for field, role in ROLES.items()})


def differences(old: TaxComputation, new: RuleSetResult, compiled: CompiledRuleSet) -> list[str]:
    """Every figure that differs between the two engines (empty when none)."""
    out: list[str] = []

    def check(name: str, a: Decimal, b: Decimal) -> None:
        if not (isinstance(a, Decimal) and isinstance(b, Decimal) and a == b):
            out.append(f"{name}: built-in {a!r}, rule set {b!r}")

    for figure, key in LINES.items():
        check(f"{figure} / line {key}", getattr(old, figure), new.amount(key))
    for figure, attr in RESULT.items():
        check(f"{figure} / result.{attr}", getattr(old, figure), getattr(new, attr))

    table = compiled.tables["general"]
    for n in range(1, len(table.bands) + 1):
        amount, tax = new.amount(f"general.band_{n}.amount"), new.amount(f"general.band_{n}.tax")
        if n <= len(old.band_workings):
            working = old.band_workings[n - 1]
            check(f"band {n} taxable_in_band", working.taxable_in_band, amount)
            check(f"band {n} tax", working.tax, tax)
            check(f"band {n} rate", working.rate, table.bands[n - 1].rate)
            if working.to_amount is not None or table.bands[n - 1].upto is not None:
                check(f"band {n} ceiling", working.to_amount, table.bands[n - 1].upto)  # type: ignore[arg-type]
        else:
            check(f"band {n} (not reached) amount", Decimal(0), amount)
            check(f"band {n} (not reached) tax", Decimal(0), tax)

    if (old.pack_country, old.pack_year, old.currency) != (new.country, new.year, new.currency):
        out.append("jurisdiction, year or currency differ")
    return out


def test_the_fixture_validates_with_every_golden_example():
    report = validate(FIXTURE.read_text())
    assert report.errors == ()
    assert all(e.passed for e in report.examples)
    assert report.ok


def test_the_fixtures_figures_are_the_packs():
    """The fixture is a copy of LK_2025_26: if the pack changes, this fails
    rather than the parity tests quietly comparing different rules."""
    pack = LK_2025_26
    doc = fixture()
    blocks = {b["key"]: b for b in doc["blocks"]}
    bands = [
        (None if b["upto"] is None else Decimal(b["upto"]), Decimal(b["rate"]))
        for b in doc["band_tables"]["general"]["bands"]
    ]
    assert bands == [(b.upto, b.rate) for b in pack.bands]
    assert Decimal(blocks["personal_relief"]["amount"]) == pack.personal_relief
    assert Decimal(blocks["qualifying_payments"]["cap"]) == pack.qualifying_payment_cap
    assert Decimal(blocks["qualifying_payments"]["fraction"]) == pack.qualifying_payment_fraction
    assert pack.foreign_service_income is not None
    assert Decimal(blocks["fsi_tax"]["rate"]) == pack.foreign_service_income.max_rate
    assert pack.rounding == "nearest_rupee"
    nearest_rupee = {"mode": "nearest", "unit": "1"}
    assert doc["band_tables"]["general"]["round"] == nearest_rupee
    assert blocks["fsi_tax"]["round"] == nearest_rupee
    assert doc["result"]["round"] == nearest_rupee
    assert (doc["jurisdiction"]["country"], doc["year"]["label"], doc["currency"]) == (
        pack.country,
        pack.year,
        pack.currency,
    )
    assert (doc["year"]["start"], doc["year"]["end"]) == (pack.period_start, pack.period_end)


# ── (a) every case in tests/golden/test_lk_2025_26.py ──────────────────────────


def _golden_cases() -> list[tuple[str, LedgerView, TaxPack]]:
    """Every (ledger, pack) the golden tests compute, recorded by running
    them with `compute` wrapped, so a case added there is covered here."""
    import tests.golden.test_lk_2025_26 as golden

    cases: list[tuple[str, LedgerView, TaxPack]] = []
    current = ""

    def recording(ledger: LedgerView, pack: TaxPack) -> TaxComputation:
        cases.append((current, ledger, pack))
        return compute(ledger, pack)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(golden, "compute", recording)
        for name, test in sorted(vars(golden).items()):
            if name.startswith("test_") and callable(test):
                current = name
                test()
    return cases


GOLDEN = _golden_cases()


def test_every_golden_test_was_recorded():
    import tests.golden.test_lk_2025_26 as golden

    tests = {name for name in vars(golden) if name.startswith("test_")}
    assert {name for name, _, _ in GOLDEN} == tests
    assert len(GOLDEN) >= 17


@pytest.mark.parametrize(
    ("name", "ledger", "pack"), GOLDEN, ids=[f"{n}[{i}]" for i, (n, _, _) in enumerate(GOLDEN)]
)
def test_every_golden_case_gives_the_same_figures_from_both_engines(name, ledger, pack):
    compiled = STOCK if pack == LK_2025_26 else rule_set_for(pack)
    assert differences(compute(ledger, pack), run(compiled, ledger), compiled) == []


# ── (b) a few thousand random ledgers ──────────────────────────────────────────

money = st.decimals(min_value=0, max_value=Decimal("50000000"), places=2)
fine_money = st.decimals(min_value=0, max_value=Decimal("50000000"), places=4)


@st.composite
def ledgers(draw: Any) -> LedgerView:
    shape = draw(
        st.sampled_from(
            [
                "any",
                "fine",
                "fsi_only",
                "fsi_above_gross",
                "qp_above_caps",
                "qp_below_cap",
                "ftc_above_liability",
                "withholding_above_tax",
                "near_relief",
                "zero",
            ]
        )
    )
    amount = fine_money if shape == "fine" else money
    total = draw(amount)
    fsi = draw(st.one_of(st.just(Decimal(0)), amount.filter(lambda v: v <= total)))
    apit, ait, ftc, qp = (draw(st.one_of(st.just(Decimal(0)), amount)) for _ in range(4))
    if shape == "fsi_only":
        fsi = total
    elif shape == "fsi_above_gross":
        fsi = total + draw(money)
    elif shape == "qp_above_caps":
        qp = Decimal("75000") + draw(money)
    elif shape == "qp_below_cap":
        # Taxable income small enough that a third of it is the binding cap,
        # where 1/3's 28 digits decide the figures.
        total = Decimal("1800000") + draw(st.decimals(min_value=0, max_value=225000, places=4))
        fsi = Decimal(0)
        qp = draw(st.decimals(min_value=0, max_value=200000, places=2))
    elif shape == "ftc_above_liability":
        fsi = draw(money.filter(lambda v: v <= total))
        ftc = total + draw(money)
    elif shape == "withholding_above_tax":
        apit = total + draw(money)
    elif shape == "near_relief":
        total = Decimal("1800000") + draw(st.decimals(min_value=-50, max_value=50, places=2))
    elif shape == "zero":
        total = fsi = apit = ait = ftc = qp = Decimal(0)
    return LedgerView(
        total_income=total,
        foreign_service_income=fsi,
        apit_withheld=apit,
        ait_withheld=ait,
        foreign_tax_paid=ftc,
        qualifying_payments=qp,
    )


@settings(max_examples=4000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ledgers())
def test_random_ledgers_give_the_same_figures_from_both_engines(ledger):
    assert differences(compute(ledger, LK_2025_26), run(STOCK, ledger), STOCK) == []


signed_money = st.decimals(min_value=Decimal("-5000000"), max_value=Decimal("50000000"), places=2)


@settings(max_examples=1000, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(signed_money, signed_money, signed_money, signed_money, signed_money, signed_money)
def test_parity_holds_for_negative_totals_too(total, fsi, apit, ait, ftc, qp):
    """A ledger total can be negative (a reversal larger than the year's
    income); the rule set follows the built-in engine there as well."""
    ledger = LedgerView(total, fsi, apit, ait, ftc, qp)
    assert differences(compute(ledger, LK_2025_26), run(STOCK, ledger), STOCK) == []
