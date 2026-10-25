"""
The phone app's sign-in, end to end (docs/design/mobile.md): the real app,
its real services and a real Postgres, driven over HTTP the way the app's
browser sheet drives it.

- `salli-mobile`, seeded by core_0022, signs in with the authorization code
  and PKCE on Salli's own page, which reads "Sign in to Salli", to its one
  redirect, `money.salli.app:/oauth/callback`, matched exactly;
- it signs in to the API as the person, and to MCP for the AI the person
  set up in the app: a page that asks to connect it, by name, and an AI
  connection like any other; never by device code;
- it holds `tax:activate` only within five minutes of the password, as the
  console does, and its sign-in has no absolute end;
- `GET /v1/auth/sign-ins` lists it as `mobile`, and `/v1/meta` names it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from salli.application.services.mcp_oauth_service import MOBILE_CLIENT_ID, MOBILE_REDIRECT_URI
from tests.integration.pg import requires_postgres
from tests.integration.test_console_sign_in import (
    API,
    BASE,
    OWNER,
    OWNER_PASSWORD,
    _app,
    _bearer,
    _me,
    _pkce,
    _refresh,
    _set_sign_in_age,
)

pytestmark = requires_postgres


@pytest.fixture
async def salli(db, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    app, services = await _app(db, monkeypatch)
    await services.logins.create_account(OWNER, OWNER_PASSWORD, owner=True, base_currency="EUR")
    engine = create_async_engine(db, connect_args={"statement_cache_size": 0})
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.services = services  # type: ignore[attr-defined]
        client.engine = engine  # type: ignore[attr-defined]
        yield client
    await engine.dispose()


async def _authorize(salli, redirect=MOBILE_REDIRECT_URI, **params):
    _, challenge = _pkce()
    query = {
        "response_type": "code",
        "client_id": MOBILE_CLIENT_ID,
        "redirect_uri": redirect,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": API,
        "state": "st",
        **params,
    }
    return await salli.get("/mcp/oauth/authorize", params=query)


async def _sign_in(salli, resource: str = API) -> dict:
    """The app's browser sheet: authorize, the sign-in page, the code."""
    verifier, _ = _pkce()
    to_page = await _authorize(salli, resource=resource)
    assert to_page.status_code == 302, to_page.text
    rt = parse_qs(urlparse(to_page.headers["location"]).query)["rt"][0]
    decided = await salli.post(
        "/mcp/oauth/consent-page",
        data={"rt": rt, "decision": "allow", "email": OWNER, "password": OWNER_PASSWORD},
    )
    assert decided.status_code == 303, decided.text
    location = decided.headers["location"]
    # Back to the app's own scheme, which only the app can open.
    assert location.startswith(f"{MOBILE_REDIRECT_URI}?")
    query = parse_qs(urlparse(location).query)
    assert query["state"] == ["st"]
    tokens = await salli.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": MOBILE_REDIRECT_URI,
            "client_id": MOBILE_CLIENT_ID,
            "code_verifier": verifier,
        },
    )
    assert tokens.status_code == 200, tokens.text
    return tokens.json()


async def test_the_app_signs_in_on_salli_s_own_page_and_gets_api_tokens(salli):
    to_page = await _authorize(salli)
    page = await salli.get(to_page.headers["location"].removeprefix(BASE))
    assert page.status_code == 200
    assert "<h1>Sign in to Salli</h1>" in page.text
    # One button, as the console's: signing in to Salli itself.
    assert page.text.count("<button") == 1 and "name=decision value=deny" not in page.text

    tokens = await _sign_in(salli)
    assert tokens["access_token"].startswith("salli_at_")
    me = (await _me(salli, tokens["access_token"])).json()
    assert (me["email"], me["method"], me["permissions"]) == (OWNER, "oauth", ["tax:activate"])
    # A refresh keeps the sign-in.
    again = await _refresh(salli, tokens["refresh_token"], MOBILE_CLIENT_ID)
    assert again.status_code == 200, again.text


@pytest.mark.parametrize(
    "redirect",
    [
        "money.salli.app:/oauth/callback/",
        "money.salli.app://oauth/callback",
        "money.salli.app:/oauth/callback?next=x",
        "money.salli.evil:/oauth/callback",
        "http://127.0.0.1:5000/callback",
        f"{BASE}/console/callback",
    ],
)
async def test_nothing_but_the_app_s_exact_redirect_matches(salli, redirect):
    refused = await _authorize(salli, redirect=redirect)
    assert refused.status_code == 400
    assert "redirect_uri" in refused.json()["detail"]


