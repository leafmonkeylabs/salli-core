"""Who may activate a tax rule set, end to end: real tokens issued by Salli's
OAuth server and stored in a real database, verified by the API's own
`get_principal`, then used against the real service.

| sign-in                                   | tax:activate         |
|-------------------------------------------|----------------------|
| the web session (Supabase JWT)            | yes                  |
| the local-development sign-in             | yes                  |
| OAuth for the API, as the salli CLI       | yes, from any grant  |
| a personal access token                   | only if made with it |
| OAuth for the API, as a registered client | no                   |
| OAuth for MCP (an AI connector)           | never                |

The last tests drive the real app over HTTP: the activate route, and making a
token that carries the permission.
"""

from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient, Response
from jose import jwt

from salli.application.permissions import TAX_ACTIVATE, Actor
from salli.application.services.mcp_oauth_service import API, CLI_CLIENT_ID, McpOAuthService
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from salli.application.services.tax_rule_service import RuleSetPermissionError, TaxRuleService
from salli.config import Settings
from salli.interfaces.api.deps import CurrentPrincipal, get_principal
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


async def _approved_device_code(oauth: McpOAuthService, client_id: str, resource: str) -> str:
    started = await oauth.start_device_authorization(client_id, "", resource)
    await oauth.decide_device(started["user_code"], USER, approve=True)
    return started["device_code"]


async def _device_token(oauth: McpOAuthService, client_id: str, resource: str) -> str:
    """A token as a client gets one: a device code the user approves."""
    device_code = await _approved_device_code(oauth, client_id, resource)
    tokens = await oauth.exchange_device_code(device_code, client_id)
    return tokens["access_token"]


def _session() -> str:
    """A Supabase session for USER, as the web app holds one."""
    return jwt.encode(
        {"sub": USER, "aud": "authenticated", "email": "a@example.org"}, SECRET, algorithm="HS256"
    )


def _real() -> Settings:
    return Settings(_env_file=None, supabase_jwt_secret=SECRET)


async def _principal(token: str, settings: Settings, services):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return await get_principal(creds, settings, services)


