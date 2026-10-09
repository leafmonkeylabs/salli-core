"""
Auth router — identity endpoints.

Supabase handles signup/login/sessions on the client side.
This router exposes server-side identity checks and profile info.
"""

from __future__ import annotations

from fastapi import APIRouter

from salli.interfaces.api.deps import CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user_id: CurrentUser):
    """
    Return the authenticated user's identity.
    The user_id comes from the verified JWT sub claim (or the raw token in dev mode).
    Clients use this to confirm their token is valid and get their canonical ID.
    """
    return {"user_id": user_id}
