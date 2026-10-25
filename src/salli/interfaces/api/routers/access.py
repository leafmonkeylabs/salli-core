"""
Read-only access to your books — `/v1/access-grants`.

You may let another member of this server read your books (a partner,
someone helping you), and end it whenever you like; so may they. Listed on
both sides, in both audit logs, and every read they make of your books is in
yours. They read by naming your books (the `Salli-Books` header, your user
id; `salli --books <id>`): only reads, only the books (deps.BOOKS_READS).

Giving access needs your own sign-in (not a personal access token, not
another application), with a recent password where the sign-in asks for one.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.interfaces.api.deps import (
    AppServices,
    CurrentPrincipal,
    CurrentUser,
    require_recent_password,
)

router = APIRouter(prefix="/access-grants", tags=["access"])


class AccessGrant(BaseModel):
    id: str
    #: The other member: whom you gave access, or who gave it to you.
    member_id: str
    member_email: str | None
    created_at: datetime


class AccessGrants(BaseModel):
    #: Members who may read your books.
    given: list[AccessGrant]
    #: Members whose books you may read (`Salli-Books: <member_id>`).
    received: list[AccessGrant]


class GrantAccessRequest(BaseModel):
    #: The email the other member signs in with.
    email: str = Field(min_length=3, max_length=320)


@router.get("")
async def list_access_grants(user_id: CurrentUser, svc: AppServices) -> AccessGrants:
    return AccessGrants.model_validate(await svc.access.list(user_id))


@router.post(
    "",
    status_code=201,
    dependencies=[require_recent_password("Giving another member access to your books")],
    responses={
        403: {"description": "Not your own sign-in, or `/problems/step-up-required`"},
        404: {"description": "No member of this server signs in with that email"},
    },
)
async def grant_access(
    body: GrantAccessRequest, user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> AccessGrant:
    """Let another member read your books, until either of you ends it."""
    if principal.method == "pat" or (
        principal.method == "oauth" and not principal.first_party_client
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only your own sign-in to Salli (the app, the console or the salli CLI) "
            "can give access to your books.",
        )
    try:
        granted = await svc.access.grant(user_id, body.email)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return AccessGrant.model_validate(granted)


@router.delete("/{grant_id}", status_code=204)
async def revoke_access_grant(grant_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    """End access you gave, or access you were given."""
    if not await svc.access.revoke(user_id, grant_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such access")
