"""
Invitations end to end (`salli-server members invite`, the /join page): the
real app and a real Postgres, over HTTP. A link is good once and for seven
days; only its hash is stored; the page has no script; the person may turn
on two-step sign-in there; both members' audit logs say so.
"""

from __future__ import annotations

import base64
import hashlib
import re
import time
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from salli import config as salli_config
from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.adapters.crypto.keyring import KeyRing
from salli.application import totp
from salli.application.services.login_service import LoginExists, LoginService
from salli.config import Settings
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

BASE = "https://money.example.org"
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


async def _rows(client, sql: str) -> list[tuple]:
    async with client.engine.connect() as conn:
        return [tuple(r) for r in (await conn.execute(text(sql))).all()]


async def test_an_invitation_is_good_once_and_stored_as_its_hash(salli):
    token = await salli.services.logins.invite("Ola@Example.org", base_currency="ISK")
    [(stored, email)] = await _rows(salli, "select token_hash, email from invitations")
    assert stored == hashlib.sha256(token.encode()).hexdigest() and email == "ola@example.org"

    page = await salli.get("/join", params={"t": token})
    assert page.status_code == 200 and "ola@example.org" in page.text
    assert "<script" not in page.text
    assert "script-src" not in page.headers["content-security-policy"]

    short = await salli.post("/join", data={"t": token, "password": "short"})
    assert short.status_code == 400  # and the invitation is still good
    joined = await salli.post("/join", data={"t": token, "password": "ola's long password"})
    assert joined.status_code == 200 and "You're in" in joined.text
    who = await salli.services.logins.authenticate("ola@example.org", "ola's long password")
    assert await salli.services.profile.get_base_currency(who.user_id) == "ISK"

    again = await salli.post("/join", data={"t": token, "password": "another long password"})
    assert again.status_code == 404
    actions = await _rows(salli, "select action from audit_logs order by created_at")
    assert [a for (a,) in actions] == ["member.invite", "member.join", "sign_in"]
    # The log outlives an erased account: nothing in it names the invitee.
    [(params,)] = await _rows(
        salli, "select params::text from audit_logs where action = 'member.invite'"
    )
    assert "ola" not in params.lower() and hashlib.sha256(token.encode()).hexdigest() in params


async def test_an_expired_or_unknown_link_does_nothing(salli):
    token = await salli.services.logins.invite("kai@example.org")
    async with salli.engine.begin() as conn:
        await conn.execute(
            text("update invitations set expires_at = :t"),
            {"t": datetime.now(UTC) - timedelta(seconds=1)},
        )
    assert (await salli.get("/join", params={"t": token})).status_code == 404
    assert (await salli.get("/join", params={"t": "salli_inv_nope"})).status_code == 404
    assert (
        await salli.post("/join", data={"t": token, "password": "kai's long password"})
    ).status_code == 404
    assert await _rows(salli, "select email from logins where email = 'kai@example.org'") == []


async def test_no_invitation_for_someone_already_here(salli):
    with pytest.raises(LoginExists):
        await salli.services.logins.invite(OWNER)


async def test_two_step_sign_in_can_be_turned_on_when_joining(salli):
    token = await salli.services.logins.invite("ines@example.org")
    page = await salli.get("/join", params={"t": token})
    secret = re.search(r'name=totp_secret value="([A-Z2-7]+)"', page.text).group(1)

    wrong = await salli.post(
        "/join",
        data={
            "t": token,
            "password": "ines's long password",
            "totp_secret": secret,
            "code": "000000",
        },
    )
    assert wrong.status_code == 400
    code = totp.code_at(secret, totp.step_of(time.time()))
    joined = await salli.post(
        "/join",
        data={"t": token, "password": "ines's long password", "totp_secret": secret, "code": code},
    )
    assert joined.status_code == 200 and "recovery codes" in joined.text
    [(enabled,)] = await _rows(
        salli, "select totp_enabled_at is not null from logins where email = 'ines@example.org'"
    )
    assert enabled
