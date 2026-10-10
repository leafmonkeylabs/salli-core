"""
The ledger as plain-text accounting: Beancount and hledger journals.

Plain-text accounting is the lingua franca of people who keep their own books.
Exporting to it means a user can leave Salli with their entire ledger, or keep
one foot in Fava or hledger, at any time. Every entry goes out with its id, so
a round trip can be checked.

Both formats get the same account names: the five Beancount roots (Assets,
Liabilities, Equity, Income, Expenses), then the account's parents and its own
name as CamelCase components, so `Bank Account` under `Savings` becomes
`Assets:Savings:BankAccount`. A posting in a currency other than the base
carries its exchange rate as a price (`100.00 USD @ 302.50 LKR`), so the entry
balances in the base currency exactly as it does in Salli. Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from decimal import Decimal

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.currency import quantize

_ROOTS = {
    "asset": "Assets",
    "liability": "Liabilities",
    "equity": "Equity",
    "income": "Income",
    "expense": "Expenses",
}
# hledger's account types, so its reports classify accounts without guessing.
_HLEDGER_TYPES = {"asset": "A", "liability": "L", "equity": "E", "income": "R", "expense": "X"}


def _component(name: str) -> str:
    """`Donations & Qualifying Payments` → `DonationsQualifyingPayments`. Each
    word keeps its own capitals (VAT stays VAT); only ASCII letters and
    digits survive, which every Beancount version accepts."""
    words = re.findall(r"[A-Za-z0-9]+", name)
    joined = "".join(w[0].upper() + w[1:] for w in words)
    return joined or "Account"


def account_names(accounts: Sequence[Account]) -> dict[str, str]:
    """account id → its full plain-text name, unique within the ledger."""
    by_id = {a.id: a for a in accounts}

    def path(account: Account, seen: frozenset[str] = frozenset()) -> list[str]:
        parent = by_id.get(account.parent_id or "")
        if parent is None or parent.id in seen or parent.type != account.type:
            return [_component(account.name)]
        return [*path(parent, seen | {account.id}), _component(account.name)]

    names: dict[str, str] = {}
    taken: set[str] = set()
    for account in sorted(accounts, key=lambda a: (a.code, a.id)):
        name = ":".join([_ROOTS[account.type], *path(account)])
        if name in taken:
            name = f"{name}-{_component(account.code)}"
        taken.add(name)
        names[account.id] = name
    return names


def _string(text: str) -> str:
    return '"' + " ".join(text.split()).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _amount(value: Decimal, currency: str) -> str:
    return f"{quantize(value, currency, strict=False)} {currency}"


def _rate(rate: Decimal) -> str:
    # The exact rate the entry recorded, without trailing zeros, and never in
    # exponent notation (`3E+2` is not a number either tool reads).
    return format(rate.normalize(), "f")


def _signed(posting: Posting) -> Decimal:
    return posting.amount if posting.direction == Direction.DEBIT else -posting.amount


def _first_date(entries: Iterable[StoredJournalEntry]) -> str:
    return min((e.entry_date for e in entries), default="1970-01-01")


def beancount(
    accounts: Sequence[Account], entries: Sequence[StoredJournalEntry], base_currency: str
) -> str:
    """The ledger as a Beancount file that `bean-check` accepts."""
    names = account_names(accounts)
    opened = _first_date(entries)
    lines = [
        "; Exported from Salli. Every transaction carries its Salli id (salli-id).",
        f'option "operating_currency" "{base_currency}"',
        "",
    ]
    for account in sorted(accounts, key=lambda a: names[a.id]):
        lines.append(f"{opened} open {names[account.id]}")
        if not account.is_active:
            lines.append('  salli-status: "inactive"')
    for entry in sorted(entries, key=lambda e: (e.entry_date, e.id)):
        lines += ["", f"{entry.entry_date} * {_string(entry.description)}"]
        lines.append(f"  salli-id: {_string(entry.id)}")
        lines.append(f"  source: {_string(entry.source)}")
        if entry.external_ref:
            lines.append(f"  external-ref: {_string(entry.external_ref)}")
        for posting in entry.postings:
            name = names.get(posting.account_id, f"Equity:Unknown:{_component(posting.account_id)}")
            line = f"  {name}  {_amount(_signed(posting), posting.currency)}"
            if posting.currency != base_currency:
                line += f" @ {_rate(posting.fx_rate)} {base_currency}"
            lines.append(line)
            for axis, slug in sorted(posting.tags.items()):
                lines.append(f"    {axis}: {_string(slug)}")
    # An entry posted to an account that no longer exists still has to parse.
    unknown = sorted(
        {
            f"Equity:Unknown:{_component(p.account_id)}"
            for e in entries
            for p in e.postings
            if p.account_id not in names
        }
    )
    if unknown:
        lines[3:3] = [f"{opened} open {name}" for name in unknown]
    return "\n".join(lines) + "\n"


def hledger(
    accounts: Sequence[Account], entries: Sequence[StoredJournalEntry], base_currency: str
) -> str:
    """The ledger as an hledger journal (also readable by Ledger)."""
    names = account_names(accounts)
    lines = ["; Exported from Salli. Every transaction carries its Salli id (salli-id).", ""]
    for account in sorted(accounts, key=lambda a: names[a.id]):
        note = "" if account.is_active else ", salli-status:inactive"
        lines.append(f"account {names[account.id]}  ; type:{_HLEDGER_TYPES[account.type]}{note}")
    for entry in sorted(entries, key=lambda e: (e.entry_date, e.id)):
        description = " ".join(entry.description.split()).replace(";", ",")
        lines += [
            "",
            f"{entry.entry_date} * {description}  ; salli-id:{entry.id}, source:{entry.source}",
        ]
        for posting in entry.postings:
            name = names.get(posting.account_id, f"Equity:Unknown:{_component(posting.account_id)}")
            line = f"    {name}  {_amount(_signed(posting), posting.currency)}"
            if posting.currency != base_currency:
                line += f" @ {_rate(posting.fx_rate)} {base_currency}"
            tags = ", ".join(f"{axis}:{slug}" for axis, slug in sorted(posting.tags.items()))
            lines.append(line + (f"  ; {tags}" if tags else ""))
    return "\n".join(lines) + "\n"
