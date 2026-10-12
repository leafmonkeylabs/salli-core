"""
When a digest goes: its period, its day and its hour, in the person's own
time zone (docs/design/decision-lab-phase-3.md, section 4). Pure: the clock is
always passed in.

- **A period** is an ISO week ("2026-W42") or a calendar month ("2026-10"),
  of the person's local date. At most one digest goes per period.
- **The digest's day** is the chosen weekday: in its week, or, monthly, the
  first such weekday of the month.
- **The digest's hour** is the chosen local hour of that day. It is the only
  hour anything is sent, so quiet hours need no setting of their own. An hour
  a clock change skips begins when the clock reaches the next time that
  exists (02:00 skipped means 03:00); an hour a clock change repeats counts
  once, the first time.
- **A failed send** is tried again at the same hour on a later day of the
  same period (the service caps the attempts), never at another hour.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import cache
from typing import Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

Cadence = Literal["weekly", "monthly"]
Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

CADENCES: tuple[Cadence, ...] = get_args(Cadence)
WEEKDAYS: tuple[Weekday, ...] = get_args(Weekday)

#: Salli's plain default: Monday at 09:00.
DEFAULT_WEEKDAY: Weekday = "monday"
DEFAULT_HOUR = 9

_HOUR = dt.timedelta(hours=1)


class TimeZoneError(ValueError):
    """Not an IANA time zone name this server knows."""


def zone(name: str) -> ZoneInfo:
    """The IANA time zone `name` ("Europe/Lisbon", "Pacific/Auckland", "UTC").
    `TimeZoneError` for anything else: an abbreviation, an offset, a path."""
    if name not in _known_zones():
        raise TimeZoneError(
            f"{name!r} is not an IANA time zone name (such as 'Europe/Lisbon' or 'UTC')"
        )
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover - listed but unreadable
        raise TimeZoneError(f"{name!r} can't be read on this server") from exc


@cache
def _known_zones() -> frozenset[str]:
    return frozenset(available_timezones())


@dataclass(frozen=True)
class Schedule:
    """A person's digest schedule."""

    cadence: Cadence
    weekday: Weekday
    hour: int
    zone: ZoneInfo

    def __post_init__(self) -> None:
        if self.cadence not in CADENCES:
            raise ValueError(f"cadence must be one of {', '.join(CADENCES)}")
        if self.weekday not in WEEKDAYS:
            raise ValueError(f"weekday must be one of {', '.join(WEEKDAYS)}")
        if not 0 <= self.hour <= 23:
            raise ValueError("hour must be 0 to 23")


def period_of(day: dt.date, cadence: Cadence) -> str:
    """The period a local date falls in: "2026-W42" (ISO week) or "2026-10"."""
    if cadence == "weekly":
        year, week, _ = day.isocalendar()
        return f"{year}-W{week:02d}"
    return f"{day.year:04d}-{day.month:02d}"


def period_bounds(day: dt.date, cadence: Cadence) -> tuple[dt.date, dt.date]:
    """The first and last local dates of the period `day` falls in."""
    if cadence == "weekly":
        monday = day - dt.timedelta(days=day.weekday())
        return monday, monday + dt.timedelta(days=6)
    first = day.replace(day=1)
    following = (first + dt.timedelta(days=32)).replace(day=1)
    return first, following - dt.timedelta(days=1)


def digest_day(day: dt.date, cadence: Cadence, weekday: Weekday) -> dt.date:
    """The day of `day`'s period a digest goes on: the chosen weekday of the
    week, or the month's first such weekday."""
    first, _ = period_bounds(day, cadence)
    target = WEEKDAYS.index(weekday)
    if cadence == "weekly":
        return first + dt.timedelta(days=target)
    return first + dt.timedelta(days=(target - first.weekday()) % 7)


def hour_begins(day: dt.date, hour: int, tz: ZoneInfo) -> dt.datetime:
    """The instant (UTC) the local `hour` of `day` begins. A wall time a clock
    change skips is read with the offset before the change, which lands on
    the first time that exists after it; one it repeats is its first
    occurrence (`fold=0`)."""
    return dt.datetime.combine(day, dt.time(hour), tzinfo=tz).astimezone(dt.UTC)


@dataclass(frozen=True)
class Due:
    """A digest due now: its period, the person's local date, and whether
    this is the period's digest day (a first attempt may go) or a later day
    (only a retry may)."""

    period: str
    today: dt.date
    first: bool


def due(now: dt.datetime, schedule: Schedule) -> Due | None:
    """Whether `now` (aware) is in the digest's hour on the period's digest
    day, or at that hour on a later day of the same period. None otherwise."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(schedule.zone).date()
    # The hour's start can fall on the local day before (an hour that begins
    # just before a clock change at midnight); look at both.
    for day in (local - dt.timedelta(days=1), local):
        start = hour_begins(day, schedule.hour, schedule.zone)
        if not start <= now < start + _HOUR:
            continue
        slot = digest_day(day, schedule.cadence, schedule.weekday)
        if day < slot:
            return None
        return Due(period_of(day, schedule.cadence), day, first=day == slot)
    return None


def next_digest(now: dt.datetime, schedule: Schedule) -> dt.datetime:
    """When the next digest's hour begins, in the person's time zone: this
    period's, if its hour hasn't ended yet, or the next period's."""
    local = now.astimezone(schedule.zone).date()
    day = local - dt.timedelta(days=1)
    for _ in range(70):
        if day == digest_day(day, schedule.cadence, schedule.weekday):
            start = hour_begins(day, schedule.hour, schedule.zone)
            if now < start + _HOUR:
                return start.astimezone(schedule.zone)
        day += dt.timedelta(days=1)
    raise AssertionError("a digest day comes within ten weeks")  # pragma: no cover


def reminders_until(today: dt.date, schedule: Schedule) -> dt.date:
    """The last day a reminder may fall due and still be in this period's
    digest: the day before the next period's digest day, so each reminder is
    in the digest before it."""
    _, last = period_bounds(today, schedule.cadence)
    following = digest_day(last + dt.timedelta(days=1), schedule.cadence, schedule.weekday)
    return following - dt.timedelta(days=1)
