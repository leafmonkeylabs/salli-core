"""
Agent documents and reminders over HTTP. Both pass repository rows through,
so these pin the row shapes, including the fields that are null on some rows.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.unit.api.conftest import AUTH

NOTE = {
    "id": "doc-1",
    "user_id": "test-user-1",
    "title": "Tax notes",
    "content": "Ask about the APIT certificate.",
    "storage_key": None,
    "mime_type": "text/plain",
    "tags": ["tax"],
    "source": "agent_created",
    "namespace": "documents",
    "slug": None,
    "description": None,
    "created_at": "2025-04-05T10:00:00+00:00",
    "updated_at": "2025-04-05T10:00:00+00:00",
}

UPLOAD = {
    **NOTE,
    "id": "doc-2",
    "title": "receipt.pdf",
    "content": None,
    "storage_key": "test-user-1/agent-uploads/doc-2/receipt.pdf",
    "mime_type": "application/pdf",
    "tags": ["upload"],
    "source": "user_upload",
}

DEADLINE = {
    "id": "r1",
    "kind": "return_due_2025/26",
    "due_date": "2026-11-30",
    "status": "pending",
    "alert_type": None,
    "source_domain": None,
    "source_id": None,
    "severity": None,
    "created_at": "2025-04-01T00:00:00+00:00",
}

ALERT = {
    "id": "r2",
    "kind": "No active health insurance coverage",
    "due_date": "2025-04-05",
    "status": "pending",
    "alert_type": "coverage_missing",
    "source_domain": "insurance",
    "source_id": "health",
    "severity": "critical",
    "created_at": "2025-04-05T00:00:00+00:00",
}


@pytest.fixture(autouse=True)
def _services(mock_services):
    mock_services.documents = AsyncMock()
    mock_services.reminders = AsyncMock()


async def test_documents_list(client, mock_services):
    mock_services.documents.list_documents.return_value = [NOTE, UPLOAD]
    r = await client.get("/v1/documents/", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"documents": [NOTE, UPLOAD], "count": 2}


async def test_a_document(client, mock_services):
    mock_services.documents.get_document.return_value = UPLOAD
    r = await client.get("/v1/documents/doc-2", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == UPLOAD


async def test_a_missing_document_is_a_404(client, mock_services):
    mock_services.documents.get_document.return_value = None
    r = await client.get("/v1/documents/nope", headers=AUTH)
    assert r.status_code == 404


async def test_reminders_list_holds_deadlines_and_alerts(client, mock_services):
    mock_services.reminders.list_reminders.return_value = [DEADLINE, ALERT]
    r = await client.get("/v1/reminders/", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"reminders": [DEADLINE, ALERT]}

    r = await client.get("/v1/reminders/", params={"alerts_only": True}, headers=AUTH)
    assert r.json() == {"reminders": [ALERT]}


async def test_creating_a_reminder_returns_its_id(client, mock_services):
    mock_services.reminders.create_reminder.return_value = "r3"
    r = await client.post(
        "/v1/reminders/", json={"kind": "Gather statements", "due_date": "2026-01-31"}, headers=AUTH
    )
    assert r.status_code == 201
    assert r.json() == {"id": "r3"}


async def test_seeding_the_filing_calendar(client, mock_services):
    mock_services.reminders.seed_filing_calendar.return_value = ["r4", "r5"]
    r = await client.post("/v1/reminders/seed", headers=AUTH)
    assert r.status_code == 201
    assert r.json() == {"created": 2, "ids": ["r4", "r5"]}


async def test_syncing_alerts_counts_them_by_type(client, mock_services):
    mock_services.reminders.sync_alerts.return_value = {
        "budget_overspend": 2,
        "coverage_missing": 1,
    }
    r = await client.post("/v1/reminders/sync-alerts", headers=AUTH)
    assert r.status_code == 201
    assert r.json() == {"counts": {"budget_overspend": 2, "coverage_missing": 1}, "total": 3}
