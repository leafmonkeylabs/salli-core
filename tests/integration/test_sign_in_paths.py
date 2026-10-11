"""
Every way in, end to end: the real app, its real services and a real
Postgres, driven over HTTP the way each client does it.

- a session: signing in with an email and password (`POST /v1/auth/sessions`);
- the salli CLI: the device grant, and the browser grant through the consent
  page, both approved with the same password;
- a personal access token;
- an AI connector over MCP, approved on the consent page.

And what each may do: `tax:activate` for a session, the CLI and a token made
with it; never for MCP, whose tokens the REST API refuses outright.
"""

from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.application.services.login_service import LoginService
from salli.application.services.mcp_oauth_service import CLI_CLIENT_ID
from salli.config import Settings
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

BASE = "http://test"
OWNER, OWNER_PASSWORD = "owner@example.org", "the owner's long password"
MEMBER, MEMBER_PASSWORD = "member@example.org", "the member's long password"


@pytest.fixture
async def salli(db):
    from salli.composition import build_services
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.main import create_app

    settings = Settings(
        _env_file=None,
        database_url=db,
        environment="production",
        mcp_public_base_url=BASE,
        mcp_signing_secret="s" * 48,
    )
    services = build_services(settings)
    # Real argon2id, with cheap parameters so the suite stays quick.
    services.logins = LoginService(
        services.tokens._uow_factory,  # noqa: SLF001
        Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1),
    )
    await services.logins.create_account(OWNER, OWNER_PASSWORD, owner=True, base_currency="NZD")
    await services.logins.create_account(MEMBER, MEMBER_PASSWORD)

    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.services = services  # type: ignore[attr-defined]
        yield client


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _sign_in(client: AsyncClient, email: str = OWNER, password: str = OWNER_PASSWORD):
    return await client.post(
        "/v1/auth/sessions",
        json={"email": email, "password": password},
        headers={"User-Agent": "test-suite"},
    )


async def _me(client: AsyncClient, token: str):
    return await client.get("/v1/auth/me", headers=_bearer(token))


# ── A session ────────────────────────────────────────────────────────────────


async def test_a_session_signs_in_holds_tax_activate_and_signs_out(salli):
    r = await _sign_in(salli)
    assert r.status_code == 201, r.text
    started = r.json()
    assert started["token"].startswith("salli_st_") and started["email"] == OWNER

    me = (await _me(salli, started["token"])).json()
    assert (me["email"], me["method"], me["permissions"]) == (OWNER, "session", ["tax:activate"])

    listed = (await salli.get("/v1/auth/sessions", headers=_bearer(started["token"]))).json()
    assert [(s["id"], s["current"], s["user_agent"]) for s in listed] == [
        (started["id"], True, "test-suite")
    ]

    out = await salli.delete("/v1/auth/sessions/current", headers=_bearer(started["token"]))
    assert out.status_code == 204
    refused = await _me(salli, started["token"])
    assert refused.status_code == 401
    assert refused.headers["www-authenticate"] == "Bearer"


async def test_a_wrong_password_and_an_unknown_email_get_the_same_answer(salli):
    wrong = await _sign_in(salli, OWNER, "not the owner's password")
    unknown = await _sign_in(salli, "nobody@example.org", OWNER_PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["detail"] == "That email and password didn't match."


async def test_too_many_failures_are_refused_with_retry_after(salli):
    for _ in range(5):
        assert (await _sign_in(salli, OWNER, "a wrong guess")).status_code == 401
    locked = await _sign_in(salli)  # even with the right password
    assert locked.status_code == 429
    assert 0 < int(locked.headers["retry-after"]) <= 900
    # Another account is not locked by it.
    assert (await _sign_in(salli, MEMBER, MEMBER_PASSWORD)).status_code == 201


async def test_changing_the_password_ends_the_other_sessions_only(salli):
    here = (await _sign_in(salli)).json()["token"]
    there = (await _sign_in(salli)).json()["token"]

    wrong = await salli.post(
        "/v1/auth/password",
        json={"current_password": "a wrong guess", "new_password": "a new long password"},
        headers=_bearer(here),
    )
    assert wrong.status_code == 403
    weak = await salli.post(
        "/v1/auth/password",
        json={"current_password": OWNER_PASSWORD, "new_password": "short"},
        headers=_bearer(here),
    )
    assert weak.status_code == 422 and "12 characters" in weak.json()["detail"]

    done = await salli.post(
        "/v1/auth/password",
        json={"current_password": OWNER_PASSWORD, "new_password": "a new long password"},
        headers=_bearer(here),
    )
    assert done.status_code == 200 and done.json() == {"sessions_ended": 1}
    assert (await _me(salli, here)).status_code == 200
    assert (await _me(salli, there)).status_code == 401
    assert (await _sign_in(salli)).status_code == 401
    assert (await _sign_in(salli, OWNER, "a new long password")).status_code == 201


async def test_one_user_cannot_end_another_s_session(salli):
    owners = (await _sign_in(salli)).json()
    members = (await _sign_in(salli, MEMBER, MEMBER_PASSWORD)).json()
    r = await salli.delete(f"/v1/auth/sessions/{owners['id']}", headers=_bearer(members["token"]))
    assert r.status_code == 404
    assert (await _me(salli, owners["token"])).status_code == 200
    mine = (await salli.get("/v1/auth/sessions", headers=_bearer(members["token"]))).json()
    assert [s["id"] for s in mine] == [members["id"]]


# ── The salli CLI ────────────────────────────────────────────────────────────


async def _device_sign_in(salli, password: str = OWNER_PASSWORD):
    started = (
        await salli.post(
            "/mcp/oauth/device_authorization",
            data={"client_id": CLI_CLIENT_ID, "resource": f"{BASE}/v1"},
        )
    ).json()
    page = await salli.get("/mcp/oauth/device", params={"user_code": started["user_code"]})
    assert "Salli CLI on another device is waiting" in page.text
    decided = await salli.post(
        "/mcp/oauth/device",
        data={
            "user_code": started["user_code"],
            "decision": "allow",
            "email": OWNER,
            "password": password,
        },
    )
    return started, decided


async def test_the_cli_signs_in_with_the_device_grant_and_holds_tax_activate(salli):
    started, decided = await _device_sign_in(salli)
    assert decided.status_code == 200 and "Signed in" in decided.text
    tokens = (
        await salli.post(
            "/mcp/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": started["device_code"],
                "client_id": CLI_CLIENT_ID,
            },
        )
    ).json()
    me = (await _me(salli, tokens["access_token"])).json()
    assert (me["email"], me["method"], me["permissions"]) == (OWNER, "oauth", ["tax:activate"])

    refreshed = (
        await salli.post(
            "/mcp/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": CLI_CLIENT_ID,
            },
        )
    ).json()
    assert (await _me(salli, refreshed["access_token"])).json()["method"] == "oauth"


