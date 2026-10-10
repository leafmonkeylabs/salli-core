"""
Any amount, written the way any locale writes it, reads back as exactly the
same Decimal: same value, same number of decimal places, never via a float.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from salli.adapters.parsing.amounts import detect_decimal_separator, parse_decimal

# (grouping mark, decimal mark, Indian lakh grouping?)
STYLES = {
    "en-US": (",", ".", False),
    "de-DE": (".", ",", False),
    "fr-FR": (" ", ",", False),
    "fr-FR (plain space)": (" ", ",", False),
    "de-CH": ("'", ".", False),
    "en-IN": (",", ".", True),
    "plain": ("", ".", False),
    "plain comma": ("", ",", False),
}

NEGATIVES = ["-{}", "{}-", "({})", "{} DR", "−{}"]
DECORATIONS = ["{}", "${}", "€ {}", "{} EUR", "USD {}", "Rs. {}", "{} zł"]


def _group(digits: str, mark: str, lakh: bool) -> str:
    if not mark or len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    size = 2 if lakh else 3
    groups: list[str] = []
    while head:
        groups.insert(0, head[-size:])
        head = head[:-size]
    return mark.join([*groups, tail])


def _format(value: Decimal, style: str) -> str:
    grouping, decimal_mark, lakh = STYLES[style]
    whole, _, fraction = f"{abs(value):f}".partition(".")
    text = _group(whole, grouping, lakh)
    return text + (decimal_mark + fraction if fraction else "")


amounts = st.integers(min_value=0, max_value=3).flatmap(
    lambda places: st.decimals(
        min_value=Decimal("-999999999"),
        max_value=Decimal("999999999"),
        places=places,
        allow_nan=False,
        allow_infinity=False,
    )
)


@given(
    value=amounts,
    style=st.sampled_from(sorted(STYLES)),
    negative=st.sampled_from(NEGATIVES),
    decoration=st.sampled_from(DECORATIONS),
)
def test_any_locale_style_reads_back_exactly(
    value: Decimal, style: str, negative: str, decoration: str
) -> None:
    text = _format(value, style)
    if value < 0:
        text = negative.format(text)
    text = decoration.format(text)

    parsed = parse_decimal(text, STYLES[style][1])

    assert parsed == value
    assert parsed.as_tuple().exponent == value.as_tuple().exponent


@given(values=st.lists(amounts, min_size=1, max_size=20), style=st.sampled_from(sorted(STYLES)))
def test_a_column_never_settles_on_the_wrong_decimal_mark(values: list[Any], style: str) -> None:
    texts = [_format(v, style) for v in values]
    detected = detect_decimal_separator(texts)

    assert detected in (None, STYLES[style][1])
    if detected is not None:
        assert [parse_decimal(t, detected) for t in texts] == [abs(v) for v in values]
