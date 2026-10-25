"""
The console's sign-in, end to end (docs/design/console.md, section 2): the
real app, its real services and a real Postgres, driven over HTTP the way the
console will drive it.

- `salli-console` signs in with the authorization code and PKCE (S256 only)
  on Salli's own page, which reads "Sign in to Salli", to its one redirect,
  `{SALLI_PUBLIC_URL}/console/callback`, matched exactly;
- every sign-in is a grant: refreshing keeps it, a rotated refresh token used
  again revokes it (the CLI's too), revoking any of its tokens revokes it;
- a console sign-in ends 12 hours after its password, however it refreshes;
- it holds `tax:activate` only within five minutes of the password (4:59 yes,
  5:01 no), and is told to sign in again otherwise; the CLI's age is no
  matter; MCP never activates;
- `GET` and `DELETE /v1/auth/sign-ins` list and end every way in.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from salli import config as salli_config
from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.application.permissions import Actor
from salli.application.services.login_service import LoginService
from salli.application.services.mcp_oauth_service import CLI_CLIENT_ID, CONSOLE_CLIENT_ID
from salli.config import Settings
from tests.integration.pg import requires_postgres
from tests.taxrules.documents import minimal

pytestmark = requires_postgres

BASE = "https://money.example.org"
API = f"{BASE}/v1"
CALLBACK = f"{BASE}/console/callback"
CLI_REDIRECT = "http://127.0.0.1:53682/callback"
OWNER, OWNER_PASSWORD = "owner@example.org", "the owner's long password"
MEMBER, MEMBER_PASSWORD = "member@example.org", "the member's long password"


def _settings(db: str, **overrides) -> Settings:
    values = {
        "database_url": db,
        "environment": "production",
        "salli_public_url": BASE,
        "mcp_signing_secret": "s" * 48,
        **overrides,
    }
    return Settings(_env_file=None, **values)


async def _app(db: str, monkeypatch, **overrides):
    from salli.composition import build_services
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.main import create_app

    settings = _settings(db, **overrides)
    monkeypatch.setattr(salli_config, "_settings", settings)
    services = build_services(settings)
    services.logins = LoginService(
        services.tokens._uow_factory,  # noqa: SLF001
        Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1),
    )
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_settings] = lambda: settings
    return app, services


@pytest.fixture
async def salli(db, monkeypatch):
    app, services = await _app(db, monkeypatch)
    await services.logins.create_account(OWNER, OWNER_PASSWORD, owner=True, base_currency="NZD")
    await services.logins.create_account(MEMBER, MEMBER_PASSWORD)
    engine = create_async_engine(db, connect_args={"statement_cache_size": 0})
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.services = services  # type: ignore[attr-defined]
        client.engine = engine  # type: ignore[attr-defined]
        yield client
    await engine.dispose()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pkce(verifier: str = "v" * 64) -> tuple[str, str]:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


async def _authorize(salli, client_id=CONSOLE_CLIENT_ID, redirect=CALLBACK, **params):
    _, challenge = _pkce()
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": API,
        "state": "st",
        **params,
    }
    return await salli.get("/mcp/oauth/authorize", params=query)


async def _sign_in(
    salli,
    client_id: str = CONSOLE_CLIENT_ID,
    redirect: str = CALLBACK,
    email: str = OWNER,
    password: str = OWNER_PASSWORD,
    **params,
) -> dict:
    """The whole browser flow: authorize, the sign-in page, the code."""
    verifier, _ = _pkce()
    to_page = await _authorize(salli, client_id, redirect, **params)
    assert to_page.status_code == 302, to_page.text
    rt = parse_qs(urlparse(to_page.headers["location"]).query)["rt"][0]
    decided = await salli.post(
        "/mcp/oauth/consent-page",
        data={"rt": rt, "decision": "allow", "email": email, "password": password},
    )
    assert decided.status_code == 303, decided.text
    back = urlparse(decided.headers["location"])
    assert f"{back.scheme}://{back.netloc}{back.path}" == redirect
    query = parse_qs(back.query)
    assert query["state"] == ["st"]
    tokens = await salli.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": redirect,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert tokens.status_code == 200, tokens.text
    return tokens.json()


async def _refresh(salli, refresh_token: str, client_id: str = CONSOLE_CLIENT_ID):
    return await salli.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )


async def _me(salli, token: str):
    return await salli.get("/v1/auth/me", headers=_bearer(token))


async def _sql(salli, statement: str, **params) -> None:
    async with salli.engine.begin() as conn:
        await conn.execute(text(statement), params)


async def _set_sign_in_age(salli, client_id: str, age: timedelta) -> None:
    await _sql(
        salli,
        "UPDATE oauth_grants SET authenticated_at = :at WHERE client_id = :client",
        at=datetime.now(UTC) - age,
        client=client_id,
    )


# ── Signing in ────────────────────────────────────────────────────────────────


async def test_the_console_signs_in_on_salli_s_own_page_and_gets_api_tokens(salli):
    to_page = await _authorize(salli)
    page = await salli.get(to_page.headers["location"].removeprefix(BASE))
    assert page.status_code == 200
    assert "<title>Sign in to Salli</title>" in page.text
    assert "<h1>Sign in to Salli</h1>" in page.text
    # One button: the console has no deny path, only closing the page.
    assert page.text.count("<button") == 1 and "name=decision value=deny" not in page.text
    assert "require-trusted-types-for 'script'" in page.headers["content-security-policy"]

    tokens = await _sign_in(salli)
    assert tokens["access_token"].startswith("salli_at_")
    me = (await _me(salli, tokens["access_token"])).json()
    assert (me["email"], me["method"], me["permissions"]) == (OWNER, "oauth", ["tax:activate"])
    # Signing in to the console is not consent to MCP.
    owner = await salli.services.logins.owner()
    assert not await salli.services.mcp_oauth.is_mcp_enabled(owner["user_id"])


async def test_a_wrong_password_on_the_page_signs_nobody_in(salli):
    to_page = await _authorize(salli)
    rt = parse_qs(urlparse(to_page.headers["location"]).query)["rt"][0]
    decided = await salli.post(
        "/mcp/oauth/consent-page",
        data={"rt": rt, "decision": "allow", "email": OWNER, "password": "a wrong guess"},
    )
    assert decided.status_code == 401
    assert "location" not in decided.headers
    assert "a wrong guess" not in decided.text


async def test_pkce_is_s256_only_and_a_wrong_verifier_is_refused(salli):
    plain = await _authorize(salli, code_challenge_method="plain")
    assert plain.status_code == 400 and "S256" in plain.json()["detail"]

    to_page = await _authorize(salli)
    rt = parse_qs(urlparse(to_page.headers["location"]).query)["rt"][0]
    decided = await salli.post(
        "/mcp/oauth/consent-page",
        data={"rt": rt, "decision": "allow", "email": OWNER, "password": OWNER_PASSWORD},
    )
    code = parse_qs(urlparse(decided.headers["location"]).query)["code"][0]

    def exchange(verifier: str):
        return salli.post(
            "/mcp/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CALLBACK,
                "client_id": CONSOLE_CLIENT_ID,
                "code_verifier": verifier,
            },
        )

    wrong = await exchange("w" * 64)
    assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
    # The wrong verifier didn't burn the code; the right one still works, once.
    assert (await exchange("v" * 64)).status_code == 200
    assert (await exchange("v" * 64)).status_code == 400


@pytest.mark.parametrize(
    "redirect",
    [
        f"{BASE}/console/callback/",
        f"{BASE}/console/callback?x=1",
        f"{BASE}/console/other",
        f"{BASE}:8443/console/callback",
        "https://evil.example/console/callback",
        "http://money.example.org/console/callback",
        "http://127.0.0.1:8000/console/callback",
        "http://127.0.0.1/callback",
    ],
)
async def test_the_console_s_one_redirect_is_matched_exactly(salli, redirect):
    refused = await _authorize(salli, redirect=redirect)
    assert refused.status_code == 400, redirect
    assert "redirect_uri" in refused.json()["detail"]
    assert "location" not in refused.headers


async def test_the_console_signs_in_to_the_api_only_and_never_by_device(salli):
    mcp = await _authorize(salli, resource=f"{BASE}/mcp")
    assert mcp.status_code == 400 and "API only" in mcp.json()["detail"]
    device = await salli.post(
        "/mcp/oauth/device_authorization", data={"client_id": CONSOLE_CLIENT_ID, "resource": API}
    )
    assert device.status_code == 400


async def test_a_web_app_s_consent_screen_cannot_start_a_first_party_sign_in(salli):
    """POST /mcp/oauth/consent checks no password: a token holding less (a
    personal access token without tax:activate) must not turn itself into a
    console or CLI sign-in that holds more."""
    session = (
        await salli.post("/v1/auth/sessions", json={"email": OWNER, "password": OWNER_PASSWORD})
    ).json()["token"]
    pat = (
        await salli.post("/v1/tokens", json={"name": "script"}, headers=_bearer(session))
    ).json()["token"]
    for client_id, redirect in ((CONSOLE_CLIENT_ID, CALLBACK), (CLI_CLIENT_ID, CLI_REDIRECT)):
        to_page = await _authorize(salli, client_id, redirect)
        rt = parse_qs(urlparse(to_page.headers["location"]).query)["rt"][0]
        r = await salli.post(
            "/mcp/oauth/consent", json={"rt": rt, "approve": True}, headers=_bearer(pat)
        )
        assert r.status_code == 403, client_id
        assert "sign-in page" in r.json()["detail"]


async def test_switched_off_the_console_s_client_refuses_and_its_tokens_stop(db, monkeypatch):
    app, services = await _app(db, monkeypatch)
    await services.logins.create_account(OWNER, OWNER_PASSWORD, owner=True, base_currency="NZD")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.services = services  # type: ignore[attr-defined]
        tokens = await _sign_in(client)

    off, off_services = await _app(db, monkeypatch, salli_console=False)
    async with AsyncClient(transport=ASGITransport(app=off), base_url=BASE) as client:
        refused = await _authorize(client)
        assert refused.status_code == 400 and "switched off" in refused.json()["detail"]
        assert (await _refresh(client, tokens["refresh_token"])).status_code == 400
        assert (await _me(client, tokens["access_token"])).status_code == 401
        # The CLI is not the console.
        assert (await _authorize(client, CLI_CLIENT_ID, CLI_REDIRECT)).status_code == 302


async def test_the_console_needs_https_or_localhost(db, monkeypatch):
    for url, ok in (
        ("http://192.168.1.20:8000", False),
        ("http://salli.lan", False),
        ("http://localhost:8000", True),
        ("http://127.0.0.1:8000", True),
        ("https://salli.lan", True),
    ):
        app, _ = await _app(db, monkeypatch, salli_public_url=url)
        async with AsyncClient(transport=ASGITransport(app=app), base_url=url) as client:
            r = await client.get(
                "/mcp/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": CONSOLE_CLIENT_ID,
                    "redirect_uri": f"{url}/console/callback",
                    "code_challenge": _pkce()[1],
                    "code_challenge_method": "S256",
                    "resource": f"{url}/v1",
                },
            )
        assert (r.status_code == 302) is ok, (url, r.text)
        if not ok:
            assert "HTTPS" in r.json()["detail"]


# ── Refresh: grants, reuse and the absolute lifetime ─────────────────────────


@pytest.mark.parametrize(
    ("client_id", "redirect"), [(CONSOLE_CLIENT_ID, CALLBACK), (CLI_CLIENT_ID, CLI_REDIRECT)]
)
async def test_a_reused_refresh_token_revokes_its_whole_grant(salli, client_id, redirect):
    first = await _sign_in(salli, client_id, redirect)
    other = await _sign_in(salli, client_id, redirect)  # another tab, or machine

    second = await _refresh(salli, first["refresh_token"], client_id)
    assert second.status_code == 200
    second = second.json()
    assert (await _me(salli, second["access_token"])).status_code == 200

    # The rotated token again: someone else had it.
    reused = await _refresh(salli, first["refresh_token"], client_id)
    assert reused.status_code == 400
    assert reused.json()["error"] == "invalid_grant"
    assert "already used" in reused.json()["error_description"]

    # Everything in that grant is gone: the thief's and the person's.
    for token in (first["access_token"], second["access_token"]):
        assert (await _me(salli, token)).status_code == 401
    assert (await _refresh(salli, second["refresh_token"], client_id)).status_code == 400
    # Another sign-in of the same client is untouched.
    assert (await _me(salli, other["access_token"])).status_code == 200
    assert (await _refresh(salli, other["refresh_token"], client_id)).status_code == 200


async def test_signing_out_revokes_the_grant_not_one_token(salli):
    first = await _sign_in(salli)
    second = (await _refresh(salli, first["refresh_token"])).json()
    # Revoking the *old* access token signs the whole sign-in out.
    assert (
        await salli.post("/mcp/oauth/revoke", data={"token": first["access_token"]})
    ).status_code == 200
    assert (await _me(salli, second["access_token"])).status_code == 401
    assert (await _refresh(salli, second["refresh_token"])).status_code == 400


async def test_a_console_sign_in_ends_twelve_hours_after_its_password(salli):
    tokens = await _sign_in(salli)
    async with salli.engine.connect() as conn:
        authenticated, expires = (
            await conn.execute(
                text("SELECT authenticated_at, expires_at FROM oauth_grants WHERE client_id = :c"),
                {"c": CONSOLE_CLIENT_ID},
            )
        ).one()
    assert expires - authenticated == timedelta(hours=12)

    # However often it refreshes, it ends then.
    assert (await _refresh(salli, tokens["refresh_token"])).status_code == 200
    await _sql(
        salli,
        "UPDATE oauth_grants SET expires_at = now() - interval '1 second' WHERE client_id = :c",
        c=CONSOLE_CLIENT_ID,
    )
    refreshed = await salli.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": CONSOLE_CLIENT_ID,
        },
    )
    assert refreshed.status_code == 400
    assert (await _me(salli, tokens["access_token"])).status_code == 401


async def test_a_refresh_never_outlives_the_sign_in(salli):
    tokens = await _sign_in(salli)
    # Eleven hours and a half in: the new pair stops when the sign-in does.
    await _sql(
        salli,
        "UPDATE oauth_grants SET expires_at = now() + interval '30 minutes' WHERE client_id = :c",
        c=CONSOLE_CLIENT_ID,
    )
    refreshed = (await _refresh(salli, tokens["refresh_token"])).json()
    assert 1700 <= refreshed["expires_in"] <= 1800
    async with salli.engine.connect() as conn:
        latest = (
            await conn.execute(
                text(
                    "SELECT max(r.expires_at) <= max(g.expires_at) FROM oauth_refresh_tokens r"
                    " JOIN oauth_grants g ON g.id = r.grant_id"
                    " WHERE r.client_id = :c AND r.revoked_at IS NULL"
                ),
                {"c": CONSOLE_CLIENT_ID},
            )
        ).scalar_one()
    assert latest is True


async def test_the_cli_s_sign_in_ends_in_90_days(salli):
    await _sign_in(salli, CLI_CLIENT_ID, CLI_REDIRECT)
    async with salli.engine.connect() as conn:
        expires = (
            await conn.execute(
                text("SELECT expires_at - authenticated_at FROM oauth_grants WHERE client_id = :c"),
                {"c": CLI_CLIENT_ID},
            )
        ).scalar_one()
    assert expires == timedelta(days=90)


# ── Step-up: tax:activate within five minutes of the password ───────────────


async def _proposed_version(salli) -> tuple[str, str]:
    owner = await salli.services.logins.owner()
    rules = salli.services.tax_rules
    version = await rules.draft(Actor.signed_in(owner["user_id"], "mcp", name="Claude"), minimal())
    await rules.propose(Actor.signed_in(owner["user_id"], "mcp"), version["id"])
    return version["rule_set_id"], version["id"]


async def _activate(salli, token: str):
    rule_set_id, version_id = await _proposed_version(salli)
    return await salli.post(
        f"/v1/tax/rule-sets/{rule_set_id}/versions/{version_id}/activate", headers=_bearer(token)
    )


async def test_the_console_activates_at_4_59_after_the_password(salli):
    tokens = await _sign_in(salli)
    await _set_sign_in_age(salli, CONSOLE_CLIENT_ID, timedelta(minutes=4, seconds=59))
    assert (await _me(salli, tokens["access_token"])).json()["permissions"] == ["tax:activate"]
    done = await _activate(salli, tokens["access_token"])
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "active"


async def test_the_console_is_sent_to_sign_in_again_at_5_01(salli):
    tokens = await _sign_in(salli)
    await _set_sign_in_age(salli, CONSOLE_CLIENT_ID, timedelta(minutes=5, seconds=1))
    assert (await _me(salli, tokens["access_token"])).json()["permissions"] == []

    refused = await _activate(salli, tokens["access_token"])
    assert refused.status_code == 403
    problem = refused.json()
    assert problem["type"] == "/problems/step-up-required"
    assert problem["max_age"] == 300
    assert "Sign in again" in problem["detail"]
    challenge = refused.headers["www-authenticate"]
    assert 'error="insufficient_user_authentication"' in challenge and "max_age=300" in challenge

    # Nor may it make a token that can activate; one that can't is fine.
    minted = await salli.post(
        "/v1/tokens",
        json={"name": "agent", "permissions": ["tax:activate"]},
        headers=_bearer(tokens["access_token"]),
    )
    assert minted.status_code == 403 and minted.json()["type"] == "/problems/step-up-required"
    plain = await salli.post(
        "/v1/tokens", json={"name": "script"}, headers=_bearer(tokens["access_token"])
    )
    assert plain.status_code == 201

    # A refresh carries the old password check, not a new one.
    refreshed = (await _refresh(salli, tokens["refresh_token"])).json()
    assert (await _me(salli, refreshed["access_token"])).json()["permissions"] == []


async def test_signing_in_again_on_the_page_steps_up(salli):
    stale = await _sign_in(salli)
    await _set_sign_in_age(salli, CONSOLE_CLIENT_ID, timedelta(hours=1))
    assert (await _activate(salli, stale["access_token"])).status_code == 403

    # The console sends the person through the page again, asking for the
    # password once more ...
    to_page = await _authorize(salli, prompt="login")
    page = await salli.get(to_page.headers["location"].removeprefix(BASE))
    assert "Confirm it&#x27;s you" in page.text or "Confirm it's you" in page.text
    assert "Enter your password again" in page.text
    fresh = await _sign_in(salli, prompt="login")
    # ... and the new sign-in may activate.
    assert (await _activate(salli, fresh["access_token"])).status_code == 200


async def test_the_cli_holds_tax_activate_whatever_its_age(salli):
    tokens = await _sign_in(salli, CLI_CLIENT_ID, CLI_REDIRECT)
    await _set_sign_in_age(salli, CLI_CLIENT_ID, timedelta(days=20))
    assert (await _me(salli, tokens["access_token"])).json()["permissions"] == ["tax:activate"]
    assert (await _activate(salli, tokens["access_token"])).status_code == 200


async def test_mcp_never_activates_however_fresh(salli):
    redirect = "https://claude.test/cb"
    client = (
        await salli.post(
            "/mcp/oauth/register", json={"client_name": "Claude", "redirect_uris": [redirect]}
        )
    ).json()
    tokens = await _sign_in(salli, client["client_id"], redirect, resource=f"{BASE}/mcp")
    # Fresh as can be: the REST API refuses an MCP token outright.
    assert (await _me(salli, tokens["access_token"])).status_code == 401
    assert (await _activate(salli, tokens["access_token"])).status_code == 401
    # And the MCP server's callers hold nothing.
    owner = await salli.services.logins.owner()
    assert Actor.signed_in(owner["user_id"], "mcp").permissions == frozenset()


# ── Every way in ──────────────────────────────────────────────────────────────


async def test_sign_ins_lists_sessions_the_cli_and_the_console_and_ends_each(salli):
    session = (
        await salli.post(
            "/v1/auth/sessions",
            json={"email": OWNER, "password": OWNER_PASSWORD},
            headers={"User-Agent": "a script"},
        )
    ).json()
    cli = await _sign_in(salli, CLI_CLIENT_ID, CLI_REDIRECT)
    console = await _sign_in(salli)
    # An AI connection is not a sign-in: it stays under /v1/mcp/connections.
    claude = (
        await salli.post(
            "/mcp/oauth/register",
            json={"client_name": "Claude", "redirect_uris": ["https://claude.test/cb"]},
        )
    ).json()
    await _sign_in(salli, claude["client_id"], "https://claude.test/cb", resource=f"{BASE}/mcp")
    # Nor is anyone else's.
    await _sign_in(salli, email=MEMBER, password=MEMBER_PASSWORD)

    listed = await salli.get("/v1/auth/sign-ins", headers=_bearer(console["access_token"]))
    assert listed.status_code == 200
    rows = listed.json()
    assert [(r["kind"], r["client_name"], r["user_agent"], r["current"]) for r in rows] == [
        ("console", "Salli console", None, True),
        ("cli", "Salli CLI", None, False),
        ("session", None, "a script", False),
    ]
    console_row, cli_row, session_row = rows
    assert session_row["id"] == session["id"]
    assert console_row["expires_at"] is not None  # its absolute end

    # End the CLI's: its tokens stop; the others go on.
    gone = await salli.delete(
        f"/v1/auth/sign-ins/{cli_row['id']}", headers=_bearer(console["access_token"])
    )
    assert gone.status_code == 204
    assert (await _me(salli, cli["access_token"])).status_code == 401
    assert (await _refresh(salli, cli["refresh_token"], CLI_CLIENT_ID)).status_code == 400
    # And the session.
    assert (
        await salli.delete(
            f"/v1/auth/sign-ins/{session_row['id']}", headers=_bearer(console["access_token"])
        )
    ).status_code == 204
    assert (await _me(salli, session["token"])).status_code == 401
    # Not twice, and not an unknown one.
    for sign_in_id in (cli_row["id"], "00000000-0000-0000-0000-000000000000"):
        r = await salli.delete(
            f"/v1/auth/sign-ins/{sign_in_id}", headers=_bearer(console["access_token"])
        )
        assert r.status_code == 404
    remaining = (
        await salli.get("/v1/auth/sign-ins", headers=_bearer(console["access_token"]))
    ).json()
    assert [r["kind"] for r in remaining] == ["console"]


async def test_no_one_ends_another_person_s_sign_in(salli):
    owner = await _sign_in(salli)
    member = await _sign_in(salli, email=MEMBER, password=MEMBER_PASSWORD)
    [owners] = (await salli.get("/v1/auth/sign-ins", headers=_bearer(owner["access_token"]))).json()
    r = await salli.delete(
        f"/v1/auth/sign-ins/{owners['id']}", headers=_bearer(member["access_token"])
    )
    assert r.status_code == 404
    assert (await _me(salli, owner["access_token"])).status_code == 200


async def test_an_ai_connection_is_not_ended_as_a_sign_in(salli):
    redirect = "https://claude.test/cb"
    client = (
        await salli.post(
            "/mcp/oauth/register", json={"client_name": "Claude", "redirect_uris": [redirect]}
        )
    ).json()
    await _sign_in(salli, client["client_id"], redirect, resource=f"{BASE}/mcp")
    console = await _sign_in(salli)
    async with salli.engine.connect() as conn:
        grant_id = (
            await conn.execute(
                text("SELECT id FROM oauth_grants WHERE client_id = :c"), {"c": client["client_id"]}
            )
        ).scalar_one()
    r = await salli.delete(
        f"/v1/auth/sign-ins/{grant_id}", headers=_bearer(console["access_token"])
    )
    assert r.status_code == 404
    connections = (
        await salli.get("/v1/mcp/connections/", headers=_bearer(console["access_token"]))
    ).json()["connections"]
    assert [c["client_name"] for c in connections] == ["Claude"]
