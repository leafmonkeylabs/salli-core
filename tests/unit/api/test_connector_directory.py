"""
What the AI connector directories check of a remote MCP server's sign-in
(docs/connectors.md): RFC 8414 and RFC 9728 metadata that agree with each
other, the authorization code grant with PKCE (S256) for a public client,
dynamic client registration that takes the directories' https callbacks,
a 401 from /mcp that names the resource metadata, and every tool annotated.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

import salli.config
from salli.application.services.mcp_oauth_service import (
    _may_register,  # pyright: ignore[reportPrivateUsage]
)
from salli.config import Settings

ORIGIN = "https://money.example.org"


@asynccontextmanager
async def _client(monkeypatch):
    from salli.interfaces.api.main import create_app

    monkeypatch.setattr(
        salli.config,
        "_settings",
        Settings(
            _env_file=None,
            salli_public_url=ORIGIN,
            database_url="postgresql+asyncpg://salli@127.0.0.1:1/salli",
        ),
    )
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as c,
    ):
        yield c


async def test_the_authorization_server_metadata_has_what_directories_read(monkeypatch):
    async with _client(monkeypatch) as client:
        meta = (await client.get("/.well-known/oauth-authorization-server")).json()
        assert meta["issuer"] == ORIGIN
        for key in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
            assert meta[key].startswith(f"{ORIGIN}/"), key
        assert meta["response_types_supported"] == ["code"]
        assert {"authorization_code", "refresh_token"} <= set(meta["grant_types_supported"])
        assert "S256" in meta["code_challenge_methods_supported"]
        assert "none" in meta["token_endpoint_auth_methods_supported"]
        assert {"mcp:read", "mcp:write"} <= set(meta["scopes_supported"])


@pytest.mark.parametrize(
    "path", ["/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"]
)
async def test_the_protected_resource_metadata_names_this_issuer(monkeypatch, path):
    async with _client(monkeypatch) as client:
        meta = (await client.get(path)).json()
        assert meta["resource"] == f"{ORIGIN}/mcp"
        assert meta["authorization_servers"] == [ORIGIN]
        assert meta["bearer_methods_supported"] == ["header"]
        assert {"mcp:read", "mcp:write"} <= set(meta["scopes_supported"])


async def test_an_unauthenticated_mcp_request_names_the_resource_metadata(monkeypatch):
    async with _client(monkeypatch) as client:
        r = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"accept": "application/json, text/event-stream"},
        )
        assert r.status_code == 401
        challenge = r.headers["www-authenticate"]
        assert challenge.startswith("Bearer ")
        assert f'resource_metadata="{ORIGIN}/.well-known/oauth-protected-resource/mcp"' in challenge
        assert (
            await client.get(f"{ORIGIN}/.well-known/oauth-protected-resource/mcp")
        ).status_code == 200


@pytest.mark.parametrize(
    "callback",
    [
        "https://claude.ai/api/mcp/auth_callback",
        "https://claude.com/api/mcp/auth_callback",
        "https://chatgpt.com/connector_platform_oauth_redirect",
    ],
)
def test_the_directories_callbacks_may_register(callback):
    assert _may_register(callback)


async def test_every_tool_says_whether_it_reads_or_changes():
    from unittest.mock import MagicMock

    from salli.interfaces.api import mcp_server

    server = mcp_server.build_mcp_server(MagicMock(), ORIGIN)
    for tool in await server.list_tools():
        hints = tool.annotations
        assert hints is not None and hints.readOnlyHint is not None, tool.name
        if hints.readOnlyHint is False:
            assert hints.destructiveHint is not None, tool.name
        assert tool.title or hints.title, tool.name
