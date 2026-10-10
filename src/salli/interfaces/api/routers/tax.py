from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from salli.domain.currency import quantize
from salli.domain.tax.models import TaxComputation as DomainTaxComputation
from salli.domain.tax.models import TaxPack as DomainTaxPack
from salli.interfaces.api.contract import Amount, CountryCode, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/tax", tags=["tax"])

#: How a pack rounds tax to whole units: the modes the engine applies
#: (domain/tax/engine.py `_round`), which refuses any other.
Rounding = Literal["nearest_rupee", "truncate_rupee"]


class WithholdingKind(BaseModel):
    """Tax withheld or paid ahead of the return that a pack credits against the bill."""

    #: What an account's `tax_role` holds for it: "apit_credit".
    code: str
    #: Its short name: "APIT".
    label: str
    description: str


def withholding_kinds(pack: DomainTaxPack) -> list[WithholdingKind]:
    return [
        WithholdingKind(code=k.code, label=k.label, description=k.description)
        for k in pack.withholding_kinds
    ]


class TaxPack(BaseModel):
    country: str
    year: str
    version: str
    #: What the pack's amounts, and every computation made with it, are in.
    currency: CurrencyCode
    period_start: str
    period_end: str
    personal_relief: Amount
    #: The filing calendar, as "MM-DD" dates.
    return_due: str
    set_due: str
    installments: list[str]
    final_installment_due: str
    #: The tax withheld or paid ahead that this pack credits.
    withholding_kinds: list[WithholdingKind]
    #: Every `tax_role` an account may carry under this pack: the withholding
    #: kinds' codes, then "qualifying_payment" and "fsi_income" where the pack
    #: has those regimes.
    tax_roles: list[str]


class TaxBandWorking(BaseModel):
    #: For display: "LKR 0 – LKR 1,000,000", or "LKR 2,500,000 – balance".
    band: str
    #: For display: "6%".
    rate: str
    from_amount: Amount
    #: Null for the open-ended top band.
    to_amount: Amount | None
    #: The rate as a decimal fraction: "0.06".
    rate_fraction: str
    taxable_in_band: Amount
    tax: Amount


class TaxComputation(BaseModel):
    pack_country: str
    pack_year: str
    pack_version: str
    #: The pack's currency; every amount here is in it.
    currency: CurrencyCode
    gross_income: Amount
    foreign_service_income: Amount
    regular_income: Amount
    personal_relief_applied: Amount
    qp_deduction: Amount
    taxable_income: Amount
    fsi_tax: Amount
    tax_before_credits: Amount
    apit_credit: Amount
    ait_credit: Amount
    foreign_tax_credit: Amount
    total_credits: Amount
    tax_payable: Amount
    #: Credits in excess of the liability: what is owed back.
    refund_due: Amount
    rounding: Rounding
    band_workings: list[TaxBandWorking]


class LatestTaxComputation(BaseModel):
    #: Null until the year has been computed.
    result: TaxComputation | None


@router.get("/packs")
async def list_packs(svc: AppServices) -> list[TaxPack]:
    packs = svc.tax.list_packs()
    return [
        TaxPack(
            country=p.country,
            year=p.year,
            version=p.version,
            currency=p.currency,
            period_start=p.period_start,
            period_end=p.period_end,
            personal_relief=str(quantize(p.personal_relief, p.currency)),
            return_due=p.filing.return_due,
            # The rest of the filing calendar was declared in the pack but never
            # exposed, so clients hardcoded deadlines instead — and drifted. The
            # dashboard said "due Jul 31" and mobile's hub said "Sep 30" while
            # the pack said 30 November. Serve the whole calendar so there is
            # one source of truth to read.
            set_due=p.filing.set_due,
            installments=p.filing.installments,
            final_installment_due=p.filing.final_installment_due,
            withholding_kinds=withholding_kinds(p),
            tax_roles=list(p.tax_roles),
        )
        for p in packs
    ]


# ── shared formatter ────────────────────────────────────────────────────────


