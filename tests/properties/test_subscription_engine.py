"""
Property-based tests for the recurring-subscription matching engine using Hypothesis.
"""

from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.subscription.engine import compute_report, find_matches
from salli.domain.subscription.models import Frequency, Subscription

_CASH = Account(id="cash", user_id="u1", code="1100", name="Cash", type="asset")
_SUB_ACCOUNT = Account(id="sub_acc", user_id="u1", code="5200", name="Subscription", type="expense")
_ACCOUNTS = [_CASH, _SUB_ACCOUNT]

lkr_amount = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("100000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
frequency = st.sampled_from(["weekly", "monthly", "quarterly", "yearly"])


@st.composite
def charge_entry(draw: Any, entry_id: str) -> StoredJournalEntry:
    amount = draw(lkr_amount)
    day = draw(st.integers(min_value=1, max_value=28))
    month = draw(st.integers(min_value=1, max_value=12))
    entry_date = f"2026-{month:02d}-{day:02d}"
    return StoredJournalEntry(
        id=entry_id,
        user_id="u1",
        entry_date=entry_date,
        description="charge",
        source="statement",
        postings=[
            Posting(account_id="sub_acc", direction=Direction.DEBIT, amount=amount, currency="LKR"),
            Posting(account_id="cash", direction=Direction.CREDIT, amount=amount, currency="LKR"),
        ],
    )


@given(
    amount=lkr_amount,
    freq=frequency,
    entries=st.lists(charge_entry("e"), min_size=0, max_size=10),
)
@settings(max_examples=100)
def test_matches_are_chronologically_sorted(
    amount: Decimal, freq: Frequency, entries: list[StoredJournalEntry]
):
    sub = Subscription(
        name="Sub", amount=amount, frequency=freq, next_due_date="2026-01-01", account_id="sub_acc"
    )
    matches = find_matches(sub, entries, _ACCOUNTS)
    dates = [m.entry_date for m in matches]
    assert dates == sorted(dates)


@given(
    amount=lkr_amount,
    freq=frequency,
    entries=st.lists(charge_entry("e"), min_size=0, max_size=10),
)
@settings(max_examples=100)
def test_account_linked_subscription_matches_every_debit_to_that_account(
    amount: Decimal, freq: Frequency, entries: list[StoredJournalEntry]
):
    sub = Subscription(
        name="Sub", amount=amount, frequency=freq, next_due_date="2026-01-01", account_id="sub_acc"
    )
    matches = find_matches(sub, entries, _ACCOUNTS)
    # every entry touches sub_acc by construction, so every entry must produce a match
    assert len(matches) == len(entries)


@given(
    amount=lkr_amount,
    freq=frequency,
    entries=st.lists(charge_entry("e"), min_size=1, max_size=10),
    today_offset=st.integers(min_value=0, max_value=3650),
)
@settings(max_examples=100)
def test_alerts_are_only_missed_charge_or_price_change(
    amount: Decimal, freq: Frequency, entries: list[StoredJournalEntry], today_offset: int
):
    from datetime import date, timedelta

    sub = Subscription(
        name="Sub", amount=amount, frequency=freq, next_due_date="2026-01-01", account_id="sub_acc"
    )
    today = (date(2026, 1, 1) + timedelta(days=today_offset)).isoformat()
    report = compute_report(sub, entries, _ACCOUNTS, today=today)
    for alert in report.alerts:
        assert alert.kind in ("missed_charge", "price_change")


@given(amount=lkr_amount, freq=frequency)
@settings(max_examples=50)
def test_no_entries_and_due_date_in_future_produces_no_missed_charge_alert(
    amount: Decimal, freq: Frequency
):
    sub = Subscription(
        name="Sub", amount=amount, frequency=freq, next_due_date="2026-06-01", account_id="sub_acc"
    )
    report = compute_report(sub, [], _ACCOUNTS, today="2026-06-01")
    assert report.alerts == []
