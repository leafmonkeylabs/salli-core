"""
Building the baseline from what the application gathered. Pure.

- **Balances** are each account's own: in its currency from what its postings
  sum to on the as-of date, and in the base currency at the published rate
  for that date. An account whose balance can't be known in its currency
  (amounts posted in a third currency), or whose currency has no rate, is
  left out of the totals and said in `notes`, never shown at a wrong value.
- **Roles** come from the account: an asset account's `asset_role`, or
  liability. Never from its name.
- **Debts** are counted once: a debt linked to its ledger account owes what
  the account says; one the ledger doesn't hold owes its declared principal.
- **Income and expenses** follow the one definition (`flows`).
- **What keeps happening** is what the cash forecast projects: the rhythms
  in the ledger, and the declared subscriptions no rhythm shows.
- **Assumptions** are the user's, then their FIRE strategy's, then labelled
  placeholders (`fi.assumptions.resolve`).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal

from salli.domain.accounting.models import Account
from salli.domain.baseline.flows import summarize
from salli.domain.baseline.models import (
    ROLE_OF,
    Balance,
    Baseline,
    BaselineDebt,
    BaselineInputs,
    DeclaredDebt,
    Rate,
)
from salli.domain.currency import quantum
from salli.domain.fi.assumptions import resolve
from salli.domain.reports import forecast, insights
from salli.domain.rules.history import booked_transactions
from salli.domain.subscription.models import Subscription

#: How far back a card must have paid for things to count as cash.
_CARD_DAYS = 90


def _native_amounts(
    totals: Sequence[tuple[str, str, Decimal, Decimal]],
    by_id: Mapping[str, Account],
    base: str,
) -> tuple[dict[str, Decimal], set[str]]:
    """Each account's balance in its own currency, and the accounts whose
    balance in it can't be known (a posting in a third currency, with no rate
    into the account's)."""
    native: dict[str, Decimal] = {}
    unknowable: set[str] = set()
    for account_id, currency, amount, in_base in totals:
        account = by_id.get(account_id)
        if account is None:
            continue
        if currency == account.currency:
            native[account_id] = native.get(account_id, Decimal(0)) + amount
        elif account.currency == base:
            native[account_id] = native.get(account_id, Decimal(0)) + in_base
        else:
            unknowable.add(account_id)
    return native, unknowable


def _interest(balance: Decimal, apr: Decimal, currency: str) -> Decimal:
    return (balance * apr / Decimal(12)).quantize(quantum(currency), rounding=ROUND_HALF_UP)


def _debts(
    declared: Sequence[DeclaredDebt], balances: Mapping[str, Balance], currency: str
) -> tuple[list[BaselineDebt], list[str]]:
    debts: list[BaselineDebt] = []
    notes: list[str] = []
    for d in declared:
        linked = balances.get(d.account_id) if d.account_id else None
        if linked is not None and linked.value is not None:
            owed = linked.owed
            debts.append(
                BaselineDebt(
                    debt_id=d.id,
                    name=d.name,
                    apr=d.apr,
                    minimum_payment=d.minimum_payment,
                    balance=owed,
                    source="account",
                    account_id=d.account_id,
                    already_paid=_interest(owed, d.apr, currency),
                )
            )
            continue
        if d.account_id:
            notes.append(f"{d.name}: its account's balance can't be read, so it counts as declared")
        owed = max(d.principal, Decimal(0))
        debts.append(
            BaselineDebt(
                debt_id=d.id,
                name=d.name,
                apr=d.apr,
                minimum_payment=d.minimum_payment,
                balance=owed,
                source="declared",
                account_id=None,
                already_paid=d.minimum_payment if owed > 0 else Decimal(0),
            )
        )
    return debts, notes


