from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class Band:
    """A single progressive tax band."""

    upto: Decimal | None  # None = unbounded (highest band)
    rate: Decimal


@dataclass(frozen=True)
class ForeignServiceIncomeRegime:
    """15% maximum/final tax on employment income remitted via a Sri Lankan bank."""

    max_rate: Decimal
    requires_bank_remittance: bool = True


@dataclass(frozen=True)
class FilingCalendar:
    set_due: str  # "MM-DD" — Self-Employment Tax / first installment
    installments: list[str] = field(default_factory=list)  # ["MM-DD", ...]
    final_installment_due: str = ""
    return_due: str = ""  # annual return deadline


@dataclass(frozen=True)
class TaxPack:
    """
    All the data needed to compute tax for a single (country, year) combination.
    The engine is a pure function; the pack is its configuration.
    """

    country: str
    year: str
    version: str
    currency: str  # ISO 4217 — what every amount in the pack is in, and the ledger must be
    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    personal_relief: Decimal
    bands: list[Band]
    foreign_service_income: ForeignServiceIncomeRegime | None
    credits: list[str]  # ["APIT", "AIT_INTEREST_10", "FOREIGN_TAX_CREDIT"]
    rounding: str  # "nearest_rupee" | "truncate_rupee"
    filing: FilingCalendar
    # Qualifying-payment relief caps. These were hardcoded in the engine as
    # `min(taxable / 3, 75_000)` — Sri Lankan rules that any future country pack
    # would have silently inherited. Rates and limits belong to the pack; the
    # engine only applies them.
    qualifying_payment_cap: Decimal = Decimal("75000")
    qualifying_payment_fraction: Decimal = Decimal("1") / Decimal("3")


# ── computation output ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BandWorkings:
    from_amount: Decimal
    to_amount: Decimal | None
    rate: Decimal
    taxable_in_band: Decimal
    tax: Decimal


@dataclass(frozen=True)
class TaxComputation:
    pack_country: str
    pack_year: str
    pack_version: str
    currency: str  # the pack's: every amount below is in it

    # Inputs (snapshot)
    gross_income: Decimal
    foreign_service_income: Decimal  # subset eligible for the 15% flat regime
    regular_income: Decimal  # gross_income - foreign_service_income
    personal_relief_applied: Decimal
    qp_deduction: Decimal  # qualifying payments / donations, capped
    taxable_income: Decimal  # regular_income after relief & QPD

    # Band-by-band workings (on taxable_income only)
    band_workings: list[BandWorkings]

    # FSI flat tax (separate from bands)
    fsi_tax: Decimal  # foreign_service_income × regime rate

    # Credits
    tax_before_credits: Decimal  # band tax + fsi_tax
    apit_credit: Decimal
    ait_credit: Decimal
    foreign_tax_credit: Decimal
    total_credits: Decimal

    # Final
    tax_payable: Decimal
    # Credits in excess of the liability. `tax_payable` floors at zero, so
    # without this a user who overpaid saw "0.00" and no indication they are
    # owed a refund — the money simply disappeared from the report.
    refund_due: Decimal
    rounding: str


@dataclass(frozen=True)
class LedgerView:
    """
    Aggregated view of ledger data needed by the tax engine.
    Built by TaxService from stored postings; passed to compute().
    """

    total_income: Decimal  # all income sources summed
    foreign_service_income: Decimal  # subset eligible for 15% regime
    apit_withheld: Decimal
    ait_withheld: Decimal
    foreign_tax_paid: Decimal
    qualifying_payments: Decimal  # donations / QPDs