def _fmt_computation(result: DomainTaxComputation | dict[str, Any]) -> dict[str, Any]:
    """Format a TaxComputation object (dataclass) or raw stored dict into a
    consistent API response shape.

    Two input shapes exist because `get_latest` returns the stored JSONB blob
    rather than re-hydrating it, so historical rows arrive as plain dicts whose
    field set is whatever the engine wrote at the time.

    Amounts come out at the currency's precision. The engine's figures carry
    whatever scale their arithmetic left them with: sums of postings carry the
    exchange rate's eight decimals on top of the amount's two
    ("250000.0000000000"), and the qualifying-payment cap the repeating
    digits of a third.
    """
    if isinstance(result, DomainTaxComputation):
        # Live TaxComputation dataclass from the engine
        bws = result.band_workings

        currency = result.currency

        def _money(amount: Decimal) -> str:
            return str(quantize(amount, currency, strict=False))

        def _band_label(bw) -> str:  # type: ignore[no-untyped-def]
            fr = int(bw.from_amount)
            return (
                f"{currency} {fr:,} – {currency} {int(bw.to_amount):,}"
                if bw.to_amount is not None
                else f"{currency} {fr:,} – balance"
            )

        band_workings = [
            {
                # `band` and `rate` are pre-rendered for display. The numeric
                # bounds below exist because mobile used to regex the label back
                # into numbers to decide how much of a band was consumed — any
                # change to the label's format silently broke those chips.
                "band": _band_label(bw),
                "rate": f"{bw.rate * 100:.0f}%",
                "from_amount": _money(bw.from_amount),
                "to_amount": None if bw.to_amount is None else _money(bw.to_amount),
                "rate_fraction": str(bw.rate),
                "taxable_in_band": _money(bw.taxable_in_band),
                "tax": _money(bw.tax),
            }
            for bw in bws
        ]
        return {
            "pack_country": result.pack_country,
            "pack_year": result.pack_year,
            "pack_version": result.pack_version,
            "currency": currency,
            "gross_income": _money(result.gross_income),
            "foreign_service_income": _money(result.foreign_service_income),
            "regular_income": _money(result.regular_income),
            "personal_relief_applied": _money(result.personal_relief_applied),
            "qp_deduction": _money(result.qp_deduction),
            "taxable_income": _money(result.taxable_income),
            "fsi_tax": _money(result.fsi_tax),
            "tax_before_credits": _money(result.tax_before_credits),
            "apit_credit": _money(result.apit_credit),
            "ait_credit": _money(result.ait_credit),
            "foreign_tax_credit": _money(result.foreign_tax_credit),
            "total_credits": _money(result.total_credits),
            "tax_payable": _money(result.tax_payable),
            "refund_due": _money(result.refund_due),
            "rounding": result.rounding,
            "band_workings": band_workings,
        }
    else:
        # Raw stored dict from JSONB (dataclasses.asdict serialised to JSON)
        raw = result
        # Computations stored before the currency was recorded were all LK, in LKR.
        currency = raw.get("currency", "LKR")

        def _stored_money(value: object) -> str:
            return str(quantize(Decimal(str(value)), currency, strict=False))

        band_workings = []
        for bw in raw.get("band_workings", []):
            fr_raw = bw.get("from_amount", "0")
            to_raw = bw.get("to_amount")
            fr = int(Decimal(str(fr_raw)))
            label = (
                f"{currency} {fr:,} – {currency} {int(Decimal(str(to_raw))):,}"
                if to_raw is not None
                else f"{currency} {fr:,} – balance"
            )
            rate_raw = Decimal(str(bw.get("rate", "0")))
            band_workings.append(
                {
                    "band": label,
                    "rate": f"{rate_raw * 100:.0f}%",
                    "from_amount": _stored_money(fr_raw),
                    "to_amount": None if to_raw is None else _stored_money(to_raw),
                    "rate_fraction": str(rate_raw),
                    "taxable_in_band": _stored_money(bw.get("taxable_in_band", "0")),
                    "tax": _stored_money(bw.get("tax", "0")),
                }
            )

        def _s(key: str, default: str = "0") -> str:
            return str(raw.get(key, default))

        def _m(key: str) -> str:
            return _stored_money(raw.get(key, "0"))

        return {
            "pack_country": _s("pack_country", "LK"),
            "pack_year": _s("pack_year", ""),
            "pack_version": _s("pack_version", ""),
            "currency": currency,
            "gross_income": _m("gross_income"),
            "foreign_service_income": _m("foreign_service_income"),
            "regular_income": _m("regular_income"),
            "personal_relief_applied": _m("personal_relief_applied"),
            "qp_deduction": _m("qp_deduction"),
            "taxable_income": _m("taxable_income"),
            "fsi_tax": _m("fsi_tax"),
            "tax_before_credits": _m("tax_before_credits"),
            "apit_credit": _m("apit_credit"),
            "ait_credit": _m("ait_credit"),
            "foreign_tax_credit": _m("foreign_tax_credit"),
            "total_credits": _m("total_credits"),
            "tax_payable": _m("tax_payable"),
            # Rows stored before `refund_due` existed have no such key; "0" is
            # the correct reading for them, since the old engine floored at zero
            # and never recorded an overpayment either way.
            "refund_due": _m("refund_due"),
            "rounding": _s("rounding", "nearest_rupee"),
            "band_workings": band_workings,
        }


