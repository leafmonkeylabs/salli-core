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
from typing import Literal

from salli.domain.currency import is_currency

# Marks that only ever group digits: spaces (plain, no-break, narrow no-break,
# thin) and apostrophes (straight and typographic).
_GROUPING = "    '’"

# The number itself: from its first digit to its last, separators between.
_NUMBER = re.compile(r"\d(?:[\d.," + _GROUPING + r"]*\d)?")

_CODE = re.compile(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])")

# More integer digits than any real balance has (a quadrillion): a misread
# (an account number taken for an amount), and beyond what a Decimal of the
# default precision can round to a currency's minor units.
MAX_INTEGER_DIGITS = 15

# What an empty cell is printed as: Excel's Accounting format, many PDFs.
_PLACEHOLDERS = {"-", "–", "—", "--"}

# Marks after an amount saying which way it went: DR/CR everywhere, S/H (Soll,
# Haben) in German statements, D/C on some others. Single letters only count
# after the number: before it, "S$" is a Singapore dollar.
_DEBIT_MARKS = {"DR", "S", "D"}
_CREDIT_MARKS = {"CR", "H", "C"}

Mark = Literal["CR", "DR"]


def is_blank_amount(text: str) -> bool:
    """Whether a cell holds no amount: empty, or a dash printed in its place."""
    return text.strip() in _PLACEHOLDERS or not text.strip()


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

    digits = "".join(groups).lstrip("0")
    if len(digits) > MAX_INTEGER_DIGITS:
        raise ValueError(f"{text!r} is too large to be an amount")
    value = Decimal("".join(groups) + ("." + fraction if fraction else ""))
    return -value if negative else value


def amount_mark(text: str) -> Mark | None:
    """The CR/DR mark written with an amount (DR, S or D after it is a debit;
    CR, H or C a credit), or None when it has none."""
    s = text.strip()
    match = _NUMBER.search(s)
    if match is None:
        return None
    prefix, suffix = s[: match.start()], s[match.end() :]
    words = {w.upper() for w in re.findall(r"[^\W\d_]+", prefix)} & {"CR", "DR"}
    after = [w.upper() for w in re.findall(r"[^\W\d_]+", suffix)]
    words |= {w for w in after if w in _DEBIT_MARKS | _CREDIT_MARKS}
    if len(words) != 1:
        return None
    (word,) = words
    return "DR" if word in _DEBIT_MARKS else "CR"


def decimal_mark_for(values: Iterable[str], exponent: int | None, default: str = ".") -> str:
    """The decimal mark of a column of amounts in a currency with `exponent`
    decimals (None when unknown).

    As `detect_decimal_separator`, and when no value settles it ("1,250",
    "1.250"), the currency does: three digits after the only mark are its
    decimals in a three-decimal currency (KWD 1.250), and grouping in any
    other (JPY 12,345). Without either, `default`.
    """
    values = list(values)
    found = detect_decimal_separator(values)
    if found is not None:
        return found
    if exponent is None:
        return default
    for value in values:
        match = _NUMBER.search(value)
        if match is None:
            continue
        number = _ungrouped(match.group())
        mark = "." if "." in number else "," if "," in number else None
        if mark is not None:
            return mark if exponent == 3 else ("," if mark == "." else ".")
    return default


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
    # A single letter after the number: Soll/Haben (S/H) or D/C.
    markers |= {
        "DR" if w in _DEBIT_MARKS else "CR"
        for w in (w.upper() for w in re.findall(r"[^\W\d_]+", suffix))
        if len(w) == 1 and w in _DEBIT_MARKS | _CREDIT_MARKS
    }
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
