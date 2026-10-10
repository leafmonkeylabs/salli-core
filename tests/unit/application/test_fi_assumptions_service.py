"""
FiService computes with the assumptions that apply to the user, and says so:
every score, projection and purchase costing carries them, with their origin.
"""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

from salli.application.services.fi_service import FiService
from salli.application.services.user_profile_service import UserProfileService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry

USER = "u1"


def _entry(n: int, days_ago: int, debit: str, credit: str, amount: str) -> StoredJournalEntry:
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    return StoredJournalEntry(
        id=f"e{n}",
        user_id=USER,
        entry_date=day.isoformat(),
        description="",
        source="manual",
        postings=[
            Posting(
                account_id=debit, direction=Direction.DEBIT, amount=Decimal(amount), currency="USD"
            ),
            Posting(
                account_id=credit,
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="USD",
            ),
        ],
    )


class _Ledger:
    accounts = [
        Account(
            id="salary", user_id=USER, code="4000", name="Salary", type="income", currency="USD"
        ),
        Account(id="cash", user_id=USER, code="1000", name="Savings", type="asset", currency="USD"),
        Account(id="rent", user_id=USER, code="5000", name="Rent", type="expense", currency="USD"),
    ]
    entries = [
        _entry(1, 40, "cash", "salary", "5000"),
        _entry(2, 30, "rent", "cash", "2000"),
    ]

    async def get_accounts(self, user_id, include_inactive=False):
        return self.accounts

    async def get_entries(self, user_id, from_date=None, to_date=None):
        return [e for e in self.entries if from_date is None or e.entry_date >= from_date]


class _Goals:
    async def list(self, user_id, active_only=True):
        return []

    async def list_allocations(self, user_id, goal_id=None):
        return []


class _Scores:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def save(self, user_id, score):
        self.rows.append(score)
        return str(len(self.rows))

    async def get_latest(self, user_id):
        return self.rows[-1] if self.rows else None


class _Strategies:
    def __init__(self, strategy: dict[str, Any] | None = None) -> None:
        self.strategy = strategy

    async def get_latest(self, user_id):
        return self.strategy


class _Profiles:
    def __init__(self, base: str, **row: Any) -> None:
        self.row: dict[str, Any] = {"id": USER, "base_currency": base, **row}

    async def get(self, user_id):
        return dict(self.row)

    async def base_currency(self, user_id):
        return self.row["base_currency"]

    async def upsert(self, user_id, fields):
        self.row.update({k: v for k, v in fields.items() if v is not None})

    async def set_fi_assumptions(self, user_id, values):
        columns = {
            "inflation": "fi_inflation",
            "real_return": "fi_real_return",
            "safe_withdrawal_rate": "fi_safe_withdrawal_rate",
        }
        self.row.update({columns[k]: v for k, v in values.items()})


def _service(base: str = "USD", strategy: dict[str, Any] | None = None, **row: Any):
    profiles = _Profiles(base, **row)
    scores = _Scores()

    class _UoW:
        ledger = _Ledger()
        goals = _Goals()
        fi_scores = scores
        fire_strategies = _Strategies(strategy)
        user_profiles = profiles

    @asynccontextmanager
    async def factory():
        yield _UoW()

    return FiService(factory), profiles, scores, factory


async def test_a_dollar_ledger_uses_the_dollars_defaults():
    svc, *_ = _service("USD")
    projections = await svc.get_projections(USER)
    assumptions = projections["assumptions"]
    assert assumptions["region"] == "USD"
    assert assumptions["inflation"] == {
        "value": "0.02",
        "origin": "default",
        "source": assumptions["inflation"]["source"],
    }
    assert "Federal Reserve" in assumptions["inflation"]["source"]
    assert Decimal(assumptions["real_return"]["value"]) == Decimal("0.04")
    # The figures are the ones computed with them.
    assert projections["expected_inflation"] == "0.02"
    assert Decimal(projections["real_returns"]["base"]) == Decimal("0.04")


async def test_a_rupee_ledger_is_computed_exactly_as_before():
    svc, *_ = _service("LKR")
    projections = await svc.get_projections(USER)
    assert projections["expected_inflation"] == "0.05"
    assert projections["swr"] == "0.04"
    # 10% nominal at 5% inflation, as it always was.
    assert Decimal(projections["real_returns"]["base"]) == Decimal("1.10") / Decimal("1.05") - 1
    assert projections["assumptions"]["region"] == "LKR"


