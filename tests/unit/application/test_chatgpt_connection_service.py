"""
A ChatGPT connection decides whose plan pays and holds tokens that renew
themselves, so its failure modes matter more than its happy path: sealed at
rest, renewed before expiry with the rotated pair stored together, marked for
sign-in (never quietly replaced) when OpenAI refuses, paused at the plan's
limit, and signed out with the session ended at OpenAI.

The row lock that makes concurrent renewals safe needs a real database; it is
proved in tests/integration/test_ai_connections_storage.py.
"""

from __future__ import annotations

import base64
import datetime as dt
import os
from typing import Any

import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.adapters.llm.chatgpt_oauth import SignInError
from salli.application.services.chatgpt_connection_service import (
    ChatGPTConnectionService,
    ChatGPTRecord,
    ChatGPTUnavailable,
)
from salli.domain.llm import LLMProviderUnavailable, LLMSignInRequired, LLMUsageLimit
from tests.openai_fakes import FakeAuthServer

USER = "u1"
KEYS = "1:" + base64.b64encode(os.urandom(32)).decode()
NOW = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.UTC)


class FakeConnections:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
        self.locked: list[tuple[str, str]] = []

    async def get(self, user_id: str, provider: str) -> dict[str, Any] | None:
        row = self.rows.get((user_id, provider))
        return dict(row) if row else None

    async def get_for_update(self, user_id: str, provider: str) -> dict[str, Any] | None:
        self.locked.append((user_id, provider))
        return await self.get(user_id, provider)

    async def save(self, user_id: str, provider: str, fields: dict[str, Any]) -> bool:
        created = (user_id, provider) not in self.rows
        row = self.rows.setdefault(
            (user_id, provider),
            {"status_detail": None, "expires_at": None, "paused_until": None},
        )
        row.update(fields)
        return created

    async def update(self, user_id: str, provider: str, fields: dict[str, Any]) -> bool:
        if (user_id, provider) not in self.rows:
            return False
        self.rows[(user_id, provider)].update(fields)
        return True

    async def delete(self, user_id: str, provider: str) -> bool:
        return self.rows.pop((user_id, provider), None) is not None


class FakeInstanceSettings:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get_or_create(self, key: str, value: str) -> str:
        return self.values.setdefault(key, value)


_SETTINGS = FakeInstanceSettings()


class FakeUoW:
    def __init__(self, repo: FakeConnections, settings: FakeInstanceSettings = _SETTINGS) -> None:
        self.ai_connections = repo
        self.instance_settings = settings

    async def __aenter__(self) -> FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> dt.datetime:
        return self.now


@pytest.fixture
def world():
    repo = FakeConnections()
    auth = FakeAuthServer()
    clock = Clock()
    service = ChatGPTConnectionService(
        lambda: FakeUoW(repo), KeyRing(KEYS), auth.oauth(), clock=clock
    )
    return service, repo, auth, clock


def _record(**overrides: Any) -> ChatGPTRecord:
    fields: dict[str, Any] = {
        "sub": "user-sub-1",
        "client_id": "oaiapp_test",
        "email": "me@example.com",
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "id_token": "id-token-1",
        "scopes": ("chatgpt.tokens.use.direct", "offline_access", "openid"),
        "expires_at": NOW + dt.timedelta(hours=1),
    }
    fields.update(overrides)
    return ChatGPTRecord(**fields)


# ── At rest ───────────────────────────────────────────────────────────────────


async def test_nothing_is_stored_in_the_clear(world):
    service, repo, _, _ = world
    assert await service.save_record(USER, _record()) is True

    row = repo.rows[(USER, "chatgpt")]
    for secret in ("access-1", "refresh-1", "id-token-1", "me@example.com", "oaiapp_test"):
        assert secret not in str(row)
    assert row["status"] == "active"


async def test_a_row_moved_to_another_user_does_not_open(world):
    service, repo, _, _ = world
    await service.save_record(USER, _record())
    repo.rows[("attacker", "chatgpt")] = dict(repo.rows[(USER, "chatgpt")])

    with pytest.raises(LLMSignInRequired):
        await service.access_token("attacker")


async def test_status_shows_the_account_and_never_a_token(world):
    service, _, _, _ = world
    await service.save_record(USER, _record())

    status = await service.status(USER)

    assert status["connected"] is True
    assert status["email"] == "me@example.com"
    assert status["client_id"] == "oaiapp_test"
    for secret in ("access-1", "refresh-1", "id-token-1"):
        assert secret not in str(status)


async def test_status_without_a_connection(world):
    service, _, _, _ = world
    assert (await service.status(USER))["status"] == "not_connected"
    assert await service.presence(USER) is None


