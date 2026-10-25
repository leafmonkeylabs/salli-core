"""The reports routes' responses, from the real ReportService over a baseline
of a small ledger and stubbed ledger and FI services."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from salli.application.services.report_service import ReportService
from tests import baseline_ledger
from tests.baseline_ledger import Ledger
from tests.unit.api.conftest import AUTH, make_account

pytestmark = pytest.mark.asyncio


TODAY = dt.date(2026, 10, 11)


def _books() -> Ledger:
    """Cash, dollars, a card, and a student loan the ledger doesn't hold."""
    books = Ledger("LKR")
    books.account("cash", "asset", name="Cash")
    books.account("usd", "asset", "USD", name="Dollars")
    books.account("card", "liability", name="Card")
    books.account("eq", "equity")
    books.book("2026-10-01", "cash", "eq", "1500.5")
    books.book("2026-10-01", "usd", "eq", "100", currency="USD", fx="290")
    books.book("2026-10-02", "eq", "card", "200")
    books.debt("student-loan", "5000", "0.05", "100")
    books.rate("USD", "300", TODAY.isoformat())
    return books


@pytest.fixture
def reports(mock_services, monkeypatch):
    monkeypatch.setattr(baseline_ledger, "USER", "test-user-1")  # whom AUTH signs in as
    baselines = _books().service(TODAY)
    mock_services.reports = ReportService(mock_services.ledger, mock_services.fi, baselines)
    return mock_services


async def test_the_balance_sheet_is_what_the_baseline_owns_and_owes_today(client, reports):
    equity = make_account("eq", "1003", "Eq")
    equity.type = "equity"
    reports.ledger.list_accounts.return_value = [equity]
    reports.ledger.get_trial_balance.return_value = {"eq": Decimal("-30300.5")}

    body = (await client.get("/v1/reports/balance-sheet", headers=AUTH)).json()

    assert body == {
        "currency": "LKR",
        # 100 USD at today's 300, not the 290 it was booked at.
        "assets": [
            {"account_id": "cash", "code": "1000", "name": "Cash", "balance": "1500.50"},
            {"account_id": "usd", "code": "1001", "name": "Dollars", "balance": "30000.00"},
        ],
        "liabilities": [
            {"account_id": "card", "code": "1002", "name": "Card", "balance": "200.00"},
            {"account_id": None, "code": "", "name": "Student-Loan", "balance": "5000.00"},
        ],
        "equity": [
            {"account_id": "eq", "code": "1003", "name": "Eq", "balance": "30300.50"},
            # Nothing in income or expenses here to close.
            {"account_id": None, "code": "", "name": "Current-year earnings", "balance": "0.00"},
        ],
        "total_assets": "31500.50",
        "total_liabilities": "5200.00",
        "total_equity": "30300.50",
        "net_worth": "26300.50",
        "as_of": TODAY.isoformat(),
        "unrealised_fx": {
            "as_of": TODAY.isoformat(),
            "currency": "LKR",
            "total": "0.00",
            "posted": "0.00",
            "unposted": "0.00",
            "lines": [],
            "notes": [],
        },
        "notes": [],
    }


async def test_the_net_worth_statement_reads_stored_scores_in_the_currency(client, reports):
    """Stored scores carry str(Decimal), and the oldest ones no currency at all."""
    reports.fi.compute_score.return_value = {"net_worth": "1300.5"}
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
