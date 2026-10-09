"""
An entry's provenance quotes the statement line it was posted from.

A statement need not be in the base currency, so the line says which currency
its amount is in, and the amount has exactly that currency's decimals.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.domain.accounting.models import Direction, Posting, StoredJournalEntry
from salli.domain.parsing.models import ParsedTransaction, RawRow
from tests.fakes import FakeProfiles


class _Ledger:
    def __init__(self, entry: StoredJournalEntry) -> None:
        self.entry = entry

    async def get_entry_by_id(self, user_id: str, entry_id: str) -> StoredJournalEntry | None:
        return self.entry if entry_id == self.entry.id else None

    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list:
        return []


class _Statements:
    def __init__(self, txn: ParsedTransaction) -> None:
        self.txn = txn

    async def get_by_ids(self, user_id: str, ids: list[str]) -> list[ParsedTransaction]:
        return [self.txn] if self.txn.id in ids else []

    async def get_statement(self, user_id: str, statement_id: str) -> None:
        return None


class _Subscriptions:
    async def list(self, user_id: str, active_only: bool = True) -> list:
        return []


class _UoW:
    def __init__(self, entry: StoredJournalEntry, txn: ParsedTransaction) -> None:
        self.ledger = _Ledger(entry)
        self.statements = _Statements(txn)
        self.recurring_subscriptions = _Subscriptions()
        self.user_profiles = FakeProfiles("LKR")

    async def __aenter__(self) -> _UoW:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


def _posting(account_id: str, direction: Direction, amount: str, currency: str) -> Posting:
    return Posting(
        account_id=account_id,
        direction=direction,
        amount=Decimal(amount),
        currency=currency,
        fx_rate=Decimal("2"),
    )


@pytest.mark.parametrize(
    ("currency", "raw_amount", "quoted"),
    [("USD", "12.5", "12.50"), ("JPY", "1500", "1500"), ("KWD", "1.5", "1.500")],
)
async def test_a_statement_line_names_its_currency(currency, raw_amount, quoted):
    txn = ParsedTransaction(
        raw=RawRow(
            date="2025-04-05",
            description="UBER TRIP",
            amount=Decimal(raw_amount),
            credit_flag=False,
            currency=currency,
            bank_ref="REF1",
        ),
        debit_account_id="travel",
        credit_account_id="card",
        id="txn-1",
    )
    entry = StoredJournalEntry(
        id="e1",
        user_id="u",
        entry_date="2025-04-05",
        description="UBER TRIP",
        source="statement",
        external_ref="txn-1",
        postings=[
            _posting("travel", Direction.DEBIT, raw_amount, currency),
            _posting("card", Direction.CREDIT, raw_amount, currency),
        ],
    )
    svc = LedgerService(lambda: _UoW(entry, txn))

    provenance = await svc.get_entry_provenance("u", "e1")

    assert provenance is not None
    assert provenance["statement"]["raw_amount"] == quoted
    assert provenance["statement"]["currency"] == currency
    assert provenance["receipt"] is None
