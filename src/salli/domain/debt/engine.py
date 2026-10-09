"""
Deterministic debt payoff engine.

Pure function: compute_payoff_plan(debts, extra_monthly_payment, strategy) -> PayoffPlan.
No I/O.

Simulates month-by-month amortization: every debt gets at least its minimum
payment; the extra payment pool cascades through debts in priority order —
if the top-priority debt is paid off with less than the full pool, the
remainder is applied to the next debt in the same month, and so on. Once a
debt is paid off, its minimum payment "frees up" and joins the extra pool from
the following month onward (the classic avalanche/snowball method).

  • avalanche — prioritizes the highest-APR debt (minimizes total interest paid)
  • snowball  — prioritizes the smallest-balance debt (maximizes early "wins")

"Avalanche minimizes total interest" is a proven result for continuous/unrounded
payment allocation. Under monthly rounding to the currency's smallest unit it holds in every realistic case,
but pathological minimum-payment-to-balance ratios can (rarely) shift a payoff
across a month boundary and flip the comparison by a few cents — this is a known,
narrow property of discretized amortization, not specific to this implementation.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from salli.domain.debt.models import Debt, PayoffPlan, PayoffScheduleEntry, PayoffStrategy

_DEFAULT_MAX_MONTHS = 600  # 50 years — a generous simulation horizon

#: The smallest unit amounts are rounded to each month: a cent by default, the
#: currency's own (1 for JPY, 0.001 for KWD) when the caller passes it.
_CENT = Decimal("0.01")


def _round(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _order_debts(debts: list[Debt], strategy: PayoffStrategy) -> list[Debt]:
    if strategy == "avalanche":
        return sorted(debts, key=lambda d: d.apr, reverse=True)
    return sorted(debts, key=lambda d: d.principal)


def compute_payoff_plan(
    debts: list[Debt],
    extra_monthly_payment: Decimal,
    strategy: PayoffStrategy,
    max_months: int = _DEFAULT_MAX_MONTHS,
    money_quantum: Decimal = _CENT,
) -> PayoffPlan:
    if not debts:
        return PayoffPlan(
            strategy=strategy, months_to_payoff=0, total_interest_paid=Decimal(0), schedule=[]
        )

    order = _order_debts(debts, strategy)
    balances = {d.name: d.principal for d in order}
    monthly_rate = {d.name: d.apr / Decimal(12) for d in order}
    min_payment = {d.name: d.minimum_payment for d in order}

    schedule: list[PayoffScheduleEntry] = []
    total_interest = Decimal(0)
    freed_minimums = Decimal(0)
    month = 0

    while any(bal > 0 for bal in balances.values()) and month < max_months:
        month += 1
        interest_this_month: dict[str, Decimal] = {}
        payment_this_month: dict[str, Decimal] = {d.name: Decimal(0) for d in order}

        # Accrue this month's interest on every still-active debt.
        for d in order:
            bal = balances[d.name]
            if bal <= 0:
                continue
            interest = _round(bal * monthly_rate[d.name], money_quantum)
            interest_this_month[d.name] = interest
            total_interest += interest
            balances[d.name] = bal + interest

        # Apply minimum payments.
        for d in order:
            bal = balances[d.name]
            if bal <= 0:
                continue
            payment = min(min_payment[d.name], bal)
            balances[d.name] = bal - payment
            payment_this_month[d.name] += payment

        # Cascade the extra pool through debts in priority order — a debt paid
        # off with less than the full pool passes the remainder to the next.
        pool = extra_monthly_payment + freed_minimums
        for d in order:
            if pool <= 0:
                break
            bal = balances[d.name]
            if bal <= 0:
                continue
            applied = min(pool, bal)
            balances[d.name] = bal - applied
            payment_this_month[d.name] += applied
            pool -= applied

        for d in order:
            if d.name not in interest_this_month:
                continue  # already paid off before this month started
            interest = interest_this_month[d.name]
            payment = payment_this_month[d.name]
            schedule.append(
                PayoffScheduleEntry(
                    month=month,
                    debt_name=d.name,
                    payment=_round(payment, money_quantum),
                    principal_paid=_round(payment - interest, money_quantum),
                    interest_paid=_round(interest, money_quantum),
                    remaining_balance=_round(balances[d.name], money_quantum),
                )
            )

        freed_minimums = sum(
            (min_payment[d.name] for d in order if balances[d.name] <= 0), Decimal(0)
        )

    paid_off = not any(bal > 0 for bal in balances.values())
    return PayoffPlan(
        strategy=strategy,
        months_to_payoff=month if paid_off else None,
        total_interest_paid=_round(total_interest, money_quantum),
        schedule=schedule,
    )
