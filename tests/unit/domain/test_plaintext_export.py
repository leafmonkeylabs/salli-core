"""
The ledger as Beancount and hledger. The Beancount output is checked by
Beancount itself: it must load without a single error, and every account must
hold exactly what it holds in Salli.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from beancount import loader
from beancount.core.data import Transaction

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.export.plaintext import account_names, beancount, hledger


def _account(id_, code, name, type_, currency="LKR", parent=None, active=True) -> Account:
    return Account(
        id=id_,
        user_id="u",
        code=code,
        name=name,
        type=type_,
        currency=currency,
        parent_id=parent,
        is_active=active,
    )


ACCOUNTS = [
    _account("bank", "1200", "Bank Account (LKR)", "asset"),
    _account("savings", "1210", "Savings", "asset", parent="bank"),
    _account("usd", "1300", "Dollar account", "asset", currency="USD"),
    _account("card", "2100", "Credit Card", "liability"),
    _account("equity", "3000", "Opening Equity", "equity"),
    _account("salary", "4100", "Employment Income", "income"),
    _account("food", "5100", "Groceries & Food", "expense"),
    _account("apit", "4110", "APIT Receivable", "asset"),
    _account("old", "5900", "Old Expenses", "expense", active=False),
    _account("dup", "5101", "Groceries & Food", "expense"),  # same name, different code
]


def _entry(id_, date, description, *legs, **kw) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=id_,
        user_id="u",
        entry_date=date,
        description=description,
        source=kw.pop("source", "manual"),
        postings=[
            Posting(
                account_id=account,
                direction=direction,
                amount=Decimal(amount),
                currency=currency,
                fx_rate=Decimal(rate),
                tags=tags,
            )
            for account, direction, amount, currency, rate, tags in legs
        ],
        **kw,
    )


D, C = Direction.DEBIT, Direction.CREDIT
ENTRIES = [
    _entry(
        "e1",
        "2026-09-01",
        "Opening balance",
        ("bank", D, "100000", "LKR", "1", {}),
        ("equity", C, "100000", "LKR", "1", {}),
    ),
    _entry(
        "e2",
        "2026-09-25",
        'Salary "September"\nACME',
        ("bank", D, "250000.50", "LKR", "1", {}),
        ("salary", C, "250000.50", "LKR", "1", {}),
        source="statement",
        external_ref="txn-9",
    ),
    _entry(
        "e3",
        "2026-09-28",
        "Groceries",
        ("food", D, "4500", "LKR", "1", {"category": "groceries", "need": "essential"}),
        ("card", C, "4500", "LKR", "1", {}),
    ),
    _entry(
        "e4",
        "2026-10-01",
        "Remittance",
        ("usd", D, "100", "USD", "302.50", {}),
        ("salary", C, "100", "USD", "302.50", {}),
    ),
    _entry(
        "e5",
        "2026-10-02",
        "To savings",
        ("savings", D, "20000", "LKR", "1", {}),
        ("bank", C, "20000", "LKR", "1", {}),
    ),
    _entry(
        "e6",
        "2026-10-03",
        "Old thing",
        ("old", D, "10", "LKR", "1", {}),
        ("bank", C, "10", "LKR", "1", {}),
    ),
    _entry(
        "e7", "2026-10-04", "Dup", ("dup", D, "5", "LKR", "1", {}), ("bank", C, "5", "LKR", "1", {})
    ),
]


def test_names_are_valid_unique_and_follow_the_hierarchy():
    names = account_names(ACCOUNTS)
    assert names["bank"] == "Assets:BankAccountLKR"
    assert names["savings"] == "Assets:BankAccountLKR:Savings"
    assert names["food"] == "Expenses:GroceriesFood"
    assert names["dup"] == "Expenses:GroceriesFood-5101"
    assert names["apit"] == "Assets:APITReceivable"
    assert len(set(names.values())) == len(names)


def test_beancount_loads_cleanly_and_every_balance_matches():
    text = beancount(ACCOUNTS, ENTRIES, "LKR")
    entries, errors, options = loader.load_string(text)
    assert errors == [], errors
    assert options["operating_currency"] == ["LKR"]

    names = account_names(ACCOUNTS)
    exported: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for entry in entries:
        if isinstance(entry, Transaction):
            for p in entry.postings:
                exported[(p.account, p.units.currency)] += p.units.number
    salli: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for entry in ENTRIES:
        for p in entry.postings:
            signed = p.amount if p.direction == Direction.DEBIT else -p.amount
            salli[(names[p.account_id], p.currency)] += signed
    assert dict(exported) == dict(salli)


def test_beancount_keeps_ids_tags_and_closed_accounts():
    text = beancount(ACCOUNTS, ENTRIES, "LKR")
    entries, _, _ = loader.load_string(text)
    transactions = {e.meta["salli-id"]: e for e in entries if isinstance(e, Transaction)}
    assert set(transactions) == {e.id for e in ENTRIES}
    salary = transactions["e2"]
    assert salary.narration == 'Salary "September" ACME'
    assert salary.meta["external-ref"] == "txn-9"
    groceries = transactions["e3"].postings[0]
    assert (groceries.meta["category"], groceries.meta["need"]) == ("groceries", "essential")
    remittance = transactions["e4"].postings[0]
    assert (remittance.price.number, remittance.price.currency) == (Decimal("302.50"), "LKR")
    assert 'salli-status: "inactive"' in text


def test_an_entry_on_a_forgotten_account_still_loads():
    orphan = _entry(
        "e9",
        "2026-10-05",
        "Orphan",
        ("gone", D, "1", "LKR", "1", {}),
        ("bank", C, "1", "LKR", "1", {}),
    )
    _, errors, _ = loader.load_string(beancount(ACCOUNTS, [*ENTRIES, orphan], "LKR"))
    assert errors == []


def test_hledger_journal():
    text = hledger(ACCOUNTS, ENTRIES, "LKR")
    assert "account Assets:BankAccountLKR  ; type:A" in text
    assert "account Expenses:Old Expenses" not in text  # names never contain spaces
    assert "account Expenses:OldExpenses  ; type:X, salli-status:inactive" in text
    assert '2026-09-25 * Salary "September" ACME  ; salli-id:e2, source:statement' in text
    assert "    Assets:Dollaraccount" not in text
    assert "    Assets:DollarAccount  100.00 USD @ 302.5 LKR" in text
    assert "    Expenses:GroceriesFood  4500.00 LKR  ; category:groceries, need:essential" in text
    assert "    Liabilities:CreditCard  -4500.00 LKR" in text
