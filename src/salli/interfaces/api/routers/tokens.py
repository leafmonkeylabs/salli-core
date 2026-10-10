"""
Personal access tokens — `/v1/tokens`.

For scripts, CI, and the `salli` CLI where a browser sign-in is not possible.
A token is shown once, when it is created; after that only its name and first
characters are. Creating one needs a real sign-in: a personal access token
cannot mint another, so a leaked token cannot be used to make more.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.interfaces.api.deps import AppServices, CurrentPrincipal, CurrentUser

router = APIRouter(prefix="/tokens", tags=["tokens"])


class PersonalAccessToken(BaseModel):
    id: str
    name: str
    #: The token's first characters, to tell it apart — not enough to use it.
    prefix: str
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
    created = await svc.tokens.create(user_id, body.name, body.expires_in_days)
    return NewPersonalAccessToken.model_validate(created)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    if not await svc.tokens.revoke(user_id, token_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such token")