async def test_the_app_s_ai_connects_over_mcp_as_an_ai_connection(salli):
    mcp = f"{BASE}/mcp"
    to_page = await _authorize(salli, resource=mcp)
    page = await salli.get(to_page.headers["location"].removeprefix(BASE))
    assert page.status_code == 200
    # Not "Sign in to Salli": an AI asking to act for you, allowed or denied.
    assert "<h1>Connect the AI in the Salli app?</h1>" in page.text
    assert "It reads your books and asks you in the app before any change." in page.text
    assert "You can disconnect it any time." in page.text
    assert "name=decision value=deny" in page.text

    tokens = await _sign_in(salli, resource=mcp)
    services = salli.services
    record = await services.mcp_oauth.verify_access_token(tokens["access_token"], audience="mcp")
    assert record is not None and record["client_id"] == MOBILE_CLIENT_ID
    # For MCP only: the API refuses it.
    assert (await _me(salli, tokens["access_token"])).status_code == 401
    # Listed and ended with the other AI connections, not with the sign-ins.
    person = await _sign_in(salli)
    listed = (
        await salli.get("/v1/mcp/connections/", headers=_bearer(person["access_token"]))
    ).json()["connections"]
    assert [c["client_name"] for c in listed] == ["Salli app"]
    signed_in = (
        await salli.get("/v1/auth/sign-ins", headers=_bearer(person["access_token"]))
    ).json()
    assert [r["kind"] for r in signed_in] == ["mobile"]
    # Under the MCP switch, as every AI connection is.
    await services.mcp_oauth.set_mcp_enabled(record["user_id"], False)
    assert await services.mcp_oauth.verify_access_token(tokens["access_token"]) is None


async def test_the_app_never_signs_in_by_device(salli):
    device = await salli.post(
        "/mcp/oauth/device_authorization", data={"client_id": MOBILE_CLIENT_ID, "resource": API}
    )
    assert device.status_code == 400


async def test_the_app_needs_https_or_localhost(db, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    plain = "http://192.168.1.20:8000"
    app, _ = await _app(db, monkeypatch, salli_public_url=plain)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=plain) as client:
        _, challenge = _pkce()
        refused = await client.get(
            "/mcp/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": MOBILE_CLIENT_ID,
                "redirect_uri": MOBILE_REDIRECT_URI,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": f"{plain}/v1",
            },
        )
    assert refused.status_code == 400 and "HTTPS" in refused.json()["detail"]


@pytest.mark.parametrize(
    ("age", "permissions"),
    [(timedelta(minutes=4, seconds=59), ["tax:activate"]), (timedelta(minutes=5, seconds=1), [])],
)
async def test_the_app_holds_tax_activate_only_soon_after_the_password(salli, age, permissions):
    tokens = await _sign_in(salli)
    await _set_sign_in_age(salli, MOBILE_CLIENT_ID, age)
    assert (await _me(salli, tokens["access_token"])).json()["permissions"] == permissions


async def test_the_app_s_sign_in_is_listed_and_has_no_absolute_end(salli):
    tokens = await _sign_in(salli)
    rows = (await salli.get("/v1/auth/sign-ins", headers=_bearer(tokens["access_token"]))).json()
    assert [(r["kind"], r["client_name"], r["current"]) for r in rows] == [
        ("mobile", "Salli app", True)
    ]
    # No absolute end, as the console's 12 hours: only its refresh token's,
    # which moves on with every refresh.
    ends = datetime.fromisoformat(rows[0]["expires_at"])
    assert ends - datetime.now(UTC) > timedelta(days=13)
    async with salli.engine.begin() as conn:
        seeded = (
            await conn.execute(
                text(
                    "SELECT first_party, step_up_seconds, redirect_uris FROM oauth_clients"
                    " WHERE client_id = :id"
                ),
                {"id": MOBILE_CLIENT_ID},
            )
        ).one()
    assert tuple(seeded) == (True, 300, [MOBILE_REDIRECT_URI])


async def test_meta_names_the_app_s_client_and_redirect(salli):
    oauth = (await salli.get("/v1/meta")).json()["oauth"]
    assert (oauth["mobile_client_id"], oauth["mobile_redirect_uri"]) == (
        MOBILE_CLIENT_ID,
        MOBILE_REDIRECT_URI,
    )
