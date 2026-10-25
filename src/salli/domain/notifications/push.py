"""
A push alert: a short message to the person's phone when something needs a
look now. Built like a digest (digest.py's wording table, counts and dates,
never an amount, a name or anything from the ledger) and pure.

**What goes in one:** monthly budget lines over their limit (`budget_over`),
the cash forecast below zero (`cash_below_zero_ahead`, the
`low_balance_ahead` signal at `high`) and the person's own reminders due
today or before (`reminder_due`).

**What the person chose:** which of those kinds their phone takes, and quiet
hours in their own time zone, when nothing is sent (`in_quiet_hours`); what
waits through them goes after.

**Once per state:** its period is a hash of its items (kinds, counts,
dates), so the delivery log's unique (user, period) key sends the same alert
once, and a new one only when what is waiting changes.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from salli.domain.canonical import digest as content_hash
from salli.domain.notifications.digest import (
    ItemKind,
    Notification,
    NotificationItem,
    item_record,
    notification_id,
)

#: The item kinds a push carries, in the wording table's order.
PUSH_ITEMS: tuple[ItemKind, ...] = ("reminder_due", "cash_below_zero_ahead", "budget_over")


def push_period(items: Iterable[NotificationItem]) -> str:
    """ "p" and nine hex digits of the items' hash: ten characters, like a
    digest's period column, and never one of a digest's ("2026-W42")."""
    return "p" + content_hash([item_record(i) for i in items]).split(":")[1][:9]


def build_push(
    user_id: str, items: Iterable[NotificationItem], *, link: str | None
) -> Notification | None:
    """The alert for what is waiting now, or None when nothing is."""
    listed = tuple(i for i in items if i.kind in PUSH_ITEMS)
    if not listed:
        return None
    period = push_period(listed)
    return Notification(
        id=notification_id(user_id, "push", period),
        user_id=user_id,
        kind="push",
        period=period,
        subject="Salli",
        text="\n".join(item.title for item in listed),
        items=listed,
        link=link,
    )


def parse_clock(value: str) -> dt.time:
    """ "22:00" as a time; ValueError unless it is HH:MM on the hour or minute."""
    if len(value) != 5 or value[2] != ":":
        raise ValueError(f"a time is HH:MM, such as '22:00', not {value!r}")
    return dt.time.fromisoformat(value)


def in_quiet_hours(local: dt.time, quiet_from: str | None, quiet_to: str | None) -> bool:
    """Whether a local time falls in quiet hours [from, to), which may run
    past midnight ("22:00" to "08:00"). None for either: no quiet hours."""
    if quiet_from is None or quiet_to is None:
        return False
    start, end = parse_clock(quiet_from), parse_clock(quiet_to)
    local = local.replace(second=0, microsecond=0, tzinfo=None)
    if start <= end:
        return start <= local < end
    return local >= start or local < end
