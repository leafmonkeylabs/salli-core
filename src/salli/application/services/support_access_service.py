"""
Support access: the one way the instance's operator reads a person's books
(docs/security.md, "Support access").

The operator opens a session on one person's books, for a reason, from the
server (`salli-server support open`): a token (`salli_sp_…`, shown once)
good for `minutes` (60 unless said, at most 240) that only reads the books
(`deps.BOOKS_READS`, GET only). Opening it, every read made under it, and
its end (by the person, by the operator, or by its time) go in the audit
log's hash chain. The person sees every session, past and open, with its
reason and reads (`GET /v1/auth/support-access`), and may end an open one
(`DELETE`). Nothing else gives the operator a person's data.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from salli.application.acting import system_path
from salli.application.services.login_service import normalize_email

#: A support session's token starts with this.
SUPPORT_PREFIX = "salli_sp_"
DEFAULT_MINUTES = 60
MAX_MINUTES = 240
MAX_REASON = 500


class SupportRefused(ValueError):
    """No session: an unknown member, no reason, or a length out of range."""


@dataclass(frozen=True)
class SupportGrant:
    #: The session's id and the person whose books it reads.
    session_id: str
    user_id: str


def is_support_token(token: str) -> bool:
    return token.startswith(SUPPORT_PREFIX)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SupportAccessService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def _lapse(self, uow: Any, now: datetime, user_id: str | None = None) -> None:
        """Record, once, the end of every session whose time is up."""
        for row in await uow.support_sessions.lapsed(now):
            if user_id is not None and row["user_id"] != user_id:
                continue
            if await uow.support_sessions.end(row["id"], "expiry", now):
                await uow.audit_log.log(
                    row["user_id"], "support.end", {"session_id": row["id"], "by": "expiry"},
                    "succeeded",
                )  # fmt: skip

    # ── The operator's ───────────────────────────────────────────────────────

    @system_path("support")
    async def open(self, email: str, reason: str, minutes: int = DEFAULT_MINUTES) -> dict[str, Any]:
        """A session on the books of the member who signs in with `email`:
        the session, and its token (`token`), seen this once."""
        reason = reason.strip()
        if not reason:
            raise SupportRefused("Say why: a ticket or the reason (--reason).")
        if len(reason) > MAX_REASON:
            raise SupportRefused(f"A reason is at most {MAX_REASON} characters.")
        if not 1 <= minutes <= MAX_MINUTES:
            raise SupportRefused(f"A session lasts 1 to {MAX_MINUTES} minutes.")
        now = self._clock()
        token = SUPPORT_PREFIX + secrets.token_urlsafe(32)
        async with self._uow_factory() as uow:
            login = await uow.logins.get_by_email(normalize_email(email))
            if login is None:
                raise SupportRefused("No member of this server signs in with that email.")
            await self._lapse(uow, now)
            row = await uow.support_sessions.open(
                str(login["user_id"]), reason, _hash(token), now, now + timedelta(minutes=minutes)
            )
            await uow.audit_log.log(
                row["user_id"],
                "support.open",
                {"session_id": row["id"], "reason": reason, "minutes": minutes},
                "succeeded",
            )
        return {**row, "token": token}

    @system_path("support")
    async def list_all(self) -> list[dict[str, Any]]:
        """Every person's sessions, newest first."""
        async with self._uow_factory() as uow:
            await self._lapse(uow, self._clock())
            return await uow.support_sessions.list()

    @system_path("support")
    async def close(self, session_id: str) -> bool:
        """End an open session; False when there is no such open one."""
        return await self._end(session_id, "operator")

    # ── Signing in with one ─────────────────────────────────────────────────

    @system_path("sign-in")
    async def verify(self, token: str) -> SupportGrant | None:
        """The open session a token belongs to, or None (ended, its time up,
        or unknown)."""
        if not is_support_token(token):
            return None
        now = self._clock()
        async with self._uow_factory() as uow:
            await self._lapse(uow, now)
            row = await uow.support_sessions.by_token(_hash(token))
        if row is None or row["ended_at"] is not None:
            return None
        return SupportGrant(session_id=row["id"], user_id=row["user_id"])

    async def record_read(self, user_id: str, session_id: str, path: str) -> None:
        """A read made under a session, in the person's audit log, before it is answered."""
        async with self._uow_factory() as uow:
            await uow.audit_log.log(
                user_id, "support.read", {"session_id": session_id, "path": path}, "succeeded"
            )

    # ── The person's ────────────────────────────────────────────────────────

    async def list(self, user_id: str) -> list[dict[str, Any]]:
        """The person's sessions, past and open, newest first, with the reads
        made under each."""
        async with self._uow_factory() as uow:
            await self._lapse(uow, self._clock(), user_id)
            return await uow.support_sessions.list(user_id)

    async def end(self, user_id: str, session_id: str) -> bool:
        """End one of the person's open sessions; False when there is no such open one."""
        return await self._end(session_id, "person", user_id)

    async def _end(self, session_id: str, by: str, user_id: str | None = None) -> bool:
        now = self._clock()
        async with self._uow_factory() as uow:
            await self._lapse(uow, now, user_id)
            row = await uow.support_sessions.end(session_id, by, now, user_id)
            if row is None:
                return False
            await uow.audit_log.log(
                row["user_id"], "support.end", {"session_id": session_id, "by": by}, "succeeded"
            )
        return True
