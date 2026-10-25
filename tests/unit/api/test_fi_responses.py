"""
The FI routes' response models against what FiService really returns.

The router tests stub the service; these run the real one over an in-memory
unit of work, so a figure the service adds, renames or formats differently
fails here instead of in a client.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal
from typing import Any

import pytest

from salli.application.services.fi_service import FiService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from tests.fakes import FakeUoW
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

#: The user the test client signs in as (conftest's AUTH).
_USER = "test-user-1"

_ACCOUNTS = [
    Account(id="salary", user_id=_USER, code="4000", name="Salary", type="income", currency="KES"),
    Account(id="savings", user_id=_USER, code="1000", name="Savings", type="asset", currency="KES"),
    Account(
        id="funds", user_id=_USER, code="1100", name="Unit Trusts", type="asset", currency="KES"
    ),
    Account(id="card", user_id=_USER, code="2000", name="Card", type="liability", currency="KES"),
    Account(
        id="food", user_id=_USER, code="5000", name="Groceries", type="expense", currency="KES"
    ),
]


def _entry(n: int, days_ago: int, debit: str, credit: str, amount: str) -> StoredJournalEntry:
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    return StoredJournalEntry(
        id=f"e{n}",
        user_id=_USER,
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
    _entry(5, 45, "food", "savings", "150000.00"),
    _entry(6, 75, "food", "savings", "150000.00"),
]


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


@pytest.fixture
def fi(mock_services) -> FiService:
    uow = FakeUoW("KES")
    uow.ledger.accounts = list(_ACCOUNTS)
    uow.ledger.entries = list(_ENTRIES)
    uow.goals = _Goals()  # type: ignore[assignment]
    uow.fi_scores = _Scores()  # type: ignore[assignment]
    mock_services.fi = FiService(uow.factory())
    return mock_services.fi


#: A KES amount as the API sends one: a plain decimal string with two decimals.
_AMOUNT = re.compile(r"-?\d+\.\d{2}")


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/v1/fi/score", None),
        ("post", "/v1/fi/score/recompute", None),
        ("get", "/v1/fi/score/history", None),
        ("get", "/v1/fi/projections", None),
        ("get", "/v1/fi/surplus", None),
        ("get", "/v1/fi/goals", None),
        ("get", "/v1/fi/goals/house/allocations", None),
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
    assert _AMOUNT.fullmatch(score["fi_number"]) and score["fi_number"] != "0.00"
    assert score["currency"] == "KES"

    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    assert projections["fi_number"] == score["fi_number"]
    assert all(_AMOUNT.fullmatch(p["base"]) for p in projections["points"])


async def test_a_score_on_too_little_data_says_so(client, mock_services):
    """Under two full months of income and spending the score is still
    computed, and says it isn't worth showing."""
    uow = FakeUoW("KES")
    uow.ledger.accounts = list(_ACCOUNTS)
    uow.ledger.entries = [_entry(1, 0, "savings", "salary", "300000.00")]
    mock_services.fi = FiService(uow.factory())

    score = (await client.get("/v1/fi/score", headers=AUTH)).json()
    assert (score["status"], score["months_observed"]) == ("not_enough_data", 0)
    assert "overall_score" in score and "grade" in score


async def test_every_fi_figure_says_which_assumptions_it_used(client, fi):
    """The placeholders, and no inflation: so no nominal figure, until the
    user sets their own."""
    score = (await client.get("/v1/fi/score", headers=AUTH)).json()
    projections = (await client.get("/v1/fi/projections", headers=AUTH)).json()
    for body in (score, projections):
        assumptions = body["assumptions"]
        assert assumptions["status"] == "placeholder"
        assert assumptions["placeholders"] == [
            "real_return",
            "safe_withdrawal_rate",
            "surplus_invested",
        ]
        assert assumptions["surplus_invested"]["value"] == "1"
        assert assumptions["inflation"] is None
        assert assumptions["safe_withdrawal_rate"]["origin"] == "placeholder"
        assert assumptions["real_returns"] == {
            "conservative": "0.02",
            "base": "0.04",
            "growth": "0.06",
        }
    assert projections["terms"] == "real"
    assert projections["inflation"] is None

    r = await client.patch(
        "/v1/fi/assumptions",
        json={
            "surplus_invested": {"value": "0.75", "source": "my standing orders"},
            "real_return": {"value": "0.03", "source": "https://example.org/returns"},
            "safe_withdrawal_rate": {"value": "0.035"},
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    for path in ("/v1/fi/score", "/v1/fi/projections"):
        assumptions = (await client.get(path, headers=AUTH)).json()["assumptions"]
        assert (assumptions["status"], assumptions["placeholders"]) == ("user", [])
        assert assumptions["surplus_invested"] == {
            "value": "0.75",
            "origin": "user",
            "source": "my standing orders",
            "note": None,
        }


@pytest.mark.parametrize("value", ["80", "1.01", "-0.1"])
async def test_the_share_of_the_surplus_invested_is_from_0_to_1(client, fi, value):
    """A share, not a rate: out of range is a 422 that says how to write it,
    and changes nothing."""
    r = await client.patch(
        "/v1/fi/assumptions", json={"surplus_invested": {"value": value}}, headers=AUTH
    )
    assert r.status_code == 422, r.text
    assert "a share from 0 to 1 (0.8 for 80%)" in r.text
    body = (await client.get("/v1/fi/assumptions", headers=AUTH)).json()
    assert body["own"]["surplus_invested"] is None
    for edge in ("0", "1"):
        r = await client.patch(
            "/v1/fi/assumptions", json={"surplus_invested": {"value": edge}}, headers=AUTH
        )
        assert r.status_code == 200, r.text
        assert r.json()["applied"]["surplus_invested"]["value"] == edge


async def test_the_assumptions_route_reports_what_applies_and_the_placeholders(client, fi):
    body = (await client.get("/v1/fi/assumptions", headers=AUTH)).json()
    assert body["applied"]["safe_withdrawal_rate"]["origin"] == "placeholder"
    assert body["placeholder_values"]["safe_withdrawal_rate"]["value"] == "0.0314"
    assert body["placeholder_values"]["real_return"]["source"].startswith("Placeholder:")
    assert body["placeholder_values"]["surplus_invested"] == {
        "value": "1",
        "source": "Placeholder: all of your monthly surplus is assumed invested at the real "
        "return; set what you actually invest.",
    }
    assert body["applied"]["surplus_invested"]["origin"] == "placeholder"
    assert body["own"] == {
        "real_return": None,
        "nominal_return": None,
        "inflation": None,
        "volatility": None,
        "safe_withdrawal_rate": None,
        "surplus_invested": None,
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
