"""Currencies have different numbers of decimals, and money must respect that."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from salli.domain.accounting.models import Direction, JournalEntry, Posting
from salli.domain.currency import (
    EXPONENTS,
    UnknownCurrencyError,
    exponent,
    format_amount,
    is_currency,
    normalize_currency,
    quantize,
)
from salli.domain.money import Money, from_minor, to_minor


@pytest.mark.parametrize(
    ("code", "places"),
    [("USD", 2), ("EUR", 2), ("LKR", 2), ("JPY", 0), ("KRW", 0), ("KWD", 3), ("BHD", 3)],
)
def test_each_currency_has_its_own_decimals(code, places):
    assert exponent(code) == places


def test_codes_are_normalized_and_checked():
    assert normalize_currency(" usd ") == "USD"
    for bad in ("XYZ", "US", "", None, 840, "XAU"):
        with pytest.raises(UnknownCurrencyError):
            normalize_currency(bad)
    assert not is_currency("XXX")


def test_reading_an_unvalidated_legacy_code_assumes_two_decimals():
    assert exponent("ZZZ", strict=False) == 2
    with pytest.raises(UnknownCurrencyError):
        exponent("ZZZ")


def test_minor_units_follow_the_currency():
    assert to_minor(Decimal("1234.56"), "USD") == 123456
    assert to_minor(Decimal("1000"), "JPY") == 1000
    assert to_minor(Decimal("1.234"), "KWD") == 1234
    # HALF-UP at the currency's own precision
    assert to_minor(Decimal("0.125"), "USD") == 13
    assert to_minor(Decimal("10.5"), "JPY") == 11


def test_amounts_read_back_with_exactly_their_currencys_decimals():
    assert str(from_minor(123450, "USD")) == "1234.50"
    assert str(from_minor(1000, "JPY")) == "1000"
    assert str(from_minor(1234, "KWD")) == "1.234"


@given(
    code=st.sampled_from(sorted(EXPONENTS)),
    minor=st.integers(min_value=-(10**15), max_value=10**15),
)
def test_minor_units_round_trip_exactly_in_every_currency(code, minor):
    assert to_minor(from_minor(minor, code), code) == minor


def test_formatting_uses_the_currency_and_never_a_symbol():
    assert format_amount(Decimal("1234.5"), "EUR") == "1,234.50 EUR"
    assert format_amount(Decimal("1234567"), "JPY") == "1,234,567 JPY"
    assert format_amount(Decimal("1.2345"), "KWD") == "1.235 KWD"
    assert str(Money.of(Decimal("1500.5"), "USD")) == "1,500.50 USD"


def test_money_knows_its_scale():
    assert Money.of(Decimal("1000"), "JPY").minor_units == 1000
    assert Money.of(Decimal("1.5"), "KWD").minor_units == 1500
    assert Money.of(Decimal("1.5"), "KWD").to_decimal() == Decimal("1.500")
    with pytest.raises(UnknownCurrencyError):
        Money(100, "ABC")


def test_a_posting_holds_what_its_currency_can_express():
    yen = Posting(
        account_id="a", direction=Direction.DEBIT, amount=Decimal("1000.4"), currency="jpy"
    )
    assert (yen.amount, yen.currency) == (Decimal("1000"), "JPY")
    usd = Posting(
        account_id="a", direction=Direction.DEBIT, amount=Decimal("10.005"), currency="USD"
    )
    assert usd.amount == Decimal("10.01")
    with pytest.raises(ValueError, match="smallest unit"):
        Posting(account_id="a", direction=Direction.DEBIT, amount=Decimal("0.4"), currency="JPY")


def test_an_entry_that_only_balances_below_the_smallest_unit_is_refused():
    """Rounding happens per posting, before the balance check, so the check sees
    exactly what will be stored. 10.005 + (5.0025 + 5.0025) balances on paper but
    stores as 10.01 against 5.00 + 5.00."""
    with pytest.raises(ValueError, match="unbalanced"):
        JournalEntry(
            entry_date="2026-10-01",
            description="x",
            source="manual",
            postings=[
                Posting(
                    account_id="a",
                    direction=Direction.DEBIT,
                    amount=Decimal("10.005"),
                    currency="USD",
                ),
                Posting(
                    account_id="b",
                    direction=Direction.CREDIT,
                    amount=Decimal("5.0025"),
                    currency="USD",
                ),
                Posting(
                    account_id="c",
                    direction=Direction.CREDIT,
                    amount=Decimal("5.0025"),
                    currency="USD",
                ),
            ],
        )


def test_quantize_rounds_half_up_to_the_currency():
    assert quantize(Decimal("2.5"), "JPY") == Decimal("3")
    assert quantize(Decimal("2.0045"), "KWD") == Decimal("2.005")
