"""
Two-step sign-in end to end: the real app, its real services and a real
Postgres, over HTTP.

- turning it on (`POST /v1/auth/totp`, then `/confirm` with a code) and off
  (`DELETE /v1/auth/totp`, the password and a code), behind the console's
  step-up like the other sensitive changes, and shown by `GET /v1/auth/me`;
- once on, a session, the sign-in page and the device page each refuse the
  password alone, and accept it with the code; no code works twice;
- the owner's reset can turn it off (`--clear-totp`);
- the table keeps a secret and its key's version together.
"""

from __future__ import annotations

import base64
import hashlib
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from salli import config as salli_config
from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.adapters.crypto.keyring import KeyRing
from salli.application import totp
from salli.application.services.login_service import LoginService
from salli.application.services.mcp_oauth_service import CONSOLE_CLIENT_ID
from salli.config import Settings
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

BASE = "https://money.example.org"
CALLBACK = f"{BASE}/console/callback"
OWNER, PASSWORD = "owner@example.org", "the owner's long password"
KEYS = "1:" + base64.b64encode(b"t" * 32).decode()


@pytest.fixture
async def salli(db, monkeypatch):
    from salli.composition import build_services
    from salli.interfaces.api.deps import get_services, get_settings
    from salli.interfaces.api.main import create_app

    settings = Settings(
        _env_file=None,
        database_url=db,
        environment="production",
        salli_public_url=BASE,
        mcp_signing_secret="s" * 48,
        byok_encryption_keys=KEYS,
    )
    monkeypatch.setattr(salli_config, "_settings", settings)
    services = build_services(settings)
    services.logins = LoginService(
        services.tokens._uow_factory,  # noqa: SLF001
        Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1),
        keyring=KeyRing(KEYS),
    )
    await services.logins.create_account(OWNER, PASSWORD, owner=True, base_currency="NZD")
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    app.dependency_overrides[get_settings] = lambda: settings
    engine = create_async_engine(db, connect_args={"statement_cache_size": 0})
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        client.services = services  # type: ignore[attr-defined]
        client.engine = engine  # type: ignore[attr-defined]
        yield client
    await engine.dispose()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _now_code(secret: str) -> str:
    return totp.code_at(secret, totp.step_of(time.time()))


def _next_code(secret: str) -> str:
    """The code for the next 30 seconds: still good now, and unused by the
    confirmation, which used this one's."""
    return totp.code_at(secret, totp.step_of(time.time()) + 1)


async def _session(salli, code: str | None = None):
    body = {"email": OWNER, "password": PASSWORD} | ({"code": code} if code else {})
    return await salli.post("/v1/auth/sessions", json=body)


async def _turn_on(salli, token: str) -> tuple[str, list[str]]:
    begun = await salli.post("/v1/auth/totp", headers=_bearer(token))
    assert begun.status_code == 201, begun.text
    secret = begun.json()["secret"]
    assert begun.json()["uri"].startswith("otpauth://totp/Salli%3Aowner%40example.org?")
    confirmed = await salli.post(
        "/v1/auth/totp/confirm", json={"code": _now_code(secret)}, headers=_bearer(token)
    )
    assert confirmed.status_code == 200, confirmed.text
    return secret, confirmed.json()["recovery_codes"]


async def test_turned_on_a_session_needs_the_code_and_each_code_works_once(salli):
    token = (await _session(salli)).json()["token"]
    me = await salli.get("/v1/auth/me", headers=_bearer(token))
    assert me.json()["totp_enabled"] is False
    secret, recovery = await _turn_on(salli, token)
    assert len(recovery) == 10
    assert (await salli.get("/v1/auth/me", headers=_bearer(token))).json()["totp_enabled"]

    alone = await _session(salli)
    assert alone.status_code == 401 and "authenticator" in alone.json()["detail"]
    code = _next_code(secret)
    assert (await _session(salli, code)).status_code == 201
    again = await _session(salli, code)
    assert again.status_code == 401 and "didn't match" in again.json()["detail"]

    assert (await _session(salli, recovery[0])).status_code == 201
    assert (await _session(salli, recovery[0])).status_code == 401
    # Turning it on again needs it off first.
    assert (await salli.post("/v1/auth/totp", headers=_bearer(token))).status_code == 409

    # Off: the password and a code.
    no_code = await salli.request(
        "DELETE", "/v1/auth/totp", json={"password": PASSWORD}, headers=_bearer(token)
    )
    assert no_code.status_code == 403
    off = await salli.request(
        "DELETE",
        "/v1/auth/totp",
        json={"password": PASSWORD, "code": recovery[1]},
        headers=_bearer(token),
    )
    assert off.status_code == 204, off.text
    assert (await _session(salli)).status_code == 201


