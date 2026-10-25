"""
Salli's OAuth server, for both kinds of client it serves.

AI clients get tokens for MCP; Salli's own CLI gets tokens for the REST API.
Each resource accepts only its own tokens, the MCP switch governs only MCP, a
native app's loopback redirect works on any port, a client registers only
https or loopback redirects, and a device without a browser can be signed in
with a code, by Salli's own CLI only.
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
    ConsentError,
    DeviceFlowError,
    McpOAuthService,
    OAuthError,
    RefreshTokenReused,
    may_change,
)

BASE = "https://salli.test"
USER = "u1"


class Clients:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def register(self, client_name, redirect_uris, first_party=False):
        client_id = f"c{len(self.rows) + 1}"
        self.rows[client_id] = {
            "client_id": client_id,
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "first_party": first_party,
            "step_up_seconds": None,
        }
        return self.rows[client_id]

    def seed(self, client_id, name, redirect_uris, step_up_seconds=None):
        """A first-party client, as a migration seeds one."""
        self.rows[client_id] = {
            "client_id": client_id,
            "client_name": name,
            "redirect_uris": redirect_uris,
            "first_party": True,
            "step_up_seconds": step_up_seconds,
        }
        return self.rows[client_id]

    async def get(self, client_id):
        return self.rows.get(client_id)


class Tokens:
    """The OAuth token store, in memory, with grants as the SQL one keeps them."""

    def __init__(self, clients: Clients, clock) -> None:
        self.clients = clients
        self.clock = clock
        self.codes: dict[str, dict[str, Any]] = {}
        self.grants: dict[str, dict[str, Any]] = {}
        self.access: dict[str, dict[str, Any]] = {}
        self.refresh: dict[str, dict[str, Any]] = {}
        self.devices: dict[str, dict[str, Any]] = {}

    async def save_authorization_code(self, code, **fields):
        self.codes[code] = fields

    async def get_authorization_code(self, code):
        return self.codes.get(code)

    async def delete_authorization_code(self, code):
        return self.codes.pop(code, None) is not None

    async def create_grant(self, **fields):
        grant_id = f"g{len(self.grants) + 1}"
        self.grants[grant_id] = {
            "id": grant_id,
            **fields,
            "revoked_at": None,
            "last_used_at": None,
            "created_at": self.clock(),
        }
        return grant_id

    async def save_access_token(self, token_hash, **fields):
        token_id = f"t{len(self.access) + 1}"
        self.access[token_hash] = {"id": token_id, **fields, "revoked": False}
        return token_id

    async def save_refresh_token(self, token_hash, **fields):
        self.refresh[token_hash] = {**fields, "revoked": False}

    def _ended(self, grant):
        return grant["revoked_at"] is not None or (
            grant["expires_at"] is not None and grant["expires_at"] <= self.clock()
        )

    async def get_access_token(self, token_hash):
        row = self.access.get(token_hash)
        if row is None or row["revoked"] or self._ended(self.grants[row["grant_id"]]):
            return None
        grant = self.grants[row["grant_id"]]
        client = self.clients.rows[row["client_id"]]
        return {
            **row,
            "authenticated_at": grant["authenticated_at"],
            "last_used_at": grant["last_used_at"],
            "client_name": client["client_name"],
            "client_first_party": client["first_party"],
            "client_step_up_seconds": client["step_up_seconds"],
        }

    def _access_by_id(self, token_id):
        return next((r for r in self.access.values() if r["id"] == token_id), None)

    async def find_refresh_token(self, token_hash):
        row = self.refresh.get(token_hash)
        if row is None:
            return None
        grant = self.grants[row["grant_id"]]
        return {
            **row,
            "revoked_at": self.clock() if row["revoked"] else None,
            "access_revoked_at": (
                self.clock() if self._access_by_id(row["access_token_id"])["revoked"] else None
            ),
            "grant_revoked_at": grant["revoked_at"],
            "grant_expires_at": grant["expires_at"],
            "authenticated_at": grant["authenticated_at"],
        }

    async def rotate_refresh_token(self, token_hash):
        row = self.refresh[token_hash]
        if row["revoked"]:
            return False
        row["revoked"] = True
        return True

    async def get_grant(self, grant_id):
        return self.grants.get(grant_id)

    async def grant_of_token(self, token_hash):
        row = self.access.get(token_hash) or self.refresh.get(token_hash)
        return self.grants[row["grant_id"]] if row else None

    async def revoke_grant(self, grant_id, user_id=None):
        grant = self.grants.get(grant_id)
        if grant is None or (user_id is not None and grant["user_id"] != user_id):
            return 0
        revoked = 0
        if grant["revoked_at"] is None:
            grant["revoked_at"] = self.clock()
            revoked += 1
        for row in [*self.access.values(), *self.refresh.values()]:
            if row["grant_id"] == grant_id and not row["revoked"]:
                row["revoked"] = True
                revoked += 1
        return revoked

    async def touch_grant(self, grant_id, at):
        self.grants[grant_id]["last_used_at"] = at

    async def revoke_access_token(self, token_id, user_id):
        row = self._access_by_id(token_id)
        if row is None or row["user_id"] != user_id or row["revoked"]:
            return False
        row["revoked"] = True
        return True

    async def get_access_token_by_id(self, token_id, user_id):
        row = self._access_by_id(token_id)
        return row if row is not None and row["user_id"] == user_id else None

    async def revoke_client_grant(self, user_id, client_id, resource):
        revoked = 0
        for grant in self.grants.values():
            if (grant["user_id"], grant["client_id"], grant["resource"]) == (
                user_id,
                client_id,
                resource,
            ):
                revoked += await self.revoke_grant(grant["id"])
        return revoked

    async def list_active_connections(self, user_id, resource=None):
        live = [r for r in self.access.values() if not r["revoked"]]
        live += [
            self._access_by_id(r["access_token_id"])
            for r in self.refresh.values()
            if not r["revoked"] and not self._access_by_id(r["access_token_id"])["revoked"]
        ]
        grants = {}
        for r in live:
            if r["user_id"] == user_id and (resource is None or r["resource"] == resource):
                grants.setdefault(
                    (r["client_id"], r["resource"]),
                    {"token_id": r["id"], "client_id": r["client_id"], "resource": r["resource"]},
                )
        return list(grants.values())

    async def list_sign_in_grants(self, user_id, resource, now):
        return [
            {
                "grant_id": g["id"],
                "client_id": g["client_id"],
                "client_name": self.clients.rows[g["client_id"]]["client_name"],
                "created_at": g["created_at"],
                "last_used_at": g["last_used_at"],
                "expires_at": g["expires_at"],
            }
            for g in self.grants.values()
            if g["user_id"] == user_id and g["resource"] == resource and not self._ended(g)
        ]

    async def save_device_code(self, device_code_hash, **fields):
        self.devices[device_code_hash] = {
            "id": device_code_hash,
            **fields,
            "status": "pending",
            "user_id": None,
            "authenticated_at": None,
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
                and d["expires_at"] > self.clock()
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


class Clock:
    """The time, as the test says it is."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def world(clock):
    clients = Clients()
    tokens, profiles = Tokens(clients, clock), Profiles(mcp_enabled=False)

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
        console_redirect_uri=f"{BASE}/console/callback",
        console_sign_in_hours=12,
        console_secure=True,
        clock=clock,
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
    back = await service.complete_consent(rt, USER, approve=True, password_checked=True)
    code = parse_qs(urlparse(back).query)["code"][0]
    return await service.exchange_authorization_code(code, redirect_uri, client_id, verifier)


