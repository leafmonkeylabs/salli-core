"""
When a digest goes (domain/notifications/schedule.py): its period, its day,
its local hour, and what a clock change does to that hour.
"""

from __future__ import annotations

import datetime as dt

import pytest

from salli.domain.notifications import schedule as timing
from salli.domain.notifications.schedule import Due, Schedule

UTC = dt.UTC


def at(text: str) -> dt.datetime:
    """An instant, from "YYYY-MM-DDTHH:MM" in UTC."""
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


def weekly(zone: str, weekday: timing.Weekday = "monday", hour: int = 9) -> Schedule:
    return Schedule("weekly", weekday, hour, timing.zone(zone))


def monthly(zone: str, weekday: timing.Weekday = "monday", hour: int = 9) -> Schedule:
    return Schedule("monthly", weekday, hour, timing.zone(zone))


# ── Time zones ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", ["Europe/Lisbon", "Pacific/Auckland", "America/Sao_Paulo", "UTC"])
def test_an_iana_name_is_a_time_zone(name):
    assert timing.zone(name).key == name


@pytest.mark.parametrize(
    "name", ["", "+05:30", "GMT+3", "Mars/Olympus", "../etc/passwd", "europe/lisbon", "Lisbon"]
)
def test_anything_else_is_refused(name):
    with pytest.raises(timing.TimeZoneError, match="not an IANA time zone"):
        timing.zone(name)


