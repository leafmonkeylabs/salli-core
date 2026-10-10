"""Who may activate a tax rule set, end to end: real tokens issued by Salli's
OAuth server and stored in a real database, verified by the API's own
`get_principal`, then used against the real service.

| sign-in                                   | tax:activate |
|-------------------------------------------|--------------|
| the web session (Supabase JWT)            | yes          |
| a personal access token                   | yes          |
| the local-development sign-in             | yes          |
| OAuth for the API, as the salli CLI       | yes          |
| OAuth for the API, as a registered client | no           |
| OAuth for MCP (an AI connector)           | never        |
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from salli.application.permissions import TAX_ACTIVATE, Actor
from salli.application.services.mcp_oauth_service import API, CLI_CLIENT_ID, McpOAuthService
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from salli.application.services.tax_rule_service import RuleSetPermissionError, TaxRuleService
from salli.config import Settings
from salli.interfaces.api.deps import get_principal
from salli.interfaces.api.mcp_server import SalliTokenVerifier
from tests.integration.pg import requires_postgres
from tests.taxrules.documents import minimal

pytestmark = requires_postgres

USER = "user-a"
BASE = "https://salli.test"
# A signing key for test sessions only (HS256 wants 32 bytes or more).
SECRET = "x" * 40


def _oauth(uow_factory) -> McpOAuthService:
    return McpOAuthService(
        uow_factory,
        signing_secret="test",
        mcp_resource_url=f"{BASE}/mcp",
        api_resource_url=f"{BASE}/v1",
        device_verification_url=f"{BASE}/mcp/oauth/device",
        consent_url=f"{BASE}/consent",
        auth_code_ttl_seconds=60,
        access_token_ttl_seconds=3600,
        refresh_token_ttl_seconds=86400,
    )


async def _device_token(oauth: McpOAuthService, client_id: str, resource: str) -> str:
    """A token as a client gets one: a device code the user approves."""
    started = await oauth.start_device_authorization(client_id, "", resource)
    await oauth.decide_device(started["user_code"], USER, approve=True)
    tokens = await oauth.exchange_device_code(started["device_code"], client_id)
    return tokens["access_token"]


async def _principal(token: str, settings: Settings, services):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return await get_principal(creds, settings, services)


@pytest.fixture
async def world(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(USER, {"base_currency": "EUR", "mcp_enabled": True})
    oauth = _oauth(uow_factory)
    tokens = PersonalAccessTokenService(uow_factory)

    class Services:
        mcp_oauth = oauth

    services = Services()
    services.tokens = tokens  # type: ignore[attr-defined]
    rules = TaxRuleService(uow_factory)

    async def proposed_version() -> str:
        version = await rules.draft(Actor.signed_in(USER, "mcp", name="Claude"), minimal())
        await rules.propose(Actor.signed_in(USER, "mcp"), version["id"])
        return version["id"]

    return oauth, tokens, services, rules, proposed_version


async def _can_activate(rules: TaxRuleService, actor: Actor, version_id: str) -> bool:
    try:
        version = await rules.activate(actor, version_id)
    except RuleSetPermissionError:
        assert (await rules.get_version(USER, version_id))["status"] == "proposed"
        return False
    assert version["status"] == "active"
    return True


async def test_the_salli_cli_is_first_party_and_a_registered_client_never_is(uow_factory, world):
    oauth, *_ = world
    async with uow_factory() as uow:
        cli = await uow.oauth_clients.get(CLI_CLIENT_ID)
        registered = await uow.oauth_clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    assert cli is not None and cli["first_party"] is True
    # Calling itself "Salli CLI" makes no difference.
    assert registered["first_party"] is False


async def test_the_user_s_own_sign_ins_can_activate(world):
    oauth, tokens, services, rules, proposed_version = world
    real = Settings(_env_file=None, supabase_jwt_secret=SECRET)

    session = jwt.encode(
        {"sub": USER, "aud": "authenticated", "email": "a@example.org"}, SECRET, algorithm="HS256"
    )
    pat = (await tokens.create(USER, "laptop"))["token"]
    cli = await _device_token(oauth, CLI_CLIENT_ID, f"{BASE}/v1")

    for token, method in ((session, "session"), (pat, "pat"), (cli, "oauth")):
        principal = await _principal(token, real, services)
        assert principal.method == method
        assert TAX_ACTIVATE in principal.permissions
        assert await _can_activate(rules, principal.actor(), await proposed_version())

    dev = Settings(_env_file=None, salli_insecure_dev_auth=True, environment="development")
    principal = await _principal(USER, dev, services)
    assert principal.method == "dev"
    assert await _can_activate(rules, principal.actor(), await proposed_version())


async def test_another_application_s_api_token_cannot_activate(uow_factory, world):
    oauth, _, services, rules, proposed_version = world
    async with uow_factory() as uow:
        client = await uow.oauth_clients.register("Some App", ["https://app.example/cb"])
    token = await _device_token(oauth, client["client_id"], f"{BASE}/v1")
    principal = await _principal(
        token, Settings(_env_file=None, supabase_jwt_secret=SECRET), services
    )
    assert (principal.method, principal.first_party_client) == ("oauth", False)
    assert principal.permissions == frozenset()
    actor = principal.actor()
    assert (actor.kind, actor.name) == ("agent", "Some App")
    assert not await _can_activate(rules, actor, await proposed_version())


async def test_an_mcp_token_never_reaches_the_api_and_its_agent_cannot_activate(uow_factory, world):
    oauth, _, services, rules, proposed_version = world
    async with uow_factory() as uow:
        client = await uow.oauth_clients.register("Claude", ["https://claude.ai/cb"])
    # Even Salli's own client, holding a token for MCP, is an AI connector there.
    for client_id in (client["client_id"], CLI_CLIENT_ID):
        token = await _device_token(oauth, client_id, f"{BASE}/mcp")
        # A real MCP token: the MCP server accepts it …
        access = await SalliTokenVerifier(oauth).verify_token(token)
        assert access is not None and access.subject == USER
        # … the REST API refuses it outright …
        with pytest.raises(HTTPException) as refused:
            await _principal(token, Settings(_env_file=None, supabase_jwt_secret=SECRET), services)
        assert refused.value.status_code == 401
        assert await oauth.verify_access_token(token, audience=API) is None
        # … and an MCP caller, whatever its client, is an agent without the permission.
        agent = Actor.signed_in(USER, "mcp", first_party_client=client_id == CLI_CLIENT_ID)
        assert not await _can_activate(rules, agent, await proposed_version())