async def _consent(service, client_id, redirect_uri, resource, *, password_checked):
    _, challenge = _pkce()
    consent = await service.build_consent_redirect(
        client_id, redirect_uri, challenge, "S256", "", resource, "st"
    )
    rt = parse_qs(urlparse(consent).query)["rt"][0]
    return await service.complete_consent(rt, USER, approve=True, password_checked=password_checked)


async def test_salli_s_own_client_needs_the_password_to_be_approved(world):
    service, clients, *_ = world
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"], first_party=True)
    with pytest.raises(ConsentError, match="with your password"):
        await _consent(
            service,
            cli["client_id"],
            "http://127.0.0.1:5/callback",
            f"{BASE}/v1",
            password_checked=False,
        )
    back = await _consent(
        service,
        cli["client_id"],
        "http://127.0.0.1:5/callback",
        f"{BASE}/v1",
        password_checked=True,
    )
    assert "code=" in back


async def test_another_client_may_still_be_approved_from_a_signed_in_screen(world):
    service, clients, _, profiles = world
    profiles.mcp_enabled = True
    app = await clients.register("An AI client", ["https://ai.example/cb"])
    back = await _consent(
        service,
        app["client_id"],
        "https://ai.example/cb",
        f"{BASE}/mcp/",
        password_checked=False,
    )
    assert "code=" in back


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


