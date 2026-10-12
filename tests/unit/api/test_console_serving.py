"""
Serving the console at /console (docs/design/console.md, sections 1 and 2;
decisions 1, 2, 7 and 23): the switch, the files, deep links, caching, the
headers on every response, nothing outside the build, `no-store` on the API,
and where /v1/meta says the console is.
"""

from __future__ import annotations

import gzip
import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import salli.config
from salli.config import Settings, is_secure_origin
from salli.interfaces.api.console import CONSOLE_CSP, CONSOLE_HEADERS

INDEX = "<!doctype html><title>Salli</title><div id=root></div>"
APP_JS = "console.log('the console')"


@pytest.fixture
def built(tmp_path: Path) -> Path:
    """A console as its build leaves it, and a secret beside it."""
    dist = tmp_path / "console"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX)
    (dist / "favicon.svg").write_text("<svg/>")
    (dist / "assets" / "app-3f9a.js").write_text(APP_JS)
    (dist / "assets" / "app-3f9a.js.gz").write_bytes(gzip.compress(APP_JS.encode()))
    (dist / "assets" / "app-3f9a.js.br").write_bytes(b"brotli bytes")
    (dist / ".env").write_text("SECRET=1")
    (tmp_path / "secret.txt").write_text("not the console's")
    os.symlink(tmp_path / "secret.txt", dist / "assets" / "linked.js")
    return dist


async def _client(monkeypatch, **settings) -> AsyncClient:
    from salli.interfaces.api.main import create_app

    monkeypatch.setattr(salli.config, "_settings", Settings(_env_file=None, **settings))
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://localhost:8000")


def _assert_console_headers(headers) -> None:
    for name, value in CONSOLE_HEADERS.items():
        assert headers[name.lower()] == value, name


def test_the_csp_is_the_design_s():
    for directive in (
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "require-trusted-types-for 'script'",
        "trusted-types 'none'",
    ):
        assert directive in CONSOLE_CSP
    assert "unsafe" not in CONSOLE_CSP and "http" not in CONSOLE_CSP


async def test_the_console_is_served_with_its_headers(monkeypatch, built):
    async with await _client(monkeypatch, salli_console_dir=str(built)) as client:
        for path in ("/console", "/console/", "/console/callback", "/console/decisions/abc/2026"):
            r = await client.get(path)
            assert r.status_code == 200, path
            assert r.text == INDEX
            assert r.headers["content-type"].startswith("text/html")
            assert r.headers["cache-control"] == "no-cache"
            _assert_console_headers(r.headers)
        head = await client.head("/console/settings")
        assert head.status_code == 200 and head.content == b""


async def test_hashed_assets_are_immutable_and_precompressed(monkeypatch, built):
    async with await _client(monkeypatch, salli_console_dir=str(built)) as client:
        plain = await client.get("/console/assets/app-3f9a.js", headers={"Accept-Encoding": ""})
        assert plain.text == APP_JS
        assert plain.headers["content-type"].startswith("text/javascript")
        assert plain.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert plain.headers["vary"] == "Accept-Encoding"
        _assert_console_headers(plain.headers)

        gz = await client.get("/console/assets/app-3f9a.js", headers={"Accept-Encoding": "gzip"})
        assert gz.headers["content-encoding"] == "gzip" and gz.text == APP_JS

        br = await client.get(
            "/console/assets/app-3f9a.js", headers={"Accept-Encoding": "gzip, br"}
        )
        assert br.headers["content-encoding"] == "br"

        favicon = await client.get("/console/favicon.svg")
        assert favicon.headers["content-type"] == "image/svg+xml"
        assert favicon.headers["cache-control"] == "no-cache"


async def test_a_missing_asset_is_a_404_with_the_headers(monkeypatch, built):
    async with await _client(monkeypatch, salli_console_dir=str(built)) as client:
        r = await client.get("/console/assets/gone-0000.js")
        assert r.status_code == 404
        _assert_console_headers(r.headers)


@pytest.mark.parametrize(
    "path",
    [
        "/console/%2e%2e/secret.txt",
        "/console/assets/%2e%2e/%2e%2e/secret.txt",
        "/console/..%2fsecret.txt",
        "/console/assets/..%2f..%2fsecret.txt",
        "/console/%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "/console/.env",
        "/console/assets/.%2e/index.html",
        "/console/assets/..%5c..%5csecret.txt",
        "/console/assets/%00.js",
        "/console//etc/passwd",
    ],
)
async def test_nothing_outside_the_build_is_served(monkeypatch, built, path):
    async with await _client(monkeypatch, salli_console_dir=str(built)) as client:
        r = await client.get(path)
    assert "not the console's" not in r.text
    assert "SECRET" not in r.text
    assert r.status_code == 404, (path, r.status_code)
    _assert_console_headers(r.headers)


async def test_a_symbolic_link_out_of_the_build_is_not_followed(monkeypatch, built):
    async with await _client(monkeypatch, salli_console_dir=str(built)) as client:
        r = await client.get("/console/assets/linked.js")
    assert r.status_code == 404 and "not the console's" not in r.text


async def test_switched_off_there_is_no_console_and_meta_says_so(monkeypatch, built):
    async with await _client(
        monkeypatch, salli_console=False, salli_console_dir=str(built)
    ) as client:
        meta = (await client.get("/v1/meta")).json()
        assert meta["console_url"] is None
        assert meta["oauth"]["console_client_id"] == "salli-console"
        # No route: /console is whatever any unknown path is, and not the console.
        for path in ("/console", "/console/assets/app-3f9a.js"):
            r = await client.get(path)
            assert r.status_code == 404 and INDEX not in r.text, path


async def test_without_a_built_console_there_is_none(monkeypatch, tmp_path):
    for console_dir in ("", str(tmp_path)):
        async with await _client(monkeypatch, salli_console_dir=console_dir) as client:
            assert (await client.get("/v1/meta")).json()["console_url"] is None
            assert (await client.get("/console")).status_code == 404


async def test_meta_names_the_console_at_the_public_url(monkeypatch, built):
    async with await _client(
        monkeypatch, salli_console_dir=str(built), salli_public_url="https://money.example.org/"
    ) as client:
        meta = (await client.get("/v1/meta")).json()
    assert meta["console_url"] == "https://money.example.org/console"


async def test_api_responses_are_never_stored(monkeypatch, built):
    async with await _client(monkeypatch, salli_console_dir=str(built)) as client:
        for path in (
            "/v1/meta",
            "/healthz",
            "/v1/auth/me",
            "/.well-known/oauth-authorization-server",
        ):
            r = await client.get(path)
            assert r.headers["cache-control"] == "no-store", path
        # The console's own files keep theirs.
        assert (await client.get("/console")).headers["cache-control"] == "no-cache"


@pytest.mark.parametrize(
    ("url", "secure"),
    [
        ("https://money.example.org", True),
        ("http://localhost:8000", True),
        ("http://127.0.0.1:8000", True),
        ("http://[::1]:8000", True),
        ("http://salli.localhost", True),
        ("http://192.168.1.20:8000", False),
        ("http://money.example.org", False),
        ("ftp://localhost", False),
    ],
)
def test_a_secure_context_is_https_or_this_machine(url, secure):
    assert is_secure_origin(url) is secure