async def test_wrong_codes_are_throttled(salli):
    token = (await _session(salli)).json()["token"]
    secret, _ = await _turn_on(salli, token)
    for _ in range(5):
        assert (await _session(salli, "aaaaa-aaaaa")).status_code == 401
    throttled = await _session(salli, _next_code(secret))
    assert throttled.status_code == 429 and "Retry-After" in throttled.headers


def _pkce() -> tuple[str, str]:
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


async def _page_sign_in(salli, code: str = "") -> tuple[int, str]:
    """The console's sign-in page: its status, and the access token if it signed in."""
    verifier, challenge = _pkce()
    to_page = await salli.get(
        "/mcp/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": CONSOLE_CLIENT_ID,
            "redirect_uri": CALLBACK,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": f"{BASE}/v1",
            "state": "st",
        },
    )
    rt = parse_qs(urlparse(to_page.headers["location"]).query)["rt"][0]
    page = await salli.get(to_page.headers["location"].removeprefix(BASE))
    assert "name=code autocomplete=one-time-code" in page.text
    decided = await salli.post(
        "/mcp/oauth/consent-page",
        data={"rt": rt, "decision": "allow", "email": OWNER, "password": PASSWORD, "code": code},
    )
    if decided.status_code != 303:
        assert PASSWORD not in decided.text
        return decided.status_code, decided.text
    query = parse_qs(urlparse(decided.headers["location"]).query)
    tokens = await salli.post(
        "/mcp/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": CALLBACK,
            "client_id": CONSOLE_CLIENT_ID,
            "code_verifier": verifier,
        },
    )
    return 303, tokens.json()["access_token"]


async def test_the_sign_in_page_and_the_console_s_step_up_need_the_code(salli):
    status, console = await _page_sign_in(salli)
    assert status == 303
    secret, recovery = await _turn_on(salli, console)

    status, page = await _page_sign_in(salli)
    assert status == 401 and "Enter the code from your authenticator app" in page
    status, console = await _page_sign_in(salli, _next_code(secret))
    assert status == 303

    # Past the console's five minutes, turning it off sends the person
    # through the sign-in page (and so the code) again.
    async with salli.engine.begin() as conn:
        await conn.execute(
            text("UPDATE oauth_grants SET authenticated_at = :at"),
            {"at": datetime.now(UTC) - timedelta(minutes=6)},
        )
    stale = await salli.request(
        "DELETE",
        "/v1/auth/totp",
        json={"password": PASSWORD, "code": recovery[0]},
        headers=_bearer(console),
    )
    assert stale.status_code == 403
    assert stale.json()["type"] == "/problems/step-up-required"
    assert (await salli.post("/v1/auth/totp", headers=_bearer(console))).status_code == 403


async def test_the_device_page_needs_the_code(salli):
    token = (await _session(salli)).json()["token"]
    secret, _ = await _turn_on(salli, token)
    started = await salli.post(
        "/mcp/oauth/device_authorization", data={"client_id": "salli-cli", "resource": f"{BASE}/v1"}
    )
    assert started.status_code == 200, started.text
    user_code = started.json()["user_code"]
    form = {"user_code": user_code, "decision": "allow", "email": OWNER, "password": PASSWORD}
    alone = await salli.post("/mcp/oauth/device", data=form)
    assert alone.status_code == 401 and "authenticator" in alone.text
    signed = await salli.post("/mcp/oauth/device", data=form | {"code": _next_code(secret)})
    assert signed.status_code == 200 and "Signed in" in signed.text


async def test_the_owner_s_reset_can_turn_it_off(salli):
    token = (await _session(salli)).json()["token"]
    await _turn_on(salli, token)
    reset = await salli.services.logins.reset_password(OWNER, PASSWORD, clear_totp=True)
    assert reset["totp_cleared"] is True
    assert (await _session(salli)).status_code == 201


async def test_a_secret_is_kept_with_the_version_of_the_key_that_sealed_it(salli):
    async with salli.engine.connect() as conn:
        with pytest.raises(IntegrityError, match="ck_logins_totp"):
            await conn.execute(text("UPDATE logins SET totp_secret = 'sealed'"))
    async with salli.engine.connect() as conn:
        with pytest.raises(IntegrityError, match="ck_logins_totp"):
            await conn.execute(text("UPDATE logins SET totp_enabled_at = now()"))
