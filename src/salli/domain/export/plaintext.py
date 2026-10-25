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
carries its exchange rate as a price (`100.00 USD @ 0.92 EUR`), so the entry
balances in the base currency exactly as it does in Salli.

A transaction is flagged `*` when one of its postings has been cleared against
a bank statement, and `!` otherwise; the cleared postings carry `*` themselves.
A completed reconciliation goes out as a balance assertion (Beancount's
`balance`, hledger's `= `) on its closing balance, when the ledger agrees with
it on that day; a reversal names the entry it reverses, and an account its
tax, asset and equity roles. Pure: no I/O.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Collection, Iterable, Iterator, Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Assertion:
    """A completed reconciliation: the account's balance in `currency` at the
    end of `on`, debit-positive."""

    account_id: str
    on: str
    balance: Decimal
    currency: str
    statement_id: str


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


def _flag(entry: StoredJournalEntry, cleared: Collection[str]) -> str:
    return "*" if any(p.id in cleared for p in entry.postings) else "!"


def _roles(account: Account) -> list[tuple[str, str]]:
    roles = [
        ("tax-role", account.tax_role),
        ("asset-role", account.asset_role),
        ("equity-role", account.equity_role),
    ]
    return [(key, value) for key, value in roles if value]


def _held(
    assertions: Sequence[Assertion], entries: Sequence[StoredJournalEntry]
) -> Iterator[tuple[Assertion, bool]]:
    """The assertions the ledger itself agrees with: a statement's balance
    that the ledger doesn't reach on that day (history before the statement
    left out, say) would make the file fail its own check."""
    for a in assertions:
        total = sum(
            (
                _signed(p)
                for e in entries
                if e.entry_date <= a.on
                for p in e.postings
                if p.account_id == a.account_id and p.currency == a.currency
            ),
            Decimal(0),
        )
        yield (
            a,
            quantize(total, a.currency, strict=False)
            == quantize(a.balance, a.currency, strict=False),
        )


def _first_date(entries: Iterable[StoredJournalEntry]) -> str:
    return min((e.entry_date for e in entries), default="1970-01-01")


def beancount(
    accounts: Sequence[Account],
    entries: Sequence[StoredJournalEntry],
    base_currency: str,
    cleared: Collection[str] = (),
    assertions: Sequence[Assertion] = (),
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
        lines += [f"  {key}: {_string(value)}" for key, value in _roles(account)]
    for entry in sorted(entries, key=lambda e: (e.entry_date, e.id)):
        flag = _flag(entry, cleared)
        lines += ["", f"{entry.entry_date} {flag} {_string(entry.description)}"]
        lines.append(f"  salli-id: {_string(entry.id)}")
        if entry.reverses:
            lines.append(f"  reverses: {_string(entry.reverses)}")
        lines.append(f"  source: {_string(entry.source)}")
        if entry.external_ref:
            lines.append(f"  external-ref: {_string(entry.external_ref)}")
        for posting in entry.postings:
            name = names.get(posting.account_id, f"Equity:Unknown:{_component(posting.account_id)}")
            mark = "* " if posting.id in cleared else ""
            line = f"  {mark}{name}  {_amount(_signed(posting), posting.currency)}"
            if posting.currency != base_currency:
                line += f" @ {_rate(posting.fx_rate)} {base_currency}"
            lines.append(line)
            for axis, slug in sorted(posting.tags.items()):
                lines.append(f"    {axis}: {_string(slug)}")
    for a, held in _held(assertions, entries):
        if a.account_id not in names:
            continue
        # Beancount checks a balance at the start of its day.
        day = dt.date.fromisoformat(a.on) + dt.timedelta(days=1)
        text = f"{day} balance {names[a.account_id]}  {_amount(a.balance, a.currency)}"
        lines += ["", text if held else f"; not asserted, the ledger differs: {text}"]
        lines.append(f"{'  ' if held else ';   '}salli-statement: {_string(a.statement_id)}")
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
    accounts: Sequence[Account],
    entries: Sequence[StoredJournalEntry],
    base_currency: str,
    cleared: Collection[str] = (),
    assertions: Sequence[Assertion] = (),
) -> str:
    """The ledger as an hledger journal (also readable by Ledger)."""
    names = account_names(accounts)
    lines = ["; Exported from Salli. Every transaction carries its Salli id (salli-id).", ""]
    for account in sorted(accounts, key=lambda a: names[a.id]):
        note = "" if account.is_active else ", salli-status:inactive"
        note += "".join(f", {key}:{value}" for key, value in _roles(account))
        lines.append(f"account {names[account.id]}  ; type:{_HLEDGER_TYPES[account.type]}{note}")
    for entry in sorted(entries, key=lambda e: (e.entry_date, e.id)):
        description = " ".join(entry.description.split()).replace(";", ",")
        link = f", reverses:{entry.reverses}" if entry.reverses else ""
        lines += [
            "",
            f"{entry.entry_date} {_flag(entry, cleared)} {description}"
            f"  ; salli-id:{entry.id}, source:{entry.source}{link}",
        ]
        for posting in entry.postings:
            name = names.get(posting.account_id, f"Equity:Unknown:{_component(posting.account_id)}")
            mark = "* " if posting.id in cleared else ""
            line = f"    {mark}{name}  {_amount(_signed(posting), posting.currency)}"
            if posting.currency != base_currency:
                line += f" @ {_rate(posting.fx_rate)} {base_currency}"
            tags = ", ".join(f"{axis}:{slug}" for axis, slug in sorted(posting.tags.items()))
            lines.append(line + (f"  ; {tags}" if tags else ""))
    # After every entry, so a same-day entry is inside the asserted balance.
    for a, held in _held(assertions, entries):
        if a.account_id not in names:
            continue
        text = f"    {names[a.account_id]}  0 {a.currency} = {_amount(a.balance, a.currency)}"
        head = f"{a.on} * Reconciled statement  ; salli-statement:{a.statement_id}"
        lines += ["", head, text] if held else ["", f"; not asserted, the ledger differs: {text}"]
    return "\n".join(lines) + "\n"
