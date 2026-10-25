"""
A push alert: a short message to the person's phone when something needs a
look now. Built like a digest (digest.py's wording table, counts and dates,
never an amount, a name or anything from the ledger) and pure.

**What goes in one:** monthly budget lines over their limit (`budget_over`),
the cash forecast below zero (`cash_below_zero_ahead`, the
`low_balance_ahead` signal at `high`) and the person's own reminders due
today or before (`reminder_due`).

**Once per state:** its period is a hash of its items (kinds, counts,
dates), so the delivery log's unique (user, period) key sends the same alert
once, and a new one only when what is waiting changes.
"""

from __future__ import annotations

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