async def _granted(service, client_id, redirect_uri, resource, scope="", **decision) -> str:
    verifier, challenge = _pkce()
    consent = await service.build_consent_redirect(
        client_id, redirect_uri, challenge, "S256", scope, resource, None
    )
    rt = parse_qs(urlparse(consent).query)["rt"][0]
    back = await service.complete_consent(rt, USER, approve=True, password_checked=True, **decision)
    code = parse_qs(urlparse(back).query)["code"][0]
    pair = await service.exchange_authorization_code(code, redirect_uri, client_id, verifier)
    record = await service.verify_access_token(pair["access_token"], audience=MCP)
    assert record is None or record["scope"] == pair["scope"]
    return pair["scope"]


async def test_an_ai_client_reads_and_changes_only_if_the_person_allowed_it(world):
    service, clients, _, profiles = world
    profiles.mcp_enabled = True
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    cb, mcp = "https://claude.test/cb", f"{BASE}/mcp"

    # Asking for the write scope is not being given it.
    read = await _granted(service, claude["client_id"], cb, mcp, scope="mcp:write")
    assert read == "mcp:read" and not may_change(read)
    allowed = await _granted(service, claude["client_id"], cb, mcp, allow_changes=True)
    assert allowed == "mcp:read mcp:write" and may_change(allowed)
    # Grants from before the scopes only read.
    assert not may_change("") and not may_change("salli")

    # The app's AI asks the person before each change, so it may change.
    _app(clients)
    assert may_change(await _granted(service, APP, APP_CALLBACK, mcp))
    # An API sign-in is not an MCP connection: its scope is as asked.
    assert await _granted(service, APP, APP_CALLBACK, f"{BASE}/v1", scope="x") == "x"


async def test_an_ai_client_on_a_device_changes_only_if_the_person_allowed_it(world):
    service, clients, tokens, profiles = world
    profiles.mcp_enabled = True
    for allow, scope in ((False, "mcp:read"), (True, "mcp:read mcp:write")):
        client_id, started = await _start_device(service, clients, resource=f"{BASE}/mcp")
        await service.decide_device(started["user_code"], USER, True, allow_changes=allow)
        _make_pollable(tokens)
        pair = await service.exchange_device_code(started["device_code"], client_id)
        assert pair["scope"] == scope


async def test_connections_list_ai_clients_not_cli_sessions(world):
    service, clients, _, profiles = world
    profiles.mcp_enabled = True
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    await _sign_in(service, cli["client_id"], "http://127.0.0.1:5000/callback", f"{BASE}/v1")
    await _sign_in(service, claude["client_id"], "https://claude.test/cb", None)
    assert [c["client_id"] for c in await service.list_connections(USER)] == [claude["client_id"]]


async def test_issued_tokens_carry_salli_prefixes(world):
    service, clients, _, _ = world
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    pair = await _sign_in(service, cli["client_id"], "http://127.0.0.1:5000/callback", f"{BASE}/v1")
    assert pair["access_token"].startswith("salli_at_")
    assert pair["refresh_token"].startswith("salli_rt_")


async def test_disconnecting_an_ai_client_kills_its_refresh_token_too(world):
    # Only the access token was revoked: the client refreshed and was back.
    service, clients, tokens, profiles = world
    profiles.mcp_enabled = True
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    first = await _sign_in(service, claude["client_id"], "https://claude.test/cb", None)
    rotated = await service.exchange_refresh_token(first["refresh_token"], claude["client_id"])

    [connection] = await service.list_connections(USER)  # one client, one connection
    assert await service.revoke_connection(USER, connection["token_id"])

    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(rotated["refresh_token"], claude["client_id"])
    for pair in (first, rotated):  # the earlier rotated access token too
        assert await service.verify_access_token(pair["access_token"], audience=MCP) is None
    assert await service.list_connections(USER) == []
    assert not await service.revoke_connection(USER, connection["token_id"])


