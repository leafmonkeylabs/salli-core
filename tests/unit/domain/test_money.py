"""Unit tests for the Money value object."""

from decimal import Decimal

import pytest

from salli.domain.money import Money


def test_zero():
    m = Money.zero("LKR")
    assert m.minor_units == 0
    assert m.currency == "LKR"


def test_from_decimal():
    m = Money.of(Decimal("1500.50"), "LKR")
    assert m.minor_units == 150050


def test_float_rejected():
    with pytest.raises(TypeError, match="int"):
        Money(300000.0, "LKR")  # type: ignore[arg-type]


def test_addition():
    a = Money(100, "LKR")
    b = Money(200, "LKR")
    assert (a + b) == Money(300, "LKR")


def test_subtraction():
    a = Money(500, "LKR")
    b = Money(200, "LKR")
    assert (a - b) == Money(300, "LKR")


def test_negation():
    m = Money(100, "LKR")
    assert -m == Money(-100, "LKR")


def test_currency_mismatch_raises():
    a = Money(100, "LKR")
    b = Money(100, "USD")
    with pytest.raises(ValueError, match="Currency mismatch"):
        _ = a + b


def test_equality():
    assert Money(500, "LKR") == Money(500, "LKR")
    assert Money(500, "LKR") != Money(500, "USD")
    assert Money(500, "LKR") != Money(501, "LKR")


def test_currency_normalised_to_upper():
    m = Money(100, "lkr")
    assert m.currency == "LKR"


def test_ordering():
    assert Money(100, "LKR") < Money(200, "LKR")
    assert Money(200, "LKR") > Money(100, "LKR")
    assert Money(100, "LKR") <= Money(100, "LKR")


def test_to_decimal_round_trip():
    original = Decimal("12345.67")
    m = Money.of(original, "LKR")
    assert m.to_decimal() == original


def test_hashable():
    s = {Money(100, "LKR"), Money(100, "LKR"), Money(200, "LKR")}
    assert len(s) == 2
