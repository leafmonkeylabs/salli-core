"""
Rounding and band arithmetic, which every rule set leans on.

Each rounding mode is pinned at the cases that tell modes apart: exact ties,
values just either side of a tie, negatives (refunds), and units other than 1.
"""

from __future__ import annotations

import decimal
from decimal import Decimal

import pytest

from salli.domain.taxrules.arith import (
    Band,
    BandTable,
    Rounding,
    decimal_context,
    normalized_str,
    round_to,
    significant_digits,
)

D = Decimal


def r(value: str, mode: str, unit: str = "1") -> Decimal:
    with decimal_context():
        return round_to(D(value), mode, D(unit))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "mode", "unit", "expected"),
    [
        # nearest is ROUND_HALF_UP: a tie goes away from zero
        ("2.5", "nearest", "1", "3"),
        ("-2.5", "nearest", "1", "-3"),
        ("2.4999", "nearest", "1", "2"),
        ("3.5", "nearest", "1", "4"),
        # half_even sends a tie to the even multiple
        ("2.5", "half_even", "1", "2"),
        ("3.5", "half_even", "1", "4"),
        ("-2.5", "half_even", "1", "-2"),
        ("2.5001", "half_even", "1", "3"),
        # down goes towards zero, up away from it, by magnitude
        ("2.9", "down", "1", "2"),
        ("-2.9", "down", "1", "-2"),
        ("2.1", "up", "1", "3"),
        ("-2.1", "up", "1", "-3"),
        ("2", "up", "1", "2"),
        # units other than 1
        ("1.005", "nearest", "0.01", "1.01"),
        ("1.004", "nearest", "0.01", "1.00"),
        ("12.5", "nearest", "5", "15"),
        ("12.4", "nearest", "5", "10"),
        ("7.62", "down", "0.05", "7.60"),
        ("7.62", "up", "0.05", "7.65"),
        ("1234", "down", "100", "1200"),
    ],
)
def test_round_to_rounds_each_mode_as_documented(value, mode, unit, expected):
    assert r(value, mode, unit) == D(expected)


def test_rounding_a_small_negative_to_zero_gives_zero_not_negative_zero():
    assert str(r("-0.4", "nearest")) == "0"


def test_rounding_refuses_a_result_too_large_to_hold_exactly():
    with pytest.raises(decimal.InvalidOperation):
        r("123456789012345678901234567.5", "nearest", "0.0001")


def test_rounding_ignores_the_ambient_decimal_context():
    """The evaluation context is installed, so a caller's context can't change
    a result."""
    with decimal.localcontext() as ambient:
        ambient.prec = 3
        ambient.rounding = decimal.ROUND_FLOOR
        assert r("12345.5", "nearest") == D("12346")


TABLE = BandTable(
    (Band(D("1000"), D("0.1")), Band(D("3000"), D("0.2")), Band(None, D("0.4"))),
)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("0", "0"),
        ("-500", "0"),
        ("1000", "100"),  # 1000 × 10%
        ("1001", "100.2"),  # 100 + 1 × 20%
        ("3000", "500"),  # 100 + 2000 × 20%
        ("3500", "700"),  # 500 + 500 × 40%
    ],
)
def test_a_band_table_taxes_each_slice_at_its_own_rate(amount, expected):
    with decimal_context():
        assert TABLE.tax(D(amount)) == D(expected)


def test_band_amounts_are_the_slices_of_the_amount():
    with decimal_context():
        assert [TABLE.amount_in_band(D("3500"), n) for n in (1, 2, 3)] == [
            D("1000"),
            D("2000"),
            D("500"),
        ]


def test_a_rounding_table_rounds_each_band_before_adding():
    """0.5 + 0.5 rounds to 2 band by band, but would round to 1 in total."""
    table = BandTable(
        (Band(D("5"), D("0.1")), Band(None, D("0.1"))),
        Rounding("nearest", D("1")),
    )
    with decimal_context():
        assert table.tax(D("10")) == D("2")


@pytest.mark.parametrize(
    "bands",
    [
        (),
        (Band(D("1000"), D("0.1")),),  # no open top band
        (Band(None, D("0.1")), Band(None, D("0.2"))),
        (Band(D("1000"), D("0.1")), Band(D("1000"), D("0.2")), Band(None, D("0.3"))),
        (Band(D("0"), D("0.1")), Band(None, D("0.2"))),
        (Band(None, D("1.5")),),
        (Band(None, D("-0.1")),),
    ],
)
def test_a_malformed_band_table_cant_be_built(bands):
    with pytest.raises(ValueError):
        BandTable(bands)


def test_significant_digits_ignore_leading_and_trailing_zeros():
    assert significant_digits(D("1.500")) == 2
    assert significant_digits(D("1500")) == 2
    assert significant_digits(D("0.0015")) == 2
    assert significant_digits(D("0")) == 1


def test_normalized_strings_are_the_shortest_plain_spelling():
    assert normalized_str(D("0.150")) == "0.15"
    assert normalized_str(D("1E+2")) == "100"
    assert normalized_str(D("-0.00")) == "0"
    assert normalized_str(D("1800000")) == "1800000"
