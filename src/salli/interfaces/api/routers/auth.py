"""
Auth router — identity endpoints.

Supabase handles signup/login/sessions on the client side.
This router exposes server-side identity checks and profile info.
"""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter
from pydantic import BaseModel

from salli.application.permissions import Permission
from salli.interfaces.api.deps import CurrentEmail, CurrentPrincipal, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthIdentity(BaseModel):
    #: The caller's canonical id: the verified token's `sub` claim.
    user_id: str
    #: The address they signed up with, when Salli knows it.
    email: str | None = None
    #: How this request signed in: a web or mobile session, a Salli OAuth
    #: token (the CLI), a personal access token, or local development.
    method: Literal["session", "oauth", "pat", "dev"]
    #: What this sign-in may do beyond reading and writing your data
    #: (`tax:activate`: activate a tax rule set). Follows from how it signed
    #: in; a personal access token holds what it was made with.
    permissions: list[Permission]


@router.get("/me")
async def me(
    user_id: CurrentUser, principal: CurrentPrincipal, email: CurrentEmail
) -> AuthIdentity:
    """
    Return the authenticated user's identity.
    The user_id comes from the verified JWT sub claim (or the raw token in dev mode).
    Clients use this to confirm their token is valid and get their canonical ID.
    """
    return AuthIdentity(
        user_id=user_id,
        email=email,
        method=principal.method,
        permissions=cast("list[Permission]", sorted(principal.permissions)),
    )
