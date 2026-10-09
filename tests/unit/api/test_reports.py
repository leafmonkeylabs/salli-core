"""The reports routes' responses, from the real ReportService over stubbed ledger and FI services."""

from __future__ import annotations

from decimal import Decimal

import pytest

from salli.application.services.report_service import ReportService
from tests.unit.api.conftest import AUTH, make_account

pytestmark = pytest.mark.asyncio


@pytest.fixture
def reports(mock_services):
    mock_services.reports = ReportService(mock_services.ledger, mock_services.fi)
    return mock_services


async def test_the_balance_sheet(client, reports):
    card = make_account("card", "2000", "Card")
    card.type = "liability"
    reports.ledger.list_accounts.return_value = [make_account("cash", "1000", "Cash"), card]
    reports.ledger.get_trial_balance.return_value = {
        "cash": Decimal("1500.5"),
        "card": Decimal("-200"),
    }

    body = (await client.get("/v1/reports/balance-sheet", headers=AUTH)).json()

    assert body == {
        "currency": "LKR",
        "assets": [{"account_id": "cash", "code": "1000", "name": "Cash", "balance": "1500.50"}],
        "liabilities": [
            {"account_id": "card", "code": "2000", "name": "Card", "balance": "200.00"}
        ],
        "equity": [],
        "total_assets": "1500.50",
        "total_liabilities": "200.00",
        "total_equity": "0.00",
        "net_worth": "1300.50",
    }


async def test_the_net_worth_statement_reads_stored_scores_in_the_currency(client, reports):
    """Stored scores carry str(Decimal), and the oldest ones no currency at all."""
    reports.fi.get_or_compute_score.return_value = {"net_worth": "1300.5"}
    reports.fi.get_score_history.return_value = [
        {"score": 54.25, "net_worth": "1300.5", "created_at": "2026-10-01T06:00:00+00:00"},
        {"score": 50.0, "net_worth": None, "created_at": "2026-09-01T06:00:00+00:00"},
        {"score": 48.0, "net_worth": "900", "created_at": "2026-08-01T06:00:00+00:00"},
    ]

    body = (await client.get("/v1/reports/net-worth", headers=AUTH)).json()

    assert body == {
        "currency": "LKR",
        "current_net_worth": "1300.50",
        "as_of": "2026-10-01T06:00:00+00:00",
        "trend": [
            {"date": "2026-08-01T06:00:00+00:00", "net_worth": "900.00"},
            {"date": "2026-10-01T06:00:00+00:00", "net_worth": "1300.50"},
        ],
    }


def _goal(goal_id: str, progress: float) -> dict:
    """A goal as FiService.list_goals returns it."""
    return {
        "id": goal_id,
        "name": goal_id.title(),
        "kind": "home",
        "currency": "LKR",
        "target_amount": "5000000.00",
        "current_amount": "1250000.00",
        "allocated_amount": "1250000.00",
        "shortfall": "0.00",
        "target_date": "2031-01-01",
        "priority": 1,
        "progress": progress,
        "created_at": "2026-01-01T00:00:00+00:00",
    }


async def test_goal_progress(client, reports):
    reports.fi.list_goals.return_value = [_goal("house", 0.25), _goal("car", 1.0)]

    body = (await client.get("/v1/reports/goal-progress", headers=AUTH)).json()

    assert body == {
        "goals": [_goal("house", 0.25), _goal("car", 1.0)],
        "completed_count": 1,
        "in_progress_count": 1,
    }


async def test_a_report_downloads_as_csv(client, reports):
    reports.fi.list_goals.return_value = [_goal("house", 0.25)]

    r = await client.get("/v1/reports/goal-progress/export", headers=AUTH)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"] == 'attachment; filename="goal-progress.csv"'


async def test_an_unknown_report_cannot_be_downloaded(client, reports):
    r = await client.get("/v1/reports/nope/export", headers=AUTH)

    assert r.status_code == 404
