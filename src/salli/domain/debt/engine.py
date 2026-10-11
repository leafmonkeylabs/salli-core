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

Calendar months: given the month of the first payment (`first_month`,
"YYYY-MM"), every schedule entry says the calendar month it falls in, and the
plan the month of its last payment. The day within the month is not modelled.

A loan with a term (`Debt.term_months`) pays what is left in its last month:
its level payment is rounded to the currency's smallest unit, so the last one
takes the cents the rounding moved. The extra payment may differ from month
to month (a function of the 1-based month), for a scenario's extra payments
that start or stop.
"""

from __future__ import annotations

from collections.abc import Callable
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


def month_after(period: str, months: int) -> str:
    """The calendar month ("YYYY-MM") `months` after `period`."""
    year, month = int(period[:4]), int(period[5:7])
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def compute_payoff_plan(
    debts: list[Debt],
    extra_monthly_payment: Decimal | Callable[[int], Decimal],
    strategy: PayoffStrategy,
    max_months: int = _DEFAULT_MAX_MONTHS,
    money_quantum: Decimal = _CENT,
    first_month: str | None = None,
) -> PayoffPlan:
    if not debts:
        return PayoffPlan(
            strategy=strategy, months_to_payoff=0, total_interest_paid=Decimal(0), schedule=[]
        )

    order = _order_debts(debts, strategy)
    balances = {d.key: d.principal for d in order}
    monthly_rate = {d.key: d.apr / Decimal(12) for d in order}
    min_payment = {d.key: d.minimum_payment for d in order}
    term = {d.key: d.term_months for d in order}

    def extra_for(month: int) -> Decimal:
        if callable(extra_monthly_payment):
            return extra_monthly_payment(month)
        return extra_monthly_payment

    schedule: list[PayoffScheduleEntry] = []
    total_interest = Decimal(0)
    freed_minimums = Decimal(0)
    month = 0

    while any(bal > 0 for bal in balances.values()) and month < max_months:
        month += 1
        interest_this_month: dict[str, Decimal] = {}
        payment_this_month: dict[str, Decimal] = {d.key: Decimal(0) for d in order}

        # Accrue this month's interest on every still-active debt.
        for d in order:
            bal = balances[d.key]
            if bal <= 0:
                continue
            interest = _round(bal * monthly_rate[d.key], money_quantum)
            interest_this_month[d.key] = interest
            total_interest += interest
            balances[d.key] = bal + interest

        # Apply minimum payments: a loan's last scheduled one pays what is left.
        for d in order:
            bal = balances[d.key]
            if bal <= 0:
                continue
            last = term[d.key]
            payment = bal if last is not None and month >= last else min(min_payment[d.key], bal)
            balances[d.key] = bal - payment
            payment_this_month[d.key] += payment

        # Cascade the extra pool through debts in priority order — a debt paid
        # off with less than the full pool passes the remainder to the next.
        pool = extra_for(month) + freed_minimums
        for d in order:
            if pool <= 0:
                break
            bal = balances[d.key]
            if bal <= 0:
                continue
            applied = min(pool, bal)
            balances[d.key] = bal - applied
            payment_this_month[d.key] += applied
            pool -= applied

        period = month_after(first_month, month - 1) if first_month else None
        for d in order:
            if d.key not in interest_this_month:
                continue  # already paid off before this month started
            interest = interest_this_month[d.key]
            payment = payment_this_month[d.key]
            schedule.append(
                PayoffScheduleEntry(
                    month=month,
                    debt_name=d.name,
                    payment=_round(payment, money_quantum),
                    principal_paid=_round(payment - interest, money_quantum),
                    interest_paid=_round(interest, money_quantum),
                    remaining_balance=_round(balances[d.key], money_quantum),
                    period=period,
                    debt_id=d.id,
                )
            )

        freed_minimums = sum(
            (min_payment[d.key] for d in order if balances[d.key] <= 0), Decimal(0)
        )

    paid_off = not any(bal > 0 for bal in balances.values())
    return PayoffPlan(
        strategy=strategy,
        months_to_payoff=month if paid_off else None,
        total_interest_paid=_round(total_interest, money_quantum),
        schedule=schedule,
        debt_free_period=(
            month_after(first_month, month - 1) if first_month and paid_off and month else None
        ),
    )