async def test_a_client_whose_access_token_expired_can_still_be_disconnected(world):
    service, clients, tokens, profiles = world
    profiles.mcp_enabled = True
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    pair = await _sign_in(service, claude["client_id"], "https://claude.test/cb", None)
    # The access token ran out; the fake lists a grant by its live refresh token.
    [access] = tokens.access.values()
    access_id = access["id"]

    assert await service.revoke_connection(USER, access_id)
    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(pair["refresh_token"], claude["client_id"])


async def test_a_refresh_token_dies_with_its_revoked_access_token(world):
    service, clients, tokens, profiles = world
    cli = await clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    pair = await _sign_in(service, cli["client_id"], "http://127.0.0.1:5000/callback", f"{BASE}/v1")
    await service.revoke_token_by_value(pair["access_token"])
    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(pair["refresh_token"], cli["client_id"])


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
    cli = clients.seed("salli-cli", "Salli CLI", ["http://127.0.0.1/callback"])
    started = await service.start_device_authorization(cli["client_id"], "", resource)
    return cli["client_id"], started


async def test_only_salli_s_own_cli_may_ask_for_a_device_code(world):
    service, clients, *_ = world
    phisher = await clients.register("Salli CLI", ["https://evil.test/cb"])
    with pytest.raises(OAuthError, match="Only Salli's own CLI"):
        await service.start_device_authorization(phisher["client_id"], "", f"{BASE}/mcp")


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


async def test_an_expired_code_says_so_and_cannot_be_approved(world, clock):
    service, clients, tokens, _ = world
    client_id, started = await _start_device(service, clients)
    for row in tokens.devices.values():
        row["expires_at"] = clock() - timedelta(seconds=1)
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


async def test_a_registered_client_is_not_offered_the_device_grant(world):
    service, *_ = world
    client = await service.register_client("An AI client", ["http://127.0.0.1/callback"])
    assert client["grant_types"] == ["authorization_code", "refresh_token"]


@pytest.mark.parametrize(
    "uri",
    [
        "https://ai.example/cb",
        "http://127.0.0.1/callback",
        "http://127.0.0.1:5000/callback",
        "http://localhost:8080/cb",
        "http://[::1]:5000/cb",
    ],
)
async def test_a_client_registers_https_or_loopback_redirects(world, uri):
    service, *_ = world
    assert (await service.register_client("An AI client", [uri]))["redirect_uris"] == [uri]


@pytest.mark.parametrize(
    "uri",
    [
        "http://ai.example/cb",
        "http://192.168.1.5/cb",
        "http://127.0.0.1.evil.test/cb",
        "javascript:alert(1)",
        "https:///cb",
    ],
)
async def test_a_client_cannot_register_another_http_redirect(world, uri):
    service, *_ = world
    with pytest.raises(OAuthError, match="invalid redirect_uri"):
        await service.register_client("An AI client", [uri])


async def test_a_plain_http_redirect_registered_before_is_refused(world):
    service, clients, *_ = world
    old = await clients.register("An AI client", ["http://ai.example/cb"])
    _, challenge = _pkce()
    with pytest.raises(OAuthError, match="redirect_uri"):
        await service.build_consent_redirect(
            old["client_id"], "http://ai.example/cb", challenge, "S256", "", None, None
        )


# ── The console's client (docs/design/console.md, section 2) ─────────────────


CONSOLE = "salli-console"
CALLBACK = f"{BASE}/console/callback"


def _console(clients):
    return clients.seed(CONSOLE, "Salli console", [], step_up_seconds=300)


async def test_the_console_signs_in_to_its_one_computed_redirect(world, clock):
    service, clients, tokens, _ = world
    _console(clients)
    pair = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    record = await service.verify_access_token(pair["access_token"], audience=API)
    assert record["client_step_up_seconds"] == 300
    # The password was checked at sign-in, and the sign-in ends 12 hours on.
    [grant] = tokens.grants.values()
    assert grant["authenticated_at"] == clock()
    assert grant["expires_at"] == clock() + timedelta(hours=12)


