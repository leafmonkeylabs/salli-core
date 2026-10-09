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
    """A flat, final rate on foreign service income, outside the bands (Sri
    Lanka's: 15% on employment income remitted through a local bank)."""

    max_rate: Decimal
    requires_bank_remittance: bool = True


@dataclass(frozen=True)
class FilingCalendar:
    set_due: str  # "MM-DD" — Self-Employment Tax / first installment
    installments: list[str] = field(default_factory=list[str])  # ["MM-DD", ...]
    final_installment_due: str = ""
    return_due: str = ""  # annual return deadline


@dataclass(frozen=True)
class WithholdingKind:
    """Tax withheld or paid ahead of the return that a pack credits against
    the bill (APIT and AIT in Sri Lanka, say). An account holds it when its
    `tax_role` is `code` (domain/accounting/models.py)."""

    code: str  # "apit_credit"
    label: str  # "APIT"
    description: str


#: The withholding kinds the engine credits, and the LedgerView field the
#: balances of each one's accounts go into. A pack may declare only these: a
#: kind the engine had no field for would be left out of the bill, silently.
CREDITED_KINDS: dict[str, str] = {
    "apit_credit": "apit_withheld",
    "ait_credit": "ait_withheld",
    "foreign_tax_credit": "foreign_tax_paid",
}

#: Account roles that come with a regime a pack may have, beside its kinds.
FSI_INCOME_ROLE = "fsi_income"  # with `foreign_service_income`
QUALIFYING_PAYMENT_ROLE = "qualifying_payment"  # with qualifying-payment relief

#: What a tax role looks like: it is stored in a VARCHAR(30).
TAX_ROLE_PATTERN = r"^[a-z][a-z0-9_]{0,29}$"


@dataclass(frozen=True)
class StarterAccount:
    """An account a resident's starter chart of accounts gets from their pack:
    where their withheld tax, reliefs and specially taxed income are booked."""

    code: str
    name: str
    type: str  # asset | liability | equity | income | expense
    tax_role: str
    #: The income source it comes with (onboarding's "employment", "interest",
    #: "foreign", …), or None for every resident.
    income_source: str | None = None


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
    # engine only applies them. No relief unless a pack declares one.
    qualifying_payment_cap: Decimal = Decimal(0)
    qualifying_payment_fraction: Decimal = Decimal(0)
    # The tax withheld or paid ahead that this pack credits. An account's
    # `tax_role` must be one the user's pack declares (`tax_roles`).
    withholding_kinds: tuple[WithholdingKind, ...] = ()
    # What a resident's starter chart of accounts gets from this pack.
    starter_accounts: tuple[StarterAccount, ...] = ()

    @property
    def has_qualifying_payment_relief(self) -> bool:
        return self.qualifying_payment_cap > 0 and self.qualifying_payment_fraction > 0

    @property
    def tax_roles(self) -> tuple[str, ...]:
        """Every value an account's `tax_role` may take under this pack: its
        withholding kinds, then the roles of the regimes it has."""
        roles = [kind.code for kind in self.withholding_kinds]
        if self.has_qualifying_payment_relief:
            roles.append(QUALIFYING_PAYMENT_ROLE)
        if self.foreign_service_income is not None:
            roles.append(FSI_INCOME_ROLE)
        return tuple(roles)


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
