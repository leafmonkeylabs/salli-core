"""Personal access tokens and device codes, stored in a real database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from salli.application.services.mcp_oauth_service import McpOAuthService
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

BASE = "https://salli.test"


async def test_a_personal_access_token_round_trips(uow_factory):
    tokens = PersonalAccessTokenService(uow_factory)
    created = await tokens.create("u1", "ci", expires_in_days=30)
    verified = await tokens.verify(created["token"])
    assert verified is not None
    assert (verified.user_id, verified.name, verified.permissions) == ("u1", "ci", frozenset())
    [listed] = await tokens.list("u1")
    assert listed["permissions"] == []
    assert listed["last_used_at"] is not None  # the verify above was recorded
    assert listed["expires_at"] > datetime.now(UTC) + timedelta(days=29)
    assert await tokens.revoke("u1", created["id"])
    assert await tokens.verify(created["token"]) is None
    assert await tokens.list("u1") == []


async def test_a_token_keeps_the_permissions_it_was_made_with(uow_factory):
    tokens = PersonalAccessTokenService(uow_factory)
    created = await tokens.create("u1", "laptop", permissions=["tax:activate"])
    assert created["permissions"] == ["tax:activate"]
    verified = await tokens.verify(created["token"])
    assert verified is not None and verified.permissions == frozenset({"tax:activate"})
    [listed] = await tokens.list("u1")
    assert listed["permissions"] == ["tax:activate"]


async def test_a_device_code_goes_from_pending_to_tokens(uow_factory):
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
    client = await service.register_client("Salli CLI", ["http://127.0.0.1/callback"])
    started = await service.start_device_authorization(client["client_id"], "", f"{BASE}/v1")
    assert (await service.device_request(started["user_code"]))["audience"] == "api"

    await service.decide_device(started["user_code"], "u1", approve=True)
    pair = await service.exchange_device_code(started["device_code"], client["client_id"])
    record = await service.verify_access_token(pair["access_token"], audience="api")
    assert record is not None and record["user_id"] == "u1"


async def test_connections_are_ai_clients_and_never_the_users_own_cli(uow_factory):
    # The stored rows said nothing about their audience, so every token read
    # as an MCP connection: the CLI listed itself, and `mcp revoke` could
    # sign it out.
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
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD", "mcp_enabled": True})
    client = await service.register_client("Salli CLI", ["http://127.0.0.1/callback"])
    for resource in (f"{BASE}/v1", f"{BASE}/mcp"):
        started = await service.start_device_authorization(client["client_id"], "", resource)
        await service.decide_device(started["user_code"], "u1", approve=True)
        await service.exchange_device_code(started["device_code"], client["client_id"])

    [connection] = await service.list_connections("u1")
    async with uow_factory() as uow:
        every = await uow.oauth_tokens.list_active_connections("u1")
    [cli] = [t for t in every if t["token_id"] != connection["token_id"]]
    assert cli["resource"] == f"{BASE}/v1"
    assert not await service.revoke_connection("u1", cli["token_id"])  # not a connection
    assert await service.revoke_connection("u1", connection["token_id"])


async def test_disconnecting_a_client_revokes_its_whole_grant(uow_factory):
    # Revoking the connection left the refresh token alive, and a client whose
    # access token had expired could not be disconnected at all.
    from sqlalchemy import update

    from salli.adapters.db.models import OAuthAccessTokenORM

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
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("u1", {"base_currency": "USD", "mcp_enabled": True})
    client = await service.register_client("Claude", ["https://claude.test/cb"])
    started = await service.start_device_authorization(client["client_id"], "", f"{BASE}/mcp")
    await service.decide_device(started["user_code"], "u1", approve=True)
    first = await service.exchange_device_code(started["device_code"], client["client_id"])
    rotated = await service.exchange_refresh_token(first["refresh_token"], client["client_id"])

    # Every access token has run out; the live refresh token still connects it.
    async with uow_factory() as uow:
        await uow._session.execute(
            update(OAuthAccessTokenORM).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    [connection] = await service.list_connections("u1")
    assert await service.revoke_connection("u1", connection["token_id"])

    assert await service.list_connections("u1") == []
    from salli.application.services.mcp_oauth_service import OAuthError

    for refresh in (first["refresh_token"], rotated["refresh_token"]):
        try:
            await service.exchange_refresh_token(refresh, client["client_id"])
        except OAuthError:
            continue
        raise AssertionError("a disconnected client refreshed its tokens")
    # Still Salli's tokens, so the dev fallback refuses them rather than
    # taking them for user ids.
    assert await service.is_salli_token(first["access_token"])
    assert await service.is_salli_token(rotated["refresh_token"])
    assert not await service.is_salli_token("someone")