@pytest.mark.parametrize(
    "requested",
    [
        f"{BASE}/console/callback/",
        f"{BASE}/console/callback?next=x",
        f"{BASE}/console/Callback",
        "https://salli.test:444/console/callback",
        "https://evil.test/console/callback",
        "http://127.0.0.1:5000/console/callback",
        "http://127.0.0.1/callback",
    ],
)
async def test_nothing_but_the_console_s_exact_redirect_matches(world, requested):
    service, clients, *_ = world
    _console(clients)
    _, challenge = _pkce()
    with pytest.raises(OAuthError, match="redirect_uri"):
        await service.build_consent_redirect(
            CONSOLE, requested, challenge, "S256", "", f"{BASE}/v1", None
        )


async def test_pkce_is_s256_and_its_verifier_must_match(world):
    service, clients, *_ = world
    _console(clients)
    verifier, challenge = _pkce()
    for method in ("plain", "", "S512"):
        with pytest.raises(OAuthError, match="S256"):
            await service.build_consent_redirect(
                CONSOLE, CALLBACK, verifier, method, "", f"{BASE}/v1", None
            )
    with pytest.raises(OAuthError, match="code_challenge"):
        await service.build_consent_redirect(CONSOLE, CALLBACK, "", "S256", "", f"{BASE}/v1", None)

    consent = await service.build_consent_redirect(
        CONSOLE, CALLBACK, challenge, "S256", "", f"{BASE}/v1", None
    )
    rt = parse_qs(urlparse(consent).query)["rt"][0]
    back = await service.complete_consent(rt, USER, True, password_checked=True)
    code = parse_qs(urlparse(back).query)["code"][0]
    with pytest.raises(OAuthError, match="PKCE"):
        await service.exchange_authorization_code(code, CALLBACK, CONSOLE, "x" * 64)
    # Not even the challenge itself works as the verifier.
    with pytest.raises(OAuthError, match="PKCE"):
        await service.exchange_authorization_code(code, CALLBACK, CONSOLE, challenge)
    assert await service.exchange_authorization_code(code, CALLBACK, CONSOLE, verifier)
    with pytest.raises(OAuthError):  # once only
        await service.exchange_authorization_code(code, CALLBACK, CONSOLE, verifier)


async def test_the_console_is_refused_while_switched_off(world, clock):
    service, clients, tokens, profiles = world
    _console(clients)
    pair = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    off = McpOAuthService(
        service._uow_factory,  # noqa: SLF001
        signing_secret="s",
        mcp_resource_url=f"{BASE}/mcp",
        api_resource_url=f"{BASE}/v1",
        consent_url=f"{BASE}/consent",
        auth_code_ttl_seconds=120,
        access_token_ttl_seconds=3600,
        refresh_token_ttl_seconds=86400,
        console_redirect_uri=None,
        clock=clock,
    )
    _, challenge = _pkce()
    with pytest.raises(OAuthError, match="switched off"):
        await off.build_consent_redirect(
            CONSOLE, CALLBACK, challenge, "S256", "", f"{BASE}/v1", None
        )
    with pytest.raises(OAuthError, match="switched off"):
        await off.exchange_refresh_token(pair["refresh_token"], CONSOLE)
    assert await off.verify_access_token(pair["access_token"], audience=API) is None


async def test_the_console_needs_a_secure_public_url(world, clock):
    service, clients, *_ = world
    _console(clients)
    insecure = McpOAuthService(
        service._uow_factory,  # noqa: SLF001
        signing_secret="s",
        mcp_resource_url=f"{BASE}/mcp",
        api_resource_url=f"{BASE}/v1",
        consent_url=f"{BASE}/consent",
        auth_code_ttl_seconds=120,
        access_token_ttl_seconds=3600,
        refresh_token_ttl_seconds=86400,
        console_redirect_uri=CALLBACK,
        console_secure=False,
        clock=clock,
    )
    _, challenge = _pkce()
    with pytest.raises(OAuthError, match="HTTPS"):
        await insecure.build_consent_redirect(
            CONSOLE, CALLBACK, challenge, "S256", "", f"{BASE}/v1", None
        )


# ── The phone app's client (docs/design/mobile.md) ──────────────────────────


APP = "salli-mobile"
APP_CALLBACK = "money.salli.app:/oauth/callback"


def _app(clients):
    return clients.seed(APP, "Salli app", [APP_CALLBACK], step_up_seconds=300)


