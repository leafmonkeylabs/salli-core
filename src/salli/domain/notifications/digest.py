"""
A digest: what is waiting for a person in Salli, said in Salli's own words
(docs/design/decision-lab-phase-3.md, section 4, decisions 26 to 30). Pure
and deterministic: no I/O, and no model is ever called.

**What goes in one** (decision 28), in this fixed order, each only when the
person chose it:

| Item | From | Chosen by default |
|---|---|---|
| `decision_review_due` | review reminders (`source_domain` "decision") due, not done | yes |
| `reminder_due` | the person's own reminders, due before the next digest | yes |
| `filing_deadline` | filing reminders (`source_domain` "tax_rules") within 14 days | yes |
| `cash_below_zero_ahead` | the cash forecast below zero (the `low_balance_ahead` signal at `high`) | yes |
| `transactions_to_review` | imported transactions waiting for review | no |
| `budget_over` | monthly budget lines spent past what is available this month | no |

**What a message may say** (decision 29): each item's kind in a sentence
from the wording table below, how many, the earliest date (as the brand
writes dates on screen, "Sep 30, 2026"; the item's `date` stays ISO 8601),
and a link.
Never an amount, a balance, a name (an account's, a payee's, a rule set's,
a reminder's), a decision's question, a note, anything else from the ledger,
or the person's email. The builder is given nothing it could leak: a
reminder reaches it as its source, its due date and whether it is done
(`ReminderFact`), never its text.

**What it never says** (decision 30): no ranking or urgency, no streaks or
counts of anything consecutive, no countdown ("N days left"), no `!`. A date,
never a number of days. Tests hold every message the builder can make to it.

Nothing waiting, nothing to send: `build_digest` returns None.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from salli.domain.canonical import digest as content_hash
from salli.domain.notifications.schedule import Cadence, period_bounds

ItemKind = Literal[
    "decision_review_due",
    "reminder_due",
    "filing_deadline",
    "cash_below_zero_ahead",
    "transactions_to_review",
    "budget_over",
]

#: Every item kind, in the order a digest lists them (the wording table's,
#: never an order of importance).
ITEM_KINDS: tuple[ItemKind, ...] = get_args(ItemKind)
#: What a digest holds unless the person chooses otherwise.
DEFAULT_ITEMS: tuple[ItemKind, ...] = (
    "decision_review_due",
    "reminder_due",
    "filing_deadline",
    "cash_below_zero_ahead",
)

#: `reminders.source_domain` of a decision's review reminder, and of a filing
#: deadline from the person's active tax rules. A reminder with none is the
#: person's own.
DECISION_SOURCE = "decision"
FILING_SOURCE = "tax_rules"
#: How far ahead a filing deadline is listed.
FILING_WINDOW_DAYS = 14


@dataclass(frozen=True)
class NotificationItem:
    """One kind of thing waiting: Salli's own sentence for it, how many, and
    the earliest date it concerns."""

    kind: ItemKind
    #: Salli's own words, from the wording table (`item_title`).
    title: str
    count: int
    #: The earliest date it concerns (YYYY-MM-DD).
    date: str | None


@dataclass(frozen=True)
class Notification:
    """A message, complete as it is: a sender renders it and may restyle it,
    but has nothing else to put in it."""

    #: Stable for (user, kind, period): the idempotency key. Every attempt in
    #: a period carries the same id, so a sender can drop a repeat.
    id: str
    user_id: str
    #: A digest, or a push alert (domain/notifications/push.py).
    kind: Literal["digest", "push"]
    #: "2026-W42" or "2026-10".
    period: str
    subject: str
    #: Plain text, complete as it is.
    text: str
    items: tuple[NotificationItem, ...]
    #: The server's public URL, when there is one; never a token.
    link: str | None


@dataclass(frozen=True)
class ReminderFact:
    """What a digest may know of a reminder: where it comes from, when it is
    due and whether it is done. Never its text, which may hold a decision's
    question, a name or an amount."""

    #: `reminders.source_domain`: "decision", "tax_rules", another of Salli's
    #: (an alert's), or None for the person's own.
    source: str | None
    due: dt.date
    done: bool


@dataclass(frozen=True)
class Waiting:
    """Everything a digest is built from."""

    reminders: Sequence[ReminderFact] = ()
    #: The first day the cash forecast is below zero, when it is.
    cash_below_zero_on: dt.date | None = None
    #: Imported transactions waiting for review, and the oldest one's date.
    to_review: int = 0
    to_review_since: dt.date | None = None
    #: Monthly budget lines over what is available this month, and that
    #: month's first day.
    budgets_over: int = 0
    budget_month: dt.date | None = None


def notification_id(user_id: str, kind: str, period: str) -> str:
    """The stable id of a person's notification of `kind` for `period`."""
    return hashlib.sha256(f"{user_id}\n{kind}\n{period}".encode()).hexdigest()


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def on_screen(day: dt.date) -> str:
    """A date as the brand writes it in prose and on screens: "Sep 30, 2026".
    Not by locale, so every message reads the same wherever it is built."""
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _month(period: str) -> str:
    """A monthly period ("2026-10") as "Oct 2026"."""
    year, month = period.split("-")
    return f"{_MONTHS[int(month) - 1]} {year}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def item_title(kind: ItemKind, count: int, date: dt.date | None) -> str:
    """The wording table: Salli's one sentence for each kind of item. Only a
    count and a date are put in."""
    if count < 1:
        raise ValueError("an item counts at least one thing")
    on = on_screen(date) if date else None
    if kind == "decision_review_due":
        what = _plural(count, "decision ready for review", "decisions ready for review")
        return f"{what} (since {on})" if on else what
    if kind == "reminder_due":
        what = _plural(count, "reminder due", "reminders due")
        if on is None:
            return what
        return f"{what} on {on}" if count == 1 else f"{what}, the first on {on}"
    if kind == "filing_deadline":
        what = _plural(count, "filing deadline", "filing deadlines")
        if on is None:
            return what
        return f"{what} on {on}" if count == 1 else f"{what}, the first on {on}"
    if kind == "cash_below_zero_ahead":
        return (
            f"Your cash forecast goes below zero on {on}"
            if on
            else "Your cash forecast goes below zero"
        )
    if kind == "budget_over":
        what = _plural(count, "budget over its limit", "budgets over their limit")
        return f"{what} (since {on})" if on else what
    what = _plural(count, "transaction to review", "transactions to review")
    return f"{what} (waiting since {on})" if on else what


