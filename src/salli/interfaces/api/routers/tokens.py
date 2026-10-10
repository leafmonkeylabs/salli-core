"""
Personal access tokens — `/v1/tokens`.

For scripts, CI, and the `salli` CLI where a browser sign-in is not possible.
A token is shown once, when it is created; after that only its name and first
characters are.

A token holds the permissions it was made with (application/permissions.py):
none unless asked for. Making one needs the user's own sign-in (the app, the
salli CLI), never a token (so a leaked token cannot be used to make more) and
never another application, and that sign-in may give the token only
permissions it holds itself.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.application.permissions import Permission, may_grant
from salli.interfaces.api.deps import AppServices, CurrentPrincipal, CurrentUser

router = APIRouter(prefix="/tokens", tags=["tokens"])


class PersonalAccessToken(BaseModel):
    id: str
    name: str
    #: The token's first characters, to tell it apart — not enough to use it.
    prefix: str
    #: What it may do beyond reading and writing your data: `tax:activate`
    #: lets it activate a tax rule set. Empty unless asked for when it was made.
    permissions: list[Permission]
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class NewPersonalAccessToken(PersonalAccessToken):
    #: The token itself. This is the only time it is ever returned.
    token: str


class CreateTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    #: Omitted: the token does not expire.
    expires_in_days: int | None = Field(default=None, gt=0, le=3650)
    #: Permissions to give it, each one your own sign-in holds. Omitted: none,
    #: so it can do everything but what needs a permission (activating a tax
    #: rule set). Tokens are what scripts and agents are given: add one only
    #: for a token that needs it.
    permissions: list[Permission] = Field(default_factory=list[Permission], max_length=16)


@router.get("")
async def list_tokens(user_id: CurrentUser, svc: AppServices) -> list[PersonalAccessToken]:
    return [PersonalAccessToken.model_validate(t) for t in await svc.tokens.list(user_id)]


@router.post("", status_code=201)
async def create_token(
    body: CreateTokenRequest,
    user_id: CurrentUser,
    principal: CurrentPrincipal,
    svc: AppServices,
) -> NewPersonalAccessToken:
    if principal.method == "pat":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="A personal access token cannot create another; sign in to make one.",
        )
    allowed, missing = may_grant(
        principal.method,
        first_party_client=principal.first_party_client,
        held=principal.permissions,
        requested=body.permissions,
    )
    if not allowed:
        if principal.method == "oauth" and not principal.first_party_client:
            detail = (
                "Only your own sign-in to Salli (the app, or the salli CLI) can make a "
                "personal access token; other applications cannot."
            )
        else:
            detail = (
                f"This sign-in doesn't hold {', '.join(missing)}, so it can't give it to a "
                "token. Sign in to the app, or with `salli login`, to make one that does."
            )
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)
    created = await svc.tokens.create(
        user_id, body.name, body.expires_in_days, permissions=body.permissions
    )
    return NewPersonalAccessToken.model_validate(created)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    if not await svc.tokens.revoke(user_id, token_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such token")
