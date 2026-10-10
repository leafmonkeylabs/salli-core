"""
Dates as statements write them.

The numbers of a date come in three orders: day first (31/10/2026, most of the
world), month first (10/31/2026, the United States) and year first
(2026-10-31). One date often cannot tell day-first from month-first —
01/10/2026 is a date either way — but a statement holds many dates, and a
single 31/10/2026 proves the whole file day-first. So the order is decided
from all of a file's dates at once (`detect_date_order`), and each date is then
read in that order (`parse_date`).

A date that names its month (1 Oct 2026, Oct 1, 2026) or starts with a
four-digit year reads the same in any order.
"""

from __future__ import annotations

import datetime
import itertools
import re
import unicodedata
from collections.abc import Callable, Iterable
from typing import Literal

DateOrder = Literal["DMY", "MDY", "YMD"]

# Also the preference when a file's dates fit several orders equally well:
# most of the world writes the day first.
DATE_ORDERS: tuple[DateOrder, ...] = ("DMY", "MDY", "YMD")

_ORDER_NAMES: dict[DateOrder, str] = {
    "DMY": "day first",
    "MDY": "month first",
    "YMD": "year first",
}

# Month names and their abbreviations, without accents, in the languages bank
# exports most often use: English, German, French, Spanish, Italian,
# Portuguese and Dutch. Only whole names count, so "Market" is not March.
_MONTHS: dict[str, int] = {
    name: number
    for number, names in enumerate(
        [
            "jan january januar janv janvier ene enero gen gennaio janeiro januari",
            "feb february februar fevr fevrier febrero febbraio fev fevereiro februari",
            "mar march marz mrz mars marzo marco mrt maart",
            "apr april avr avril abr abril aprile",
            "may mai mayo mag maggio maio mei",
            "jun june juni juin junio giu giugno junho",
            "jul july juli juil juillet julio lug luglio julho",
            "aug august aout ago agosto augustus",
            "sep sept september septembre septiembre setiembre set settembre setembro",
            "oct october okt oktober octobre octubre ott ottobre out outubro",
            "nov november novembre noviembre novembro",
            "dec december dez dezember decembre dic diciembre dicembre dezembro",
        ],
        1,
    )
    for name in names.split()
}

# Dates are read after every run of whitespace is collapsed to one space (and
# a cell longer than this is no date), so no pattern below can backtrack over
# a long run of spaces: each separator is one mark with at most one space on
# either side, or a single space, and the two never overlap.
_MAX_DATE_LENGTH = 64
_TIME = r"(?:[T ,]+\d{1,2}[:.]\d{2}.*)?"
_SEP = r"(?: ?([./\-']) ?| ())"
_NUMERIC = re.compile(r"(\d{1,4})" + _SEP + r"(\d{1,2})" + _SEP + r"(\d{1,4})" + _TIME, re.S)
_COMPACT = re.compile(r"(\d{8})(?:\d{4,6})?" + _TIME, re.S)
_DAY_MONTH_YEAR = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)?[ ./\-]*([^\W\d_]{3,})\.?[ ./\-,]*(\d{4}|\d{2})" + _TIME, re.S
)
# The day must stand apart from the year: "October 2026" is a month, not the
# 20th of October '26.
_MONTH_DAY_YEAR = re.compile(
    r"([^\W\d_]{3,})\.?[ ./\-]*(\d{1,2})(?:st|nd|rd|th)?[ ./\-,]+(\d{4}|\d{2})" + _TIME, re.S
)
# A date somewhere in a longer cell ("02/10/2026*", "Mon 01/10/2026", two
# stacked dates): numbers with separators, eight digits, or a named month.
# Searched at every position (a lookahead), so "Mon 01/10/2026" finds the
# date after "Mon 01" fails to be one.
_DATE_TOKEN = re.compile(
    r"(?=((?<![\d.,])(?:\d{1,4}[./\-]\d{1,2}[./\-]\d{2,4}|\d{8})(?![\d.,])"
    r"|(?<!\d)\d{1,2}(?:st|nd|rd|th)?[ ./\-]+[^\W\d_]{3,}\.?[ ./\-,]*\d{2,4}(?!\d)"
    r"|(?<![^\W\d_])[^\W\d_]{3,}\.?[ ./\-]*\d{1,2}(?:st|nd|rd|th)?[ ./\-,]+\d{2,4}(?!\d)))"
)


