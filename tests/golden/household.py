"""
One fixed household ledger, read by every engine's golden test.

The decision lab's baseline (docs/design/decision-lab.md) reconciles FI,
insights, the cash forecast and debt onto one model of a user's money. Each
engine's golden test reads this same ledger, so a figure that changes as the
definitions are reconciled changes on purpose, with the test saying why.

The household keeps its books in euros, as of Sunday 2026-10-11:

- Books opened 2026-03-31 with opening balances; money in and out from
  2026-04-01. So there are six full months of history (April to September)
  and a partial October.
- Salary 4,000 on the 25th; rent 1,500 on the 1st; groceries and eating out
  on a credit card, paid from checking on the 15th; streaming 12.99 on the
  card on the 8th; a car loan paid on the 5th (300 principal, 50 interest);
  500 to the brokerage and 300 to savings on the 26th.
- Two mistakes, each reversed: a salary booked twice in May, and a grocery
  charge in June that was refunded by reversal.
- A dollar account (2,000 USD opened at 0.90, 500 USD added at 0.95); the
  published rate for the as-of date is 0.86.
- A brokerage account (a name no pattern recognises), a pension fund (a name
  one does), and the flat they live in.
- Two declared debts: the car loan (whose ledger account is 2100) and a
  student loan the ledger knows nothing about.

Amounts are chosen so the hand checks in the tests stay readable.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeFx, FakeUoW

USER = "household"
OTHER = "someone-else"
AS_OF = dt.date(2026, 10, 11)
BASE = "EUR"


def _account(
    id_: str, code: str, name: str, type_: str, currency: str = BASE, **kw: Any
) -> Account:
    return Account(id=id_, user_id=USER, code=code, name=name, type=type_, currency=currency, **kw)  # type: ignore[arg-type]


#: Each asset account says what it holds: the brokerage and the pension fund
#: are investments, the flat is neither cash nor invested.
ACCOUNTS: list[Account] = [
    _account("chk", "1000", "Checking", "asset"),
    _account("sav", "1100", "Savings", "asset"),
    _account("usd", "1200", "Dollar account", "asset", "USD"),
    _account("brk", "1300", "Brokerage", "asset", asset_role="investment"),
    _account("pen", "1400", "Pension fund", "asset", asset_role="investment"),
    _account("flat", "1500", "Flat", "asset", asset_role="other"),
    _account("card", "2000", "Credit card", "liability"),
    _account("loan", "2100", "Car loan", "liability"),
    _account("eq", "3000", "Opening equity", "equity"),
    _account("sal", "4000", "Salary", "income"),
    _account("rent", "5000", "Rent", "expense"),
    _account("food", "5100", "Groceries", "expense"),
    _account("out", "5200", "Eating out", "expense"),
    _account("int", "5300", "Loan interest", "expense"),
    _account("tv", "5400", "Streaming", "expense"),
]

_entries: list[StoredJournalEntry] = []


def _leg(
    account: str,
    direction: Direction,
    amount: str,
    currency: str = BASE,
    fx: str = "1",
    tags: dict[str, str] | None = None,
) -> Posting:
    return Posting(
        account_id=account,
        direction=direction,
        amount=Decimal(amount),
        currency=currency,
        fx_rate=Decimal(fx),
        fx_rate_source=None if fx == "1" else "user",
        tags=tags or {},
    )


def _book(
    day: str,
    description: str,
    postings: list[Posting],
    *,
    source: str = "statement",
    external_ref: str | None = None,
) -> StoredJournalEntry:
    entry = StoredJournalEntry(
        id=f"e{len(_entries) + 1:03d}",
        user_id=USER,
        entry_date=day,
        description=description,
        source=source,  # type: ignore[arg-type]
        external_ref=external_ref,
        postings=postings,
    )
    _entries.append(entry)
    return entry


def _move(day: str, description: str, debit: str, credit: str, amount: str, **kw: Any):
    tags = kw.pop("tags", None)
    return _book(
        day,
        description,
        [_leg(debit, Direction.DEBIT, amount, tags=tags), _leg(credit, Direction.CREDIT, amount)],
        **kw,
    )


def _reverse(original: StoredJournalEntry) -> StoredJournalEntry:
    flipped = [
        _leg(
            p.account_id,
            Direction.CREDIT if p.direction == Direction.DEBIT else Direction.DEBIT,
            str(p.amount),
            p.currency,
            str(p.fx_rate),
            dict(p.tags),
        )
        for p in original.postings
    ]
    return _book(
        original.entry_date,
        f"REVERSAL: {original.description}",
        flipped,
        source="system",
        external_ref=original.id,
    )


ESSENTIAL = {"need": "essential"}
WANT = {"need": "discretionary"}

# ── Opening balances, 2026-03-31 ──────────────────────────────────────────────
for account, amount in (
    ("chk", "3200"),
    ("sav", "6000"),
    ("brk", "10000"),
    ("pen", "25000"),
    ("flat", "300000"),
):
    _move("2026-03-31", "Opening balance", account, "eq", amount, source="manual")
_book(
    "2026-03-31",
    "Opening balance",
    [
        _leg("usd", Direction.DEBIT, "2000", "USD", "0.90"),
        _leg("eq", Direction.CREDIT, "1800"),
    ],
    source="manual",
)
_move("2026-03-31", "Opening balance", "eq", "loan", "12000", source="manual")

# ── Six full months, April to September, and October so far ──────────────────
#
# Card spending in month m is paid from checking on the 15th of month m + 1.
_GROCERIES = {
    4: ("182.40", "211.60"),
    5: ("176.10", "224.30"),
    6: ("190.00", "205.50"),
    7: ("168.80", "231.20"),
    8: ("185.25", "214.75"),
    9: ("179.90", "220.10"),
    10: ("188.00",),
}
_EATING_OUT = {4: "64.00", 5: "88.50", 6: "71.20", 7: "95.00", 8: "58.30", 9: "77.70"}

card_owed: dict[int, Decimal] = {}
for month in range(4, 11):
    m = f"2026-{month:02d}"
    owed = Decimal(0)
    _move(f"{m}-01", "CITY LETTINGS RENT", "rent", "chk", "1500", tags=ESSENTIAL)
    _book(
        f"{m}-05",
        "AUTOFIN CAR LOAN",
        [
            _leg("loan", Direction.DEBIT, "300"),
            _leg("int", Direction.DEBIT, "50"),
            _leg("chk", Direction.CREDIT, "350"),
        ],
    )
    _move(f"{m}-08", "STREAMFLIX", "tv", "card", "12.99", tags=WANT)
    owed += Decimal("12.99")
    first, *second = _GROCERIES[month]
    _move(f"{m}-09", "FRESHMART", "food", "card", first, tags=ESSENTIAL)
    owed += Decimal(first)
    if month == 10:
        # The as-of date is the 11th: nothing later in October has happened
        # (September's card bill is due on the 15th).
        break
    if month in card_owed:
        _move(f"{m}-15", "CARD PAYMENT THANK YOU", "card", "chk", str(card_owed[month]))
    for amount in second:
        _move(f"{m}-21", "FRESHMART", "food", "card", amount, tags=ESSENTIAL)
        owed += Decimal(amount)
    _move(f"{m}-18", "BISTRO NOVO", "out", "card", _EATING_OUT[month], tags=WANT)
    owed += Decimal(_EATING_OUT[month])
    _move(f"{m}-25", "ACME LTD SALARY", "chk", "sal", "4000")
    _move(f"{m}-26", "TO BROKERAGE", "brk", "chk", "500")
    _move(f"{m}-26", "TO SAVINGS", "sav", "chk", "300")
    card_owed[month + 1] = owed

# The mistakes, each reversed by the reversing entry Salli itself books.
_reverse(_move("2026-05-25", "ACME LTD SALARY", "chk", "sal", "4000"))
_reverse(_move("2026-06-12", "FRESHMART", "food", "card", "150.00", tags=ESSENTIAL))

# 500 USD more, bought from checking at 0.95.
_book(
    "2026-07-15",
    "TO DOLLAR ACCOUNT",
    [
        _leg("usd", Direction.DEBIT, "500", "USD", "0.95"),
        _leg("chk", Direction.CREDIT, "475"),
    ],
)

ENTRIES: list[StoredJournalEntry] = sorted(_entries, key=lambda e: (e.entry_date, e.id))

#: The two declared debts, as the debts repository keeps them (minor units).
#: The car loan is linked to the ledger account that holds it.
DEBTS: list[dict[str, Any]] = [
    {
        "id": "debt-car",
        "name": "Car loan",
        "principal_minor": 1020000,
        "apr": "0.0590",
        "minimum_payment_minor": 35000,
        "account_id": "loan",
    },
    {
        "id": "debt-student",
        "name": "Student loan",
        "principal_minor": 800000,
        "apr": "0.0450",
        "minimum_payment_minor": 12000,
        "account_id": None,
    },
]

#: The published rate for the as-of date, a Sunday: the Friday's.
FX_RATES = {("USD", BASE, AS_OF.isoformat()): (Decimal("0.86"), "ecb", "2026-10-09")}


def fx() -> FakeFx:
    return FakeFx(FX_RATES)


def uow(**profile: Any) -> FakeUoW:
    """A unit of work over the household's books (and nobody else's)."""
    unit = FakeUoW(BASE)
    unit.ledger.accounts = list(ACCOUNTS)
    unit.ledger.entries = list(ENTRIES)
    for debt in DEBTS:
        unit.debts.rows[debt["id"]] = {
            **debt,
            "user_id": USER,
            "is_active": True,
            "created_at": "2026-04-01T00:00:00+00:00",
            "updated_at": "2026-04-01T00:00:00+00:00",
        }
    if profile:
        unit.user_profiles.rows[USER] = dict(profile)
    return unit
