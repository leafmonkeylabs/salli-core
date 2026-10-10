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
    Account(id="salary", user_id="u1", code="4000", name="Salary", type="income", currency="KES"),
    Account(id="savings", user_id="u1", code="1000", name="Savings", type="asset", currency="KES"),
    Account(
        id="funds", user_id="u1", code="1100", name="Unit Trusts", type="asset", currency="KES"
    ),
    Account(id="card", user_id="u1", code="2000", name="Card", type="liability", currency="KES"),
    Account(id="food", user_id="u1", code="5000", name="Groceries", type="expense", currency="KES"),
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
                account_id=debit, direction=Direction.DEBIT, amount=Decimal(amount), currency="KES"
            ),
            Posting(
                account_id=credit,
                direction=Direction.CREDIT,
                amount=Decimal(amount),
                currency="KES",
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
            "real_return_conservative": 0.02,
            "real_return_base": 0.04,
            "real_return_growth": 0.06,
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
        user_profiles = FakeProfiles("KES")

    @asynccontextmanager
    async def factory():
        yield _UoW()

    mock_services.fi = FiService(factory)
    return mock_services.fi


#: A KES amount as the API sends one: a plain decimal string with two decimals.
_AMOUNT = re.compile(r"-?\d+\.\d{2}")


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
    assert score["currency"] == "KES"

    impact = (
        await client.post(
            "/v1/fi/simulate-purchase", json={"amount": "450000", "term_months": 12}, headers=AUTH
        )
    ).json()
    # The same Freedom number, however it was reached.
    assert impact["fi_number"] == score["fi_number"]
    installments = next(o for o in impact["options"] if o["key"] == "installments")
    for key in ("total_cost", "interest_cost", "monthly_payment"):
        assert _AMOUNT.fullmatch(installments[key]), installments[key]

    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    assert projections["fi_number"] == score["fi_number"]
    assert all(_AMOUNT.fullmatch(p["base"]) for p in projections["points"])


async def test_every_fi_figure_says_which_assumptions_it_used(client, fi):
    """The stored strategy's rate and real returns, and no inflation: so no
    placeholder, and no nominal figure."""
    score = (await client.get("/v1/fi/score", headers=AUTH)).json()
    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    impact = (
        await client.post("/v1/fi/simulate-purchase", json={"amount": "450000"}, headers=AUTH)
    ).json()

    for body in (score, projections, impact):
        assumptions = body["assumptions"]
        assert assumptions["status"] == "user"
        assert assumptions["placeholders"] == []
        assert assumptions["inflation"] is None
        assert assumptions["safe_withdrawal_rate"]["origin"] == "strategy"
        assert assumptions["real_return"]["origin"] == "strategy"
        assert assumptions["real_returns"] == {
            "conservative": "0.02",
            "base": "0.04",
            "growth": "0.06",
        }
    assert projections["terms"] == "real"
    assert projections["inflation"] is None


async def test_the_assumptions_route_reports_what_applies_and_the_placeholders(client, fi):
    body = (await client.get("/v1/fi/assumptions", headers=AUTH)).json()
    assert body["applied"]["safe_withdrawal_rate"]["origin"] == "strategy"
    assert body["placeholder_values"]["safe_withdrawal_rate"]["value"] == "0.04"
    assert body["placeholder_values"]["real_return"]["source"].startswith("Placeholder:")
    assert body["own"] == {
        "real_return": None,
        "nominal_return": None,
        "inflation": None,
        "safe_withdrawal_rate": None,
    }
    assert body["scenario_spread"] == "0.02"


async def test_setting_inflation_brings_nominal_figures_to_the_projections(client, fi):
    r = await client.patch(
        "/v1/fi/assumptions",
        json={"inflation": {"value": "0.03", "source": "https://example.org/cpi"}},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    assert r.json()["own"]["inflation"]["source"] == "https://example.org/cpi"

    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    assert projections["terms"] == "real_and_nominal"
    assert projections["inflation"] == "0.03"
    year_one = projections["points"][1]
    assert _AMOUNT.fullmatch(year_one["nominal"]["base"])
    assert _AMOUNT.fullmatch(year_one["nominal"]["fi_number"])
    assert projections["assumptions"]["inflation"]["origin"] == "user"
