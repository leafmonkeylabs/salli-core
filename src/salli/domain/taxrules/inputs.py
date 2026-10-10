"""
A rule set's role totals, read from a ledger.

A rule set's roles are what the ledger supplies: for each role key, the total
of the postings on accounts whose `tax_role` is that key. Nothing is known
about any role: a rule set declares its keys, an account names one, and the
postings are added up.

How each posting counts:

- **Only postings dated within the tax year** (`year.start` to `year.end`,
  both included) and on an account whose `tax_role` is one of the rule set's
  role keys. An account's other attributes (its name, code, type) never decide
  whether it counts.
- **In the account's normal-balance direction**: debits add on asset and
  expense accounts, credits add on income, liability and equity accounts. So
  income comes out positive, and so does tax withheld kept as an asset (a
  receivable), whichever side of the ledger the rule set's author imagined.
- **Signed, not filtered by direction**, so a reversing entry cancels the one
  it reverses (entries are immutable; reversal is the only correction).
- **Never clamped.** A total that comes out negative (a ledger mid-correction,
  a net loss) is passed on as it is and reported, so the rules (which can say
  `max(0, role.x)`) decide, rather than a silent floor here.

Currency: a posting carries its own amount and currency, and its value in the
owner's base currency. When the rule set computes in the base currency, the
base values are added. When it computes in another, a posting already in that
currency counts at its own amount, and any other posting's base value is
converted at the rate for its entry's date (`rates`, which the caller fetches;
see `dates_needing_rates`). Each total is then rounded to the currency's minor
units, as the amounts a person reads off a statement are.

Pure: entries, accounts and rates in; totals out.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from salli.domain.accounting.models import Account, AccountType, StoredJournalEntry
from salli.domain.currency import quantize

#: Account types whose balance grows with debits. The rest grow with credits.
DEBIT_NORMAL: frozenset[AccountType] = frozenset({"asset", "expense"})


@dataclass(frozen=True)
class RolePosting:
    """One posting that counts towards a role, signed in its account's
    normal-balance direction."""

    role: str
    entry_date: str
    currency: str
    #: In the posting's own currency.
    amount: Decimal
    #: In the owner's base currency, at the rate the posting was booked at.
    base_amount: Decimal


@dataclass(frozen=True)
class RoleTotals:
    #: Every declared role, zero where nothing counted.
    totals: Mapping[str, Decimal]
    #: How many postings counted towards each role.
    postings: Mapping[str, int]
    #: The roles whose total came out negative.
    negative: tuple[str, ...] = field(default=())


def normal_sign(account_type: AccountType) -> int:
    return 1 if account_type in DEBIT_NORMAL else -1


def role_postings(
    entries: Iterable[StoredJournalEntry],
    accounts: Iterable[Account],
    roles: Collection[str],
    start: date,
    end: date,
) -> list[RolePosting]:
    """The postings that count towards `roles` between `start` and `end`."""
    by_id = {a.id: a for a in accounts if a.tax_role is not None and a.tax_role in roles}
    first, last = start.isoformat(), end.isoformat()
    found: list[RolePosting] = []
    for entry in entries:
        # ISO dates compare as strings; the store filters too, but the rule
        # set's year is what decides, whatever a caller fetched.
        day = str(entry.entry_date)[:10]
        if not first <= day <= last:
            continue
        for posting in entry.postings:
            account = by_id.get(posting.account_id)
            if account is None:
                continue
            assert account.tax_role is not None
            sign = normal_sign(account.type) * posting.direction.value
            found.append(
                RolePosting(
                    role=account.tax_role,
                    entry_date=day,
                    currency=posting.currency,
                    amount=sign * posting.amount,
                    base_amount=sign * posting.amount * posting.fx_rate,
                )
            )
    return found


def dates_needing_rates(postings: Iterable[RolePosting], base: str, target: str) -> list[str]:
    """The entry dates whose postings must be converted from `base` into
    `target`, in order: none when the rule set computes in the base currency."""
    if base == target:
        return []
    return sorted({p.entry_date for p in postings if p.currency != target})


def total_roles(
    postings: Iterable[RolePosting],
    roles: Collection[str],
    base: str,
    target: str,
    rates: Mapping[str, Decimal] | None = None,
) -> RoleTotals:
    """Each role's total in `target`. `rates` maps an entry date to the rate
    from `base` into `target` that day; every date `dates_needing_rates` named
    must be in it (KeyError otherwise: a missing rate is never taken as 1)."""
    rates = rates or {}
    sums = dict.fromkeys(roles, Decimal(0))
    counts = dict.fromkeys(roles, 0)
    for p in postings:
        if base == target:
            amount = p.base_amount
        elif p.currency == target:
            amount = p.amount
        else:
            amount = p.base_amount * rates[p.entry_date]
        sums[p.role] += amount
        counts[p.role] += 1
    totals = {role: quantize(amount, target) for role, amount in sums.items()}
    negative = tuple(sorted(role for role, amount in totals.items() if amount < 0))
    return RoleTotals(totals, counts, negative)
