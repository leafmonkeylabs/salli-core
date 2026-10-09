"""
Apportioning account balances across the goals that claim them.

The case that motivated all of this: one savings account, several goals.
"""

from __future__ import annotations

from decimal import Decimal

from salli.domain.fi.allocation import Claim, apportion_account, compute_goal_funding


def _claim(goal: str, account: str, amount: str, priority: int = 2) -> Claim:
    return Claim(goal_id=goal, account_id=account, allocated=Decimal(amount), priority=priority)


# ── one account, one goal ─────────────────────────────────────────────────────


def test_a_funded_claim_is_fully_backed():
    funded = apportion_account([_claim("house", "sav", "600000")], Decimal("1000000"))
    assert funded == {"house": Decimal("600000")}


def test_progress_tracks_the_balance_not_the_claim():
    """The whole point — earmark 600k against an account holding 300k and you
    have 300k saved, not 600k."""
    funded = apportion_account([_claim("house", "sav", "600000")], Decimal("300000"))
    assert funded == {"house": Decimal("300000")}


def test_an_empty_account_funds_nothing():
    assert apportion_account([_claim("house", "sav", "600000")], Decimal(0)) == {}


def test_an_overdrawn_account_funds_nothing_rather_than_going_negative():
    assert apportion_account([_claim("house", "sav", "600000")], Decimal("-5000")) == {}


# ── one account, several goals ────────────────────────────────────────────────


def test_one_account_backs_several_goals():
    claims = [_claim("house", "sav", "600000"), _claim("emergency", "sav", "400000")]
    funded = apportion_account(claims, Decimal("1000000"))
    assert funded == {"house": Decimal("600000"), "emergency": Decimal("400000")}


def test_priority_decides_who_stays_funded_when_the_balance_drops():
    """Balance falls to 500k against 1,000k of claims. The higher-priority goal
    stays whole; the other absorbs the shortfall."""
    claims = [
        _claim("house", "sav", "600000", priority=1),
        _claim("emergency", "sav", "400000", priority=3),
    ]
    funded = apportion_account(claims, Decimal("500000"))
    assert funded == {"house": Decimal("500000")}
    assert "emergency" not in funded


def test_a_higher_priority_goal_leaves_the_remainder_to_the_next():
    claims = [
        _claim("house", "sav", "600000", priority=1),
        _claim("emergency", "sav", "400000", priority=3),
    ]
    funded = apportion_account(claims, Decimal("800000"))
    assert funded["house"] == Decimal("600000")
    assert funded["emergency"] == Decimal("200000")


def test_equal_priority_splits_pro_rata_rather_than_starving_one():
    """A tie in priority says the goals matter equally, so neither is starved to
    fully fund the other."""
    claims = [
        _claim("house", "sav", "750000", priority=2),
        _claim("car", "sav", "250000", priority=2),
    ]
    funded = apportion_account(claims, Decimal("400000"))
    assert funded["house"] == Decimal("300000")  # 75%
    assert funded["car"] == Decimal("100000")  # 25%


def test_apportioned_shares_never_exceed_the_balance():
    """Rounding must not conjure money — the parts always sum to at most what
    the account actually holds."""
    claims = [_claim(f"g{i}", "sav", "100", priority=2) for i in range(3)]
    balance = Decimal("100.00")
    funded = apportion_account(claims, balance)
    assert sum(funded.values()) == balance


# ── across accounts, with targets ─────────────────────────────────────────────


def test_a_goal_backed_by_several_accounts_sums_them():
    claims = [_claim("house", "sav", "400000"), _claim("house", "fd", "300000")]
    result = compute_goal_funding(
        claims,
        balances={"sav": Decimal("400000"), "fd": Decimal("300000")},
        targets={"house": Decimal("1000000")},
    )
    assert result["house"].funded == Decimal("700000")
    assert result["house"].claimed == Decimal("700000")
    assert result["house"].shortfall == Decimal(0)


def test_shortfall_is_reported_rather_than_rejected():
    """Claiming more than an account holds is a normal, unfunded plan — surface
    it, do not refuse it."""
    result = compute_goal_funding(
        [_claim("house", "sav", "600000")],
        balances={"sav": Decimal("250000")},
        targets={"house": Decimal("1000000")},
    )
    assert result["house"].funded == Decimal("250000")
    assert result["house"].shortfall == Decimal("350000")


def test_funding_is_capped_at_the_target():
    """Earmarking beyond what a goal needs is not progress toward it — without
    the cap this would report 200% complete."""
    result = compute_goal_funding(
        [_claim("house", "sav", "2000000")],
        balances={"sav": Decimal("2000000")},
        targets={"house": Decimal("1000000")},
    )
    assert result["house"].funded == Decimal("1000000")


def test_a_goal_with_no_target_is_not_capped():
    result = compute_goal_funding(
        [_claim("misc", "sav", "50000")],
        balances={"sav": Decimal("50000")},
        targets={},
    )
    assert result["misc"].funded == Decimal("50000")


def test_an_account_missing_from_balances_funds_nothing():
    result = compute_goal_funding(
        [_claim("house", "closed-acct", "600000")],
        balances={},
        targets={"house": Decimal("1000000")},
    )
    assert result["house"].funded == Decimal(0)
    assert result["house"].shortfall == Decimal("600000")


def test_the_motivating_case_end_to_end():
    """One savings account of 1,000,000 backing a house deposit (600k, high
    priority) and an emergency fund (400k). The balance falls to 500,000."""
    claims = [
        _claim("house", "sav", "600000", priority=1),
        _claim("emergency", "sav", "400000", priority=2),
    ]
    targets = {"house": Decimal("2000000"), "emergency": Decimal("400000")}

    full = compute_goal_funding(claims, {"sav": Decimal("1000000")}, targets)
    assert full["house"].funded == Decimal("600000")
    assert full["emergency"].funded == Decimal("400000")

    drained = compute_goal_funding(claims, {"sav": Decimal("500000")}, targets)
    assert drained["house"].funded == Decimal("500000")
    assert drained["house"].shortfall == Decimal("100000")
    assert drained["emergency"].funded == Decimal(0)
    assert drained["emergency"].shortfall == Decimal("400000")
