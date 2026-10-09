"""
Golden tests for the Sri Lanka 2025/26 tax pack.

These are worked examples computed by hand against the IRD's published
rate bands and the Inland Revenue (Amendment) Act No. 2 of 2025.
A chartered accountant must review and sign off these figures before
the pack is used in production.

STATUS: pending CA review — figures are based on the Act; treat as draft.
"""

from decimal import Decimal

from salli.domain.tax.engine import compute
from salli.domain.tax.models import LedgerView
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26


def ledger(
    total_income: str,
    apit: str = "0",
    ait: str = "0",
    ftc: str = "0",
    qp: str = "0",
    fsi: str = "0",
) -> LedgerView:
    return LedgerView(
        total_income=Decimal(total_income),
        foreign_service_income=Decimal(fsi),
        apit_withheld=Decimal(apit),
        ait_withheld=Decimal(ait),
        foreign_tax_paid=Decimal(ftc),
        qualifying_payments=Decimal(qp),
    )


# ── Case 1: Income below personal relief ──────────────────────────────────────
# Gross = LKR 1,500,000 — below LKR 1,800,000 relief → tax = 0


def test_income_below_relief_no_tax():
    result = compute(ledger("1_500_000"), LK_2025_26)
    assert result.taxable_income == Decimal(0)
    assert result.tax_payable == Decimal(0)


# ── Case 2: Just above relief — falls entirely in the 6% band ─────────────────
# Gross = LKR 2,300,000
# Taxable = 2,300,000 − 1,800,000 = 500,000
# Tax = 500,000 × 6% = 30,000 (within first LKR 1,000,000 band)


def test_single_band_6_percent():
    result = compute(ledger("2_300_000"), LK_2025_26)
    assert result.taxable_income == Decimal("500_000")
    assert result.tax_payable == Decimal("30_000")


# ── Case 3: Spans first two bands ─────────────────────────────────────────────
# Gross = LKR 3,300,000
# Taxable = 3,300,000 − 1,800,000 = 1,500,000
# Band 1: 1,000,000 × 6%  = 60,000
# Band 2: 500,000 × 18% = 90,000
# Total tax = 150,000


def test_two_bands():
    result = compute(ledger("3_300_000"), LK_2025_26)
    assert result.taxable_income == Decimal("1_500_000")
    assert result.tax_payable == Decimal("150_000")


# ── Case 4: Full band traversal up to 36% ─────────────────────────────────────
# Gross = LKR 6,500,000
# Taxable = 6,500,000 − 1,800,000 = 4,700,000
# Band 1: 1,000,000 × 6%  = 60,000
# Band 2: 500,000 × 18%  = 90,000
# Band 3: 500,000 × 24%  = 120,000
# Band 4: 500,000 × 30%  = 150,000
# Band 5: 2,200,000 × 36% = 792,000
# Total = 1,212,000


def test_all_bands():
    result = compute(ledger("6_500_000"), LK_2025_26)
    assert result.taxable_income == Decimal("4_700_000")
    assert result.tax_payable == Decimal("1_212_000")


# ── Case 5: APIT credit reduces payable ───────────────────────────────────────
# Same as Case 2 but employer withheld LKR 20,000 APIT
# Payable = 30,000 − 20,000 = 10,000


def test_apit_credit():
    result = compute(ledger("2_300_000", apit="20_000"), LK_2025_26)
    assert result.apit_credit == Decimal("20_000")
    assert result.tax_payable == Decimal("10_000")


# ── Case 6: Credits exceed tax — payable floors at zero ───────────────────────


def test_excess_credits_floor_at_zero():
    result = compute(ledger("2_300_000", apit="50_000"), LK_2025_26)
    assert result.tax_payable == Decimal(0)


# Withheld tax in excess of the liability is money the taxpayer is owed, and it
# used to vanish: `tax_payable` floors at zero and nothing else recorded it.
# Gross 2,300,000 → taxable 500,000 → tax 30,000; APIT 50,000 → refund 20,000.


def test_excess_apit_is_reported_as_a_refund():
    result = compute(ledger("2_300_000", apit="50_000"), LK_2025_26)
    assert result.tax_payable == Decimal(0)
    assert result.refund_due == Decimal("20_000")


