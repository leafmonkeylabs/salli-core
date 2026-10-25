"""
Read-only access grants: a member lets another member of the same server
read their books (a partner, someone helping them), until either of them
revokes it.

The grantee reads the grantor's books through the API's read routes by
naming them (`Salli-Books`, deps.get_current_user): only reads, only books,
and each such read is in the grantor's audit log. Making, receiving and
ending a grant are in both members' audit logs. Making one needs a recent
password where the sign-in asks for one (the route's step-up).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from salli.application.services.login_service import normalize_email


class AccessGrantService:
    def __init__(self, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = uow_factory

    async def grant(self, grantor_id: str, email: str) -> dict[str, Any]:
        """Let the member who signs in with `email` read the grantor's books."""
        async with self._uow_factory() as uow:
            login = await uow.logins.get_by_email(normalize_email(email))
            if login is None:
                raise LookupError("No member of this server signs in with that email.")
            grantee_id = str(login["user_id"])
            if grantee_id == grantor_id:
                raise ValueError("Your own books are yours already.")
            row = await uow.access_grants.create(grantor_id, grantee_id)
            params = {"grant_id": row["id"], "grantor_id": grantor_id, "grantee_id": grantee_id}
            await uow.audit_log.log(grantor_id, "access_grant.give", params, "succeeded")
            await uow.audit_log.log(grantee_id, "access_grant.receive", params, "succeeded")
            return await self._view(uow, grantor_id, row)

    async def list(self, user_id: str) -> dict[str, list[dict[str, Any]]]:
        """The live grants the user gave (`given`) and holds (`received`)."""
        async with self._uow_factory() as uow:
            rows = await uow.access_grants.list_for(user_id)
            views = [await self._view(uow, user_id, r) for r in rows]
        return {
            "given": [v for v, r in zip(views, rows, strict=True) if r["grantor_id"] == user_id],
            "received": [v for v, r in zip(views, rows, strict=True) if r["grantee_id"] == user_id],
        }

    async def revoke(self, user_id: str, grant_id: str) -> bool:
        """End a grant the user gave or holds; False when there is no such
        live one."""
        async with self._uow_factory() as uow:
            row = await uow.access_grants.revoke(user_id, grant_id)
            if row is None:
                return False
            params = {"grant_id": grant_id, "revoked_by": user_id}
            for member in (row["grantor_id"], row["grantee_id"]):
                await uow.audit_log.log(member, "access_grant.revoke", params, "succeeded")
        return True

    async def may_read(self, grantee_id: str, grantor_id: str, path: str) -> bool:
        """Whether the grantee holds a live grant to the grantor's books; a
        read under it goes in the grantor's audit log."""
        async with self._uow_factory() as uow:
            if not await uow.access_grants.is_live(grantor_id, grantee_id):
                return False
            await uow.audit_log.log(
                grantor_id,
                "access_grant.read",
                {"grantee_id": grantee_id, "path": path},
                "succeeded",
            )
        return True

    @staticmethod
    async def _view(uow: Any, user_id: str, row: dict[str, Any]) -> dict[str, Any]:
        """A grant as one side sees it: the other member's id and email."""
        other = row["grantee_id"] if row["grantor_id"] == user_id else row["grantor_id"]
        login = await uow.logins.get(other)
        return {
            "id": row["id"],
            "member_id": other,
            "member_email": (login or {}).get("email"),
            "created_at": row["created_at"],
        }