def test_a_schedule_checks_its_own_fields():
    with pytest.raises(ValueError, match="hour"):
        Schedule("weekly", "monday", 24, timing.zone("UTC"))
    with pytest.raises(ValueError, match="weekday"):
        Schedule("weekly", "someday", 9, timing.zone("UTC"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cadence"):
        Schedule("daily", "monday", 9, timing.zone("UTC"))  # type: ignore[arg-type]


# ── Periods ─────────────────────────────────────────────────────────────────


def test_a_week_is_its_iso_week_and_a_month_its_month():
    assert timing.period_of(dt.date(2026, 10, 12), "weekly") == "2026-W42"
    assert timing.period_of(dt.date(2026, 10, 18), "weekly") == "2026-W42"
    assert timing.period_of(dt.date(2026, 10, 19), "weekly") == "2026-W43"
    assert timing.period_of(dt.date(2026, 10, 31), "monthly") == "2026-10"


def test_the_iso_week_crosses_the_new_year():
    # 2027-01-01 is a Friday: still the last week of 2026, which has 53.
    assert timing.period_of(dt.date(2027, 1, 1), "weekly") == "2026-W53"
    assert timing.period_of(dt.date(2027, 1, 4), "weekly") == "2027-W01"
    assert timing.period_bounds(dt.date(2027, 1, 1), "weekly") == (
        dt.date(2026, 12, 28),
        dt.date(2027, 1, 3),
    )


def test_a_month_has_its_own_last_day():
    assert timing.period_bounds(dt.date(2028, 2, 10), "monthly") == (
        dt.date(2028, 2, 1),
        dt.date(2028, 2, 29),
    )
    assert timing.period_bounds(dt.date(2026, 12, 31), "monthly") == (
        dt.date(2026, 12, 1),
        dt.date(2026, 12, 31),
    )


def test_the_digest_day_is_the_weekday_of_the_week_or_the_months_first():
    assert timing.digest_day(dt.date(2026, 10, 15), "weekly", "monday") == dt.date(2026, 10, 12)
    assert timing.digest_day(dt.date(2026, 10, 15), "weekly", "sunday") == dt.date(2026, 10, 18)
    # The first Monday of November 2026 is the 2nd; of October, the 5th.
    assert timing.digest_day(dt.date(2026, 11, 20), "monthly", "monday") == dt.date(2026, 11, 2)
    assert timing.digest_day(dt.date(2026, 10, 1), "monthly", "monday") == dt.date(2026, 10, 5)
    # A month that starts on the weekday chosen.
    assert timing.digest_day(dt.date(2026, 6, 9), "monthly", "monday") == dt.date(2026, 6, 1)


# ── The hour ────────────────────────────────────────────────────────────────


def test_due_only_in_the_chosen_hour_of_the_digest_day():
    lisbon = weekly("Europe/Lisbon")  # WEST, UTC+1, in October 2026
    assert timing.due(at("2026-10-12T08:00"), lisbon) == Due(
        "2026-W42", dt.date(2026, 10, 12), True
    )
    assert timing.due(at("2026-10-12T08:59"), lisbon) is not None
    assert timing.due(at("2026-10-12T07:59"), lisbon) is None
    assert timing.due(at("2026-10-12T09:00"), lisbon) is None
    # Before the digest day in its week: nothing at all.
    assert timing.due(at("2026-10-12T08:30"), weekly("Europe/Lisbon", "tuesday")) is None


def test_a_later_day_of_the_period_at_the_same_hour_is_only_for_a_retry():
    lisbon = weekly("Europe/Lisbon")
    assert timing.due(at("2026-10-14T08:30"), lisbon) == Due(
        "2026-W42", dt.date(2026, 10, 14), first=False
    )
    assert timing.due(at("2026-10-14T10:30"), lisbon) is None


def test_the_local_date_decides_the_period_not_utcs():
    # Monday 09:30 in Auckland (NZDT, UTC+13) is Sunday 20:30 in UTC, which
    # is still week 41 there.
    auckland = weekly("Pacific/Auckland")
    when = at("2026-10-11T20:30")
    assert timing.period_of(when.date(), "weekly") == "2026-W41"
    assert timing.due(when, auckland) == Due("2026-W42", dt.date(2026, 10, 12), True)


def test_monthly_goes_on_the_first_such_weekday_then_retries_in_the_month():
    sao_paulo = monthly("America/Sao_Paulo", "wednesday", 18)  # UTC-3
    assert timing.due(at("2026-11-04T21:15"), sao_paulo) == Due(
        "2026-11", dt.date(2026, 11, 4), True
    )
    assert timing.due(at("2026-11-11T21:15"), sao_paulo) == Due(
        "2026-11", dt.date(2026, 11, 11), False
    )
    assert timing.due(at("2026-11-03T21:15"), sao_paulo) is None


def test_an_hour_a_clock_change_skips_goes_at_the_next_hour_that_exists():
    # New York springs forward on 2027-03-14: 02:00 EST becomes 03:00 EDT.
    new_york = weekly("America/New_York", "sunday", 2)
    assert timing.due(at("2027-03-14T06:30"), new_york) is None  # 01:30 EST
    assert timing.due(at("2027-03-14T07:30"), new_york) == Due(  # 03:30 EDT
        "2027-W10", dt.date(2027, 3, 14), True
    )
    assert timing.due(at("2027-03-14T08:30"), new_york) is None  # 04:30 EDT


def test_an_hour_a_clock_change_repeats_counts_once():
    # New York falls back on 2026-11-01: 01:00 to 02:00 happens twice.
    new_york = weekly("America/New_York", "sunday", 1)
    assert timing.due(at("2026-11-01T05:30"), new_york) is not None  # 01:30 EDT
    assert timing.due(at("2026-11-01T06:30"), new_york) is None  # 01:30 EST, again


def test_lisbons_own_clock_changes():
    # Lisbon skips 01:00 on 2027-03-28 and repeats it on 2026-10-25.
    assert timing.due(at("2027-03-28T01:30"), weekly("Europe/Lisbon", "sunday", 1)) is not None
    assert timing.due(at("2027-03-28T00:30"), weekly("Europe/Lisbon", "sunday", 1)) is None
    repeated = weekly("Europe/Lisbon", "sunday", 1)
    assert timing.due(at("2026-10-25T00:30"), repeated) is not None  # 01:30 WEST
    assert timing.due(at("2026-10-25T01:30"), repeated) is None  # 01:30 WET


def test_due_needs_an_aware_instant():
    with pytest.raises(ValueError, match="aware"):
        timing.due(dt.datetime(2026, 10, 12, 9), weekly("UTC"))


# ── The next digest, and what it covers ─────────────────────────────────────


def test_the_next_digest_is_this_periods_until_its_hour_ends():
    lisbon = weekly("Europe/Lisbon")
    assert timing.next_digest(at("2026-10-12T07:00"), lisbon).isoformat() == (
        "2026-10-12T09:00:00+01:00"
    )
    assert timing.next_digest(at("2026-10-12T08:30"), lisbon).isoformat() == (
        "2026-10-12T09:00:00+01:00"
    )
    # After it: next week's, in winter time by then.
    assert timing.next_digest(at("2026-10-26T10:30"), lisbon).isoformat() == (
        "2026-11-02T09:00:00+00:00"
    )
    assert timing.next_digest(at("2026-11-02T10:30"), monthly("Europe/Lisbon")).isoformat() == (
        "2026-12-07T09:00:00+00:00"
    )


def test_reminders_count_until_the_day_before_the_next_digest():
    assert timing.reminders_until(dt.date(2026, 10, 12), weekly("UTC")) == dt.date(2026, 10, 18)
    assert timing.reminders_until(dt.date(2026, 10, 14), weekly("UTC", "wednesday")) == dt.date(
        2026, 10, 20
    )
    assert timing.reminders_until(dt.date(2026, 11, 2), monthly("UTC")) == dt.date(2026, 12, 6)
