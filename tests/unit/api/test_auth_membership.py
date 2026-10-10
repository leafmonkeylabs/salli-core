"""
Who the API answers.

- With no auth provider configured, nobody — unless the local-dev fallback is
  switched on explicitly, in a development environment.
- A closed instance (the default) answers only its members; an open one
  creates an account for anyone the provider vouches for.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from salli.application.services.user_profile_service import UserProfileService
from salli.config import Settings
from salli.interfaces.api.deps import _decode_jwt, get_current_user, get_principal

pytestmark = pytest.mark.asyncio


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _services(
    profile, oauth_user: str | None = None, dead_tokens: frozenset[str] = frozenset()
) -> SimpleNamespace:
    """Services for authentication: the profile service, and an OAuth server
    that knows one token ("salli-oauth-token") if given a user for it, plus
    `dead_tokens` it issued that no longer verify."""

    async def verify(token: str, audience: str = "api"):
        return {"user_id": oauth_user} if oauth_user and token == "salli-oauth-token" else None

    async def is_salli_token(token: str) -> bool:
        return token in dead_tokens or (oauth_user is not None and token == "salli-oauth-token")

    return SimpleNamespace(
        profile=profile,
        mcp_oauth=SimpleNamespace(verify_access_token=verify, is_salli_token=is_salli_token),
    )


async def _caller(token: str, settings: Settings, services) -> str:
    """Authenticate the token, then check membership — as a request does."""
    principal = await get_principal(_creds(token), settings, services)
    return await get_current_user(principal, settings, services)


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


# ── No auth provider ────────────────────────────────────────────────────────


async def test_an_unconfigured_server_refuses_every_token():
    with pytest.raises(HTTPException) as caught:
        _decode_jwt("anyone", _settings())
    assert caught.value.status_code == 503


async def test_the_dev_fallback_needs_the_flag_and_a_development_environment():
    dev = _settings(salli_insecure_dev_auth=True, environment="development")
    assert _decode_jwt("dev-user", dev) == ("dev-user", None)

    for settings in (
        _settings(salli_insecure_dev_auth=True, environment="production"),
        _settings(salli_insecure_dev_auth=False, environment="development"),
    ):
        with pytest.raises(HTTPException) as caught:
            _decode_jwt("dev-user", settings)
        assert caught.value.status_code == 503


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


async def test_an_open_instance_creates_an_account_on_first_contact():
    profile, profiles = _profile_service()
    services = _services(profile)
    settings = _settings(**DEV, salli_registration="open")

    assert await _caller("newcomer", settings, services) == "newcomer"
    assert "newcomer" in profiles.rows


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
        ({}, True),  # no Supabase, no fallback: only real tokens get in
        ({**DEV, "supabase_jwt_secret": "s"}, True),
        ({"salli_insecure_dev_auth": True, "environment": "production"}, True),
    ],
)
async def test_secrets_are_kept_unless_the_dev_fallback_is_live(overrides, holds_secrets):
    from salli.config import auth_can_hold_secrets, dev_auth_fallback_live

    settings = _settings(**overrides)
    assert auth_can_hold_secrets(settings) is holds_secrets
    assert dev_auth_fallback_live(settings) is not holds_secrets


async def test_a_prefixed_salli_token_is_never_a_dev_user_id():
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    services = _services(profile)  # knows no tokens: no lookup is needed
    for token in ("salli_at_expired", "salli_rt_refresh"):
        with pytest.raises(HTTPException) as refused:
            await get_principal(_creds(token), _settings(**DEV), services)
        assert refused.value.status_code == 401