@pytest.mark.parametrize(("keys", "enabled"), [("", True), (KEYS, False)])
async def test_unavailable_without_an_encryption_key_or_real_auth(keys, enabled):
    repo = FakeConnections()
    service = ChatGPTConnectionService(
        lambda: FakeUoW(repo), KeyRing(keys), FakeAuthServer().oauth(), feature_enabled=enabled
    )
    assert service.available is False
    with pytest.raises(ChatGPTUnavailable):
        await service.save_record(USER, _record())
    assert repo.rows == {}


# ── Renewal ───────────────────────────────────────────────────────────────────


async def test_a_fresh_token_is_used_as_it_is(world):
    service, repo, auth, _ = world
    await service.save_record(USER, _record())

    assert await service.access_token(USER) == "access-1"
    assert auth.refreshes == [] and repo.locked == []


async def test_a_token_about_to_expire_is_renewed_and_the_new_pair_stored_together(world):
    service, repo, auth, clock = world
    await service.save_record(USER, _record())
    clock.now = NOW + dt.timedelta(minutes=56)

    assert await service.access_token(USER) == "access-2"

    (refresh,) = auth.refreshes
    assert refresh == {
        "grant_type": "refresh_token",
        "client_id": "oaiapp_test",  # the issued id, never dynamic_agent_client
        "refresh_token": "refresh-1",
        "resource": "https://api.openai.com/v1",
    }
    assert "scope" not in refresh  # omitted, so the grant stays as it is
    assert repo.locked == [(USER, "chatgpt")]
    stored = await service.record(USER)
    assert (stored.access_token, stored.refresh_token) == ("access-2", "refresh-2")
    assert stored.expires_at == clock.now + dt.timedelta(hours=1)
    # The next request uses it, and the spent refresh token is never sent again.
    assert await service.access_token(USER) == "access-2"
    assert len(auth.refreshes) == 1


async def test_a_rejected_token_is_renewed_once(world):
    service, _, auth, _ = world
    await service.save_record(USER, _record())

    session = service.session(USER)
    assert await session.bearer() == "access-1"
    assert await session.bearer(force_refresh=True) == "access-2"
    assert len(auth.refreshes) == 1


async def test_a_token_renewed_by_another_request_is_not_renewed_again(world):
    """The second request reached the lock after the first renewed: it was
    rejected with the old token, so it takes the new one instead of spending
    the refresh token again."""
    service, _, auth, _ = world
    await service.save_record(USER, _record())

    assert await service.access_token(USER, rejected="access-1") == "access-2"
    assert await service.access_token(USER, rejected="access-1") == "access-2"
    assert len(auth.refreshes) == 1


async def test_earliest_refresh_at_is_respected_until_the_token_expires(world):
    service, _, auth, clock = world
    await service.save_record(USER, _record(earliest_refresh_at=NOW + dt.timedelta(minutes=58)))
    clock.now = NOW + dt.timedelta(minutes=56)
    assert await service.access_token(USER) == "access-1"
    assert auth.refreshes == []

    clock.now = NOW + dt.timedelta(minutes=58)
    assert await service.access_token(USER) == "access-2"


@pytest.mark.parametrize(
    "code",
    [
        "invalid_grant",
        "invalid_refresh_token",
        "token_expired",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
    ],
)
async def test_a_refused_renewal_marks_the_connection_for_sign_in(world, code):
    service, repo, auth, clock = world
    await service.save_record(USER, _record())
    auth.refuse_with = code
    clock.now = NOW + dt.timedelta(minutes=59)

    with pytest.raises(LLMSignInRequired, match="salli ai connect chatgpt"):
        await service.access_token(USER)

    assert repo.rows[(USER, "chatgpt")]["status"] == "needs_sign_in"
    stored = await service.record(USER)
    # The unusable tokens are cleared; the account, its issued client id and
    # the ID token (the next sign-in's hint) are kept.
    assert (stored.access_token, stored.refresh_token) == (None, None)
    assert (stored.client_id, stored.id_token) == ("oaiapp_test", "id-token-1")
    # Every later request says so, without asking OpenAI again.
    with pytest.raises(LLMSignInRequired):
        await service.access_token(USER)
    assert len(auth.refreshes) == 1


async def test_an_invalid_client_is_forgotten_so_the_next_sign_in_registers_anew(world):
    service, _, auth, clock = world
    await service.save_record(USER, _record())
    auth.refuse_with = "invalid_client"
    clock.now = NOW + dt.timedelta(minutes=59)

    with pytest.raises(LLMSignInRequired):
        await service.access_token(USER)
    assert (await service.record(USER)).client_id is None


