"""
The FI routes' response models against what FiService really returns.

The router tests stub the service; these run the real one over an in-memory
unit of work, so a figure the service adds, renames or formats differently
fails here instead of in a client.
"""

from __future__ import annotations

import datetime
import re
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeProfiles
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

_ACCOUNTS = [
    Account(id="salary", user_id="u1", code="4000", name="Salary", type="income", currency="LKR"),
    Account(id="savings", user_id="u1", code="1000", name="Savings", type="asset", currency="LKR"),
    Account(
        id="funds", user_id="u1", code="1100", name="Unit Trusts", type="asset", currency="LKR"
    ),
    Account(id="card", user_id="u1", code="2000", name="Card", type="liability", currency="LKR"),
    Account(id="food", user_id="u1", code="5000", name="Groceries", type="expense", currency="LKR"),
]


def _entry(n: int, days_ago: int, debit: str, credit: str, amount: str) -> StoredJournalEntry:
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    return StoredJournalEntry(
        id=f"e{n}",
        user_id="u1",
        entry_date=day.isoformat(),
        description="",
        source="manual",
        postings=[
            Posting(
                account_id=debit, direction=Direction.DEBIT, amount=Decimal(amount), currency="LKR"
            ),
            Posting(
                account_id=credit,
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="LKR",
            ),
        ],
    )


_ENTRIES = [
    _entry(1, 60, "savings", "salary", "300000.00"),
    _entry(2, 30, "savings", "salary", "300000.00"),
    _entry(3, 20, "food", "card", "45000.50"),
    _entry(4, 10, "funds", "savings", "200000.00"),
]


class _Ledger:
    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Account]:
        return _ACCOUNTS

    async def get_entries(self, user_id: str, from_date: str | None = None, to_date=None):
        return [e for e in _ENTRIES if from_date is None or e.entry_date >= from_date]


class _Goals:
    async def list(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        return [
            {
                "id": "house",
                "name": "House",
                "kind": "home",
                "target_amount_minor": 500_000_000,
                "current_amount_minor": 0,
                "target_date": "2031-01-01",
                "priority": 1,
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        ]

    async def list_allocations(self, user_id: str, goal_id: str | None = None):
        return [{"id": "a1", "goal_id": "house", "account_id": "savings", "allocated_minor": 1}]


class _Scores:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def save(self, user_id: str, score: dict[str, Any]) -> str:
        self.rows.append(score)
        return str(len(self.rows))

    async def get_latest(self, user_id: str) -> dict[str, Any] | None:
        return self.rows[-1] if self.rows else None

    async def history(self, user_id: str, limit: int = 90) -> list[dict[str, Any]]:
        return [
            {"score": float(r["overall_score"]), "net_worth": r.get("net_worth"), "created_at": "x"}
            for r in reversed(self.rows)
        ]


class _Strategies:
    """A strategy as the model writes one: rates as floats, and a target whose
    FI number divides exactly (1800000.0 / 0.04), which Decimal renders as
    "4.500000E+7"."""

    async def get_latest(self, user_id: str) -> dict[str, Any]:
        return {
            "version": 1,
            "created_at": "2026-09-01T00:00:00+00:00",
            "fire_style": "standard",
            "swr": 0.04,
            "return_conservative": 0.06,
            "return_base": 0.1,
            "return_growth": 0.14,
            "target_monthly_expenses": 150000.0,
            "target_age": 50,
            "buckets": [
                {
                    "key": "moat",
                    "name": "Emergency Moat",
                    "target_pct": 1.0,
                    "description": "Six months of spending.",
                    "color": "emerald",
                }
            ],
            "ai_rationale": "Build the moat first.",
            "theories_applied": ["Trinity Study"],
            "is_initial": True,
        }

    async def get_history(self, user_id: str) -> list[dict[str, Any]]:
        return [{"version": 1, "created_at": "x", "fire_style": "standard", "theories_applied": []}]


@pytest.fixture
def fi(mock_services) -> FiService:
    scores = _Scores()

    class _UoW:
        ledger = _Ledger()
        goals = _Goals()
        fi_scores = scores
        fire_strategies = _Strategies()
        user_profiles = FakeProfiles()

    @asynccontextmanager
    async def factory():
        yield _UoW()

    mock_services.fi = FiService(factory)
    return mock_services.fi


#: An LKR amount as the API sends one: a plain decimal string with two decimals.
_LKR = re.compile(r"-?\d+\.\d{2}")


async def test_the_service_raw_fi_number_is_an_exact_quotient_in_exponent_form(fi):
    """Why the router normalises money: the service's own string is no Amount."""
    score = await fi.compute_score("u1")
    assert "E+" in score["fi_number"]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/v1/fi/score", None),
        ("post", "/v1/fi/score/recompute", None),
        ("get", "/v1/fi/score/history", None),
        ("get", "/v1/fi/projections", None),
        ("get", "/v1/fi/surplus", None),
        ("post", "/v1/fi/simulate-purchase", {"amount": "450000", "term_months": 12}),
        ("get", "/v1/fi/goals", None),
        ("get", "/v1/fi/goals/house/allocations", None),
        ("get", "/v1/fi/strategy", None),
        ("get", "/v1/fi/strategy/history", None),
    ],
)
async def test_each_route_returns_what_the_service_computes(client, fi, method, path, body):
    kwargs: dict[str, Any] = {"headers": AUTH}
    if body is not None:
        kwargs["json"] = body
    r = await getattr(client, method)(path, **kwargs)
    assert r.status_code == 200, r.text