def full_year(two_digits: int) -> int:
    """A two-digit year in full, pivoting as POSIX strptime does: 69–99 are
    1969–1999, 00–68 are 2000–2068."""
    return two_digits + (1900 if two_digits >= 69 else 2000)


def parse_date(text: str, order: DateOrder) -> str | None:
    """`text` as YYYY-MM-DD, its numbers read in `order`; None if it is no real date."""
    found = _date(text, order)
    return found.isoformat() if found else None


def candidate_orders(text: str) -> frozenset[DateOrder] | None:
    """The orders in which `text` reads as a real date.

    None when it does not look like a date at all (a footer's "Total"), and
    empty when it looks like one but is not (31/31/2026). A date that names its
    month or starts with a four-digit year fits every order.
    """
    s = _squeezed(text)
    if s is None:
        return None
    if _named(s) is not None or _numbers(s) is not None:
        return frozenset(o for o in DATE_ORDERS if _date(s, o) is not None)
    return None


def find_date(text: str) -> str | None:
    """The first date-shaped part of a longer cell ("02/10/2026*",
    "Mon 01/10/2026", "01/10/2026\n02/10/2026": the first, the transaction
    date), or None. The cell itself when it is a date already."""
    if candidate_orders(text) is not None:
        return text
    s = " ".join(text.split())[: _MAX_DATE_LENGTH * 4]
    for match in _DATE_TOKEN.finditer(s):
        if candidate_orders(match.group(1)) is not None:
            return match.group(1)
    return None


def default_order(currency: str | None) -> DateOrder:
    """The order to fall back on when a file's dates read more than one way:
    month first for dollar statements (the United States writes them so),
    day first everywhere else."""
    return "MDY" if (currency or "").upper() == "USD" else "DMY"


# A reading whose dates leave a gap this long between two consecutive ones is
# no statement's, when another reading leaves none: 01/05/2025..02/05/2026
# day-first is twelve days in May 2025 and two in May 2026.
_MAX_GAP_DAYS = 183
# Two-digit years read the wrong way round scatter a file over decades.
_MAX_SPREAD_DAYS = 5 * 366
# How far past today a statement's date can be (a card's next posting date).
_FUTURE_DAYS = 30


def detect_date_order(
    values: Iterable[str],
    *,
    prefer: DateOrder = "DMY",
    today: datetime.date | None = None,
) -> tuple[DateOrder, str | None]:
    """The order a file's dates are written in, and a notice if it was a guess.

    `values` are the file's dates in the order its rows give them. The order
    is one in which every date is real; when several are, the readings are
    weighed in turn, each test only ever narrowing them:

    1. plausibility: no date more than a month in the future, and not spread
       over decades (01.10.26 to 30.10.26 are not the 26th of October in
       2001 to 2030);
    2. agreement with the rows' order: a statement lists its transactions in
       date order, oldest or newest first, so a reading that keeps them
       sorted wins over one that does not ('15.01.25'..'15.02.26' read
       year-first goes back in time at each new year);
    3. no gap of half a year between consecutive dates when another reading
       has none.

    What is left after that is genuinely ambiguous (05/07, 05/08, 05/09 are
    three days in May or the 5th of three months), and is read in `prefer`,
    the order the statement's country writes (`default_order`). That is a
    guess, and is said, so the user can import again with the order set.
    """
    dated: list[tuple[str, frozenset[DateOrder]]] = []
    for value in values:
        orders = candidate_orders(value)
        if orders:
            dated.append((value.strip(), orders))
    fits: list[DateOrder] = [o for o in DATE_ORDERS if all(o in orders for _, orders in dated)]
    if not fits:
        # No order reads every date: take the one that reads the most. The
        # rest are reported as their rows are read.
        most: DateOrder = max(DATE_ORDERS, key=lambda o: sum(o in orders for _, orders in dated))
        return most, None

    readings: dict[DateOrder, list[datetime.date]] = {
        o: [d for d in (_date(value, o) for value, _ in dated) if d is not None] for o in fits
    }
    latest = (today or datetime.date.today()) + datetime.timedelta(days=_FUTURE_DAYS)

    def narrowed(keep: Callable[[DateOrder], bool]) -> None:
        nonlocal fits
        kept: list[DateOrder] = [o for o in fits if keep(o)]
        if kept:
            fits = kept

    def spread(o: DateOrder) -> int:
        days = readings[o]
        return (max(days) - min(days)).days if days else 0

    def in_order(o: DateOrder) -> int:
        days = readings[o]
        pairs = list(itertools.pairwise(days))
        return max(sum(a <= b for a, b in pairs), sum(a >= b for a, b in pairs))

    def widest_gap(o: DateOrder) -> int:
        days = sorted(readings[o])
        return max(((b - a).days for a, b in itertools.pairwise(days)), default=0)

    narrowed(lambda o: all(d <= latest for d in readings[o]))
    narrowed(lambda o: spread(o) <= _MAX_SPREAD_DAYS)
    most_in_order = max(in_order(o) for o in fits)
    narrowed(lambda o: in_order(o) == most_in_order)
    narrowed(lambda o: widest_gap(o) <= _MAX_GAP_DAYS)

    best: DateOrder = prefer if prefer in fits else fits[0]
    if len(fits) == 1:
        return best, None
    # Only a date that reads differently in the orders still in play is
    # evidence of a guess; 05/05/2026 is the same day either way.
    example = next(
        (value for value, _ in dated if len({_date(value, o) for o in fits}) > 1),
        None,
    )
    if example is None:
        return best, None
    others = " or ".join(o for o in fits if o != best)
    return best, (
        f"Dates such as {example!r} could be read more than one way; read them "
        f"{_ORDER_NAMES[best]} ({best}). If that is wrong, import the file again "
        f"with the date order set to {others}."
    )


