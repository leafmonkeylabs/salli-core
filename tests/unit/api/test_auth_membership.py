"""
Who the API answers.

- Salli's own tokens (sessions, OAuth, personal access tokens), and nothing
  else — unless an extension's identity provider vouches for a token, or the
  local-dev fallback is switched on explicitly, in a development environment.
- Only members: no request ever creates an account.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from salli.application.ports import ExternalIdentity
from salli.application.services.user_profile_service import UserProfileService
from salli.config import Settings
from salli.interfaces.api.deps import get_current_user, get_principal

pytestmark = pytest.mark.asyncio


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _services(
    profile,
    oauth_user: str | None = None,
    dead_tokens: frozenset[str] = frozenset(),
    identity_provider=None,
) -> SimpleNamespace:
    """Services for authentication: the profile service, an OAuth server that
    knows one token ("salli-oauth-token") if given a user for it, plus
    `dead_tokens` it issued that no longer verify, and an extension's
    identity provider if given one."""

    async def verify(token: str, audience: str = "api"):
        return {"user_id": oauth_user} if oauth_user and token == "salli-oauth-token" else None

    async def is_salli_token(token: str) -> bool:
        return token in dead_tokens or (oauth_user is not None and token == "salli-oauth-token")

    async def no_session(token: str):
        return None

    return SimpleNamespace(
        profile=profile,
        mcp_oauth=SimpleNamespace(verify_access_token=verify, is_salli_token=is_salli_token),
        logins=SimpleNamespace(verify_session=no_session),
        tokens=SimpleNamespace(verify=no_session),
        extensions=SimpleNamespace(identity_provider=identity_provider),
    )


async def _caller(token: str, settings: Settings, services) -> str:
    """Authenticate the token, then check membership — as a request does."""
    principal = await get_principal(_creds(token), settings, services)
    return await get_current_user(principal, services)


class _Profiles:
    def __init__(self, rows=None) -> None:
        self.rows = dict(rows or {})
        self.reads = 0

    async def get(self, user_id):
        self.reads += 1
        return self.rows.get(user_id)

    async def upsert(self, user_id, fields):
        self.rows.setdefault(user_id, {"id": user_id}).update(
            {k: v for k, v in fields.items() if v is not None}
        )


def _profile_service(rows=None) -> tuple[UserProfileService, _Profiles]:
    profiles = _Profiles(rows)

    @asynccontextmanager
    async def uow():
        yield SimpleNamespace(user_profiles=profiles)

    return UserProfileService(uow, None, None, None), profiles


# ── Tokens that are none of Salli's ─────────────────────────────────────────


async def test_a_token_that_is_none_of_salli_s_is_refused():
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    for token in ("owner", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJvd25lciJ9.c2ln", "salli_st_unknown"):
        with pytest.raises(HTTPException) as caught:
            await get_principal(_creds(token), _settings(), _services(profile))
        assert caught.value.status_code == 401
        assert caught.value.headers == {"WWW-Authenticate": "Bearer"}


async def test_the_dev_fallback_needs_the_flag_and_a_development_environment():
    profile, _ = _profile_service({"dev-user": {"id": "dev-user"}})
    dev = _settings(salli_insecure_dev_auth=True, environment="development")
    principal = await get_principal(_creds("dev-user"), dev, _services(profile))
    assert (principal.user_id, principal.method) == ("dev-user", "dev")

    for settings in (
        _settings(salli_insecure_dev_auth=True, environment="production"),
        _settings(salli_insecure_dev_auth=False, environment="development"),
    ):
        with pytest.raises(HTTPException) as caught:
            await get_principal(_creds("dev-user"), settings, _services(profile))
        assert caught.value.status_code == 401


class _Provider:
    """An extension's identity provider that knows one token."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def verify(self, token: str) -> ExternalIdentity | None:
        self.asked.append(token)
        return ExternalIdentity("member", "m@example.org") if token == "idp-token" else None


async def test_an_identity_provider_vouches_for_its_own_tokens_as_a_session():
    profile, _ = _profile_service({"member": {"id": "member"}})
    provider = _Provider()
    services = _services(profile, identity_provider=provider)

    principal = await get_principal(_creds("idp-token"), _settings(), services)
    assert (principal.user_id, principal.email, principal.method) == (
        "member",
        "m@example.org",
        "session",
    )
    with pytest.raises(HTTPException) as caught:
        await get_principal(_creds("someone-else"), _settings(), services)
    assert caught.value.status_code == 401