async def test_an_unreachable_auth_server_keeps_the_credentials(world):
    """ "Do not erase credentials solely because of a temporary network or
    infrastructure failure.\""""
    service, repo, auth, clock = world
    await service.save_record(USER, _record())
    auth.fail_status = 503
    clock.now = NOW + dt.timedelta(minutes=59)

    with pytest.raises(LLMProviderUnavailable):
        await service.access_token(USER)

    assert repo.rows[(USER, "chatgpt")]["status"] == "active"
    assert (await service.record(USER)).refresh_token == "refresh-1"
    auth.fail_status = None
    assert await service.access_token(USER) == "access-2"


async def test_a_renewal_without_plan_use_needs_consent_again(world):
    service, repo, auth, clock = world
    await service.save_record(USER, _record())
    auth.grant_plan = False
    clock.now = NOW + dt.timedelta(minutes=59)

    with pytest.raises(LLMSignInRequired, match="allow plan use"):
        await service.access_token(USER)
    assert repo.rows[(USER, "chatgpt")]["status"] == "needs_consent"


# ── The plan's usage limit ────────────────────────────────────────────────────


async def test_a_usage_limit_pauses_new_requests_for_a_while(world):
    service, _, auth, clock = world
    await service.save_record(USER, _record())

    await service.session(USER).usage_limited()

    with pytest.raises(LLMUsageLimit, match="chatgpt.com/settings/usage"):
        await service.access_token(USER)
    assert (await service.status(USER))["paused_until"] is not None
    clock.now = NOW + dt.timedelta(minutes=11)
    assert await service.access_token(USER) == "access-1"
    assert auth.refreshes == []


# ── Sign out ──────────────────────────────────────────────────────────────────


async def test_disconnecting_ends_the_session_at_openai_and_keeps_the_mapping(world):
    service, repo, auth, _ = world
    await service.save_record(USER, _record())

    result = await service.disconnect(USER)

    assert result == {
        "disconnected": True,
        "revoked": True,
        "message": "Disconnected from ChatGPT.",
    }
    assert auth.revoked == [
        {"token": "refresh-1", "token_type_hint": "refresh_token", "client_id": "oaiapp_test"}
    ]
    assert repo.rows[(USER, "chatgpt")]["status"] == "signed_out"
    stored = await service.record(USER)
    assert (stored.access_token, stored.refresh_token, stored.id_token) == (None, None, None)
    assert (stored.client_id, stored.sub) == ("oaiapp_test", "user-sub-1")
    assert await service.presence(USER) is None
    with pytest.raises(LLMSignInRequired):
        await service.access_token(USER)


async def test_an_unconfirmed_revocation_still_clears_and_says_so(world):
    service, repo, auth, _ = world
    await service.save_record(USER, _record())
    auth.revoke_status = 503

    result = await service.disconnect(USER)

    assert result["revoked"] is False
    assert "ChatGPT's settings" in result["message"]
    assert len(auth.revoked) == 3  # retried with backoff
    assert repo.rows[(USER, "chatgpt")]["status"] == "signed_out"


async def test_disconnecting_nothing(world):
    service, _, _, _ = world
    assert (await service.disconnect(USER))["disconnected"] is False


# ── The host id ───────────────────────────────────────────────────────────────


async def test_the_instance_has_one_stable_uuid_host_id():
    import uuid

    settings = FakeInstanceSettings()
    service = ChatGPTConnectionService(
        lambda: FakeUoW(FakeConnections(), settings), KeyRing(KEYS), FakeAuthServer().oauth()
    )

    host = await service.host_id()

    assert host.startswith("urn:uuid:")
    assert uuid.UUID(host.removeprefix("urn:uuid:")).version == 4
    assert await service.host_id() == host


# ── Signing in ────────────────────────────────────────────────────────────────


async def _sign_in(service: ChatGPTConnectionService, auth: FakeAuthServer, **connect: Any):
    from salli.adapters.llm.chatgpt_oauth import authorization_url, begin_sign_in, read_callback

    context = await service.sign_in_context(USER)
    pending = begin_sign_in(
        host_id=context.host_id,
        redirect_uri="http://127.0.0.1:1455/auth/callback",
        client_id=context.client_id,
    )
    callback = read_callback(pending, auth.authorize(authorization_url(pending)))
    tokens = await service.oauth.exchange_code(pending, callback)
    return await service.connect(
        USER, tokens, client_id=callback.client_id, nonce=pending.nonce, **connect
    )


async def test_a_sign_in_is_checked_then_kept(world):
    service, repo, auth, _ = world

    status = await _sign_in(service, auth)

    assert status["status"] == "active" and status["connected"] is True
    assert status["first_time"] is True
    assert status["email"] == "me@example.com"
    assert status["client_id"] == "oaiapp_test"
    # It was tried for what it is for before it was kept.
    (models,) = auth.model_requests
    assert models.headers["authorization"] == "Bearer access-1"
    record = await service.record(USER)
    assert (record.sub, record.refresh_token) == ("user-sub-1", "refresh-1")
    assert "chatgpt.tokens.use.direct" in record.scopes


