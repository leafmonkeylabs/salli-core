"""
The conformance suite: fictional jurisdictions that prove the engine can carry
the shapes real tax systems have, without encoding any real country's law.

Each document under conformance/ uses a user-assigned country code (XA–XG) and
made-up figures, and carries worked examples. The expected figures were worked
out by hand, below, independently of the engine; the engine must reproduce
every one exactly.

Taperland (XA) — an allowance withdrawn by 1 for every 2 of income over 100,000
    allowance = max(0, 12,000 − max(0, income − 100,000) / 2)
    bands on income − allowance: 20% to 40,000; 40% to 110,000; 45% above
    30,000:   allowance 12,000; taxable 18,000; tax 18,000 × 20% = 3,600
    100,000:  allowance 12,000; taxable 88,000;
              tax 40,000 × 20% + 48,000 × 40% = 8,000 + 19,200 = 27,200
    100,001:  allowance 12,000 − 0.5 = 11,999.5; taxable 88,001.5;
              tax 8,000 + 48,001.5 × 40% = 8,000 + 19,200.6 = 27,200.6 → 27,200.60
    124,000:  allowance 12,000 − 24,000 / 2 = 0; taxable 124,000;
              tax 8,000 + 70,000 × 40% + 14,000 × 45% = 8,000 + 28,000 + 6,300 = 42,300
    150,000 (120,000 + 30,000), withheld 50,000: allowance 0;
              tax 8,000 + 28,000 + 40,000 × 45% = 54,000; payable 54,000 − 50,000 = 4,000
    30,000, withheld 4,000: tax 3,600; net −400 → refund 400
    nothing:  allowance applied min(12,000, 0) = 0; tax 0

Jointland (XB) — filing status picks the allowance and the band table
    allowance: single 10,000, joint 20,000; +2,500 when blind (default: not)
    single: 10% to 20,000, 30% above; joint: 10% to 40,000, 30% above
    net rounded down (towards zero) to whole euros
    single 50,000: taxable 40,000; 20,000 × 10% + 20,000 × 30% = 2,000 + 6,000 = 8,000
    joint 50,000:  taxable 30,000; joint 30,000 × 10% = 3,000
                   (single rates, computed but unused: 2,000 + 10,000 × 30% = 5,000)
    single 30,000: taxable 20,000; 2,000, nothing in band 2
    joint, blind, 62,500.50, withheld 5,000: allowance 22,500; taxable 40,000.50;
                   40,000 × 10% + 0.50 × 30% = 4,000.15; net −999.85 → −999 → refund 999
    single 10,000: taxable 0
    joint, blind, 21,000: allowance 22,500 applies only up to 21,000; taxable 0

Stackland (XC) — gains in their own bands, stacked on ordinary taxable income
    ordinary: salary − 12,000; income tax 20% to 50,000, 40% above
    gains: gains − 3,000 exempt; CGT 10% to 50,000, 20% above, the bands filled
    from where ordinary taxable income ends:
        gains tax = CGT(ordinary + gains) − CGT(ordinary)
    net rounded to the nearest 0.05
    40,000 + gains 23,000: ordinary 28,000 → 5,600; gains 20,000 fill 28,000–48,000,
                   all at 10% → 2,000; total 7,600
    52,000 + 23,000: ordinary 40,000 → 8,000; gains 20,000 fill 40,000–60,000:
                   10,000 × 10% + 10,000 × 20% = 3,000; total 11,000
    80,000 + 13,000: ordinary 68,000 → 10,000 + 18,000 × 40% = 17,200;
                   gains 10,000 all above 50,000 → 2,000; total 19,200
    30,000 + 2,500: gains within the exemption → 0; ordinary 18,000 → 3,600
    62,000 + 3,001.10: ordinary exactly 50,000 → 10,000; gains 1.10 at 20% → 0.22;
                   10,000.22 → nearest 0.05 → 10,000.20
    gains 63,000 only, withheld 7,500: gains 60,000 → 5,000 + 10,000 × 20% = 7,000;
                   refund 500

Capland (XD) — a social contribution on earnings between a floor and a ceiling
    contribution = round down(8% × (clamp(earnings, 1,200,000, 6,000,000) − 1,200,000))
    taxable = earnings − 1,000,000 allowance − contribution;
    5% to 3,000,000, 20% above, each band rounded down to 1
    1,000,000: contribution 0; taxable 0
    1,200,000: contribution 0; taxable 200,000 → 10,000
    1,200,005: contribution 0.4 → 0; taxable 200,005 → 10,000.25 → 10,000
    4,000,000: contribution 8% × 2,800,000 = 224,000; taxable 2,776,000 → 138,800;
               payable 138,800 + 224,000 = 362,800
    6,000,000: contribution 8% × 4,800,000 = 384,000; taxable 4,616,000 →
               150,000 + 1,616,000 × 20% = 473,200; payable 857,200
    9,000,000, withheld 1,000,000 tax and 384,000 contributions: contribution capped
               at 384,000; taxable 7,616,000 → 150,000 + 923,200 = 1,073,200;
               payable 1,073,200 + 384,000 − 1,000,000 − 384,000 = 73,200

Formulaland (XE) — a formula tariff in zones, rounded down to whole units
    x = income − expenses, rounded down; y = (x − 10,000) / 10,000; z = (x − 20,000) / 10,000
    x ≤ 10,000: 0
    x ≤ 20,000: (600y + 1,400)y
    x ≤ 60,000: (200z + 2,600)z + 2,000
    above:      0.42x − 9,600         (zones meet at 20,000 → 2,000 and 60,000 → 15,600)
    10,000: 0;   10,000.99: x = 10,000 → 0
    15,000: y = 0.5; (300 + 1,400) × 0.5 = 850
    15,001: y = 0.5001; (300.06 + 1,400) × 0.5001 = 850.200006 → 850
    20,000: y = 1; 2,000 × 1 = 2,000
    33,333.99: x = 33,333; z = 1.3333; 200 × 1.3333 = 266.66; 2,866.66 × 1.3333 =
               3,822.117778; + 2,000 = 5,822.117778 → 5,822
    60,000: z = 4; 3,400 × 4 + 2,000 = 15,600
    100,000 − 5,000.50, withheld 40,000: x = 94,999; 0.42 × 94,999 = 39,899.58;
               − 9,600 = 30,299.58 → 30,299; refund 40,000 − 30,299 = 9,701

Rebateland (XF) — a rebate that cancels tax up to 20,000, with marginal relief
    gross: 10% to 30,000, 25% above, on all income
    rebate: all of the gross tax at or under 20,000; above it,
            max(0, gross − (income − 20,000)), so tax never exceeds income − 20,000
    18,000: gross 1,800, rebate 1,800, tax 0;   20,000: gross 2,000, tax 0
    20,000.01: gross 2,000.001; rebate 2,000.001 − 0.01 = 1,999.991; tax 0.01
    21,000: gross 2,100; rebate 2,100 − 1,000 = 1,100; tax 1,000 (= income over 20,000)
    22,222.22: gross 2,222.222; rebate 0.002; tax 2,222.22 (relief ends near here)
    25,000: gross 2,500 < 5,000 over → rebate 0; tax 2,500
    40,000, withheld 6,000: gross 3,000 + 10,000 × 25% = 5,500; refund 500

Remitland (XG) — final-rate foreign income outside the bands
    foreign tax = 10% of foreign income, rounded down to 1; relief 5,000 on local
    income only; local: 5% to 10,000, 15% to 30,000, 25% above, per band to 0.001;
    foreign tax credit non-refundable, capped at the foreign tax (per source);
    withholding refundable
    local 4,000: under the relief → 0
    local 20,000: taxable 15,000 → 500 + 5,000 × 15% = 1,250
    foreign 12,345.678 only: 1,234.5678 → 1,234; the relief has nothing to apply to
    local 20,000, foreign 10,000, paid abroad 600: 1,250 + 1,000 − 600 = 1,650
    … paid abroad 1,500: credit capped at 1,000 → 1,250 + 1,000 − 1,000 = 1,250
    local 20,000, withheld 2,000: 1,250 − 2,000 → refund 750
    local 6,000, foreign 5,000, paid abroad 900, withheld 300: local 1,000 × 5% = 50;
               foreign 500; credit min(900, 500) = 500; 550 − 500 − 300 → refund 250
               (without the withholding the bill would be 50: no refund from the credit)
    local 15,000.01: taxable 10,000.01 → 500 + 0.01 × 15% = 0.0015 → 0.002 (a tie
               goes away from zero); 500.002
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator

from salli.domain.taxrules.common import is_user_assigned_country
from salli.domain.taxrules.engine import compile_rule_set, evaluate
from salli.domain.taxrules.schema import rule_set_json_schema
from salli.domain.taxrules.validate import validate

CONFORMANCE = Path(__file__).parent / "conformance"
DOCUMENTS = sorted(CONFORMANCE.glob("*.json"))
EXPECTED = {
    "taperland",
    "jointland",
    "stackland",
    "capland",
    "formulaland",
    "rebateland",
    "remitland",
}


def test_every_jurisdiction_in_the_suite_is_present():
    assert {p.stem for p in DOCUMENTS} == EXPECTED


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.stem)
def test_each_fictional_jurisdiction_validates_and_every_example_passes(path):
    report = validate(path.read_text())
    assert report.errors == ()
    assert report.warnings == ()
    failures = [
        (e.name, e.error, [str(m) for m in e.mismatches]) for e in report.examples if not e.passed
    ]
    assert failures == []
    assert len(report.examples) >= 6
    assert report.ok


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.stem)
def test_no_real_country_is_encoded(path):
    doc = json.loads(path.read_text())
    assert is_user_assigned_country(doc["jurisdiction"]["country"])
    assert all(s["url"].startswith("https://example.org/") for s in doc["sources"])


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.stem)
def test_each_document_matches_the_published_json_schema(path):
    Draft202012Validator(rule_set_json_schema()).validate(json.loads(path.read_text()))


# ── Rebateland's guarantee, for every income near the threshold ────────────────

REBATELAND = compile_rule_set(json.loads((CONFORMANCE / "rebateland.json").read_text()))


@settings(max_examples=300)
@given(st.decimals(min_value=Decimal("20000"), max_value=Decimal("30000"), places=2))
def test_rebateland_tax_never_exceeds_the_income_above_the_threshold(income):
    result = evaluate(REBATELAND, {"income": income})
    tax = result.amount("tax")
    assert Decimal(0) <= tax <= income - Decimal("20000")
    assert tax <= result.amount("gross_tax")


# ── Taperland's taper, for every income ────────────────────────────────────────

TAPERLAND = compile_rule_set(json.loads((CONFORMANCE / "taperland.json").read_text()))


@settings(max_examples=300)
@given(st.decimals(min_value=Decimal("0"), max_value=Decimal("200000"), places=2))
def test_taperland_allowance_falls_by_half_of_each_unit_over_the_threshold(income):
    result = evaluate(TAPERLAND, {"employment_income": income})
    over = max(Decimal(0), income - Decimal("100000"))
    assert result.amount("allowance") == max(Decimal(0), Decimal("12000") - over / 2)
