"""Personal access tokens: shown once, stored hashed, and dead once revoked or expired."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from salli.application.services.personal_access_token_service import (
    PREFIX,
    PersonalAccessTokenService,
    VerifiedToken,
    is_personal_access_token,
)
from salli.config import Settings
from salli.interfaces.api.deps import get_principal


class Store:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.touches = 0

    async def create(self, user_id, name, token_hash, prefix, expires_at, permissions):
        row = {
            "id": f"p{len(self.rows) + 1}",
            "user_id": user_id,
            "name": name,
            "token_hash": token_hash,
            "prefix": prefix,
            "permissions": permissions,
            "expires_at": expires_at,
            "last_used_at": None,
            "created_at": datetime.now(UTC),
            "revoked": False,
        }
        self.rows[row["id"]] = row
        return {k: v for k, v in row.items() if k not in ("token_hash", "revoked")}

    async def list(self, user_id):
        return [r for r in self.rows.values() if r["user_id"] == user_id and not r["revoked"]]

    async def get_active(self, token_hash):
        for row in self.rows.values():
            if row["token_hash"] == token_hash and not row["revoked"]:
                expired = row["expires_at"] and row["expires_at"] < datetime.now(UTC)
                return None if expired else row
        return None

    async def revoke(self, user_id, token_id):
        row = self.rows.get(token_id)
        if not row or row["user_id"] != user_id or row["revoked"]:
            return False
        row["revoked"] = True
        return True

    async def touch(self, token_id, at):
        self.touches += 1
        self.rows[token_id]["last_used_at"] = at


@pytest.fixture
def tokens():
    store = Store()

    @asynccontextmanager
    async def uow_factory():
        yield SimpleNamespace(personal_access_tokens=store)

    return PersonalAccessTokenService(uow_factory), store


async def test_a_token_is_shown_once_and_only_its_hash_is_kept(tokens):
    service, store = tokens
    created = await service.create("u1", " laptop CLI ", expires_in_days=30)
    token = created["token"]
    assert token.startswith(PREFIX) and is_personal_access_token(token)
    assert created["name"] == "laptop CLI"
    assert created["prefix"] == token[: len(PREFIX) + 4]
    [row] = store.rows.values()
    assert token not in str(row) and row["token_hash"] != token
    assert "token" not in (await service.list("u1"))[0]


async def test_a_token_verifies_until_revoked(tokens):
    service, _ = tokens
    created = await service.create("u1", "ci")
    assert (await service.verify(created["token"])).user_id == "u1"
    assert await service.revoke("u1", created["id"])
    assert await service.verify(created["token"]) is None
    assert not await service.revoke("u1", created["id"])


async def test_someone_elses_token_cannot_be_revoked(tokens):
    service, _ = tokens
    created = await service.create("u1", "ci")
    assert not await service.revoke("u2", created["id"])
    assert (await service.verify(created["token"])).user_id == "u1"


async def test_an_expired_token_is_refused(tokens):
    service, store = tokens
    created = await service.create("u1", "ci", expires_in_days=1)
    store.rows[created["id"]]["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert await service.verify(created["token"]) is None


async def test_use_is_recorded_at_most_once_a_minute(tokens):
    service, store = tokens
    created = await service.create("u1", "ci")
    for _ in range(5):
        await service.verify(created["token"])
    assert store.touches == 1


async def test_a_token_holds_only_what_it_was_made_with(tokens):
    service, _ = tokens
    plain = await service.create("u1", "backup job")
    trusted = await service.create("u1", "laptop", permissions=["tax:activate", "tax:activate"])
    assert plain["permissions"] == [] and trusted["permissions"] == ["tax:activate"]
    assert await service.verify(plain["token"]) == VerifiedToken("u1", "backup job", frozenset())
    assert await service.verify(trusted["token"]) == VerifiedToken(
        "u1", "laptop", frozenset({"tax:activate"})
    )
    with pytest.raises(ValueError, match="Unknown permission: admin"):
        await service.create("u1", "x", permissions=["admin"])


async def test_a_token_needs_a_name_and_a_sane_lifetime(tokens):
    service, _ = tokens
    with pytest.raises(ValueError, match="name"):
        await service.create("u1", "   ")
    with pytest.raises(ValueError, match="positive"):
        await service.create("u1", "x", expires_in_days=0)


# ── how a request is authenticated ────────────────────────────────────────────


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, supabase_jwt_secret="secret", **overrides)


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class _OAuth:
    def __init__(self, record: dict[str, Any] | None) -> None:
        self.record = record
        self.asked: list[str] = []

    async def verify_access_token(self, token: str, audience: str = "mcp"):
        self.asked.append(audience)
        return self.record


async def test_a_personal_access_token_authenticates_as_its_owner(tokens):
    service, _ = tokens
    created = await service.create("u1", "ci")
    services = SimpleNamespace(tokens=service, mcp_oauth=_OAuth(None))
    principal = await get_principal(_creds(created["token"]), _settings(), services)
    assert (principal.user_id, principal.method) == ("u1", "pat")
    assert (principal.client_name, principal.permissions) == ("ci", frozenset())

    trusted = await service.create("u1", "laptop", permissions=["tax:activate"])
    principal = await get_principal(_creds(trusted["token"]), _settings(), services)
    assert principal.permissions == frozenset({"tax:activate"})

    await service.revoke("u1", created["id"])
    with pytest.raises(HTTPException) as refused:
        await get_principal(_creds(created["token"]), _settings(), services)
    assert refused.value.status_code == 401


async def test_an_oauth_token_must_be_one_issued_for_the_api(tokens):
    service, _ = tokens
    oauth = _OAuth({"user_id": "u1"})
    principal = await get_principal(
        _creds("opaque-token"), _settings(), SimpleNamespace(tokens=service, mcp_oauth=oauth)
    )
    assert (principal.user_id, principal.method) == ("u1", "oauth")
    assert oauth.asked == ["api"]

    with pytest.raises(HTTPException) as refused:
        await get_principal(
            _creds("an-mcp-token"),
            _settings(),
            SimpleNamespace(tokens=service, mcp_oauth=_OAuth(None)),
        )
    assert refused.value.status_code == 401