async def test_an_identity_provider_never_sees_a_salli_token_and_never_makes_an_account():
    profile, profiles = _profile_service({"owner": {"id": "owner"}})
    provider = _Provider()
    services = _services(profile, identity_provider=provider)
    for token in ("salli_at_expired", "salli_pat_revoked", "salli_st_ended"):
        with pytest.raises(HTTPException):
            await get_principal(_creds(token), _settings(), services)
    assert provider.asked == []

    # Vouched for, but not a member here: refused, and nothing is created.
    with pytest.raises(HTTPException) as caught:
        await _caller("idp-token", _settings(), services)
    assert caught.value.status_code == 403
    assert "member" not in profiles.rows


# ── Membership ──────────────────────────────────────────────────────────────


DEV = {"salli_insecure_dev_auth": True, "environment": "development"}


async def test_a_closed_instance_refuses_a_stranger_and_creates_nothing():
    profile, profiles = _profile_service({"owner": {"id": "owner"}})
    services = _services(profile)

    with pytest.raises(HTTPException) as caught:
        await _caller("stranger", _settings(**DEV), services)

    assert caught.value.status_code == 403
    assert "stranger" not in profiles.rows


async def test_a_closed_instance_answers_its_members():
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    services = _services(profile)
    assert await _caller("owner", _settings(**DEV), services) == "owner"


async def test_no_request_creates_an_account_even_under_the_dev_fallback():
    profile, profiles = _profile_service()
    with pytest.raises(HTTPException) as caught:
        await _caller("newcomer", _settings(**DEV), _services(profile))
    assert caught.value.status_code == 403
    assert "newcomer" not in profiles.rows


async def test_membership_is_read_once_per_process():
    profile, profiles = _profile_service({"owner": {"id": "owner"}})
    for _ in range(3):
        assert await profile.ensure_user("owner", None, may_create=False)
    assert profiles.reads == 1


async def test_a_missing_email_is_filled_in_but_never_overwritten():
    profile, profiles = _profile_service({"a": {"id": "a"}, "b": {"id": "b", "email": "b@x"}})
    await profile.ensure_user("a", "a@x", may_create=False)
    await profile.ensure_user("b", "changed@x", may_create=False)
    assert profiles.rows["a"]["email"] == "a@x"
    assert profiles.rows["b"]["email"] == "b@x"


async def test_a_deleted_account_is_forgotten():
    profile, profiles = _profile_service({"owner": {"id": "owner"}})
    assert await profile.ensure_user("owner", None, may_create=False)
    del profiles.rows["owner"]
    profile.forget("owner")
    assert not await profile.ensure_user("owner", None, may_create=False)


async def test_a_salli_token_is_its_user_even_under_the_dev_fallback():
    # The fallback takes any token as a user id; a CLI that signed in with
    # the device flow was taken to be the user named by its access token.
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    services = _services(profile, oauth_user="owner")
    principal = await get_principal(_creds("salli-oauth-token"), _settings(**DEV), services)
    assert (principal.user_id, principal.method) == ("owner", "oauth")
    dev = await get_principal(_creds("someone"), _settings(**DEV), services)
    assert (dev.user_id, dev.method) == ("someone", "dev")


async def test_a_dead_salli_token_is_refused_under_the_dev_fallback():
    # An expired, revoked or MCP-audience token, or a refresh token, failed to
    # verify and was then taken to be a user id by the dev fallback.
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    services = _services(profile, dead_tokens=frozenset({"expired-or-revoked-token"}))
    with pytest.raises(HTTPException) as refused:
        await get_principal(_creds("expired-or-revoked-token"), _settings(**DEV), services)
    assert refused.value.status_code == 401
    dev = await get_principal(_creds("not-a-salli-token"), _settings(**DEV), services)
    assert (dev.user_id, dev.method) == ("not-a-salli-token", "dev")


@pytest.mark.parametrize(
    ("overrides", "holds_secrets"),
    [
        ({**DEV}, False),  # the dev fallback is live: anyone can be anyone
        ({}, True),  # only Salli's own tokens get in
        ({"salli_insecure_dev_auth": True, "environment": "production"}, True),
    ],
)
async def test_secrets_are_kept_unless_the_dev_fallback_is_live(overrides, holds_secrets):
    from salli.config import auth_can_hold_secrets, insecure_dev_auth

    settings = _settings(**overrides)
    assert auth_can_hold_secrets(settings) is holds_secrets
    assert insecure_dev_auth(settings) is not holds_secrets


async def test_a_prefixed_salli_token_is_never_a_dev_user_id():
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    services = _services(profile)  # knows no tokens: no lookup is needed
    for token in ("salli_at_expired", "salli_rt_refresh", "salli_st_ended", "salli_pat_x"):
        with pytest.raises(HTTPException) as refused:
            await get_principal(_creds(token), _settings(**DEV), services)
        assert refused.value.status_code == 401
