"""
Statement dates in every order and spelling, and how a file's own dates
decide whether 01/10/2026 is the first of October or the tenth of January.
"""

import pytest

from salli.adapters.parsing.dates import candidate_orders, detect_date_order, parse_date


@pytest.mark.parametrize(
    ("text", "order", "expected"),
    [
        ("31/10/2026", "DMY", "2026-10-31"),
        ("10/31/2026", "MDY", "2026-10-31"),
        ("01/10/2026", "DMY", "2026-10-01"),
        ("01/10/2026", "MDY", "2026-01-10"),
        ("1.10.2026", "DMY", "2026-10-01"),
        ("01-10-26", "DMY", "2026-10-01"),
        ("26/10/01", "YMD", "2026-10-01"),
        ("10/ 1'26", "MDY", "2026-10-01"),  # Quicken
        ("2026-10-01", "DMY", "2026-10-01"),  # a leading four-digit year wins over the order
        ("2026/10/01", "MDY", "2026-10-01"),
        ("2026-10-01T14:22:05+02:00", "DMY", "2026-10-01"),
        ("10/01/2026 2:30 PM", "MDY", "2026-10-01"),
        ("20261001", "MDY", "2026-10-01"),
        ("01102026", "DMY", "2026-10-01"),
        ("01 Oct 2026", "MDY", "2026-10-01"),
        ("1-OCT-26", "MDY", "2026-10-01"),
        ("Oct 1, 2026", "DMY", "2026-10-01"),
        ("October 1st 2026", "DMY", "2026-10-01"),
        ("3. März 2026", "MDY", "2026-03-03"),
        ("1 août 2026", "MDY", "2026-08-01"),
        ("15 dic 2026", "MDY", "2026-12-15"),
    ],
)
def test_reads_dates_as_statements_write_them(text, order, expected):
    assert parse_date(text, order) == expected


@pytest.mark.parametrize(
    ("text", "order"),
    [
        ("31/02/2026", "DMY"),
        ("10/31/2026", "DMY"),
        ("10/ 1'26", "YMD"),  # the apostrophe marks the year as last
        ("01/10/2026", "YMD"),
        ("Total", "DMY"),
        ("Market 5 26", "DMY"),
        ("1.234,56", "DMY"),
    ],
)
def test_not_a_date_in_that_order(text, order):
    assert parse_date(text, order) is None


def test_what_looks_like_a_date_and_what_does_not():
    assert candidate_orders("Total") is None
    assert candidate_orders("") is None
    assert candidate_orders("31/31/2026") == frozenset()  # looks like one, isn't
    assert candidate_orders("31/10/2026") == {"DMY"}
    assert candidate_orders("01/10/2026") == {"DMY", "MDY"}
    assert candidate_orders("01 Oct 2026") == {"DMY", "MDY", "YMD"}


def test_one_unambiguous_date_decides_the_file():
    assert detect_date_order(["01/10/2026", "05/10/2026", "25/10/2026"]) == ("DMY", None)
    assert detect_date_order(["10/01/2026", "10/05/2026", "10/25/2026"]) == ("MDY", None)


def test_ambiguous_dates_are_read_the_way_that_keeps_them_together_and_said_so():
    # Nine days in October, or the 10th of nine different months.
    order, notice = detect_date_order(["10/01/2026", "10/05/2026", "10/09/2026"])
    assert order == "MDY"
    assert notice is not None and "'10/01/2026'" in notice and "DMY" in notice

    order, notice = detect_date_order(["01/10/2026", "05/10/2026", "09/10/2026"])
    assert order == "DMY"
    assert notice is not None and "MDY" in notice


def test_a_lone_ambiguous_date_is_read_day_first():
    order, notice = detect_date_order(["01/02/2026"])
    assert order == "DMY"
    assert notice is not None


def test_no_notice_when_the_order_cannot_matter():
    assert detect_date_order(["2026-10-01", "2026-10-09"]) == ("DMY", None)
    assert detect_date_order(["05/05/2026"]) == ("DMY", None)
    assert detect_date_order(["01 Oct 2026"]) == ("DMY", None)
    assert detect_date_order([]) == ("DMY", None)


def test_when_no_order_reads_every_date_the_best_one_wins():
    # The last value is a typo; the rest are plainly day-first.
    assert detect_date_order(["25/10/2026", "26/10/2026", "10/31/2026"]) == ("DMY", None)