def test_no_refund_when_credits_match_liability():
    result = compute(ledger("2_300_000", apit="30_000"), LK_2025_26)
    assert result.tax_payable == Decimal(0)
    assert result.refund_due == Decimal(0)


# ── Case 7: Qualifying payments deduction ─────────────────────────────────────
# Gross = 2,800,000; taxable before QP = 1,000,000
# QP = 100,000; cap = min(1,000,000/3, 75,000) = 75,000
# Taxable after QP = 925,000
# Tax = 925,000 × 6% = 55,500


def test_qualifying_payments_deduction():
    result = compute(ledger("2_800_000", qp="100_000"), LK_2025_26)
    assert result.taxable_income == Decimal("925_000")
    assert result.tax_payable == Decimal("55_500")


# ── Case 8: Relief capped at gross when gross < relief ────────────────────────


def test_relief_capped_at_gross():
    result = compute(ledger("1_000_000"), LK_2025_26)
    assert result.personal_relief_applied == Decimal("1_000_000")
    assert result.taxable_income == Decimal(0)
    assert result.tax_payable == Decimal(0)


# ── Pack metadata ──────────────────────────────────────────────────────────────


def test_pack_version_recorded():
    result = compute(ledger("3_000_000"), LK_2025_26)
    assert result.pack_country == "LK"
    assert result.pack_year == "2025/26"
    assert result.pack_version == "1.0.0"


# ── Foreign Service Income ────────────────────────────────────────────────────
# The pack has carried an FSI regime since day one with no golden coverage at
# all, in either direction — neither the flat 15% nor its interaction with
# relief. These pin both.


def test_fsi_taxed_flat_and_excluded_from_the_bands():
    """FSI is taxed at 15% outside the progressive bands, and personal relief
    applies only to the regular income that remains."""
    # 5,000,000 gross of which 3,000,000 is FSI.
    # FSI tax = 3,000,000 × 15% = 450,000
    # Regular = 2,000,000; relief 1,800,000 → taxable 200,000 → 6% = 12,000
    result = compute(ledger("5_000_000", fsi="3_000_000"), LK_2025_26)
    assert result.foreign_service_income == Decimal("3_000_000")
    assert result.regular_income == Decimal("2_000_000")
    assert result.fsi_tax == Decimal("450_000")
    assert result.taxable_income == Decimal("200_000")
    assert result.tax_before_credits == Decimal("462_000")
    assert result.tax_payable == Decimal("462_000")


def test_relief_does_not_shelter_fsi():
    """All income is FSI: relief has no regular income to apply to, so the whole
    amount stays taxed at the flat rate rather than being sheltered."""
    result = compute(ledger("3_000_000", fsi="3_000_000"), LK_2025_26)
    assert result.regular_income == Decimal(0)
    assert result.personal_relief_applied == Decimal(0)
    assert result.taxable_income == Decimal(0)
    assert result.tax_payable == Decimal("450_000")


def test_foreign_tax_credit_offsets_the_liability():
    """FSI 3,000,000 → 450,000 LK tax; 200,000 already paid abroad leaves
    250,000 to pay here."""
    result = compute(ledger("3_000_000", fsi="3_000_000", ftc="200_000"), LK_2025_26)
    assert result.foreign_tax_credit == Decimal("200_000")
    assert result.tax_payable == Decimal("250_000")


def test_foreign_tax_credit_cannot_create_a_refund():
    """A foreign tax credit relieves double taxation; it must not hand back tax
    paid to another government. Uncapped, this would report a refund."""
    result = compute(ledger("3_000_000", fsi="3_000_000", ftc="900_000"), LK_2025_26)
    assert result.foreign_tax_credit == Decimal("450_000"), "FTC capped at the liability"
    assert result.tax_payable == Decimal(0)
    assert result.refund_due == Decimal(0)


def test_qualifying_payment_cap_comes_from_the_pack():
    """The cap used to be a constant inside the engine, so any future country
    pack would have silently inherited Sri Lankan QP rules."""
    from dataclasses import replace

    generous = replace(LK_2025_26, qualifying_payment_cap=Decimal("150_000"))
    result = compute(ledger("2_800_000", qp="150_000"), generous)
    assert result.qp_deduction == Decimal("150_000")
    # And the stock pack still enforces its own 75,000 limit.
    assert compute(ledger("2_800_000", qp="150_000"), LK_2025_26).qp_deduction == Decimal("75_000")
