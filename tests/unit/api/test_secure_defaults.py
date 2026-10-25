"""
Defaults that keep a server safe without anyone setting anything: HSTS over
HTTPS, MCP answering only requests addressed to Salli (DNS rebinding), and a
production server that won't run its workflows in memory.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request

import salli.config
from salli.config import Settings
from salli.interfaces.api import main, mcp_server

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("public_url", "hsts"),
    [("https://money.example.org", "max-age=31536000"), ("http://localhost:8000", None)],
)
async def test_every_response_over_https_says_https_only(monkeypatch, public_url, hsts):
    monkeypatch.setattr(
        salli.config, "_settings", Settings(_env_file=None, salli_public_url=public_url)
    )
    transport = ASGITransport(app=main.create_app())
    async with AsyncClient(transport=transport, base_url=public_url) as client:
        for path in ("/healthz", "/v1/meta", "/no-such-page"):
            r = await client.get(path)
            assert r.headers.get("strict-transport-security") == hsts, path


def _request(host: str, origin: str | None = None) -> Request:
    headers = [(b"host", host.encode()), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    return Request({"type": "http", "method": "POST", "path": "/mcp", "headers": headers})


async def test_mcp_answers_only_requests_addressed_to_salli():
    server = mcp_server.build_mcp_server(
        MagicMock(), "https://money.example.org", ["https://app.example.org"]
    )
    guard = TransportSecurityMiddleware(server.settings.transport_security)

    async def status(host: str, origin: str | None = None) -> int:
        refused = await guard.validate_request(_request(host, origin), is_post=True)
        return 200 if refused is None else refused.status_code

    assert await status("money.example.org") == 200
    assert await status("money.example.org:443") == 200
    assert await status("money.example.org", "https://money.example.org") == 200
    assert await status("money.example.org", "https://app.example.org") == 200
    # A name an attacker points at this server, or a page of theirs.
    assert await status("attacker.test") == 421
    assert await status("money.example.org.attacker.test") == 421
    assert await status("money.example.org", "https://attacker.test") == 403


class _Stop(Exception):
    """The lifespan got past the checkpointer."""


@pytest.mark.parametrize(("environment", "starts"), [("production", False), ("development", True)])
async def test_production_needs_the_postgres_checkpointer(monkeypatch, environment, starts):
    monkeypatch.setattr(
        salli.config, "_settings", Settings(_env_file=None, environment=environment)
    )
    with (
        patch(
            "langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string",
            side_effect=OSError("connection refused"),
        ),
        patch.object(main, "get_services", side_effect=_Stop),
    ):
        expected = _Stop if starts else RuntimeError
        with pytest.raises(expected) as raised:
            async with main.lifespan(MagicMock()):
                pass
    if not starts:
        assert "checkpointer is unavailable in production" in str(raised.value)