def _squeezed(text: str) -> str | None:
    """`text` with its whitespace collapsed, or None if too long to be a date."""
    if len(text) > _MAX_DATE_LENGTH * 4:
        return None
    s = " ".join(text.split())
    return s if len(s) <= _MAX_DATE_LENGTH else None


def _date(text: str, order: DateOrder) -> datetime.date | None:
    s = _squeezed(text)
    if s is None:
        return None
    named = _named(s)
    if named is not None:
        return _real(*named)
    numbers = _numbers(s)
    if numbers is None:
        return None
    a, b, c, year_last = numbers
    if len(a) == 4:  # a four-digit year first is year-month-day, whatever the order
        year, month, day = a, b, c
    elif order == "DMY":
        day, month, year = a, b, c
    elif order == "MDY":
        month, day, year = a, b, c
    elif year_last:
        return None
    else:
        year, month, day = a, b, c
    if len(year) not in (2, 4) or len(day) > 2:
        return None
    full = int(year) if len(year) == 4 else full_year(int(year))
    return _real(full, int(month), int(day))


def _numbers(s: str) -> tuple[str, str, str, bool] | None:
    """The three numbers of a numeric date in the order written, and whether
    the last one is marked as the year (Quicken writes 10/ 1'26)."""
    match = _NUMERIC.fullmatch(s)
    if match:
        return match.group(1), match.group(4), match.group(7), match.group(5) == "'"
    match = _COMPACT.fullmatch(s)
    if match:
        digits = match.group(1)
        # 20261001 leads with its year; 01102026 ends with it. Eight digits
        # that are no real year-month-day (19102026: the 19th of October)
        # end with the year.
        if _real(int(digits[:4]), int(digits[4:6]), int(digits[6:])) is not None:
            return digits[:4], digits[4:6], digits[6:], False
        return digits[:2], digits[2:4], digits[4:], True
    return None


def _named(s: str) -> tuple[int, int, int] | None:
    """(year, month, day) of a date that names its month, unchecked."""
    for pattern, month_group, day_group in ((_DAY_MONTH_YEAR, 2, 1), (_MONTH_DAY_YEAR, 1, 2)):
        match = pattern.fullmatch(s)
        if match:
            month = _month(match.group(month_group))
            if month is None:
                continue
            year = match.group(3)
            full = int(year) if len(year) == 4 else full_year(int(year))
            return full, month, int(match.group(day_group))
    return None


def _month(name: str) -> int | None:
    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(ch)
    )
    return _MONTHS.get(folded)


def _real(year: int, month: int, day: int) -> datetime.date | None:
    if not 1900 <= year <= 2100:
        return None
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None
