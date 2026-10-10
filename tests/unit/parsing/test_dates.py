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
        ("19102026", "DMY", "2026-10-19"),  # not the 26th of the 20th month of 1910
        ("20102026", "DMY", "2026-10-20"),
        ("10192026", "MDY", "2026-10-19"),
        ("01  /  10 /   2026", "DMY", "2026-10-01"),
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
        ("October 2026", "DMY"),  # a month, not the 20th of October '26
        ("Oct 2026", "MDY"),
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


def test_genuinely_ambiguous_dates_are_read_in_the_countrys_order_and_said_so():
    # Nine days in October, or the 10th of nine different months: both are
    # statements. The smallest spread used to win, which read day-first Sri
    # Lankan statements (05/07, 05/08, 05/09: the 5th of each month) as May.
    order, notice = detect_date_order(["10/01/2026", "10/05/2026", "10/09/2026"])
    assert order == "DMY"
    assert notice is not None and "'10/01/2026'" in notice and "MDY" in notice

    order, notice = detect_date_order(["05/07/2025", "05/08/2025", "05/09/2025"])
    assert (order, notice is not None) == ("DMY", True)

    order, notice = detect_date_order(["10/01/2026", "10/05/2026", "10/09/2026"], prefer="MDY")
    assert order == "MDY"
    assert notice is not None and "DMY" in notice


def test_a_reading_that_keeps_the_rows_in_order_wins():
    # Fourteen months of German two-digit dates. Year-first they all fall in
    # 2015 (within a year, which used to win) but go back in time at the new
    # year; day-first they are in order.
    months = [("25", m) for m in range(1, 13)] + [("26", 1), ("26", 2)]
    assert detect_date_order([f"15.{m:02d}.{y}" for y, m in months]) == ("DMY", None)


def test_a_reading_with_a_half_year_gap_is_no_alternative():
    # US monthly dates over fourteen months. Day-first they are twelve days in
    # May 2025 and two in May 2026, which also reads within a year.
    months = [("2025", m) for m in range(1, 13)] + [("2026", 1), ("2026", 2)]
    values = [f"{m:02d}/05/{y}" for y, m in months]
    assert detect_date_order(values) == ("MDY", None)


def test_a_reading_far_in_the_future_is_no_alternative():
    import datetime

    today = datetime.date(2026, 10, 9)
    # Month-first, 03/12 is the 12th of March; day-first it is December, two
    # months ahead of today.
    assert detect_date_order(["03/09/2026", "03/12/2026"], today=today)[0] == "MDY"


def test_a_reading_that_spans_decades_is_no_alternative():
    # Day-first, these are October 2026. Year-first they would be the 26th of
    # October in 2001, 2014 and 2030: no statement looks like that.
    assert detect_date_order(["01.10.26", "14.10.26", "30.10.26"]) == ("DMY", None)


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


def test_a_date_is_found_in_a_cell_with_more_in_it():
    from salli.adapters.parsing.dates import find_date

    assert find_date("02/10/2026*") == "02/10/2026"
    assert find_date("Mon 01/10/2026") == "01/10/2026"
    assert find_date("01/10/2026\n02/10/2026") == "01/10/2026"  # the transaction date
    assert find_date("Total 1,234.00") is None
    assert find_date("October 2026") is None


def test_a_long_run_of_whitespace_is_read_quickly():
    # The separators overlapped, and backtracked cubically on whitespace.
    import time

    from salli.adapters.parsing.dates import find_date

    padded = "1" + " " * 2000 + "x"
    started = time.perf_counter()
    assert candidate_orders(padded) is None
    assert parse_date("1" + " " * 40 + "/2/2026" + " " * 2000, "DMY") is None
    assert find_date(padded) is None
    assert time.perf_counter() - started < 0.5
