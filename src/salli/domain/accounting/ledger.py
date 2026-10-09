"""
Pure ledger logic: balance queries, trial balance, and reversing-entry construction.
No I/O — operates on in-memory domain models only.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from salli.domain.accounting.models import (
    AccountType,
    Direction,
    JournalEntry,
    Posting,
    StoredJournalEntry,
)


def account_balance(postings: list[Posting]) -> Decimal:
    """Signed sum of postings (LKR base amounts)."""
    return sum((p.base_signed for p in postings), Decimal(0))


def trial_balance(entries: list[StoredJournalEntry]) -> dict[str, Decimal]:
    """
    Return {account_id: signed_balance} for all accounts in the given entries.
    The sum of all values must equal zero — this is the trial balance invariant.
    """
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for entry in entries:
        for posting in entry.postings:
            balances[posting.account_id] += posting.base_signed
    return dict(balances)


def assert_trial_balance(entries: list[StoredJournalEntry]) -> None:
    """Raise if the trial balance does not net to zero."""
    total = sum(trial_balance(entries).values(), Decimal(0))
    if total != Decimal(0):
        raise AssertionError(f"Trial balance is out of balance: {total}")


def build_reversing_entry(original: StoredJournalEntry) -> JournalEntry:
    """
    Construct the reversing entry for a posted journal entry.
    Flips the direction of every posting; does not persist.
    """
    return JournalEntry(
        entry_date=original.entry_date,
        description=f"REVERSAL: {original.description}",
        source="system",
        external_ref=original.id,
        postings=[
            Posting(
                account_id=p.account_id,
                direction=Direction.CREDIT if p.direction == Direction.DEBIT else Direction.DEBIT,
                amount=p.amount,
                currency=p.currency,
                fx_rate=p.fx_rate,
                fx_rate_source=p.fx_rate_source,
            )
            for p in original.postings
        ],
    )


# ── derived report helpers ─────────────────────────────────────────────────────


def income_for_period(
    entries: list[StoredJournalEntry],
    income_account_ids: set[str],
    expense_account_ids: set[str],
) -> Decimal:
    """Net income = sum of income credits − sum of expense debits (both positive)."""
    income = Decimal(0)
    expenses = Decimal(0)
    for entry in entries:
        for p in entry.postings:
            if p.account_id in income_account_ids:
                # income accounts increase with a credit (direction = -1)
                income += -p.base_signed
            elif p.account_id in expense_account_ids:
                # expense accounts increase with a debit (direction = +1)
                expenses += p.base_signed
    return income - expenses


def net_worth(
    entries: list[StoredJournalEntry],
    asset_account_ids: set[str],
    liability_account_ids: set[str],
) -> Decimal:
    """Assets − Liabilities."""
    balances = trial_balance(entries)
    assets = sum((balances.get(aid, Decimal(0)) for aid in asset_account_ids), Decimal(0))
    liabilities = sum((balances.get(lid, Decimal(0)) for lid in liability_account_ids), Decimal(0))
    # Assets have debit-normal balances (+), liabilities have credit-normal (-).
    return assets + liabilities  # liabilities are negative, so addition subtracts them


def account_running_balance(
    entries: list[StoredJournalEntry], account_id: str
) -> list[tuple[StoredJournalEntry, Decimal]]:
    """
    Chronological running balance for a single account. `entries` is expected to
    already be sorted chronologically (as returned by the repository); each
    result pairs an entry that touched this account with the cumulative balance
    immediately after it. Entries with no posting to this account are skipped.
    """
    running = Decimal(0)
    results: list[tuple[StoredJournalEntry, Decimal]] = []
    for entry in entries:
        contribution = sum(
            (p.base_signed for p in entry.postings if p.account_id == account_id), Decimal(0)
        )
        if contribution == 0:
            continue
        running += contribution
        results.append((entry, running))
    return results


NORMAL_BALANCE: dict[AccountType, Direction] = {
    "asset": Direction.DEBIT,
    "expense": Direction.DEBIT,
    "liability": Direction.CREDIT,
    "equity": Direction.CREDIT,
    "income": Direction.CREDIT,
}
