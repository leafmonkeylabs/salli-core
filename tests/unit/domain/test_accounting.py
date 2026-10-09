"""Unit tests for the double-entry accounting domain models and ledger logic."""

from decimal import Decimal

import pytest

from salli.domain.accounting.ledger import (
    account_balance,
    account_running_balance,
    assert_trial_balance,
    build_reversing_entry,
    income_for_period,
    net_worth,
    trial_balance,
)
from salli.domain.accounting.models import Direction, JournalEntry, Posting, StoredJournalEntry

# ── helpers ────────────────────────────────────────────────────────────────────


def make_stored(entry: JournalEntry, id: str = "e1", user_id: str = "u1") -> StoredJournalEntry:
    return StoredJournalEntry(id=id, user_id=user_id, **entry.model_dump())


def salary_entry() -> JournalEntry:
    return JournalEntry(
        entry_date="2025-05-01",
        description="Salary received",
        source="manual",
        postings=[
            Posting(
                account_id="bank",
                direction=Direction.DEBIT,
                amount=Decimal("300000"),
                currency="LKR",
            ),
            Posting(
                account_id="salary_income",
                direction=Direction.CREDIT,
                amount=Decimal("300000"),
                currency="LKR",
            ),
        ],
    )


# ── JournalEntry validation ────────────────────────────────────────────────────


def test_balanced_entry_accepted():
    entry = salary_entry()
    assert len(entry.postings) == 2


def test_unbalanced_entry_rejected():
    with pytest.raises(ValueError, match="unbalanced"):
        JournalEntry(
            entry_date="2025-05-01",
            description="Bad entry",
            source="manual",
            postings=[
                Posting(
                    account_id="bank",
                    direction=Direction.DEBIT,
                    amount=Decimal("300000"),
                    currency="LKR",
                ),
                Posting(
                    account_id="salary_income",
                    direction=Direction.CREDIT,
                    amount=Decimal("250000"),  # wrong — doesn't balance
                    currency="LKR",
                ),
            ],
        )


def test_entry_requires_at_least_two_postings():
    with pytest.raises(ValueError):
        JournalEntry(
            entry_date="2025-05-01",
            description="Single posting",
            source="manual",
            postings=[
                Posting(
                    account_id="bank",
                    direction=Direction.DEBIT,
                    amount=Decimal("100"),
                    currency="LKR",
                )
            ],
        )


def test_float_amount_rejected():
    with pytest.raises(ValueError, match="float"):
        Posting(
            account_id="bank",
            direction=Direction.DEBIT,
            amount=300000.0,  # type: ignore[arg-type]
            currency="LKR",
        )


def test_multicurrency_entry_balances_in_base():
    """Foreign remittance: USD 1000 at rate 300 → LKR 300,000."""
    entry = JournalEntry(
        entry_date="2025-06-01",
        description="Freelance remittance",
        source="manual",
        postings=[
            Posting(
                account_id="bank_lkr",
                direction=Direction.DEBIT,
                amount=Decimal("300000"),
                currency="LKR",
                fx_rate=Decimal(1),
            ),
            Posting(
                account_id="foreign_service_income",
                direction=Direction.CREDIT,
                amount=Decimal("1000"),
                currency="USD",
                fx_rate=Decimal("300"),
                fx_rate_source="CBSL",
            ),
        ],
    )
    assert entry is not None


# ── Ledger functions ───────────────────────────────────────────────────────────


def test_account_balance():
    entry = make_stored(salary_entry())
    bank_postings = [p for p in entry.postings if p.account_id == "bank"]
    assert account_balance(bank_postings) == Decimal("300000")


def test_trial_balance_nets_to_zero():
    entries = [make_stored(salary_entry())]
    balances = trial_balance(entries)
    assert sum(balances.values()) == Decimal(0)


def test_assert_trial_balance_passes():
    assert_trial_balance([make_stored(salary_entry())])


def test_reversing_entry_restores_balance():
    original = make_stored(salary_entry())
    reversal = build_reversing_entry(original)
    all_entries = [original, make_stored(reversal, id="e2")]
    assert_trial_balance(all_entries)

    # Both accounts should net to zero after the reversal.
    balances = trial_balance(all_entries)
    for balance in balances.values():
        assert balance == Decimal(0)


def test_reversing_entry_flips_directions():
    original = make_stored(salary_entry())
    reversal = build_reversing_entry(original)
    for orig_p, rev_p in zip(original.postings, reversal.postings, strict=True):
        assert orig_p.direction != rev_p.direction
        assert orig_p.account_id == rev_p.account_id
        assert orig_p.amount == rev_p.amount


def test_income_for_period():
    entries = [make_stored(salary_entry())]
    net = income_for_period(entries, {"salary_income"}, set())
    assert net == Decimal("300000")


def test_net_worth():
    entries = [make_stored(salary_entry())]
    # bank is an asset (debit-normal, positive balance)
    # salary_income is income (credit-normal, negative in trial balance)
    worth = net_worth(entries, {"bank"}, set())
    assert worth == Decimal("300000")


def test_account_running_balance_accumulates_chronologically():
    e1 = make_stored(salary_entry(), id="e1")  # bank +300000
    rent_entry = JournalEntry(
        entry_date="2025-05-05",
        description="Rent paid",
        source="manual",
        postings=[
            Posting(
                account_id="rent_expense",
                direction=Direction.DEBIT,
                amount=Decimal("50000"),
                currency="LKR",
            ),
            Posting(
                account_id="bank",
                direction=Direction.CREDIT,
                amount=Decimal("50000"),
                currency="LKR",
            ),
        ],
    )
    e2 = make_stored(rent_entry, id="e2")

    history = account_running_balance([e1, e2], "bank")
    assert len(history) == 2
    assert history[0][0].id == "e1"
    assert history[0][1] == Decimal("300000")
    assert history[1][0].id == "e2"
    assert history[1][1] == Decimal("250000")


def test_account_running_balance_skips_entries_not_touching_the_account():
    e1 = make_stored(salary_entry(), id="e1")
    history = account_running_balance([e1], "rent_expense")
    assert history == []


def test_account_running_balance_final_value_matches_account_balance():
    e1 = make_stored(salary_entry(), id="e1")
    history = account_running_balance([e1], "bank")
    bank_postings = [p for p in e1.postings if p.account_id == "bank"]
    assert history[-1][1] == account_balance(bank_postings)
