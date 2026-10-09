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
    """Signed sum of postings, in the base currency."""
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


def owned_and_owed(account_type: AccountType, balance: Decimal) -> tuple[Decimal, Decimal]:
    """(owned, owed) for an account's signed base balance, judged on its own
    sign: what is in debit is owned, what is in credit is owed, so an
    overdrawn bank account is debt, not a smaller asset, and an overpaid card
    is money owned. Accounts other than assets and liabilities are neither.
    The one rule net worth is told by, wherever it is told."""
    if account_type not in ("asset", "liability"):
        return Decimal(0), Decimal(0)
    return (balance, Decimal(0)) if balance >= 0 else (Decimal(0), -balance)


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


def native_signed(posting: Posting, account_currency: str, base_currency: str) -> Decimal | None:
    """A posting's signed amount in its account's own currency, if that is knowable.

    A posting in the account's currency is that amount. A posting in another
    currency to an account kept in the base currency is its base equivalent
    (amount × fx_rate). Anything else — euros posted to a dollar account in a
    rupee ledger — has no rate into the account's currency, so None.
    """
    if posting.currency == account_currency:
        amount = posting.amount
    elif account_currency == base_currency:
        amount = posting.amount * posting.fx_rate
    else:
        return None
    return Decimal(posting.direction.value) * amount


def account_history(
    entries: list[StoredJournalEntry],
    account_id: str,
    account_currency: str,
    base_currency: str,
) -> list[tuple[StoredJournalEntry, Decimal, Decimal | None]]:
    """`account_running_balance`, with the running balance in the account's own
    currency alongside the base one: (entry, base balance, native balance).

    The native balance becomes None from the first posting it cannot be known
    for (see `native_signed`) and stays None, because a running total that has
    silently skipped a posting is worse than none.
    """
    base_running = Decimal(0)
    native_running: Decimal | None = Decimal(0)
    results: list[tuple[StoredJournalEntry, Decimal, Decimal | None]] = []
    for entry in entries:
        touching = [p for p in entry.postings if p.account_id == account_id]
        if not touching:
            continue
        base_contribution = sum((p.base_signed for p in touching), Decimal(0))
        if base_contribution == 0:
            # Same rule as account_running_balance: an entry that nets to
            # nothing on this account is not part of its history.
            continue
        base_running += base_contribution
        if native_running is not None:
            natives = [native_signed(p, account_currency, base_currency) for p in touching]
            if any(n is None for n in natives):
                native_running = None
            else:
                native_running += sum((n for n in natives if n is not None), Decimal(0))
        results.append((entry, base_running, native_running))
    return results


NORMAL_BALANCE: dict[AccountType, Direction] = {
    "asset": Direction.DEBIT,
    "expense": Direction.DEBIT,
    "liability": Direction.CREDIT,
    "equity": Direction.CREDIT,
    "income": Direction.CREDIT,
}
