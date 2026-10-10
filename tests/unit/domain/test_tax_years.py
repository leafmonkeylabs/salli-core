"""
The tax year comes from the pack.

A pack declares its country's tax year (Sri Lanka: 1 April to 31 March), so
Salli can name the year any date falls in, find the pack for it, and tell which
year is the latest it can compute, without "2025/26" written in as current.
"""

from __future__ import annotations

import datetime
from dataclasses import replace

import pytest

from salli.domain.tax.models import year_label
from salli.domain.tax.packs import registry
from salli.domain.tax.packs.lk_2025_26 import LK_2025_26
from salli.domain.tax.packs.registry import InvalidTaxPack, validate_pack

D = datetime.date


def test_sri_lanka_declares_april_to_march():
    assert (LK_2025_26.year_start, LK_2025_26.year_end) == ("04-01", "03-31")


@pytest.mark.parametrize(
    ("day", "label", "start", "end"),
    [
        (D(2026, 10, 9), "2026/27", D(2026, 4, 1), D(2027, 3, 31)),
        (D(2026, 3, 31), "2025/26", D(2025, 4, 1), D(2026, 3, 31)),
        (D(2026, 4, 1), "2026/27", D(2026, 4, 1), D(2027, 3, 31)),
        (D(2025, 1, 15), "2024/25", D(2024, 4, 1), D(2025, 3, 31)),
        (D(2028, 2, 29), "2027/28", D(2027, 4, 1), D(2028, 3, 31)),
    ],
)
def test_the_tax_year_a_day_falls_in(day, label, start, end):
    year = registry.tax_year("LK", day)
    assert year is not None
    assert (year.country, year.label, year.start, year.end) == ("LK", label, start, end)
    assert day in year


def test_a_country_without_a_pack_has_no_known_tax_year():
    assert registry.tax_year("US", D(2026, 1, 1)) is None
    assert registry.current_tax_year("US", D(2026, 1, 1)) is None
    assert registry.current_tax_year(None, D(2026, 1, 1)) is None


def test_the_pack_for_a_day_and_the_latest_salli_can_compute():
    assert registry.pack_for("LK", D(2025, 12, 1)) is LK_2025_26
    assert registry.pack_for("LK", D(2026, 10, 9)) is None
    # The latest year that has begun, whether or not it has ended.
    assert registry.latest_pack("LK", D(2026, 10, 9)) is LK_2025_26
    assert registry.latest_pack("LK", D(2025, 4, 1)) is LK_2025_26
    assert registry.latest_pack("LK", D(2025, 3, 31)) is None


def test_where_a_sri_lankan_stands_today():
    """9 October 2026: in 2026/27, which has no pack yet; 2025/26 is the latest
    year Salli can compute, and what a computation uses by default."""
    current = registry.current_tax_year("LK", D(2026, 10, 9))
    assert current is not None
    assert current.year.label == "2026/27"
    assert current.pack is None
    assert current.latest is LK_2025_26


def test_a_tax_year_is_named_for_its_shape():
    assert year_label("04-01", D(2025, 4, 1)) == "2025/26"
    assert year_label("01-01", D(2025, 1, 1)) == "2025"
    assert year_label("07-01", D(2099, 7, 1)) == "2099/00"


def test_other_shapes_of_year_work_the_same(monkeypatch):
    """A calendar year, and a year that starts on 6 April, as some countries' do."""
    calendar = replace(
        LK_2025_26,
        country="ZZ",
        year="2025",
        period_start="2025-01-01",
        period_end="2025-12-31",
        year_start="01-01",
        year_end="12-31",
    )
    sixth = replace(
        LK_2025_26,
        country="ZY",
        period_start="2025-04-06",
        period_end="2026-04-05",
        year_start="04-06",
        year_end="04-05",
    )
    validate_pack(calendar)
    validate_pack(sixth)
    monkeypatch.setitem(registry._REGISTRY, ("ZZ", "2025"), calendar)
    monkeypatch.setitem(registry._REGISTRY, ("ZY", "2025/26"), sixth)

    year = registry.tax_year("ZZ", D(2026, 6, 1))
    assert year is not None and (year.label, year.start, year.end) == (
        "2026",
        D(2026, 1, 1),
        D(2026, 12, 31),
    )
    assert registry.pack_for("ZZ", D(2025, 12, 31)) is calendar
    assert registry.tax_year("ZY", D(2026, 4, 5)).label == "2025/26"  # type: ignore[union-attr]
    assert registry.tax_year("ZY", D(2026, 4, 6)).label == "2026/27"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"year_start": "4-1"}, "not an MM-DD date"),
        ({"year_start": "02-30"}, "not an MM-DD date"),
        ({"period_end": "2026-04-30"}, "not one tax year"),
        ({"period_start": "2025-04-02"}, "not one tax year"),
        ({"year_end": "03-30"}, "not the period's last day"),
        ({"year": "2025-26"}, "is called '2025/26'"),
    ],
)
def test_a_pack_whose_year_does_not_add_up_is_refused(changes, message):
    with pytest.raises(InvalidTaxPack, match=message):
        validate_pack(replace(LK_2025_26, **changes))


def test_the_one_country_whose_packs_compute_in_a_currency():
    assert registry.country_for_currency("LKR") == "LK"
    assert registry.country_for_currency("lkr") == "LK"
    assert registry.country_for_currency("USD") is None