async def test_signing_in_again_reuses_the_registration_and_ends_the_old_session(world):
    service, _, auth, _ = world
    await _sign_in(service, auth)
    context = await service.sign_in_context(USER)
    assert (context.client_id, context.login_hint, context.id_token_hint) == (
        "oaiapp_test",
        "me@example.com",
        (await service.record(USER)).id_token,
    )
    auth.valid_refresh = "refresh-9"

    status = await _sign_in(service, auth, expected_sub=context.expected_sub)

    assert status["first_time"] is False
    assert (await service.record(USER)).refresh_token == "refresh-9"
    assert [r["token"] for r in auth.revoked] == ["refresh-1"]


async def test_signing_in_again_as_another_account_is_refused(world):
    service, _, auth, _ = world
    await _sign_in(service, auth)
    auth.id_claims = {"sub": "someone-else"}

    with pytest.raises(SignInError, match="different ChatGPT account"):
        await _sign_in(service, auth, expected_sub="user-sub-1")
    assert (await service.record(USER)).sub == "user-sub-1"


async def test_without_plan_use_the_sign_in_is_kept_with_plan_use_off(world):
    service, repo, auth, _ = world
    auth.grant_plan = False

    with pytest.raises(SignInError, match="plan use wasn't allowed"):
        await _sign_in(service, auth)

    assert repo.rows[(USER, "chatgpt")]["status"] == "needs_consent"
    record = await service.record(USER)
    assert record.access_token is None and record.refresh_token is None
    assert auth.model_requests == []
    # The next sign-in reuses the registration and asks for consent again.
    context = await service.sign_in_context(USER)
    assert context.client_id == "oaiapp_test" and context.ask_consent is True
    auth.grant_plan = True
    assert (await _sign_in(service, auth))["first_time"] is True


async def test_a_sign_in_whose_token_cannot_list_models_is_not_kept(world):
    from salli.domain.llm import LLMKeyRejected

    service, repo, auth, _ = world
    auth.models_status = 401

    with pytest.raises(LLMKeyRejected):
        await _sign_in(service, auth)
    assert repo.rows == {}


async def test_dynamic_agent_client_is_never_kept_as_the_client_id(world):
    from salli.adapters.llm.chatgpt_oauth import token_set

    service, repo, auth, _ = world
    tokens = token_set(
        {
            "access_token": "a",
            "refresh_token": "r",
            "id_token": auth.signer.id_token(),
            "scope": "chatgpt.tokens.use.direct",
            "expires_in": 3600,
        }
    )
    with pytest.raises(SignInError, match="dynamic_agent_client"):
        await service.connect(USER, tokens, client_id="dynamic_agent_client")
    assert repo.rows == {}


async def test_tokens_from_another_registration_are_refused(world):
    import base64
    import json as _json

    from salli.adapters.llm.chatgpt_oauth import token_set

    service, repo, auth, _ = world
    claims = base64.urlsafe_b64encode(_json.dumps({"client_id": "oaiapp_other"}).encode())
    access = f"e30.{claims.decode().rstrip('=')}.sig"
    tokens = token_set(
        {
            "access_token": access,
            "refresh_token": "r",
            "id_token": auth.signer.id_token(),
            "scope": "chatgpt.tokens.use.direct",
            "expires_in": 3600,
        }
    )
    with pytest.raises(SignInError, match="different registration"):
        await service.connect(USER, tokens, client_id="oaiapp_test")
    assert repo.rows == {}


async def test_a_credential_from_another_computer_is_checked_and_kept(world):
    """OpenAI's example credential record, as a laptop would write it: its
    `scopes` list and `saved_at` are read, its host id is not."""
    service, _, auth, _ = world
    host = await service.host_id()
    saved_at = "2026-10-09T11:50:00+00:00"

    status = await service.import_credential(
        USER,
        {
            "email": "me@example.com",
            "issuer": "https://auth.openai.com",
            "subject": "user-sub-1",
            "client_id": "oaiapp_test",
            "ext_agent_host_id": "urn:uuid:the-laptops-own",
            "id_token": auth.signer.id_token(),
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": ["chatgpt.tokens.use.direct", "email", "offline_access", "openid"],
            "saved_at": saved_at,
        },
    )

    assert status["status"] == "active"
    assert status["expires_at"] == "2026-10-09T12:50:00+00:00"
    assert await service.host_id() == host  # never the laptop's


async def test_a_new_account_registers_afresh(world):
    service, _, auth, _ = world
    await _sign_in(service, auth)
    context = await service.sign_in_context(USER, new_account=True)
    assert context.client_id is None and context.expected_sub is None
