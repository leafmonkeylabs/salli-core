"""
Amounts as people write them, read exactly.

The same number is written 1,234.56 in the US, 1.234,56 in Germany, 1 234,56
in France, 1'234.56 in Switzerland and 12,34,567.89 in India; a negative one
as -12.50, 12.50-, (12.50) or "12.50 DR"; often with a currency symbol or code
stuck to it. `parse_decimal` reads all of these from the text and builds the
Decimal from its digits, so an amount never passes through a float and is
never rounded.

What one value cannot always say is which mark is the decimal point: "1,234"
is a little over a thousand in New York and a little over one in Berlin.
`detect_decimal_separator` settles that from a whole column of amounts, and
the importer passes its answer to `parse_decimal`.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from decimal import Decimal

from salli.domain.currency import is_currency

# Marks that only ever group digits: spaces (plain, no-break, narrow no-break,
# thin) and apostrophes (straight and typographic).
_GROUPING = "    '’"

# The number itself: from its first digit to its last, separators between.
_NUMBER = re.compile(r"\d(?:[\d.," + _GROUPING + r"]*\d)?")

_CODE = re.compile(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])")


def parse_decimal(text: str, decimal_separator: str | None = None) -> Decimal:
    """The signed amount written in `text`, exactly.

    `decimal_separator` is "." or "," when the caller knows it — from
    `detect_decimal_separator`, the file format's rules, or the user. Without
    it, a value that reads two ways ("1,234") is refused rather than guessed.
    Raises ValueError for anything that is not a single amount.
    """
    s = text.strip().replace("−", "-")
    match = _NUMBER.search(s)
    if match is None:
        raise ValueError(f"{text!r} is not an amount")
    prefix, number, suffix = s[: match.start()], match.group(), s[match.end() :]
    negative = _is_negative(prefix, suffix, text)

    mark = decimal_separator or _decimal_mark(_ungrouped(number))
    if mark is None:
        if "." in number or "," in number:
            raise ValueError(f"{text!r} could be read with either decimal mark")
        mark = "."
    if mark not in (".", ","):
        raise ValueError(f"{mark!r} is not a decimal mark")
    if number.count(mark) > 1:
        raise ValueError(f"{text!r} has more than one decimal mark")

    grouping = _GROUPING + ("," if mark == "." else ".")
    whole, _, fraction = number.partition(mark)
    if any(ch in grouping for ch in fraction):
        raise ValueError(f"{text!r} groups digits after its decimal mark")
    groups = re.split("[" + re.escape(grouping) + "]", whole)
    # Thousands come in threes; Indian lakhs and crores group in twos before
    # the last three (12,34,567). Anything else is not a grouping but a
    # misread, such as "12.5" in a column whose decimal mark is a comma.
    if len(groups) > 1 and not (
        1 <= len(groups[0]) <= 3
        and all(len(g) in (2, 3) for g in groups[1:-1])
        and len(groups[-1]) == 3
    ):
        raise ValueError(f"{text!r} is not grouped like an amount")

    value = Decimal("".join(groups) + ("." + fraction if fraction else ""))
    return -value if negative else value


def detect_decimal_separator(values: Iterable[str]) -> str | None:
    """The decimal mark a column of amounts uses, or None if no value shows it.

    A value settles it when it uses both marks (the later one is the decimal
    point), repeats a mark (that one groups thousands), or has other than
    three digits after its only mark. "1,234" settles nothing. When values
    disagree the majority wins, and the rest then fail to parse loudly.
    """
    votes: Counter[str] = Counter()
    for value in values:
        match = _NUMBER.search(value)
        if match is not None:
            mark = _decimal_mark(_ungrouped(match.group()))
            if mark is not None:
                votes[mark] += 1
    ranked = votes.most_common()
    if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
        return None
    return ranked[0][0]


def currency_code_in(text: str) -> str | None:
    """The ISO 4217 code written beside an amount ("EUR 12,50", "12.50 USD"), if any.

    Symbols are not read as currencies: "$" alone could be a dozen of them.
    """
    codes = {code for code in _CODE.findall(text) if is_currency(code)}
    return codes.pop() if len(codes) == 1 else None


def _ungrouped(number: str) -> str:
    return "".join(ch for ch in number if ch not in _GROUPING)


def _decimal_mark(digits: str) -> str | None:
    """The decimal mark `digits` (digits, dots and commas) shows, if it shows one."""
    dots, commas = digits.count("."), digits.count(",")
    if dots and commas:
        return "." if digits.rfind(".") > digits.rfind(",") else ","
    for mark, other, count in ((".", ",", dots), (",", ".", commas)):
        if count > 1:
            return other
        if count == 1 and len(digits) - digits.index(mark) - 1 != 3:
            return mark
    return None


def _is_negative(prefix: str, suffix: str, text: str) -> bool:
    """Whether the marks around the number make it negative.

    Around an amount there may be a currency symbol or code, a sign, brackets,
    or CR/DR (credit/debit) as many statements print. Anything else — another
    number, a stray decimal mark — means this is not one amount.
    """
    # ".50" or "12.": a decimal mark outside the number. "Rs.12" is fine.
    if (prefix[-1:] in (".", ",") and not prefix[-2:-1].isalpha()) or suffix[:1] in (".", ","):
        raise ValueError(f"{text!r} is not an amount")
    before, after = _signs(prefix), _signs(suffix)
    if (
        set(before) - set("+-(")
        or set(after) - set("+-)")
        or before.count("(") != after.count(")")
        or before.count("(") > 1
        or len((before + after).replace("(", "").replace(")", "")) > 1
    ):
        raise ValueError(f"{text!r} is not an amount")

    minus = "-" in before + after or "(" in before
    plus = "+" in before + after
    words = {w.upper() for w in re.findall(r"[^\W\d_]+", prefix + " " + suffix)}
    markers = words & {"CR", "DR"}
    if len(markers) > 1:
        raise ValueError(f"{text!r} is marked both CR and DR")
    if markers:
        debit = markers == {"DR"}
        if (debit and plus) or (not debit and minus):
            raise ValueError(f"{text!r} has a sign that contradicts its CR/DR mark")
        return debit
    return minus


def _signs(part: str) -> str:
    """`part` without its currency symbols, letters, dots and spaces."""
    return "".join(
        ch
        for ch in part
        if not (ch.isspace() or ch == "." or unicodedata.category(ch)[0] in "LM")
        and unicodedata.category(ch) != "Sc"
    )
