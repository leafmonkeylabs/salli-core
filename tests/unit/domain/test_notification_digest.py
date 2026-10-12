"""
The digest builder (domain/notifications/digest.py): every kind of item, the
wording table, nothing waiting, the message's id and hash, and the "never"
list over every message it can make.
"""

from __future__ import annotations

import datetime as dt
import itertools
from typing import Any

import pytest

from salli.domain.notifications.digest import (
    DEFAULT_ITEMS,
    ITEM_KINDS,
    Notification,
    NotificationItem,
    ReminderFact,
    Waiting,
    build_digest,
    item_record,
    item_title,
    message_hash,
    notification_id,
    waiting_items,
)
from tests.guardrails import assert_never_urges

TODAY = dt.date(2026, 10, 12)  # a Monday
UNTIL = dt.date(2026, 10, 18)
LINK = "https://money.example.org"


def d(day: str) -> dt.date:
    return dt.date.fromisoformat(day)


def reminder(source: str | None, due: str, done: bool = False) -> ReminderFact:
    return ReminderFact(source, d(due), done)


def view(n: Notification) -> dict[str, Any]:
    return {
        "subject": n.subject,
        "text": n.text,
        "items": [{"title": i.title, "kind": i.kind, "date": i.date} for i in n.items],
    }


# ── Each item ───────────────────────────────────────────────────────────────


def test_a_decision_review_counts_once_its_date_has_come():
    waiting = Waiting(
        [
            reminder("decision", "2026-10-05"),
            reminder("decision", "2026-10-12"),
            reminder("decision", "2026-10-13"),  # not yet
            reminder("decision", "2026-09-01", done=True),  # reviewed
        ]
    )
    (item,) = waiting_items(waiting, TODAY, UNTIL, ITEM_KINDS)
    assert item == NotificationItem(
        "decision_review_due", "2 decisions ready for review (since 2026-10-05)", 2, "2026-10-05"
    )


def test_the_persons_own_reminders_count_until_the_next_digest():
    waiting = Waiting(
        [
            reminder(None, "2026-10-01"),  # overdue, still pending
            reminder(None, "2026-10-18"),  # the day before the next digest
            reminder(None, "2026-10-19"),  # the next digest's
            reminder(None, "2026-10-14", done=True),
            # Salli's own alerts are other signals: they stay in the product.
            reminder("budget", "2026-10-12"),
            reminder("insurance", "2026-10-12"),
        ]
    )
    (item,) = waiting_items(waiting, TODAY, UNTIL, ITEM_KINDS)
    assert item.kind == "reminder_due"
    assert (item.count, item.date) == (2, "2026-10-01")
    assert item.title == "2 reminders due, the first on 2026-10-01"


def test_filing_deadlines_count_from_today_to_fourteen_days_ahead():
    waiting = Waiting(
        [
            reminder("tax_rules", "2026-10-11"),  # passed
            reminder("tax_rules", "2026-10-12"),
            reminder("tax_rules", "2026-10-26"),
            reminder("tax_rules", "2026-10-27"),  # fifteen days out
            reminder("tax_rules", "2026-10-20", done=True),
        ]
    )
    (item,) = waiting_items(waiting, TODAY, UNTIL, ITEM_KINDS)
    assert (item.kind, item.count, item.date) == ("filing_deadline", 2, "2026-10-12")
    assert item.title == "2 filing deadlines, the first on 2026-10-12"


def test_cash_below_zero_says_the_day():
    (item,) = waiting_items(Waiting(cash_below_zero_on=d("2026-11-02")), TODAY, UNTIL, ITEM_KINDS)
    assert item == NotificationItem(
        "cash_below_zero_ahead", "Your cash forecast goes below zero on 2026-11-02", 1, "2026-11-02"
    )


def test_transactions_to_review_only_when_chosen():
    waiting = Waiting(to_review=4, to_review_since=d("2026-10-01"))
    assert waiting_items(waiting, TODAY, UNTIL, DEFAULT_ITEMS) == ()
    (item,) = waiting_items(waiting, TODAY, UNTIL, ITEM_KINDS)
    assert item == NotificationItem(
        "transactions_to_review",
        "4 transactions to review (waiting since 2026-10-01)",
        4,
        "2026-10-01",
    )


def test_one_of_a_kind_reads_in_the_singular():
    assert item_title("decision_review_due", 1, d("2026-10-05")) == (
        "1 decision ready for review (since 2026-10-05)"
    )
    assert item_title("reminder_due", 1, d("2026-10-14")) == "1 reminder due on 2026-10-14"
    assert item_title("filing_deadline", 1, d("2026-10-20")) == "1 filing deadline on 2026-10-20"
    assert item_title("transactions_to_review", 1, None) == "1 transaction to review"
    with pytest.raises(ValueError):
        item_title("reminder_due", 0, None)


def test_only_the_chosen_items_in_the_tables_order():
    waiting = Waiting(
        [reminder("tax_rules", "2026-10-20"), reminder(None, "2026-10-13")],
        cash_below_zero_on=d("2026-11-02"),
        to_review=1,
        to_review_since=d("2026-10-10"),
    )
    chosen = ["transactions_to_review", "filing_deadline", "cash_below_zero_ahead"]
    kinds = [i.kind for i in waiting_items(waiting, TODAY, UNTIL, chosen)]
    assert kinds == ["filing_deadline", "cash_below_zero_ahead", "transactions_to_review"]