async def test_the_device_page_refuses_a_wrong_password_and_approves_nothing(salli):
    started, decided = await _device_sign_in(salli, password="a wrong guess")
    assert decided.status_code == 401 and "didn" in decided.text
    pending = await salli.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": started["device_code"],
            "client_id": CLI_CLIENT_ID,
        },
    )
    assert pending.json()["error"] == "authorization_pending"


def _pkce() -> tuple[str, str]:
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


async def _browser_grant(salli, client_id: str, redirect: str, resource: str, password: str):
    verifier, challenge = _pkce()
    to_consent = await salli.get(
        "/mcp/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
            "state": "st",
        },
    )
    assert to_consent.status_code == 302
    consent = urlparse(to_consent.headers["location"])
    assert consent.path == "/mcp/oauth/consent-page"
    rt = parse_qs(consent.query)["rt"][0]
    decided = await salli.post(
        "/mcp/oauth/consent-page",
        data={"rt": rt, "decision": "allow", "email": OWNER, "password": password},
    )
    return verifier, decided


async def _exchange(salli, client_id: str, redirect: str, verifier: str, decided) -> dict:
    code = parse_qs(urlparse(decided.headers["location"]).query)["code"][0]
    return (
        await salli.post(
            "/mcp/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect,
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
    ).json()


async def test_the_cli_signs_in_in_a_browser_through_the_consent_page(salli):
    redirect = "http://127.0.0.1:53682/callback"
    verifier, decided = await _browser_grant(
        salli, CLI_CLIENT_ID, redirect, f"{BASE}/v1", OWNER_PASSWORD
    )
    assert decided.status_code == 303
    tokens = await _exchange(salli, CLI_CLIENT_ID, redirect, verifier, decided)
    me = (await _me(salli, tokens["access_token"])).json()
    assert (me["method"], me["permissions"]) == ("oauth", ["tax:activate"])


async def test_the_consent_page_refuses_a_wrong_password(salli):
    _, decided = await _browser_grant(
        salli, CLI_CLIENT_ID, "http://127.0.0.1:1/callback", f"{BASE}/v1", "a wrong guess"
    )
    assert decided.status_code == 401
    assert "location" not in decided.headers
    assert "a wrong guess" not in decided.text


# ── A personal access token ──────────────────────────────────────────────────


async def test_a_token_holds_tax_activate_only_if_made_with_it(salli):
    session = (await _sign_in(salli)).json()["token"]
    for permissions, expected in (([], []), (["tax:activate"], ["tax:activate"])):
        made = await salli.post(
            "/v1/tokens",
            json={"name": "script", "permissions": permissions},
            headers=_bearer(session),
        )
        assert made.status_code == 201, made.text
        me = (await _me(salli, made.json()["token"])).json()
        assert (me["method"], me["permissions"]) == ("pat", expected)


# ── An AI connector over MCP ─────────────────────────────────────────────────


async def test_an_mcp_connector_is_approved_with_the_password_and_never_reaches_the_api(salli):
    redirect = "https://claude.test/cb"
    client = (
        await salli.post(
            "/mcp/oauth/register", json={"client_name": "Claude", "redirect_uris": [redirect]}
        )
    ).json()
    verifier, decided = await _browser_grant(
        salli, client["client_id"], redirect, f"{BASE}/mcp", OWNER_PASSWORD
    )
    assert decided.status_code == 303
    tokens = await _exchange(salli, client["client_id"], redirect, verifier, decided)

    # The MCP server accepts it (approving it switched MCP on) …
    record = await salli.services.mcp_oauth.verify_access_token(tokens["access_token"])
    owner = await salli.services.logins.owner()
    assert record is not None and record["user_id"] == owner["user_id"]
    # … the REST API refuses it outright, so it can never activate tax rules.
    assert (await _me(salli, tokens["access_token"])).status_code == 401
    activate = await salli.post(
        "/v1/tax/rule-sets/x/versions/y/activate", headers=_bearer(tokens["access_token"])
    )
    assert activate.status_code == 401
