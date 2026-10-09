"""
Request-correlation middleware.

The 500 test is the load-bearing one: it only passes while the exception is
handled *inside* RequestContextMiddleware. If someone moves that handling to
`@app.exception_handler(Exception)`, Starlette's ServerErrorMiddleware takes over,
re-raises, and this test fails with a raised RuntimeError instead of a 500 —
which is exactly the production symptom (a 500 with no CORS headers that the
browser discards).
"""

import uuid

import pytest

from tests.unit.api.conftest import AUTH

ORIGIN = {"Origin": "https://app.salli.lk"}


@pytest.mark.asyncio
async def test_request_id_header_present(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    uuid.UUID(r.headers["x-request-id"])  # raises if it isn't a UUID


@pytest.mark.asyncio
async def test_client_supplied_request_id_is_echoed(client):
    r = await client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


@pytest.mark.asyncio
async def test_unhandled_exception_returns_json_with_request_id(client, mock_services):
    mock_services.ledger.list_accounts.side_effect = RuntimeError("boom")
    r = await client.get("/accounts/", headers=AUTH)
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error"
    assert body["request_id"] == r.headers["x-request-id"]


@pytest.mark.asyncio
async def test_cors_exposes_request_id(client):
    r = await client.get("/healthz", headers=ORIGIN)
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()
