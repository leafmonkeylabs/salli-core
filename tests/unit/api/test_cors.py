"""CORS: a self-hosted server trusts no web origin until told to
(ALLOWED_ORIGINS), in any environment."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

import salli.config
from salli.config import Settings

pytestmark = pytest.mark.asyncio


async def _preflight(monkeypatch, origin: str, **settings) -> dict[str, str]:
    from salli.interfaces.api.main import create_app

    monkeypatch.setattr(salli.config, "_settings", Settings(_env_file=None, **settings))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.options(
            "/v1/auth/me",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
    return dict(r.headers)


@pytest.mark.parametrize("environment", ["production", "development"])
async def test_no_origin_is_trusted_by_default(monkeypatch, environment):
    for origin in (
        "https://app.salli.leafmonkey.org",
        "https://evil.example",
        "http://localhost:3000",
    ):
        headers = await _preflight(monkeypatch, origin, environment=environment)
        assert "access-control-allow-origin" not in headers


async def test_only_the_origins_named_are_trusted(monkeypatch):
    allowed = {"allowed_origins": "https://money.example.org, https://other.example.org/"}
    trusted = await _preflight(monkeypatch, "https://other.example.org", **allowed)
    assert trusted["access-control-allow-origin"] == "https://other.example.org"
    assert "access-control-allow-origin" not in await _preflight(
        monkeypatch, "https://evil.example", **allowed
    )


async def test_allowed_origins_reads_a_comma_separated_list_from_the_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example/ ,")
    assert Settings(_env_file=None).allowed_origins == ["https://a.example", "https://b.example"]
    monkeypatch.delenv("ALLOWED_ORIGINS")
    assert Settings(_env_file=None).allowed_origins == []
