"""Salli's own accounts against a real Postgres: what is stored (and what
never is), sessions, revocation, throttling across restarts, isolation
between users, and account deletion."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from salli.adapters.auth.passwords import Argon2PasswordHasher
from salli.application.services.login_service import (
    LoginExists,
    LoginService,
    SignInRefused,
    SignInThrottled,
)
from salli.application.services.personal_access_token_service import PersonalAccessTokenService
from tests.integration.pg import requires_postgres, scalar

pytestmark = requires_postgres

PASSWORD = "a long enough password"


def _service(uow_factory) -> LoginService:
    # Real argon2id, with cheap parameters so the suite stays quick.
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    return LoginService(uow_factory, hasher, default_currency="CHF")


async def _rows(uow_factory, sql: str) -> list[tuple]:
    async with uow_factory() as uow:
        return [tuple(r) for r in (await uow._session.execute(text(sql))).all()]  # noqa: SLF001


async def test_an_account_stores_a_hash_never_the_password(uow_factory):
    logins = _service(uow_factory)
    login = await logins.create_account("Ada@Example.org", PASSWORD, owner=True)
    [(email, stored, owner)] = await _rows(
        uow_factory, "select email, password_hash, is_owner from logins"
    )
    assert (email, owner) == ("ada@example.org", True)
    assert stored.startswith("$argon2id$") and PASSWORD not in stored
    [(currency,)] = await _rows(
        uow_factory, f"select base_currency from user_profiles where id = '{login['user_id']}'"
    )
    assert currency == "CHF"


async def test_the_database_holds_one_account_per_email_and_one_owner(uow_factory, db):
    logins = _service(uow_factory)
    await logins.create_account("ada@example.org", PASSWORD, owner=True)
    with pytest.raises(LoginExists):
        await logins.create_account("ADA@example.org", PASSWORD)
    with pytest.raises(LoginExists):
        await logins.create_account("bob@example.org", PASSWORD, owner=True)
    # And the constraints hold even past the service.
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("p2", {"base_currency": "EUR"})
    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            await uow.logins.create("p2", "Mixed@Case.org", "h", is_owner=False, at=_now())
    with pytest.raises(IntegrityError):
        async with uow_factory() as uow:
            await uow.logins.create("p2", "other@example.org", "h", is_owner=True, at=_now())


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)


async def test_a_session_is_stored_as_its_hash_and_ends_when_revoked(uow_factory, db):
    logins = _service(uow_factory)
    login = await logins.create_account("ada@example.org", PASSWORD)
    session = await logins.sign_in("ada@example.org", PASSWORD, user_agent="Salli for iOS")

    [(stored_hash, agent)] = await _rows(
        uow_factory, "select token_hash, user_agent from login_sessions"
    )
    assert stored_hash == hashlib.sha256(session.token.encode()).hexdigest()
    assert agent == "Salli for iOS"
    assert (
        scalar(db, f"select count(*) from login_sessions where token_hash = '{session.token}'") == 0
    )

    verified = await logins.verify_session(session.token)
    assert verified is not None and verified.user_id == login["user_id"]
    assert await logins.revoke_session(login["user_id"], session.id)
    assert await logins.verify_session(session.token) is None


async def test_one_user_cannot_see_or_end_another_s_sessions(uow_factory):
    logins = _service(uow_factory)
    ada = (await logins.create_account("ada@example.org", PASSWORD))["user_id"]
    bob = (await logins.create_account("bob@example.org", PASSWORD))["user_id"]
    adas = await logins.sign_in("ada@example.org", PASSWORD)
    await logins.sign_in("bob@example.org", PASSWORD)

    assert [s["id"] for s in await logins.list_sessions(ada)] == [adas.id]
    assert not await logins.revoke_session(bob, adas.id)
    assert await logins.verify_session(adas.token) is not None
    # A password change ends only your own other sessions.
    await logins.change_password(bob, PASSWORD, "bob's brand new password")
    assert await logins.verify_session(adas.token) is not None


async def test_the_throttle_survives_a_restart(uow_factory):
    await _service(uow_factory).create_account("ada@example.org", PASSWORD)
    for _ in range(5):
        with pytest.raises(SignInRefused):
            await _service(uow_factory).authenticate(
                "ada@example.org", "wrong", address="203.0.113.9"
            )
    # A new service (a restarted server) still knows.
    with pytest.raises(SignInThrottled):
        await _service(uow_factory).authenticate("ada@example.org", PASSWORD)
    stored = await _rows(uow_factory, "select key_hash from login_failures")
    assert len(stored) == 10  # by email and by address, hashed
    assert all("ada" not in k and "203.0" not in k for (k,) in stored)


async def test_a_hash_with_old_parameters_is_upgraded_at_sign_in(uow_factory):
    old = LoginService(
        uow_factory, Argon2PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1)
    )
    await old.create_account("ada@example.org", PASSWORD)
    new = LoginService(
        uow_factory, Argon2PasswordHasher(time_cost=2, memory_cost=2048, parallelism=1)
    )
    await new.authenticate("ada@example.org", PASSWORD)
    [(stored,)] = await _rows(uow_factory, "select password_hash from logins")
    assert stored.startswith("$argon2id$v=19$m=2048,t=2,p=1$")


async def test_signing_out_everywhere_revokes_every_kind_of_token(uow_factory):
    from salli.application.services.mcp_oauth_service import (
        CLI_CLIENT_ID,
        McpOAuthService,
        OAuthError,
    )

    logins = _service(uow_factory)
    uid = (await logins.create_account("ada@example.org", PASSWORD))["user_id"]
    other = (await logins.create_account("bob@example.org", PASSWORD))["user_id"]
    session = await logins.sign_in("ada@example.org", PASSWORD)
    tokens = PersonalAccessTokenService(uow_factory)
    pat = (await tokens.create(uid, "script"))["token"]
    bobs_pat = (await tokens.create(other, "script"))["token"]
    oauth = McpOAuthService(
        uow_factory,
        signing_secret="test",
        mcp_resource_url="https://salli.test/mcp",
        api_resource_url="https://salli.test/v1",
        consent_url="https://salli.test/consent",
        auth_code_ttl_seconds=60,
        access_token_ttl_seconds=3600,
        refresh_token_ttl_seconds=86400,
    )
    started = await oauth.start_device_authorization(CLI_CLIENT_ID, "", "https://salli.test/v1")
    await oauth.decide_device(started["user_code"], uid, approve=True)
    cli = await oauth.exchange_device_code(started["device_code"], CLI_CLIENT_ID)

    ended = await logins.sign_out_everywhere(uid)
    assert ended == {"sessions": 1, "oauth_tokens": 2, "personal_access_tokens": 1}
    assert await logins.verify_session(session.token) is None
    assert await tokens.verify(pat) is None
    assert await oauth.verify_access_token(cli["access_token"], audience="api") is None
    with pytest.raises(OAuthError):  # the refresh token is dead too
        await oauth.exchange_refresh_token(cli["refresh_token"], CLI_CLIENT_ID)
    # Someone else's are untouched.
    assert await tokens.verify(bobs_pat) is not None


async def test_deleting_an_account_deletes_its_login_and_sessions(uow_factory):
    logins = _service(uow_factory)
    uid = (await logins.create_account("ada@example.org", PASSWORD))["user_id"]
    await logins.sign_in("ada@example.org", PASSWORD)
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all(uid)
    assert counts["logins"] == 1 and counts["login_sessions"] == 1
    with pytest.raises(SignInRefused):
        await logins.authenticate("ada@example.org", PASSWORD)
    # The email can be given to someone new.
    await logins.create_account("ada@example.org", PASSWORD)
