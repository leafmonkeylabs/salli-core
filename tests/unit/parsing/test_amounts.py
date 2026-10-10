"""
Amounts as banks around the world write them, read exactly — and anything
that is not clearly one amount refused rather than guessed.
"""

from decimal import Decimal

import pytest

from salli.adapters.parsing.amounts import (
    currency_code_in,
    detect_decimal_separator,
    parse_decimal,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,234.56", "1234.56"),  # US, UK
        ("1.234,56", "1234.56"),  # Germany
        ("1 234,56", "1234.56"),  # France, with a plain space
        ("1 234,56", "1234.56"),  # ... and with the narrow no-break space
        ("1'234.56", "1234.56"),  # Switzerland
        ("12,34,567.89", "1234567.89"),  # India
        ("1,234,567", "1234567"),
        ("1.234.567", "1234567"),
        ("0.5", "0.5"),
        ("1234", "1234"),
    ],
)
def test_grouping_and_decimal_marks_of_each_locale(text, expected):
    assert parse_decimal(text) == Decimal(expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-12,50", "-12.50"),
        ("12,50-", "-12.50"),
        ("(12.50)", "-12.50"),
        ("−12.50", "-12.50"),  # the Unicode minus sign
        ("+12.50", "12.50"),
        ("12.50 DR", "-12.50"),
        ("12.50 Cr", "12.50"),
        ("-12.50 DR", "-12.50"),
    ],
)
def test_every_way_of_writing_a_sign(text, expected):
    assert parse_decimal(text) == Decimal(expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,234.56", "1234.56"),
        ("-$1,234.56", "-1234.56"),
        ("€ 1.234,56", "1234.56"),
        ("1 234,56 €", "1234.56"),
        ("USD -12.00", "-12.00"),
        ("Rs. 1,234.00", "1234.00"),
        ("Rs.50", "50"),
        ("CHF 1'234.50", "1234.50"),
        ("12.50 CRC", "12.50"),  # Costa Rican colones, not a CR mark
    ],
)
def test_currency_symbols_and_codes_stuck_to_the_amount(text, expected):
    assert parse_decimal(text) == Decimal(expected)


def test_the_amount_keeps_exactly_the_digits_written():
    assert parse_decimal("12.50").as_tuple() == Decimal("12.50").as_tuple()
    assert parse_decimal("1.234,500", ",").as_tuple() == Decimal("1234.500").as_tuple()


def test_a_value_that_reads_two_ways_needs_the_decimal_mark():
    with pytest.raises(ValueError, match="either decimal mark"):
        parse_decimal("1,234")
    assert parse_decimal("1,234", ".") == Decimal("1234")
    assert parse_decimal("1,234", ",") == Decimal("1.234")
    assert parse_decimal("1.234", ",") == Decimal("1234")


@pytest.mark.parametrize(
    ("text", "separator"),
    [
        ("", None),
        ("abc", None),
        (".50", None),  # a leading decimal mark
        ("12.", None),
        ("12.50 1", "."),  # two numbers
        ("1.23457E+11", None),  # scientific notation: the export already lost digits
        ("12.5", ","),  # "12.5" in a comma-decimal column is a misread, not 125
        ("1 2345", None),
        ("1,234.56", ","),
        ("12,50 CR DR", None),
        ("-12.50 CR", None),  # a minus sign on a credit contradicts itself
        ("(12.50", None),
        ("12.50 #", None),
    ],
)
def test_anything_but_one_clear_amount_is_refused(text, separator):
    with pytest.raises(ValueError):
        parse_decimal(text, separator)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["1.234,56", "12,50", "1,234"], ","),
        (["12.50", "1,234.56", "1,234"], "."),
        (["1,234,567"], "."),  # a repeated mark groups thousands
        (["1.234.567"], ","),
        (["1,234", "5,678"], None),  # nothing settles it
        (["1234", "17"], None),
        ([], None),
    ],
)
def test_a_column_settles_its_decimal_mark(values, expected):
    assert detect_decimal_separator(values) == expected


def test_currency_codes_beside_an_amount():
    assert currency_code_in("USD -12.00") == "USD"
    assert currency_code_in("1.234,56 EUR") == "EUR"
    assert currency_code_in("12.50 CR") is None
    assert currency_code_in("$12.50") is None  # a symbol is not a currency
    assert currency_code_in("EUR 1 USD 2") is None
