"""
Personal access tokens: long-lived credentials a person creates for scripts,
CI, and the `salli` CLI on a machine where signing in through a browser is not
an option.

A token is `salli_pat_` followed by 43 random characters. Only its SHA-256 is
stored; the token itself is shown once, when it is created. The prefix makes a
leaked token recognisable to secret scanners and lets the API tell one apart
from a session token without a database lookup.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

PREFIX = "salli_pat_"
# Enough of the token to tell two apart in a list, nowhere near enough to use.
_SHOWN = len(PREFIX) + 4
# Recording "last used" on every request would be a write per request; once a
# minute is plenty for a list that says when a token was last used.
_TOUCH_EVERY = timedelta(minutes=1)


def is_personal_access_token(token: str) -> bool:
    return token.startswith(PREFIX)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PersonalAccessTokenService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def create(
        self, user_id: str, name: str, expires_in_days: int | None = None
    ) -> dict[str, Any]:
        """A new token. The returned `token` is the only time it is ever seen."""
        name = name.strip()
        if not name:
            raise ValueError("A token needs a name, so you can tell it apart later")
        if expires_in_days is not None and expires_in_days <= 0:
            raise ValueError("expires_in_days must be positive")
        token = PREFIX + secrets.token_urlsafe(32)
        expires_at = (
            datetime.now(UTC) + timedelta(days=expires_in_days) if expires_in_days else None
        )
        async with self._uow_factory() as uow:
            row = await uow.personal_access_tokens.create(
                user_id, name[:100], _hash(token), token[:_SHOWN], expires_at
            )
        return {**row, "token": token}

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.personal_access_tokens.list(user_id)

    async def revoke(self, user_id: str, token_id: str) -> bool:
        async with self._uow_factory() as uow:
            return await uow.personal_access_tokens.revoke(user_id, token_id)

    async def verify(self, token: str) -> str | None:
        """The user a token belongs to, or None if it is unknown, revoked or expired."""
        async with self._uow_factory() as uow:
            row = await uow.personal_access_tokens.get_active(_hash(token))
            if row is None:
                return None
            now = datetime.now(UTC)
            if row["last_used_at"] is None or now - row["last_used_at"] > _TOUCH_EVERY:
                await uow.personal_access_tokens.touch(row["id"], now)
        return str(row["user_id"])
