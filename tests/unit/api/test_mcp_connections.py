"""
The MCP connection settings answer with what the OAuth service lists, encoded
as clients have always received it.
"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock

from fastapi.encoders import jsonable_encoder

from .conftest import AUTH


def _connection() -> dict:
    """What SQLOAuthTokenRepository.list_active_connections returns."""
    return {
        "token_id": "tok-1",
        "client_id": "client-1",
        "client_name": "Unnamed app",
        "scope": "salli",
        "connected_at": datetime.datetime(2026, 10, 9, 8, 30, 5, 120000, tzinfo=datetime.UTC),
    }


async def test_connections_are_listed_as_the_service_returns_them(client, mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.list_connections.return_value = [_connection()]

    r = await client.get("/v1/mcp/connections/", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == jsonable_encoder({"connections": [_connection()]})


async def test_connected_at_keeps_its_utc_offset(client, mock_services):
    """A typed datetime would go out as "...Z"; clients have been sent
    "...+00:00", and still are."""
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.list_connections.return_value = [_connection()]

    r = await client.get("/v1/mcp/connections/", headers=AUTH)

    assert r.json()["connections"][0]["connected_at"] == "2026-10-09T08:30:05.120000+00:00"


async def test_whether_mcp_is_enabled(client, mock_services):
    mock_services.mcp_oauth = AsyncMock()
    mock_services.mcp_oauth.is_mcp_enabled.return_value = True

    r = await client.get("/v1/mcp/connections/enabled", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == {"enabled": True}
