"""
Pack validation.

A malformed pack computes silently wrong tax rather than failing, and tax is
exactly the thing nobody re-checks by hand — so every case here is one that
previously produced a plausible-looking but wrong figure.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from salli.domain.tax.models import Band
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.domain.tax.packs.registry import InvalidTaxPack, validate_pack


def test_the_shipping_pack_is_valid():
    validate_pack(LK_2025_26)


def test_rejects_a_pack_with_no_bands():
    with pytest.raises(InvalidTaxPack, match="no bands"):
        validate_pack(replace(LK_2025_26, bands=[]))


def test_rejects_a_missing_open_ended_band():
    """Without an open top band, income above the last threshold is untaxed."""
    closed = [Band(upto=Decimal("1000000"), rate=Decimal("0.06"))]
    with pytest.raises(InvalidTaxPack, match="open-ended"):
        validate_pack(replace(LK_2025_26, bands=closed))


def test_rejects_an_open_ended_band_that_is_not_last():
    """The engine stops at the open band, so anything after it never applies."""
    bands = [
        Band(upto=None, rate=Decimal("0.06")),
        Band(upto=Decimal("2000000"), rate=Decimal("0.18")),
    ]
    with pytest.raises(InvalidTaxPack, match="must be last"):
        validate_pack(replace(LK_2025_26, bands=bands))


def test_rejects_two_open_ended_bands():
    bands = [Band(upto=None, rate=Decimal("0.06")), Band(upto=None, rate=Decimal("0.18"))]
    with pytest.raises(InvalidTaxPack, match="exactly one"):
        validate_pack(replace(LK_2025_26, bands=bands))


def test_rejects_non_ascending_thresholds():
    """Thresholds are cumulative ceilings — a repeat yields a zero-width band."""
    bands = [
        Band(upto=Decimal("1000000"), rate=Decimal("0.06")),
        Band(upto=Decimal("1000000"), rate=Decimal("0.18")),
        Band(upto=None, rate=Decimal("0.24")),
    ]
    with pytest.raises(InvalidTaxPack, match="strictly ascend"):
        validate_pack(replace(LK_2025_26, bands=bands))


def test_rejects_a_rate_expressed_as_a_percentage():
    """`6` where `0.06` is meant overtaxes by 100x and looks like a real number."""
    bands = [Band(upto=Decimal("1000000"), rate=Decimal(6)), Band(upto=None, rate=Decimal("0.18"))]
    with pytest.raises(InvalidTaxPack, match="fraction between 0 and 1"):
        validate_pack(replace(LK_2025_26, bands=bands))


def test_rejects_negative_personal_relief():
    with pytest.raises(InvalidTaxPack, match="relief cannot be negative"):
        validate_pack(replace(LK_2025_26, personal_relief=Decimal(-1)))


def test_rejects_an_fsi_rate_expressed_as_a_percentage():
    fsi = replace(LK_2025_26.foreign_service_income, max_rate=Decimal(15))
    with pytest.raises(InvalidTaxPack, match="FSI rate"):
        validate_pack(replace(LK_2025_26, foreign_service_income=fsi))


def test_rejects_an_unknown_rounding_mode():
    with pytest.raises(InvalidTaxPack, match="rounding"):
        validate_pack(replace(LK_2025_26, rounding="banker"))