async def test_the_app_signs_in_to_its_one_redirect_with_no_absolute_end(world, clock):
    service, clients, tokens, _ = world
    _app(clients)
    pair = await _sign_in(service, APP, APP_CALLBACK, f"{BASE}/v1")
    record = await service.verify_access_token(pair["access_token"], audience=API)
    assert (record["client_first_party"], record["client_step_up_seconds"]) == (True, 300)
    [grant] = tokens.grants.values()
    assert grant["expires_at"] is None


@pytest.mark.parametrize(
    "requested",
    [
        "money.salli.app:/oauth/callback/",
        "money.salli.app://oauth/callback",
        "money.salli.app:/oauth/callback?next=x",
        "money.salli.evil:/oauth/callback",
        "http://127.0.0.1:5000/oauth/callback",
    ],
)
async def test_nothing_but_the_app_s_exact_redirect_matches(world, requested):
    service, clients, *_ = world
    _app(clients)
    _, challenge = _pkce()
    with pytest.raises(OAuthError, match="redirect_uri"):
        await service.build_consent_redirect(
            APP, requested, challenge, "S256", "", f"{BASE}/v1", None
        )


async def test_the_app_signs_in_to_the_api_or_mcp_and_never_by_device(world):
    service, clients, *_ = world
    _app(clients)
    _, challenge = _pkce()
    # MCP, for the AI the person set up in the app, as well as the API.
    for resource in (f"{BASE}/v1", f"{BASE}/mcp"):
        assert await service.build_consent_redirect(
            APP, APP_CALLBACK, challenge, "S256", "", resource, None
        )
    with pytest.raises(OAuthError, match="authorization code grant only"):
        await service.start_device_authorization(APP, "", f"{BASE}/v1")


# ── Grants: rotation, reuse, the absolute lifetime ───────────────────────────


@pytest.mark.parametrize("which", ["console", "cli"])
async def test_reusing_a_rotated_refresh_token_revokes_the_whole_grant(world, which):
    service, clients, tokens, _ = world
    if which == "console":
        client_id, redirect = _console(clients)["client_id"], CALLBACK
    else:
        client_id = clients.seed("salli-cli", "Salli CLI", ["http://127.0.0.1/callback"])[
            "client_id"
        ]
        redirect = "http://127.0.0.1:5000/callback"
    first = await _sign_in(service, client_id, redirect, f"{BASE}/v1")
    second = await service.exchange_refresh_token(first["refresh_token"], client_id)
    third = await service.exchange_refresh_token(second["refresh_token"], client_id)
    # One grant through every rotation.
    assert len(tokens.grants) == 1

    with pytest.raises(RefreshTokenReused, match="already used"):
        await service.exchange_refresh_token(first["refresh_token"], client_id)
    [grant] = tokens.grants.values()
    assert grant["revoked_at"] is not None
    for pair in (first, second, third):
        assert await service.verify_access_token(pair["access_token"], audience=API) is None
    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(third["refresh_token"], client_id)


async def test_a_refresh_token_raced_by_another_request_counts_as_reused(world):
    service, clients, tokens, _ = world
    _console(clients)
    pair = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")

    # Another request rotates it between this one's read and its claim.
    real_find = tokens.find_refresh_token

    async def find_then_lose_the_race(token_hash):
        found = await real_find(token_hash)
        tokens.refresh[token_hash]["revoked"] = True
        return found

    tokens.find_refresh_token = find_then_lose_the_race
    with pytest.raises(RefreshTokenReused):
        await service.exchange_refresh_token(pair["refresh_token"], CONSOLE)
    assert next(iter(tokens.grants.values()))["revoked_at"] is not None


async def test_the_password_check_is_carried_through_rotation_not_renewed(world, clock):
    service, clients, tokens, _ = world
    _console(clients)
    signed_in_at = clock()
    pair = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    clock.advance(hours=2)
    rotated = await service.exchange_refresh_token(pair["refresh_token"], CONSOLE)
    record = await service.verify_access_token(rotated["access_token"], audience=API)
    assert record["authenticated_at"] == signed_in_at


async def test_a_console_sign_in_ends_twelve_hours_after_its_password(world, clock):
    service, clients, tokens, _ = world
    _console(clients)
    pair = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    # Refreshing every hour keeps it going, until the twelfth.
    for _ in range(11):
        clock.advance(hours=1)
        pair = await service.exchange_refresh_token(pair["refresh_token"], CONSOLE)
    clock.advance(minutes=30)
    last = await service.exchange_refresh_token(pair["refresh_token"], CONSOLE)
    # The last access token stops when the sign-in does, not an hour on.
    assert last["expires_in"] == 30 * 60
    clock.advance(minutes=30)
    assert await service.verify_access_token(last["access_token"], audience=API) is None
    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(last["refresh_token"], CONSOLE)