async def test_the_users_own_figures_apply_and_say_so():
    svc, *_ = _service(
        "USD",
        fi_inflation=Decimal("0.030000"),
        fi_safe_withdrawal_rate=Decimal("0.035000"),
    )
    score = await svc.compute_score(USER)
    assumptions = score["assumptions"]
    assert (assumptions["inflation"]["value"], assumptions["inflation"]["origin"]) == (
        "0.03",
        "user",
    )
    assert assumptions["safe_withdrawal_rate"]["origin"] == "user"
    assert score["swr"] == "0.035"
    assert assumptions["real_return"]["origin"] == "default"


async def test_a_strategy_s_figures_apply_unless_the_user_set_their_own():
    strategy = {
        "swr": 0.045,
        "return_conservative": 0.05,
        "return_base": 0.08,
        "return_growth": 0.11,
    }
    svc, *_ = _service("USD", strategy=strategy)
    impact = await svc.simulate_purchase(USER, Decimal("1000"))
    assert impact["assumptions"]["safe_withdrawal_rate"]["origin"] == "strategy"
    assert impact["swr"] == "0.045"

    svc, *_ = _service("USD", strategy=strategy, fi_safe_withdrawal_rate=Decimal("0.03"))
    impact = await svc.simulate_purchase(USER, Decimal("1000"))
    assert impact["assumptions"]["safe_withdrawal_rate"]["origin"] == "user"
    assert impact["swr"] == "0.03"


async def test_changing_ones_own_figure_recomputes_the_stored_score():
    svc, profiles, scores, _ = _service("USD")
    first = await svc.get_or_compute_score(USER)
    assert len(scores.rows) == 1
    assert await svc.get_or_compute_score(USER) is first  # nothing moved

    profiles.row["fi_inflation"] = Decimal("0.04")
    second = await svc.get_or_compute_score(USER)
    assert len(scores.rows) == 2
    assert second["assumptions"]["inflation"]["origin"] == "user"


async def test_the_report_has_what_applies_the_defaults_and_the_users_own():
    svc, *_ = _service("EUR", fi_real_return=Decimal("0.03"))
    report = await svc.assumptions(USER)
    assert report["applied"]["real_return"]["origin"] == "user"
    assert report["defaults"]["real_return"]["origin"] == "default"
    assert "European Central Bank" in report["defaults"]["inflation"]["source"]
    assert report["overrides"] == {
        "inflation": None,
        "real_return": "0.03",
        "safe_withdrawal_rate": None,
    }


async def test_the_strategy_is_asked_to_build_on_the_users_assumptions(monkeypatch):
    """Not the previous strategy's: those come separately, as the strategy."""
    from salli.domain.agents import fire_strategy

    seen: dict[str, Any] = {}

    async def generate(context, *, llm, model=None):
        seen.update(context)
        raise RuntimeError("stop here")

    monkeypatch.setattr(fire_strategy, "generate_strategy", generate)
    svc, *_ = _service("GBP", strategy={"swr": 0.05}, tax_residency="GB")
    stream = svc.generate_strategy(USER, api_key="k")
    try:
        async for _ in stream:
            pass
    except RuntimeError:
        pass

    assert seen["tax_residency"] == "GB"
    assert seen["assumptions"]["region"] == "GBP"
    assert seen["assumptions"]["safe_withdrawal_rate"]["origin"] == "default"


# ── Set on the profile ───────────────────────────────────────────────────────


def _profile_service(profiles: _Profiles, factory) -> UserProfileService:
    from unittest.mock import AsyncMock

    documents = AsyncMock()
    documents.get_memory.return_value = None
    return UserProfileService(factory, AsyncMock(), AsyncMock(), documents)


async def test_the_users_own_figures_are_set_and_cleared_through_the_profile():
    _, profiles, _, factory = _service("USD")
    svc = _profile_service(profiles, factory)

    await svc.update_identity(USER, {"fi_assumptions": {"inflation": Decimal("0.03")}})
    assert (await svc.get_profile(USER))["fi_assumptions"] == {
        "inflation": "0.03",
        "real_return": None,
        "safe_withdrawal_rate": None,
    }

    await svc.update_identity(USER, {"fi_assumptions": {"inflation": None}})
    assert (await svc.get_profile(USER))["fi_assumptions"]["inflation"] is None


async def test_a_figure_that_cannot_be_a_yearly_fraction_is_refused():
    import pytest

    _, profiles, _, factory = _service("USD")
    svc = _profile_service(profiles, factory)
    with pytest.raises(ValueError, match="yearly fraction"):
        await svc.update_identity(USER, {"fi_assumptions": {"inflation": Decimal("3")}})
    with pytest.raises(ValueError, match="Not FI assumptions"):
        await svc.update_identity(USER, {"fi_assumptions": {"growth": Decimal("0.1")}})
    assert profiles.row.get("fi_inflation") is None
