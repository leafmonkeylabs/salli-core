"""
Salli's OAuth server, for both kinds of client it serves.

AI clients get tokens for MCP; Salli's own CLI gets tokens for the REST API.
Each resource accepts only its own tokens, the MCP switch governs only MCP, a
native app's loopback redirect works on any port, and a device without a
browser can be signed in with a code.
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from salli.application.services.mcp_oauth_service import (
    API,
    MCP,
    DeviceFlowError,
    McpOAuthService,
    OAuthError,
)

BASE = "https://salli.test"
USER = "u1"


class Clients:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def register(self, client_name, redirect_uris):
        client_id = f"c{len(self.rows) + 1}"
        self.rows[client_id] = {
            "client_id": client_id,
            "client_name": client_name,
            "redirect_uris": redirect_uris,
        }
        return self.rows[client_id]

    async def get(self, client_id):
        return self.rows.get(client_id)


class Tokens:
    def __init__(self) -> None:
        self.codes: dict[str, dict[str, Any]] = {}
        self.access: dict[str, dict[str, Any]] = {}
        self.refresh: dict[str, dict[str, Any]] = {}
        self.devices: dict[str, dict[str, Any]] = {}

    async def save_authorization_code(self, code, **fields):
        self.codes[code] = fields

    async def get_authorization_code(self, code):
        return self.codes.get(code)

    async def delete_authorization_code(self, code):
        self.codes.pop(code, None)

    async def save_access_token(self, token_hash, **fields):
        token_id = f"t{len(self.access) + 1}"
        self.access[token_hash] = {"id": token_id, **fields, "revoked": False}
        return token_id

    async def save_refresh_token(self, token_hash, **fields):
        self.refresh[token_hash] = {**fields, "revoked": False}

    async def get_access_token(self, token_hash):
        row = self.access.get(token_hash)
        return None if row is None or row["revoked"] else row

    async def get_refresh_token(self, token_hash):
        row = self.refresh.get(token_hash)
        return None if row is None or row["revoked"] else row

    async def revoke_refresh_token(self, token_hash):
        if token_hash in self.refresh:
            self.refresh[token_hash]["revoked"] = True

    async def list_active_connections(self, user_id, resource=None):
        return [
            {"token_id": r["id"], "client_id": r["client_id"], "resource": r["resource"]}
            for r in self.access.values()
            if r["user_id"] == user_id and not r["revoked"]
        ]

    async def save_device_code(self, device_code_hash, **fields):
        self.devices[device_code_hash] = {
            "id": device_code_hash,
            **fields,
            "status": "pending",
            "user_id": None,
            "last_polled_at": None,
        }

    async def get_device_code(self, device_code_hash):
        return self.devices.get(device_code_hash)

    async def get_device_code_by_user_code(self, user_code):
        return next(
            (
                d
                for d in self.devices.values()
                if d["user_code"] == user_code
                and d["status"] == "pending"
                and d["expires_at"] > datetime.now(UTC)
            ),
            None,
        )

    async def update_device_code(self, device_id, **fields):
        self.devices[device_id].update(fields)


class Profiles:
    def __init__(self, mcp_enabled: bool) -> None:
        self.mcp_enabled = mcp_enabled

    async def get(self, user_id):
        return {"id": user_id, "mcp_enabled": self.mcp_enabled}

    async def upsert(self, user_id, fields):
        self.mcp_enabled = fields.get("mcp_enabled", self.mcp_enabled)


@pytest.fixture
def world():
    clients, tokens, profiles = Clients(), Tokens(), Profiles(mcp_enabled=False)

    class UoW:
        oauth_clients = clients
        oauth_tokens = tokens
        user_profiles = profiles

    @asynccontextmanager
    async def uow_factory():
        yield UoW()

    service = McpOAuthService(
        uow_factory,
        signing_secret="s",
        mcp_resource_url=f"{BASE}/mcp",
        api_resource_url=f"{BASE}/v1",
        device_verification_url=f"{BASE}/mcp/oauth/device",
        consent_url=f"{BASE}/consent",
        auth_code_ttl_seconds=120,
        access_token_ttl_seconds=3600,
        refresh_token_ttl_seconds=86400,
    )
    return service, clients, tokens, profiles


def _pkce() -> tuple[str, str]:
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


async def _sign_in(service, client_id, redirect_uri, resource) -> dict[str, Any]:
    verifier, challenge = _pkce()
    consent = await service.build_consent_redirect(
        client_id, redirect_uri, challenge, "S256", "", resource, "st"
    )
    rt = parse_qs(urlparse(consent).query)["rt"][0]
    back = await service.complete_consent(rt, USER, approve=True)
    code = parse_qs(urlparse(back).query)["code"][0]
    return await service.exchange_authorization_code(code, redirect_uri, client_id, verifier)


# ── audiences ────────────────────────────────────────────────────────────────


def test_a_request_names_one_of_two_resources(world):
    service, *_ = world
    assert service.audience(None) == MCP  # MCP clients that predate resource indicators
    assert service.audience(f"{BASE}/mcp/") == MCP
    assert service.audience(f"{BASE}/v1") == API
    with pytest.raises(OAuthError, match="unknown resource"):
        service.audience("https://elsewhere.test/v1")


async def test_the_cli_signs_in_without_mcp_and_its_token_only_opens_the_api(world):
    service, clients, _, profiles = world
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    pair = await _sign_in(
        service, cli["client_id"], "http://127.0.0.1:53124/callback", f"{BASE}/v1"
    )

    assert profiles.mcp_enabled is False  # signing in the CLI leaves MCP alone
    assert await service.verify_access_token(pair["access_token"], audience=API)
    assert await service.verify_access_token(pair["access_token"], audience=MCP) is None
    # And it keeps working whatever the MCP switch says.
    assert await service.exchange_refresh_token(pair["refresh_token"], cli["client_id"])


async def test_an_ai_clients_token_never_opens_the_api(world):
    service, clients, _, profiles = world
    profiles.mcp_enabled = True
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    pair = await _sign_in(service, claude["client_id"], "https://claude.test/cb", f"{BASE}/mcp")

    assert await service.verify_access_token(pair["access_token"], audience=MCP)
    assert await service.verify_access_token(pair["access_token"], audience=API) is None
    profiles.mcp_enabled = False
    assert await service.verify_access_token(pair["access_token"], audience=MCP) is None


async def test_connections_list_ai_clients_not_cli_sessions(world):
    service, clients, _, profiles = world
    profiles.mcp_enabled = True
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    await _sign_in(service, cli["client_id"], "http://127.0.0.1:5000/callback", f"{BASE}/v1")
    await _sign_in(service, claude["client_id"], "https://claude.test/cb", None)
    assert [c["client_id"] for c in await service.list_connections(USER)] == [claude["client_id"]]


# ── loopback redirects (RFC 8252) ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("registered", "requested", "ok"),
    [
        ("http://127.0.0.1/callback", "http://127.0.0.1:53124/callback", True),
        ("http://[::1]/callback", "http://[::1]:8080/callback", True),
        ("http://127.0.0.1/callback", "http://127.0.0.1:53124/other", False),
        ("http://127.0.0.1/callback", "http://10.0.0.5:53124/callback", False),
        ("https://app.test/cb", "https://app.test:8443/cb", False),
        ("https://app.test/cb", "https://app.test/cb", True),
    ],
)
async def test_a_loopback_redirect_matches_on_any_port_and_nothing_else_does(
    world, registered, requested, ok
):
    service, clients, *_ = world
    client = await clients.register("x", [registered])
    _, challenge = _pkce()
    attempt = service.build_consent_redirect(
        client["client_id"], requested, challenge, "S256", "", f"{BASE}/v1", None
    )
    if ok:
        assert await attempt
    else:
        with pytest.raises(OAuthError, match="redirect_uri"):
            await attempt


# ── device sign-in (RFC 8628) ────────────────────────────────────────────────


async def _start_device(service, clients, resource=f"{BASE}/v1"):
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    started = await service.start_device_authorization(cli["client_id"], "", resource)
    return cli["client_id"], started


def _make_pollable(tokens):
    # Each poll is allowed immediately (the interval is tested separately).
    for row in tokens.devices.values():
        row["last_polled_at"] = None


async def test_a_device_is_signed_in_once_its_code_is_approved(world):
    service, clients, tokens, profiles = world
    client_id, started = await _start_device(service, clients)
    assert started["user_code"][4] == "-" and len(started["user_code"]) == 9
    assert started["verification_uri"] == f"{BASE}/mcp/oauth/device"
    assert started["verification_uri_complete"].endswith(started["user_code"])

    with pytest.raises(DeviceFlowError) as waiting:
        await service.exchange_device_code(started["device_code"], client_id)
    assert waiting.value.error == "authorization_pending"

    info = await service.device_request(started["user_code"].lower())
    assert info == {"client_name": "Salli CLI", "audience": API}
    await service.decide_device(started["user_code"], USER, approve=True)
    assert profiles.mcp_enabled is False

    _make_pollable(tokens)
    pair = await service.exchange_device_code(started["device_code"], client_id)
    assert await service.verify_access_token(pair["access_token"], audience=API)

    _make_pollable(tokens)
    with pytest.raises(DeviceFlowError) as reused:
        await service.exchange_device_code(started["device_code"], client_id)
    assert reused.value.error == "invalid_grant"


async def test_a_declined_device_is_told_so(world):
    service, clients, tokens, _ = world
    client_id, started = await _start_device(service, clients)
    await service.decide_device(started["user_code"], "", approve=False)
    with pytest.raises(DeviceFlowError) as declined:
        await service.exchange_device_code(started["device_code"], client_id)
    assert declined.value.error == "access_denied"


async def test_polling_faster_than_the_interval_is_slowed_down(world):
    service, clients, *_ = world
    client_id, started = await _start_device(service, clients)
    with pytest.raises(DeviceFlowError):
        await service.exchange_device_code(started["device_code"], client_id)
    with pytest.raises(DeviceFlowError) as fast:
        await service.exchange_device_code(started["device_code"], client_id)
    assert fast.value.error == "slow_down"


async def test_an_expired_code_says_so_and_cannot_be_approved(world):
    service, clients, tokens, _ = world
    client_id, started = await _start_device(service, clients)
    for row in tokens.devices.values():
        row["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(DeviceFlowError) as expired:
        await service.exchange_device_code(started["device_code"], client_id)
    assert expired.value.error == "expired_token"
    assert await service.device_request(started["user_code"]) is None


async def test_another_client_cannot_redeem_the_code(world):
    service, clients, *_ = world
    _, started = await _start_device(service, clients)
    other = await clients.register("other", ["http://127.0.0.1/callback"])
    with pytest.raises(DeviceFlowError) as wrong:
        await service.exchange_device_code(started["device_code"], other["client_id"])
    assert wrong.value.error == "invalid_grant"


async def test_an_ai_client_on_a_device_still_needs_mcp_switched_on(world):
    service, clients, *_ = world
    _, started = await _start_device(service, clients, resource=f"{BASE}/mcp")
    from salli.application.services.mcp_oauth_service import ConsentError

    with pytest.raises(ConsentError, match="MCP"):
        await service.decide_device(started["user_code"], USER, approve=True)


def test_metadata_advertises_the_device_grant(world):
    service, *_ = world
    metadata = service.authorization_server_metadata(BASE)
    assert metadata["device_authorization_endpoint"] == f"{BASE}/mcp/oauth/device_authorization"
    assert "urn:ietf:params:oauth:grant-type:device_code" in metadata["grant_types_supported"]


async def test_a_registered_client_is_told_it_may_use_the_device_grant(world):
    # Strict OAuth libraries refuse a grant the registration did not list.
    service, *_ = world
    client = await service.register_client("salli CLI", ["http://127.0.0.1/callback"])
    assert "urn:ietf:params:oauth:grant-type:device_code" in client["grant_types"]