async def test_the_cli_s_sign_in_has_no_absolute_end(world, clock):
    service, clients, tokens, _ = world
    clients.seed("salli-cli", "Salli CLI", ["http://127.0.0.1/callback"])
    pair = await _sign_in(service, "salli-cli", "http://127.0.0.1:5000/callback", f"{BASE}/v1")
    for _ in range(3):
        clock.advance(hours=20)  # within the refresh token's day
        pair = await service.exchange_refresh_token(pair["refresh_token"], "salli-cli")
    assert next(iter(tokens.grants.values()))["expires_at"] is None


async def test_an_ai_client_s_connection_ends_ninety_days_after_its_approval(world, clock):
    service, clients, tokens, profiles = world
    profiles.mcp_enabled = True
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    pair = await _sign_in(service, claude["client_id"], "https://claude.test/cb", f"{BASE}/mcp")
    [grant] = tokens.grants.values()
    assert grant["expires_at"] == clock() + timedelta(days=90)
    # Refreshing within each refresh token's day keeps it going, to the end.
    for _ in range(93):
        clock.advance(hours=23)
        pair = await service.exchange_refresh_token(pair["refresh_token"], claude["client_id"])
    clock.advance(hours=90 * 24 - 93 * 23)
    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(pair["refresh_token"], claude["client_id"])
    assert await service.verify_access_token(pair["access_token"], audience=MCP) is None


async def test_revoking_any_token_of_a_grant_revokes_the_grant(world):
    service, clients, tokens, _ = world
    _console(clients)
    first = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    second = await service.exchange_refresh_token(first["refresh_token"], CONSOLE)
    await service.revoke_token_by_value(first["access_token"])  # an old, rotated one
    assert await service.verify_access_token(second["access_token"], audience=API) is None
    with pytest.raises(OAuthError):
        await service.exchange_refresh_token(second["refresh_token"], CONSOLE)


async def test_sign_ins_are_the_api_s_grants_and_end_one_at_a_time(world):
    service, clients, tokens, profiles = world
    _console(clients)
    profiles.mcp_enabled = True
    claude = await clients.register("Claude", ["https://claude.test/cb"])
    tab_one = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    tab_two = await _sign_in(service, CONSOLE, CALLBACK, f"{BASE}/v1")
    await _sign_in(service, claude["client_id"], "https://claude.test/cb", f"{BASE}/mcp")

    listed = await service.list_sign_ins(USER)
    assert [s["client_id"] for s in listed] == [CONSOLE, CONSOLE]
    ai_grant = next(g for g in tokens.grants.values() if g["client_id"] == claude["client_id"])
    assert not await service.revoke_sign_in(USER, ai_grant["id"])  # an AI connection
    assert not await service.revoke_sign_in("someone-else", listed[0]["grant_id"])
    assert await service.revoke_sign_in(USER, listed[0]["grant_id"])
    assert not await service.revoke_sign_in(USER, listed[0]["grant_id"])  # once
    alive = [
        await service.verify_access_token(t["access_token"], audience=API)
        for t in (tab_one, tab_two)
    ]
    assert [a is not None for a in alive] == [False, True]


async def test_the_console_is_never_signed_in_without_the_password(world, clock):
    """The console is first party too: the JSON consent route, which checks no
    password, can't approve it; the sign-in page, which does, records when."""
    service, clients, tokens, _ = world
    _console(clients)
    _, challenge = _pkce()
    consent = await service.build_consent_redirect(
        CONSOLE, CALLBACK, challenge, "S256", "", f"{BASE}/v1", None
    )
    rt = parse_qs(urlparse(consent).query)["rt"][0]
    with pytest.raises(ConsentError, match="password"):
        await service.complete_consent(rt, USER, True, password_checked=False)
    assert tokens.codes == {}

    checked_at = clock() - timedelta(seconds=7)
    await service.complete_consent(
        rt, USER, True, password_checked=True, authenticated_at=checked_at
    )
    [code] = tokens.codes.values()
    assert code["authenticated_at"] == checked_at
