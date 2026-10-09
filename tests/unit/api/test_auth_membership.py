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
    services = SimpleNamespace(profile=profile)

    with pytest.raises(HTTPException) as caught:
        await _caller("stranger", _settings(**DEV), services)

    assert caught.value.status_code == 403
    assert "stranger" not in profiles.rows


async def test_a_closed_instance_answers_its_members():
    profile, _ = _profile_service({"owner": {"id": "owner"}})
    services = SimpleNamespace(profile=profile)
    assert await _caller("owner", _settings(**DEV), services) == "owner"


async def test_an_open_instance_creates_an_account_on_first_contact():
    profile, profiles = _profile_service()
    services = SimpleNamespace(profile=profile)
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
