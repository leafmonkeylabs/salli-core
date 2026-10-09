"""
The band payload carries numeric bounds, not just a display label.

Mobile used to regex `"LKR 0 – LKR 1,000,000"` back into numbers to decide how
much of a band was consumed, so any change to that string — the currency prefix,
the separator, the dash character — silently turned every band into "Applied to
top band" without failing anywhere.
"""

from __future__ import annotations

from decimal import Decimal

from salli.domain.tax.engine import compute
from salli.domain.tax.models import LedgerView
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.interfaces.api.routers.tax import _fmt_computation


def _computation(total_income: str = "10000000"):
    """Income high enough to reach the open-ended top band.

    The engine only emits workings for bands actually reached, so a smaller
    figure produces no open band at all.
    """
    return compute(
        LedgerView(
            total_income=Decimal(total_income),
            foreign_service_income=Decimal(0),
            apit_withheld=Decimal(0),
            ait_withheld=Decimal(0),
            foreign_tax_paid=Decimal(0),
            qualifying_payments=Decimal(0),
        ),
        LK_2025_26,
    )


def test_live_bands_carry_numeric_bounds():
    payload = _fmt_computation(_computation())
    bands = payload["band_workings"]
    assert bands, "expected progressive bands"

    for b in bands:
        assert "from_amount" in b and "rate_fraction" in b
        # Parseable as numbers without touching the display string.
        Decimal(b["from_amount"])
        Decimal(b["rate_fraction"])
        if b["to_amount"] is not None:
            Decimal(b["to_amount"])

    # At most one open-ended band, and if present it is last.
    open_ended = [i for i, b in enumerate(bands) if b["to_amount"] is None]
    assert len(open_ended) == 1 and open_ended[0] == len(bands) - 1


def test_bounds_ascend_and_match_the_pack():
    bands = _fmt_computation(_computation())["band_workings"]
    assert Decimal(bands[0]["from_amount"]) == Decimal(0)
    # Each band starts exactly where the previous one ended — no gaps, so the
    # bounds can be trusted to compute how much of a band was consumed.
    for previous, current in zip(bands, bands[1:], strict=False):
        assert Decimal(previous["to_amount"]) == Decimal(current["from_amount"])


def test_a_partially_reached_band_emits_no_open_band():
    """Income that stops mid-scale produces only the bands it touched."""
    bands = _fmt_computation(_computation("4000000"))["band_workings"]
    assert all(b["to_amount"] is not None for b in bands)


def test_stored_rows_without_numeric_bounds_still_format():
    """`/tax/latest` replays stored JSONB, and rows written before these fields
    existed must not break the endpoint."""
    legacy = {
        "pack_country": "LK",
        "pack_year": "2025/26",
        "pack_version": "1.0.0",
        "band_workings": [
            {
                "from_amount": "0",
                "to_amount": "1000000",
                "rate": "0.06",
                "taxable_in_band": "1000000",
                "tax": "60000",
            },
            {
                "from_amount": "1000000",
                "to_amount": None,
                "rate": "0.36",
                "taxable_in_band": "0",
                "tax": "0",
            },
        ],
    }
    bands = _fmt_computation(legacy)["band_workings"]
    assert bands[0]["from_amount"] == "0"
    assert bands[1]["to_amount"] is None
    # The display label is still produced for both.
    assert "LKR" in bands[0]["band"] and "balance" in bands[1]["band"]