# ── The message ─────────────────────────────────────────────────────────────


def _items() -> tuple[NotificationItem, ...]:
    return waiting_items(
        Waiting(
            [reminder("decision", "2026-10-05"), reminder(None, "2026-10-14")],
            cash_below_zero_on=d("2026-11-02"),
        ),
        TODAY,
        UNTIL,
        DEFAULT_ITEMS,
    )


def test_nothing_waiting_means_no_message():
    assert waiting_items(Waiting(), TODAY, UNTIL, ITEM_KINDS) == ()
    assert (
        build_digest("u1", (), period="2026-W42", cadence="weekly", today=TODAY, link=LINK) is None
    )


def test_a_weekly_digest_reads_in_full():
    n = build_digest("u1", _items(), period="2026-W42", cadence="weekly", today=TODAY, link=LINK)
    assert n is not None
    assert (n.kind, n.period, n.user_id, n.link) == ("digest", "2026-W42", "u1", LINK)
    assert n.subject == "Salli: what is waiting, week of 2026-10-12"
    assert n.text == (
        "What is waiting for you in Salli, as of 2026-10-12:\n"
        "\n"
        "- 1 decision ready for review (since 2026-10-05)\n"
        "- 1 reminder due on 2026-10-14\n"
        "- Your cash forecast goes below zero on 2026-11-02\n"
        "\n"
        "Open Salli to see them: https://money.example.org\n"
        "\n"
        "You asked for this digest every week. To change it or turn it off: "
        "salli notifications set\n"
    )


def test_a_monthly_digest_without_a_link():
    n = build_digest(
        "u1", _items(), period="2026-11", cadence="monthly", today=d("2026-11-02"), link=None
    )
    assert n is not None
    assert n.subject == "Salli: what is waiting, 2026-11"
    assert "Open Salli, or run `salli status`, to see them." in n.text
    assert "every month" in n.text
    assert n.link is None


def test_the_id_is_stable_for_the_person_and_period_only():
    first = build_digest(
        "u1", _items(), period="2026-W42", cadence="weekly", today=TODAY, link=LINK
    )
    fewer = build_digest(
        "u1", _items()[:1], period="2026-W42", cadence="weekly", today=d("2026-10-14"), link=LINK
    )
    assert first is not None and fewer is not None
    assert first.id == fewer.id == notification_id("u1", "digest", "2026-W42")
    assert notification_id("u1", "digest", "2026-W43") != first.id
    assert notification_id("u2", "digest", "2026-W42") != first.id
    assert len(first.id) == 64


def test_the_hash_covers_the_message_and_is_what_the_log_keeps():
    n = build_digest("u1", _items(), period="2026-W42", cadence="weekly", today=TODAY, link=LINK)
    again = build_digest(
        "u1", _items(), period="2026-W42", cadence="weekly", today=TODAY, link=LINK
    )
    other = build_digest(
        "u1", _items(), period="2026-W42", cadence="weekly", today=TODAY, link=None
    )
    assert n is not None and again is not None and other is not None
    assert message_hash(n) == message_hash(again)
    assert message_hash(n) != message_hash(other)
    assert message_hash(n).startswith("sha256:")
    assert item_record(n.items[0]) == {
        "kind": "decision_review_due",
        "count": 1,
        "date": "2026-10-05",
    }


# ── The "never" list, over every message the builder can make ──────────────


def _every_message() -> list[Notification]:
    """Every combination of item kinds, each at a count of one and of many,
    weekly and monthly, with a link and without."""
    messages: list[Notification] = []
    for size in range(1, len(ITEM_KINDS) + 1):
        for kinds in itertools.combinations(ITEM_KINDS, size):
            for count in (1, 7):
                items = [
                    NotificationItem(
                        k,
                        item_title(
                            k, 1 if k == "cash_below_zero_ahead" else count, d("2026-10-05")
                        ),
                        count,
                        "2026-10-05",
                    )
                    for k in kinds
                ]
                for cadence, link in (("weekly", LINK), ("monthly", None)):
                    n = build_digest(
                        "u1",
                        items,
                        period="2026-W42" if cadence == "weekly" else "2026-10",
                        cadence=cadence,
                        today=TODAY,
                        link=link,
                    )
                    assert n is not None
                    messages.append(n)
    return messages


def test_no_message_ranks_presses_counts_down_or_exclaims():
    messages = _every_message()
    assert len(messages) == (2**5 - 1) * 2 * 2
    for n in messages:
        assert_never_urges(view(n))


def test_every_title_has_a_date_and_never_a_number_of_days():
    for kind in ITEM_KINDS:
        for count in (1, 2, 30):
            title = item_title(kind, count, d("2026-12-31"))
            assert "2026-12-31" in title
            assert_never_urges({"title": title})


def test_the_guard_catches_what_it_is_for():
    for pressing in (
        "Only 3 days left to file",
        "Don't miss your review",
        "You are on a 4 week streak",
        "Act fast: cash runs out",
        "Urgent: review now",
        "Your cash goes below zero!",
        "The best time to review",
    ):
        with pytest.raises(AssertionError):
            assert_never_urges({"text": pressing})