@pytest.fixture
async def world(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(USER, {"base_currency": "EUR", "mcp_enabled": True})
    oauth = _oauth(uow_factory)
    tokens = PersonalAccessTokenService(uow_factory)
    services = SimpleNamespace(mcp_oauth=oauth, tokens=tokens)
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
    async with uow_factory() as uow:
        cli = await uow.oauth_clients.get(CLI_CLIENT_ID)
        registered = await uow.oauth_clients.register("Salli CLI", ["http://127.0.0.1/callback"])
    assert cli is not None and cli["first_party"] is True
    # Calling itself "Salli CLI" makes no difference.
    assert registered["first_party"] is False


async def test_the_user_s_own_sign_ins_can_activate(world):
    oauth, tokens, services, rules, proposed_version = world

    pat = (await tokens.create(USER, "laptop", permissions=[TAX_ACTIVATE]))["token"]
    cli = await _device_token(oauth, CLI_CLIENT_ID, f"{BASE}/v1")

    for token, method in ((_session(), "session"), (pat, "pat"), (cli, "oauth")):
        principal = await _principal(token, _real(), services)
        assert principal.method == method
        assert TAX_ACTIVATE in principal.permissions
        assert await _can_activate(rules, principal.actor(), await proposed_version())

    dev = Settings(_env_file=None, salli_insecure_dev_auth=True, environment="development")
    principal = await _principal(USER, dev, services)
    assert principal.method == "dev"
    assert await _can_activate(rules, principal.actor(), await proposed_version())


async def test_a_token_made_without_tax_activate_cannot_activate(world):
    _, tokens, services, rules, proposed_version = world
    pat = (await tokens.create(USER, "backup job"))["token"]
    principal = await _principal(pat, _real(), services)
    assert principal.method == "pat" and principal.permissions == frozenset()
    actor = principal.actor()
    # Still the user's own token, recorded under its name: it just can't activate.
    assert (actor.kind, actor.name) == ("user", "backup job")
    assert not await _can_activate(rules, actor, await proposed_version())


def _pkce() -> tuple[str, str]:
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


async def test_a_salli_cli_token_from_every_grant_holds_tax_activate(world):
    """The CLI signs in as `salli-cli` in a browser (authorization code +
    PKCE, redirected to a loopback port of its choosing) or with the device
    grant, and stays signed in by refreshing: every token it gets can activate."""
    oauth, _, services, rules, proposed_version = world

    verifier, challenge = _pkce()
    redirect = "http://127.0.0.1:53682/callback"
    consent = await oauth.build_consent_redirect(
        CLI_CLIENT_ID, redirect, challenge, "S256", "", f"{BASE}/v1", "st"
    )
    art = parse_qs(urlparse(consent).query)["rt"][0]
    back = await oauth.complete_consent(art, USER, approve=True)
    code = parse_qs(urlparse(back).query)["code"][0]
    browser = await oauth.exchange_authorization_code(code, redirect, CLI_CLIENT_ID, verifier)

    device_code = await _approved_device_code(oauth, CLI_CLIENT_ID, f"{BASE}/v1")
    device = await oauth.exchange_device_code(device_code, CLI_CLIENT_ID)
    refreshed = await oauth.exchange_refresh_token(browser["refresh_token"], CLI_CLIENT_ID)

    for grant, issued in (("browser", browser), ("device", device), ("refresh", refreshed)):
        principal = await _principal(issued["access_token"], _real(), services)
        assert (principal.method, principal.first_party_client) == ("oauth", True), grant
        assert principal.client_name == "Salli CLI", grant
        assert TAX_ACTIVATE in principal.permissions, grant
        assert await _can_activate(rules, principal.actor(), await proposed_version()), grant


async def test_another_application_s_api_token_cannot_activate(uow_factory, world):
    oauth, _, services, rules, proposed_version = world
    async with uow_factory() as uow:
        client = await uow.oauth_clients.register("Some App", ["https://app.example/cb"])
    token = await _device_token(oauth, client["client_id"], f"{BASE}/v1")
    principal = await _principal(token, _real(), services)
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
            await _principal(token, _real(), services)
        assert refused.value.status_code == 401
        assert await oauth.verify_access_token(token, audience=API) is None
        # … and an MCP caller, whatever its client, is an agent without the permission.
        agent = Actor.signed_in(USER, "mcp", first_party_client=client_id == CLI_CLIENT_ID)
        assert not await _can_activate(rules, agent, await proposed_version())


# ── over HTTP ─────────────────────────────────────────────────────────────────


@pytest.fixture
def api(world):
    """The real app, its real sign-in (get_principal) and the real services
    it needs, on the test database."""
    from salli.interfaces.api.deps import get_current_user, get_services, get_settings
    from salli.interfaces.api.main import create_app

    oauth, tokens, _, rules, _ = world

    async def member(principal: CurrentPrincipal) -> str:
        return principal.user_id

    app = create_app()
    app.dependency_overrides[get_services] = lambda: SimpleNamespace(
        mcp_oauth=oauth, tokens=tokens, tax_rules=rules
    )
    app.dependency_overrides[get_settings] = _real
    app.dependency_overrides[get_current_user] = member
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_over_http_a_token_activates_only_if_made_with_tax_activate(world, api):
    _, tokens, _, rules, proposed_version = world
    plain = (await tokens.create(USER, "backup job"))["token"]
    trusted = (await tokens.create(USER, "laptop", permissions=[TAX_ACTIVATE]))["token"]

    async def activate(token: str) -> tuple[str, Response]:
        version = await rules.get_version(USER, await proposed_version())
        path = f"/v1/tax/rule-sets/{version['rule_set_id']}/versions/{version['id']}/activate"
        return version["id"], await api.post(path, headers=_bearer(token))

    version_id, refused = await activate(plain)
    assert refused.status_code == 403
    assert "--allow tax:activate" in refused.json()["detail"]
    assert (await rules.get_version(USER, version_id))["status"] == "proposed"

    version_id, done = await activate(trusted)
    assert done.status_code == 200
    assert done.json()["status"] == "active"
    assert (await rules.get_version(USER, version_id))["status"] == "active"


async def test_over_http_only_a_sign_in_holding_tax_activate_may_give_it_to_a_token(
    uow_factory, world, api
):
    oauth, tokens, *_ = world
    async with uow_factory() as uow:
        app_client = await uow.oauth_clients.register("Some App", ["https://app.example/cb"])
    other_app = await _device_token(oauth, app_client["client_id"], f"{BASE}/v1")
    plain = (await tokens.create(USER, "backup job"))["token"]
    trusted = (await tokens.create(USER, "laptop", permissions=[TAX_ACTIVATE]))["token"]
    cli = await _device_token(oauth, CLI_CLIENT_ID, f"{BASE}/v1")
    wanted = {"name": "agent", "permissions": [TAX_ACTIVATE]}

    # No token makes another, whatever it holds; another application can't
    # make one at all (it would be a way round its own sign-in's limits).
    for token in (plain, trusted, other_app):
        r = await api.post("/v1/tokens", json=wanted, headers=_bearer(token))
        assert r.status_code == 403, r.json()
        assert "token" in r.json()["detail"]

    # A name that isn't a permission is a 422.
    r = await api.post(
        "/v1/tokens", json={"name": "x", "permissions": ["admin"]}, headers=_bearer(cli)
    )
    assert r.status_code == 422

    # The user's own sign-ins hold it, so they may give it.
    for token in (_session(), cli):
        r = await api.post("/v1/tokens", json=wanted, headers=_bearer(token))
        assert r.status_code == 201, r.json()
        assert r.json()["permissions"] == [TAX_ACTIVATE]
    # One made without asking holds nothing.
    r = await api.post("/v1/tokens", json={"name": "script"}, headers=_bearer(cli))
    assert r.status_code == 201 and r.json()["permissions"] == []

    listed = (await api.get("/v1/tokens", headers=_bearer(cli))).json()
    assert sorted((t["name"], tuple(t["permissions"])) for t in listed) == [
        ("agent", (TAX_ACTIVATE,)),
        ("agent", (TAX_ACTIVATE,)),
        ("backup job", ()),
        ("laptop", (TAX_ACTIVATE,)),
        ("script", ()),
    ]