def build(inputs: BaselineInputs) -> Baseline:
    as_of = inputs.as_of
    base = inputs.currency
    day = as_of.isoformat()
    accounts = list(inputs.accounts)
    by_id = {a.id: a for a in accounts}
    # Nothing after the as-of date: the baseline as of a day is what was known then.
    entries = [e for e in inputs.entries if e.entry_date <= day]
    notes: list[str] = []

    native, unknowable = _native_amounts(inputs.totals, by_id, base)
    linked = {d.account_id: d.id for d in inputs.debts if d.account_id}
    booked = booked_transactions(entries, accounts)
    since = (as_of - dt.timedelta(days=_CARD_DAYS)).isoformat()
    cash_ids = forecast.cash_accounts(
        booked, accounts, since, inputs.statement_accounts, debt_accounts=set(linked)
    )

    balances: list[Balance] = []
    cash_notes: list[str] = []
    for a in accounts:
        if a.type not in ("asset", "liability"):
            continue
        amount = None if a.id in unknowable else native.get(a.id, Decimal(0))
        if not a.is_active and not amount and a.id not in linked:
            continue  # closed and empty
        said = cash_notes if a.id in cash_ids else notes
        if amount is None:
            said.append(
                f"{a.name}: its balance in {a.currency} can't be known (amounts posted to it "
                f"in another currency, with no rate into its own); left out"
            )
            value = None
        elif a.currency == base:
            value = amount
        else:
            rate = inputs.rates.get(a.currency)
            if rate is None or rate.rate is None:
                said.append(
                    f"{a.name}: no published {a.currency} rate for {day}, so it is left out "
                    f"of the totals in {base}"
                )
                value = None
            else:
                value = amount * rate.rate
        role = ROLE_OF[a.asset_role or "cash"] if a.type == "asset" else "liability"
        in_cash = amount is not None and (
            a.id in cash_ids or (role == "cash" and not a.is_active and amount != 0)
        )
        balances.append(
            Balance(
                account_id=a.id,
                code=a.code,
                name=a.name,
                role=role,
                currency=a.currency,
                amount=amount,
                value=value,
                is_active=a.is_active,
                in_cash=in_cash,
                debt_id=linked.get(a.id),
            )
        )

    debts, debt_notes = _debts(inputs.debts, {b.account_id: b for b in balances}, base)
    notes += debt_notes

    flows = summarize(entries, accounts, as_of, inputs.first_flow)
    if not flows.months:
        notes.append(
            "No full calendar month of income and expenses is recorded before "
            f"{insights.month_of(day)}, so the monthly figures are zero until one is"
        )

    currencies = {a.id: a.currency for a in accounts}
    found = insights.detect_recurring(
        booked, as_of, direction=None, currencies=currencies, base=base
    )
    covered_by = forecast.coverage(inputs.subscriptions, entries, accounts, base)
    covering = [covered_by(r) for r in found]
    covered = set(covering) - {None}
    charges: list[forecast.DeclaredCharge] = []
    for row in inputs.subscriptions:
        if row.get("id") in covered:
            continue
        try:
            declared = Subscription.from_row(row, base)
        except ValueError as exc:
            cash_notes.append(f"{row.get('name', 'A subscription')}: left out ({exc})")
            continue
        charges.append(
            forecast.DeclaredCharge(
                name=declared.name,
                amount=declared.amount,
                cadence=declared.frequency,
                next_due=dt.date.fromisoformat(declared.next_due_date),
            )
        )

    used = sorted({b.currency for b in balances} - {base})
    rates = tuple(inputs.rates.get(c) or Rate(c, None, None, None) for c in used)
    return Baseline(
        as_of=as_of,
        currency=base,
        balances=tuple(balances),
        rates=rates,
        flows=flows,
        debts=tuple(debts),
        assumptions=resolve(inputs.own_assumptions, inputs.strategy),
        recurring=tuple(found),
        covered_by=tuple(covering),
        charges=tuple(charges),
        notes=tuple(dict.fromkeys([*cash_notes, *notes])),
        first_flow=inputs.first_flow,
        cash_notes=tuple(dict.fromkeys(cash_notes)),
    )