# ── routes ────────────────────────────────────────────────────────────────────


#: A tax year by its pack's name: "2025/26". Omitted: the latest year Salli can
#: compute for the user (GET /tax/current-year says which).
TaxYearParam = Annotated[str | None, Query(examples=["2025/26"])]


@router.post("/compute")
async def compute_tax(
    user_id: CurrentUser, svc: AppServices, year: TaxYearParam = None
) -> TaxComputation:
    """Compute the user's income tax for a year with their country's pack.

    Their country is their tax residency or, while they have not set one, the
    one country whose packs compute in their base currency. 422
    (/problems/no-tax-pack) when Salli has no pack that can compute it.
    """
    result = await svc.tax.compute_tax(user_id, year)
    return TaxComputation.model_validate(_fmt_computation(result))


@router.get("/latest")
async def get_latest(
    user_id: CurrentUser, svc: AppServices, year: TaxYearParam = None
) -> LatestTaxComputation:
    result = await svc.tax.get_latest_computation(user_id, year)
    if result is None:
        return LatestTaxComputation(result=None)
    return LatestTaxComputation(result=TaxComputation.model_validate(_fmt_computation(result)))


class TaxYearStatus(BaseModel):
    """The tax year the user is in today, and the latest one Salli can compute."""

    #: Whose tax packs compute the user's tax; null when Salli cannot tell.
    country: CountryCode | None
    #: "tax_residency" when the user set it; "base_currency" while they have
    #: not, and one country's packs compute in their base currency.
    country_source: Literal["tax_residency", "base_currency"] | None
    #: The country's tax year today falls in ("2026/27"), with its first and
    #: last day (YYYY-MM-DD). Null when Salli has no pack for the country.
    year: str | None
    start: str | None
    end: str | None
    #: Whether Salli has a pack for that year.
    has_pack: bool
    #: The latest year Salli can compute for the user: what /tax/compute and
    #: /tax/latest use when no year is given. Null when there is none.
    latest_year: str | None


@router.get("/current-year")
async def get_current_year(user_id: CurrentUser, svc: AppServices) -> TaxYearStatus:
    """The tax year the user is in today, in their country."""
    where, current = await svc.tax.current_tax_year(user_id)
    return TaxYearStatus(
        country=where.country,
        country_source=where.source,
        year=current.year.label if current else None,
        start=current.year.start.isoformat() if current else None,
        end=current.year.end.isoformat() if current else None,
        has_pack=bool(current and current.pack),
        latest_year=current.latest.year if current and current.latest else None,
    )