async def test_amounts_are_at_the_currency_precision(client, fi):
    score = (await client.get("/v1/fi/score", headers=AUTH)).json()
    assert score["fi_number"] == "45000000.00"
    assert score["currency"] == "LKR"

    impact = (
        await client.post(
            "/v1/fi/simulate-purchase", json={"amount": "450000", "term_months": 12}, headers=AUTH
        )
    ).json()
    # The same Freedom number, however it was reached.
    assert impact["fi_number"] == score["fi_number"]
    installments = next(o for o in impact["options"] if o["key"] == "installments")
    for key in ("total_cost", "interest_cost", "monthly_payment"):
        assert _LKR.fullmatch(installments[key]), installments[key]

    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    assert projections["fi_number"] == score["fi_number"]
    assert all(_LKR.fullmatch(p["base"]) for p in projections["points"])


async def test_every_fi_figure_says_which_assumptions_it_used(client, fi):
    """A rupee ledger: Sri Lanka's figures, as defaults, with their sources."""
    score = (await client.get("/v1/fi/score", headers=AUTH)).json()
    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    impact = (
        await client.post("/v1/fi/simulate-purchase", json={"amount": "450000"}, headers=AUTH)
    ).json()

    for body in (score, projections, impact):
        assumptions = body["assumptions"]
        assert assumptions["region"] == "LKR"
        assert assumptions["inflation"]["value"] == "0.05"
        assert assumptions["inflation"]["origin"] == "default"
        assert "Central Bank of Sri Lanka" in assumptions["inflation"]["source"]
        # The stored strategy's rate and returns: it has one.
        assert assumptions["safe_withdrawal_rate"]["origin"] == "strategy"
        assert assumptions["real_return"]["origin"] == "strategy"


async def test_the_assumptions_route_reports_what_applies_and_the_defaults(client, fi):
    body = (await client.get("/v1/fi/assumptions", headers=AUTH)).json()
    assert body["applied"]["safe_withdrawal_rate"]["origin"] == "strategy"
    assert body["defaults"]["safe_withdrawal_rate"] == {
        "value": "0.04",
        "origin": "default",
        "source": body["defaults"]["safe_withdrawal_rate"]["source"],
    }
    assert body["overrides"] == {
        "inflation": None,
        "real_return": None,
        "safe_withdrawal_rate": None,
    }