def _item(kind: ItemKind, dates: Sequence[dt.date]) -> NotificationItem | None:
    if not dates:
        return None
    first = min(dates)
    return NotificationItem(
        kind, item_title(kind, len(dates), first), len(dates), first.isoformat()
    )


def waiting_items(
    waiting: Waiting, today: dt.date, until: dt.date, chosen: Collection[ItemKind]
) -> tuple[NotificationItem, ...]:
    """The items of `waiting` the person chose, as of their local `today`.
    Reminders count up to `until` (the day before the next digest), review
    reminders up to today, filing deadlines from today to 14 days ahead."""
    pending = [r for r in waiting.reminders if not r.done]
    found: dict[ItemKind, NotificationItem | None] = {
        "decision_review_due": _item(
            "decision_review_due",
            [r.due for r in pending if r.source == DECISION_SOURCE and r.due <= today],
        ),
        "reminder_due": _item(
            "reminder_due", [r.due for r in pending if r.source is None and r.due <= until]
        ),
        "filing_deadline": _item(
            "filing_deadline",
            [
                r.due
                for r in pending
                if r.source == FILING_SOURCE
                and today <= r.due <= today + dt.timedelta(days=FILING_WINDOW_DAYS)
            ],
        ),
        "cash_below_zero_ahead": _item(
            "cash_below_zero_ahead",
            [waiting.cash_below_zero_on] if waiting.cash_below_zero_on else [],
        ),
        "transactions_to_review": None,
        "budget_over": None,
    }
    if waiting.budgets_over > 0:
        month = waiting.budget_month
        found["budget_over"] = NotificationItem(
            "budget_over",
            item_title("budget_over", waiting.budgets_over, month),
            waiting.budgets_over,
            month.isoformat() if month else None,
        )
    if waiting.to_review > 0:
        since = waiting.to_review_since
        found["transactions_to_review"] = NotificationItem(
            "transactions_to_review",
            item_title("transactions_to_review", waiting.to_review, since),
            waiting.to_review,
            since.isoformat() if since else None,
        )
    return tuple(
        item for kind in ITEM_KINDS if kind in chosen and (item := found[kind]) is not None
    )


def subject(period: str, cadence: Cadence, today: dt.date) -> str:
    """The message's subject line."""
    if cadence == "weekly":
        monday, _ = period_bounds(today, cadence)
        return f"Salli: what is waiting, week of {on_screen(monday)}"
    return f"Salli: what is waiting, {_month(period)}"


def build_digest(
    user_id: str,
    items: Iterable[NotificationItem],
    *,
    period: str,
    cadence: Cadence,
    today: dt.date,
    link: str | None,
) -> Notification | None:
    """The digest for `period`, or None when nothing is waiting: nothing is
    ever sent to say there is nothing."""
    listed = tuple(items)
    if not listed:
        return None
    every = "every week" if cadence == "weekly" else "every month"
    lines = [
        f"What is waiting for you in Salli, as of {on_screen(today)}:",
        "",
        *(f"- {item.title}" for item in listed),
        "",
        f"Open Salli to see them: {link}"
        if link
        else "Open Salli, or run `salli status`, to see them.",
        "",
        f"You asked for this digest {every}. To change it or turn it off: salli notifications set",
    ]
    return Notification(
        id=notification_id(user_id, "digest", period),
        user_id=user_id,
        kind="digest",
        period=period,
        subject=subject(period, cadence, today),
        text="\n".join(lines) + "\n",
        items=listed,
        link=link,
    )


def message_hash(notification: Notification) -> str:
    """ "sha256:" over the message's canonical JSON: what the delivery log
    keeps instead of the text."""
    return content_hash(
        {
            "id": notification.id,
            "period": notification.period,
            "subject": notification.subject,
            "text": notification.text,
            "items": [item_record(i) for i in notification.items],
            "link": notification.link,
        }
    )


def item_record(item: NotificationItem) -> dict[str, str | int | None]:
    """An item as the delivery log keeps it: kind, count and date only."""
    return {"kind": item.kind, "count": item.count, "date": item.date}
