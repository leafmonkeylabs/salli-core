"""
Golden tests for the recurring-subscription matching engine — hand-computed scenarios.
"""

from decimal import Decimal

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.subscription.engine import compute_report, find_matches
from salli.domain.subscription.models import Subscription

_CASH = Account(id="cash", user_id="u1", code="1100", name="Cash", type="asset", currency="LKR")
_NETFLIX = Account(
    id="netflix", user_id="u1", code="5200", name="Netflix", type="expense", currency="LKR"
)
_OTHER_EXPENSE = Account(
    id="other", user_id="u1", code="5300", name="Other", type="expense", currency="LKR"
)


def _charge(
    entry_id: str, entry_date: str, amount: str, account_id: str = "netflix"
) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=entry_id,
        user_id="u1",
        entry_date=entry_date,
        description="charge",
        source="statement",
        postings=[
            Posting(
                account_id=account_id,
                direction=Direction.DEBIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
            Posting(
                account_id="cash",
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
        ],
    )


# ── Case 1: two on-time, on-amount charges — no alerts ──────────────────────────


def test_regular_charges_produce_no_alerts():
    sub = Subscription(
        name="Netflix",
        amount=Decimal("1500"),
        frequency="monthly",
        next_due_date="2026-05-15",
        account_id="netflix",
    )
    entries = [_charge("e1", "2026-05-15", "1500"), _charge("e2", "2026-06-15", "1500")]
    report = compute_report(sub, entries, [_CASH, _NETFLIX], today="2026-06-20")

    assert len(report.matches) == 2
    assert report.alerts == []


# ── Case 2: missed charge — no match for well past the frequency + grace window ─


def test_missed_charge_after_grace_period():
    sub = Subscription(
        name="Netflix",
        amount=Decimal("1500"),
        frequency="monthly",
        next_due_date="2026-05-15",
        account_id="netflix",
    )
    entries = [_charge("e1", "2026-05-15", "1500")]
    # 62 days since the last (and only) match — well past 30 + 5 grace days
    report = compute_report(sub, entries, [_CASH, _NETFLIX], today="2026-07-16")

    assert len(report.alerts) == 1
    assert report.alerts[0].kind == "missed_charge"


# ── Case 3: never charged at all — missed charge measured from next_due_date ───


def test_never_charged_measures_from_due_date():
    sub = Subscription(
        name="Netflix",
        amount=Decimal("1500"),
        frequency="monthly",
        next_due_date="2026-05-15",
        account_id="netflix",
    )
    report = compute_report(sub, [], [_CASH, _NETFLIX], today="2026-07-16")

    assert report.matches == []
    assert len(report.alerts) == 1
    assert report.alerts[0].kind == "missed_charge"


# ── Case 4: price change — account-linked match with a drifted amount ──────────


def test_price_change_detected_when_account_linked():
    sub = Subscription(
        name="Netflix",
        amount=Decimal("1500"),
        frequency="monthly",
        next_due_date="2026-05-15",
        account_id="netflix",
    )
    entries = [_charge("e1", "2026-05-15", "1500"), _charge("e2", "2026-06-15", "1800")]
    report = compute_report(sub, entries, [_CASH, _NETFLIX], today="2026-06-20")

    assert len(report.matches) == 2  # the account link matches regardless of amount
    price_alerts = [a for a in report.alerts if a.kind == "price_change"]
    assert len(price_alerts) == 1
    assert price_alerts[0].expected_amount == Decimal("1500")
    assert price_alerts[0].actual_amount == Decimal("1800")


# ── Case 5: without an account link, amount-tolerance matching can't see drift ──


def test_price_change_not_detectable_without_account_link():
    sub = Subscription(
        name="Netflix", amount=Decimal("1500"), frequency="monthly", next_due_date="2026-05-15"
    )
    entries = [_charge("e1", "2026-05-15", "1500"), _charge("e2", "2026-06-15", "1800")]
    report = compute_report(sub, entries, [_CASH, _NETFLIX], today="2026-06-20")

    # the 1800 charge falls outside the default 5% tolerance of 1500, so it's simply
    # not matched at all — no price_change alert, because there's nothing to compare
    assert len(report.matches) == 1
    assert not any(a.kind == "price_change" for a in report.alerts)


# ── Case 6: account link restricts matching to that account only ───────────────


def test_account_link_ignores_other_accounts_even_at_the_right_amount():
    sub = Subscription(
        name="Netflix",
        amount=Decimal("1500"),
        frequency="monthly",
        next_due_date="2026-05-15",
        account_id="netflix",
    )
    entries = [_charge("e1", "2026-05-15", "1500", account_id="other")]
    matches = find_matches(sub, entries, [_CASH, _NETFLIX, _OTHER_EXPENSE])
    assert matches == []
