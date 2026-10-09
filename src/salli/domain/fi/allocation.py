"""
Apportioning real account balances across the goals that claim them.

A goal used to carry `current_amount`, a number the user typed and then had to
maintain by hand. Nothing connected it to the ledger, so it drifted from reality
immediately — and since neither client ever exposed the field, every goal made
in the app sat at 0% forever.

An allocation is a *claim on a live balance* instead: "600,000 of my savings
account is for the house deposit". Progress is derived from what the account
actually holds, so it moves when money moves and only when money moves.

The interesting case is deliberate: one account can back several goals, and
their claims may exceed what is actually there. Rather than rejecting that (a
plan you have not funded yet is a normal thing to have), the shortfall is
surfaced and the balance is apportioned by the goal's own `priority` — which
finally gives that field a job, since nothing else used it.

Pure functions: no I/O, Decimal money, no framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class Claim:
    """One goal's claim on one account."""

    goal_id: str
    account_id: str
    allocated: Decimal
    # From the goal: 1 high … 3 low. Decides who stays funded when an account
    # cannot cover everything claimed against it.
    priority: int


@dataclass(frozen=True)
class GoalFunding:
    goal_id: str
    claimed: Decimal
    """Total claimed across every account backing this goal."""
    funded: Decimal
    """How much of that is actually covered by live balances."""

    @property
    def shortfall(self) -> Decimal:
        return max(Decimal(0), self.claimed - self.funded)


def apportion_account(claims: list[Claim], balance: Decimal) -> dict[str, Decimal]:
    """Split one account's balance across the claims on it.

    Highest priority first. Within a priority, a balance that cannot cover the
    group is split pro-rata — a tie in priority is a statement that the goals
    matter equally, so neither should be starved to fully fund the other.

    Returns goal_id → funded amount. Goals that get nothing are omitted.
    """
    if balance <= 0 or not claims:
        return {}

    funded: dict[str, Decimal] = {}
    remaining = balance

    for _, group in _by_priority(claims):
        if remaining <= 0:
            break
        group_total = sum((c.allocated for c in group), Decimal(0))
        if group_total <= 0:
            continue

        if group_total <= remaining:
            for c in group:
                funded[c.goal_id] = funded.get(c.goal_id, Decimal(0)) + c.allocated
            remaining -= group_total
            continue

        # Constrained: split what is left in proportion to each claim. Rounding
        # is ROUND_DOWN so the parts can never sum to more than the balance;
        # the residual cent or two goes to the largest claim in the group, which
        # is the one whose share the rounding shaved most.
        shares = [
            (c, (c.allocated / group_total * remaining).quantize(_CENTS, rounding=ROUND_DOWN))
            for c in group
        ]
        distributed = sum((s for _, s in shares), Decimal(0))
        residual = remaining - distributed
        if residual > 0 and shares:
            biggest = max(range(len(shares)), key=lambda i: shares[i][0].allocated)
            shares[biggest] = (shares[biggest][0], shares[biggest][1] + residual)

        for c, share in shares:
            if share > 0:
                funded[c.goal_id] = funded.get(c.goal_id, Decimal(0)) + share
        remaining = Decimal(0)

    return funded


def compute_goal_funding(
    claims: list[Claim],
    balances: dict[str, Decimal],
    targets: dict[str, Decimal],
) -> dict[str, GoalFunding]:
    """Funding for every goal named in `claims`.

    `balances` is account_id → current balance (a signed trial balance; a
    negative or missing balance funds nothing). `targets` is goal_id → target
    amount, used to cap progress: money earmarked beyond what a goal needs is
    not progress toward it, and letting it overflow would report 140% complete.
    """
    by_account: dict[str, list[Claim]] = {}
    for c in claims:
        by_account.setdefault(c.account_id, []).append(c)

    funded: dict[str, Decimal] = {}
    for account_id, account_claims in by_account.items():
        for goal_id, amount in apportion_account(
            account_claims, balances.get(account_id, Decimal(0))
        ).items():
            funded[goal_id] = funded.get(goal_id, Decimal(0)) + amount

    claimed: dict[str, Decimal] = {}
    for c in claims:
        claimed[c.goal_id] = claimed.get(c.goal_id, Decimal(0)) + c.allocated

    result: dict[str, GoalFunding] = {}
    for goal_id, total_claimed in claimed.items():
        target = targets.get(goal_id)
        got = funded.get(goal_id, Decimal(0))
        if target is not None and target > 0:
            got = min(got, target)
        result[goal_id] = GoalFunding(goal_id=goal_id, claimed=total_claimed, funded=got)
    return result


def _by_priority(claims: list[Claim]) -> list[tuple[int, list[Claim]]]:
    groups: dict[int, list[Claim]] = {}
    for c in claims:
        groups.setdefault(c.priority, []).append(c)
    return sorted(groups.items())
