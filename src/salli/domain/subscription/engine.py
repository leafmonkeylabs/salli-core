"""
Deterministic recurring-subscription matching engine.

Pure functions: find_matches(subscription, entries, accounts) -> list[SubscriptionMatch],
compute_report(subscription, entries, accounts, today) -> SubscriptionReport. No I/O.

Two matching strategies, depending on whether the subscription is linked to a
specific expense account:
  • account_id set    — every debit posting to that account is a match, regardless
    of amount. This is the strong-identity case: because the account link (not the
    amount) is what identifies the subscription, a matched charge's amount can
    legitimately differ from the expected one — which is exactly what enables
    price-change detection.
  • account_id unset  — falls back to amount-tolerance matching across all expense
    accounts. Since amount IS the matching criterion here, every match is by
    definition within tolerance, so price-change detection cannot fire in this mode
    (there is nothing distinguishing this subscription from any other expense of a
    similar amount) — only missed-charge detection is meaningful without an account
    link.

There is no attempt to project a precise calendar of expected due dates (which
would need day-of-month/leap-year handling per frequency). Missed-charge detection
instead compares the gap since the most recent match (or since next_due_date, if
there is no match yet) against the frequency's typical day-count plus a grace
period.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from salli.domain.accounting.models import Direction
from salli.domain.subscription.models import (
    Subscription,
    SubscriptionAlert,
    SubscriptionMatch,
    SubscriptionReport,
)

_FREQUENCY_DAYS = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}


def find_matches(
    subscription: Subscription, entries: list[Any], accounts: list[Any]
) -> list[SubscriptionMatch]:
    acc_map = {a.id: a for a in accounts}
    tolerance = subscription.amount * subscription.amount_tolerance_pct
    matches: list[SubscriptionMatch] = []

    for entry in entries:
        for p in entry.postings:
            acc = acc_map.get(p.account_id)
            if acc is None or acc.type != "expense" or p.direction != Direction.DEBIT:
                continue
            amount = abs(p.base_signed)

            if subscription.account_id:
                # Strong identity: the account link determines the match, not the
                # amount — this is what lets a drifted amount surface as a
                # price-change alert instead of just falling out of matching.
                if p.account_id != subscription.account_id:
                    continue
            else:
                # No account link — fall back to amount-tolerance matching, which
                # by construction can never surface a price change (see docstring).
                if abs(amount - subscription.amount) > tolerance:
                    continue

            matches.append(
                SubscriptionMatch(entry_id=entry.id, entry_date=entry.entry_date, amount=amount)
            )

    matches.sort(key=lambda m: m.entry_date)
    return matches


def compute_report(
    subscription: Subscription, entries: list[Any], accounts: list[Any], today: str
) -> SubscriptionReport:
    matches = find_matches(subscription, entries, accounts)
    alerts: list[SubscriptionAlert] = []
    expected_gap = _FREQUENCY_DAYS[subscription.frequency]
    today_date = date.fromisoformat(today)

    if matches:
        latest = matches[-1]
        tolerance = subscription.amount * subscription.amount_tolerance_pct
        if abs(latest.amount - subscription.amount) > tolerance:
            alerts.append(
                SubscriptionAlert(
                    kind="price_change",
                    message=(
                        f"Latest charge {latest.amount} differs from the expected "
                        f"{subscription.amount} by more than the configured tolerance."
                    ),
                    expected_amount=subscription.amount,
                    actual_amount=latest.amount,
                )
            )

        days_since = (today_date - date.fromisoformat(latest.entry_date)).days
        if days_since > expected_gap + subscription.grace_days:
            alerts.append(
                SubscriptionAlert(
                    kind="missed_charge",
                    message=(
                        f"No matching charge in {days_since} days "
                        f"(expected roughly every {expected_gap} days)."
                    ),
                )
            )
    else:
        days_since_due = (today_date - date.fromisoformat(subscription.next_due_date)).days
        if days_since_due > subscription.grace_days:
            alerts.append(
                SubscriptionAlert(
                    kind="missed_charge",
                    message=f"No charge found; {days_since_due} days past the due date.",
                )
            )

    return SubscriptionReport(matches=matches, alerts=alerts)
