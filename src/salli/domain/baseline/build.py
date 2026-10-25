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
- **Net worth** is what those balances own less what they and the debts owe
  (`Worth`); `worth` makes it as of a day from only what it needs, and
  `worth_by_day` as of many, so every net worth Salli gives is the
  baseline's.
- **Income and expenses** follow the one definition (`flows`).
- **What keeps happening** is what the cash forecast projects: the rhythms
  in the ledger, and the declared subscriptions no rhythm shows.
- **Assumptions** are the user's, then labelled placeholders (`fi.assumptions.resolve`); the active tax rule sets that
  cover the as-of date are recorded with them.
- **Tax** (`BaselineTax`): the active rules a scenario's tax is computed
  with, the postings on accounts whose tax role they declare (to the as-of
  date), and each role's monthly average over the months observed, as
  income and expenses are averaged (`domain/scenarios/tax.py`).
- **Holdings** (`holdings.py`): each as of the as-of date at its last
  recorded price, never counted (the ledger's investment accounts are), and
  a note where a linked account and its holdings disagree.
- **A fingerprint** of the inputs (`fingerprint`): a content hash a result
  computed from the baseline records, so the same inputs are known to give
  the same figures.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal

from salli.domain import canonical
from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.baseline import holdings as holdings_
from salli.domain.baseline.flows import summarize
from salli.domain.baseline.models import (
    ROLE_OF,
    Balance,
    Baseline,
    BaselineDebt,
    BaselineInputs,
    BaselineTax,
    DeclaredDebt,
    Flows,
    Rate,
    Worth,
)
from salli.domain.currency import quantum
from salli.domain.fi.assumptions import resolve
from salli.domain.reports import forecast, insights
from salli.domain.rules.history import booked_transactions
from salli.domain.subscription.models import Subscription
from salli.domain.taxrules.inputs import role_postings

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


def _balances(
    accounts: Sequence[Account],
    totals: Sequence[tuple[str, str, Decimal, Decimal]],
    rates: Mapping[str, Rate],
    base: str,
    day: str,
    linked: Mapping[str, str],
    cash_ids: Collection[str] = frozenset(),
) -> tuple[list[Balance], list[str], list[str]]:
    """Each asset and liability account's balance on `day`, in its currency
    and in the base currency at the published rate for the day; and what was
    left out and why: the cash accounts' notes, then the others'."""
    native, unknowable = _native_amounts(totals, {a.id: a for a in accounts}, base)
    balances: list[Balance] = []
    cash_notes: list[str] = []
    notes: list[str] = []
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
            rate = rates.get(a.currency)
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
    return balances, cash_notes, notes


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


def _tax(
    inputs: BaselineInputs,
    entries: Sequence[StoredJournalEntry],
    accounts: Sequence[Account],
    flows: Flows,
) -> BaselineTax:
    """What a scenario's tax starts from: the postings on the accounts whose
    tax role the active rules declare, to the as-of date, and each role's
    monthly average over the months observed (netted per calendar month in
    the base currency, at the rates they were booked at)."""
    tax = inputs.tax
    roles = sorted({r.key for rules in tax.rules for r in rules.document.roles})
    postings = role_postings(entries, accounts, roles, dt.date.min, inputs.as_of) if roles else []
    months = set(flows.months)
    average: dict[str, Decimal] = {}
    if months:
        sums = dict.fromkeys(roles, Decimal(0))
        for p in postings:
            if p.entry_date[:7] in months:
                sums[p.role] += p.base_amount
        average = {role: total / Decimal(len(months)) for role, total in sums.items()}
    return BaselineTax(
        residency=tax.residency,
        rules=tuple(tax.rules),
        unavailable=tax.unavailable,
        rates={currency: dict(days) for currency, days in tax.rates.items()},
        postings=tuple(postings),
        average=average,
        account_roles={a.id: a.tax_role for a in accounts if a.tax_role is not None},
    )


def fingerprint(inputs: BaselineInputs) -> str:
    """A content hash of everything the baseline is built from, in a
    canonical order (accounts, entries, debts and subscriptions by id;
    totals by account), so the same inputs always hash alike."""
    return canonical.digest(
        {
            "as_of": inputs.as_of,
            "currency": inputs.currency,
            "accounts": sorted(inputs.accounts, key=lambda a: a.id),
            "totals": sorted(inputs.totals, key=lambda t: (t[0], t[1])),
            "rates": dict(inputs.rates),
            "entries": sorted(inputs.entries, key=lambda e: (e.entry_date, e.id)),
            "first_flow": inputs.first_flow,
            "debts": sorted(inputs.debts, key=lambda d: d.id),
            "subscriptions": sorted(
                (dict(row) for row in inputs.subscriptions), key=lambda r: str(r.get("id"))
            ),
            "statement_accounts": inputs.statement_accounts,
            "own_assumptions": inputs.own_assumptions,
            # Only when goals claim cash, so a baseline without any
            # fingerprints as it did before.
            **({"goal_claims": dict(inputs.goal_claims)} if inputs.goal_claims else {}),
            # Only when set, so a baseline without either fingerprints as before.
            **({"cma": inputs.cma.content_hash} if inputs.cma is not None else {}),
            **({"plan": inputs.plan} if not inputs.plan.empty else {}),
            "rule_sets": sorted(inputs.rule_sets, key=lambda r: (r.rule_set_id, r.version)),
            # Only when there are rules to compute tax with, so a baseline
            # without any fingerprints as it did before scenarios computed tax.
            **(
                {
                    "tax": {
                        "rules": sorted(
                            (r.ref for r in inputs.tax.rules),
                            key=lambda r: (r.rule_set_id, r.version),
                        ),
                        "rates": {c: dict(days) for c, days in inputs.tax.rates.items()},
                    }
                }
                if inputs.tax.rules
                else {}
            ),
            # Only when there are holdings, so a baseline without any
            # fingerprints as it did before scenarios could sell one.
            **(
                {"holdings": sorted(inputs.holdings, key=lambda h: h.holding_id)}
                if inputs.holdings
                else {}
            ),
        },
        floats=True,
    )


def build(inputs: BaselineInputs) -> Baseline:
    as_of = inputs.as_of
    base = inputs.currency
    day = as_of.isoformat()
    accounts = list(inputs.accounts)
    # Nothing after the as-of date: the baseline as of a day is what was known then.
    entries = [e for e in inputs.entries if e.entry_date <= day]
    notes: list[str] = []

    linked = {d.account_id: d.id for d in inputs.debts if d.account_id}
    booked = booked_transactions(entries, accounts)
    since = (as_of - dt.timedelta(days=_CARD_DAYS)).isoformat()
    cash_ids = forecast.cash_accounts(
        booked, accounts, since, inputs.statement_accounts, debt_accounts=set(linked)
    )

    balances, cash_notes, balance_notes = _balances(
        accounts, inputs.totals, inputs.rates, base, day, linked, cash_ids
    )
    notes += balance_notes
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

    held, holding_notes = holdings_.build(inputs.holdings, as_of, base, inputs.rates, balances)
    notes += holding_notes

    used = sorted({b.currency for b in balances} - {base})
    rates = tuple(inputs.rates.get(c) or Rate(c, None, None, None) for c in used)
    return Baseline(
        as_of=as_of,
        currency=base,
        balances=tuple(balances),
        rates=rates,
        flows=flows,
        debts=tuple(debts),
        assumptions=resolve(inputs.own_assumptions, inputs.cma),
        plan=inputs.plan,
        recurring=tuple(found),
        covered_by=tuple(covering),
        charges=tuple(charges),
        notes=tuple(dict.fromkeys([*cash_notes, *notes])),
        first_flow=inputs.first_flow,
        cash_notes=tuple(dict.fromkeys(cash_notes)),
        latest_entry=max((e.entry_date for e in entries), default=None),
        rule_sets=tuple(inputs.rule_sets),
        tax=_tax(inputs, entries, accounts, flows),
        fingerprint=fingerprint(inputs),
        holdings=held,
        held_for_goals=sum(
            (
                min(inputs.goal_claims[b.account_id], max(b.value, Decimal(0)))
                for b in balances
                if b.in_cash and b.value is not None and b.account_id in inputs.goal_claims
            ),
            Decimal(0),
        ),
    )


def worth(
    as_of: dt.date,
    currency: str,
    accounts: Sequence[Account],
    totals: Sequence[tuple[str, str, Decimal, Decimal]],
    rates: Mapping[str, Rate],
    debts: Sequence[DeclaredDebt],
) -> Worth:
    """What is owned and owed as of a day, from only what it needs of a
    baseline's inputs: the balances and debts `build` makes from them, so
    `Worth.net_worth` is the baseline's."""
    day = as_of.isoformat()
    linked = {d.account_id: d.id for d in debts if d.account_id}
    balances, _, notes = _balances(accounts, totals, rates, currency, day, linked)
    owed, debt_notes = _debts(debts, {b.account_id: b for b in balances}, currency)
    return Worth(
        as_of=as_of,
        currency=currency,
        balances=tuple(balances),
        debts=tuple(owed),
        notes=tuple(dict.fromkeys([*notes, *debt_notes])),
    )


def worth_by_day(
    days: Sequence[dt.date],
    currency: str,
    accounts: Sequence[Account],
    opening: Sequence[tuple[str, str, Decimal, Decimal]],
    entries: Sequence[StoredJournalEntry],
    rates: Mapping[str, Mapping[str, Rate]],
    debts: Sequence[DeclaredDebt],
) -> list[Worth]:
    """`worth` as of each of `days`, oldest first, without summing the whole
    ledger for each: `opening` is the totals (as `BaselineInputs.totals`) of
    everything before `entries`, which run to the last day; `rates` the
    published rates for each day (ISO date → currency → rate)."""
    held = {a.id for a in accounts if a.type in ("asset", "liability")}
    sums: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
        (account_id, cur): (amount, in_base) for account_id, cur, amount, in_base in opening
    }
    ordered = sorted(entries, key=lambda e: e.entry_date)
    out: list[Worth] = []
    i = 0
    for as_of in sorted(days):
        day = as_of.isoformat()
        while i < len(ordered) and ordered[i].entry_date <= day:
            for p in ordered[i].postings:
                if p.account_id in held:
                    amount, in_base = sums.get((p.account_id, p.currency), (Decimal(0), Decimal(0)))
                    signed = Decimal(p.direction.value) * p.amount
                    sums[(p.account_id, p.currency)] = (amount + signed, in_base + p.base_signed)
            i += 1
        totals = [(a, cur, amount, in_base) for (a, cur), (amount, in_base) in sums.items()]
        out.append(worth(as_of, currency, accounts, totals, rates.get(day, {}), debts))
    return out
