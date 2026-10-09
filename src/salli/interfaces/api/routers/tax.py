from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter

from salli.domain.tax.models import TaxComputation
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/tax", tags=["tax"])


@router.get("/packs")
async def list_packs(svc: AppServices):
    packs = svc.tax.list_packs()
    return [
        {
            "country": p.country,
            "year": p.year,
            "version": p.version,
            "period_start": p.period_start,
            "period_end": p.period_end,
            "personal_relief": str(p.personal_relief),
            "return_due": p.filing.return_due,
            # The rest of the filing calendar was declared in the pack but never
            # exposed, so clients hardcoded deadlines instead — and drifted. The
            # dashboard said "due Jul 31" and mobile's hub said "Sep 30" while
            # the pack said 30 November. Serve the whole calendar so there is
            # one source of truth to read.
            "set_due": p.filing.set_due,
            "installments": p.filing.installments,
            "final_installment_due": p.filing.final_installment_due,
        }
        for p in packs
    ]


# ── shared formatter ────────────────────────────────────────────────────────


def _fmt_computation(result: TaxComputation | dict[str, Any]) -> dict[str, Any]:
    """Format a TaxComputation object (dataclass) or raw stored dict into a
    consistent API response shape.

    Two input shapes exist because `get_latest` returns the stored JSONB blob
    rather than re-hydrating it, so historical rows arrive as plain dicts whose
    field set is whatever the engine wrote at the time.
    """
    if isinstance(result, TaxComputation):
        # Live TaxComputation dataclass from the engine
        bws = result.band_workings

        def _band_label(bw) -> str:  # type: ignore[no-untyped-def]
            fr = int(bw.from_amount)
            return (
                f"LKR {fr:,} – LKR {int(bw.to_amount):,}"
                if bw.to_amount is not None
                else f"LKR {fr:,} – balance"
            )

        band_workings = [
            {
                # `band` and `rate` are pre-rendered for display. The numeric
                # bounds below exist because mobile used to regex the label back
                # into numbers to decide how much of a band was consumed — any
                # change to the label's format silently broke those chips.
                "band": _band_label(bw),
                "rate": f"{bw.rate * 100:.0f}%",
                "from_amount": str(bw.from_amount),
                "to_amount": None if bw.to_amount is None else str(bw.to_amount),
                "rate_fraction": str(bw.rate),
                "taxable_in_band": str(bw.taxable_in_band),
                "tax": str(bw.tax),
            }
            for bw in bws
        ]
        return {
            "pack_country": result.pack_country,
            "pack_year": result.pack_year,
            "pack_version": result.pack_version,
            "gross_income": str(result.gross_income),
            "foreign_service_income": str(result.foreign_service_income),
            "regular_income": str(result.regular_income),
            "personal_relief_applied": str(result.personal_relief_applied),
            "qp_deduction": str(result.qp_deduction),
            "taxable_income": str(result.taxable_income),
            "fsi_tax": str(result.fsi_tax),
            "tax_before_credits": str(result.tax_before_credits),
            "apit_credit": str(result.apit_credit),
            "ait_credit": str(result.ait_credit),
            "foreign_tax_credit": str(result.foreign_tax_credit),
            "total_credits": str(result.total_credits),
            "tax_payable": str(result.tax_payable),
            "refund_due": str(result.refund_due),
            "rounding": result.rounding,
            "band_workings": band_workings,
        }
    else:
        # Raw stored dict from JSONB (dataclasses.asdict serialised to JSON)
        raw: dict = result  # type: ignore[assignment]
        band_workings = []
        for bw in raw.get("band_workings", []):
            fr_raw = bw.get("from_amount", "0")
            to_raw = bw.get("to_amount")
            fr = int(Decimal(str(fr_raw)))
            label = (
                f"LKR {fr:,} – LKR {int(Decimal(str(to_raw))):,}"
                if to_raw is not None
                else f"LKR {fr:,} – balance"
            )
            rate_raw = Decimal(str(bw.get("rate", "0")))
            band_workings.append(
                {
                    "band": label,
                    "rate": f"{rate_raw * 100:.0f}%",
                    "from_amount": str(fr_raw),
                    "to_amount": None if to_raw is None else str(to_raw),
                    "rate_fraction": str(rate_raw),
                    "taxable_in_band": str(bw.get("taxable_in_band", "0")),
                    "tax": str(bw.get("tax", "0")),
                }
            )

        def _s(key: str, default: str = "0") -> str:
            return str(raw.get(key, default))

        return {
            "pack_country": _s("pack_country", "LK"),
            "pack_year": _s("pack_year", ""),
            "pack_version": _s("pack_version", ""),
            "gross_income": _s("gross_income"),
            "foreign_service_income": _s("foreign_service_income"),
            "regular_income": _s("regular_income"),
            "personal_relief_applied": _s("personal_relief_applied"),
            "qp_deduction": _s("qp_deduction"),
            "taxable_income": _s("taxable_income"),
            "fsi_tax": _s("fsi_tax"),
            "tax_before_credits": _s("tax_before_credits"),
            "apit_credit": _s("apit_credit"),
            "ait_credit": _s("ait_credit"),
            "foreign_tax_credit": _s("foreign_tax_credit"),
            "total_credits": _s("total_credits"),
            "tax_payable": _s("tax_payable"),
            # Rows stored before `refund_due` existed have no such key; "0" is
            # the correct reading for them, since the old engine floored at zero
            # and never recorded an overpayment either way.
            "refund_due": _s("refund_due"),
            "rounding": _s("rounding", "nearest_rupee"),
            "band_workings": band_workings,
        }


# ── routes ────────────────────────────────────────────────────────────────────


@router.post("/compute")
async def compute_tax(user_id: CurrentUser, svc: AppServices, year: str = "2025/26"):
    result = await svc.tax.compute_tax(user_id, year)
    return _fmt_computation(result)


@router.get("/latest")
async def get_latest(user_id: CurrentUser, svc: AppServices, year: str = "2025/26"):
    result = await svc.tax.get_latest_computation(user_id, year)
    if result is None:
        return {"result": None}
    return {"result": _fmt_computation(result)}
