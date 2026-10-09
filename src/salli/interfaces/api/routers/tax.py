from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from salli.domain.currency import quantize
from salli.domain.tax.models import TaxComputation as DomainTaxComputation
from salli.interfaces.api.contract import Amount, CurrencyCode
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/tax", tags=["tax"])

#: How a pack rounds tax to whole units: the modes the engine applies
#: (domain/tax/engine.py `_round`), which refuses any other.
Rounding = Literal["nearest_rupee", "truncate_rupee"]


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


@router.post("/compute")
async def compute_tax(
    user_id: CurrentUser, svc: AppServices, year: str = "2025/26"
) -> TaxComputation:
    result = await svc.tax.compute_tax(user_id, year)
    return TaxComputation.model_validate(_fmt_computation(result))


@router.get("/latest")
async def get_latest(
    user_id: CurrentUser, svc: AppServices, year: str = "2025/26"
) -> LatestTaxComputation:
    result = await svc.tax.get_latest_computation(user_id, year)
    if result is None:
        return LatestTaxComputation(result=None)
    return LatestTaxComputation(result=TaxComputation.model_validate(_fmt_computation(result)))
