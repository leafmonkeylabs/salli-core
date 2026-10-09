"""
Deterministic tax computation engine.

Pure function: compute(ledger_view, pack) -> TaxComputation.
No I/O, no LLM calls, no side effects.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from salli.domain.tax.models import BandWorkings, LedgerView, TaxComputation, TaxPack


def _round(amount: Decimal, rounding: str) -> Decimal:
    if rounding == "nearest_rupee":
        return amount.to_integral_value(ROUND_HALF_UP)
    if rounding == "truncate_rupee":
        return amount.to_integral_value(ROUND_DOWN)
    raise ValueError(f"Unknown rounding mode: {rounding!r}")


def compute(ledger: LedgerView, pack: TaxPack) -> TaxComputation:
    """
    Compute personal income tax for a single year of assessment.

    Foreign Service Income (FSI) is taxed at the pack's flat regime rate and
    excluded from the progressive bands.  Personal relief and QPDs reduce the
    remaining (regular) taxable income only.  All credits offset the combined
    tax liability.
    """
    gross = ledger.total_income

    # ── FSI flat tax ──────────────────────────────────────────────────────────
    fsi = min(ledger.foreign_service_income, gross)  # cap at gross (defensive)
    regular_income = max(Decimal(0), gross - fsi)

    if pack.foreign_service_income is not None and fsi > Decimal(0):
        fsi_tax = _round(fsi * pack.foreign_service_income.max_rate, pack.rounding)
    else:
        fsi_tax = Decimal(0)

    # ── Regular income: relief + QPD → bands ─────────────────────────────────
    relief_applied = min(pack.personal_relief, regular_income)
    taxable = max(Decimal(0), regular_income - relief_applied)

    # Qualifying payments / donations, capped by the pack's own limits rather
    # than by constants baked into the engine.
    qp_cap = min(taxable * pack.qualifying_payment_fraction, pack.qualifying_payment_cap)
    qp_deduction = min(ledger.qualifying_payments, qp_cap)
    taxable = max(Decimal(0), taxable - qp_deduction)

    # Progressive band computation (applies to regular taxable income only)
    workings: list[BandWorkings] = []
    remaining = taxable
    prev_upto = Decimal(0)

    for band in pack.bands:
        if remaining <= Decimal(0):
            break

        band_size = (band.upto - prev_upto) if band.upto is not None else remaining
        in_band = min(remaining, band_size)
        band_tax = _round(in_band * band.rate, pack.rounding)

        workings.append(
            BandWorkings(
                from_amount=prev_upto,
                to_amount=band.upto,
                rate=band.rate,
                taxable_in_band=in_band,
                tax=band_tax,
            )
        )

        remaining -= in_band
        if band.upto is not None:
            prev_upto = band.upto

    band_tax_total = sum((w.tax for w in workings), Decimal(0))
    tax_before_credits = band_tax_total + fsi_tax

    # ── Credits ───────────────────────────────────────────────────────────────
    apit = ledger.apit_withheld
    ait = ledger.ait_withheld

    # Non-refundable vs refundable credits, applied in that order.
    #
    # A foreign tax credit relieves double taxation — it should never hand back
    # more than this country charged. Left uncapped it now not only zeroed the
    # bill but, with `refund_due` below, would manufacture a refund of tax paid
    # to another government.
    #
    # The cap here is the total liability, deliberately *not* `fsi_tax`. Capping
    # per-source would be the stricter and probably more correct treatment, but
    # the ledger cannot currently attribute foreign tax to the income it was
    # paid on (only FSI is distinguished), so a tighter cap would under-credit
    # anyone with non-FSI foreign income. Choosing between those is a revenue
    # ruling, not an implementation detail — flagged for the chartered-accountant
    # review this pack is still pending.
    ftc = min(ledger.foreign_tax_paid, tax_before_credits)

    # APIT and AIT are tax already withheld from this taxpayer's own income, so
    # an excess genuinely is refundable to them.
    refundable = apit + ait
    total_credits = ftc + refundable

    net = _round(tax_before_credits - total_credits, pack.rounding)
    tax_payable = max(Decimal(0), net)
    refund_due = max(Decimal(0), -net)

    return TaxComputation(
        pack_country=pack.country,
        pack_year=pack.year,
        pack_version=pack.version,
        gross_income=gross,
        foreign_service_income=fsi,
        regular_income=regular_income,
        personal_relief_applied=relief_applied,
        qp_deduction=qp_deduction,
        taxable_income=taxable,
        band_workings=workings,
        fsi_tax=fsi_tax,
        tax_before_credits=tax_before_credits,
        apit_credit=apit,
        ait_credit=ait,
        foreign_tax_credit=ftc,
        total_credits=total_credits,
        tax_payable=tax_payable,
        refund_due=refund_due,
        rounding=pack.rounding,
    )
