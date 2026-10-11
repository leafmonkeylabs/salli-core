"""
Auth router — who you are, signing in with a password, your sessions, and
changing your password (application/services/login_service.py).

Signing in (`POST /v1/auth/sessions`) returns a session token to send as a
bearer token, like any other. Nothing here sets a cookie, so there is nothing
for another site's page to ride on. The salli CLI signs in through the
browser or device pages instead (OAuth), which take the same password.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from salli.application.permissions import Permission, is_first_party
from salli.application.services.login_service import (
    MAX_PASSWORD_LENGTH,
    REFUSED,
    LoginNotFound,
    PasswordRejected,
    SignInRefused,
    SignInThrottled,
)
from salli.interfaces.api.deps import AppServices, CurrentEmail, CurrentPrincipal, CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthIdentity(BaseModel):
    #: The caller's canonical id.
    user_id: str
    #: The address they sign in with, when Salli knows it.
    email: str | None = None
    #: How this request signed in: a session (signing in with a password),
    #: a Salli OAuth token (the CLI), a personal access token, or local
    #: development.
    method: Literal["session", "oauth", "pat", "dev"]
    #: What this sign-in may do beyond reading and writing your data
    #: (`tax:activate`: activate a tax rule set). Follows from how it signed
    #: in; a personal access token holds what it was made with.
    permissions: list[Permission]


@router.get("/me")
async def me(
    user_id: CurrentUser, principal: CurrentPrincipal, email: CurrentEmail
) -> AuthIdentity:
    """Return the authenticated user's identity. Clients use this to confirm
    their token is valid and get their canonical id."""
    return AuthIdentity(
        user_id=user_id,
        email=email,
        method=principal.method,
        permissions=cast("list[Permission]", sorted(principal.permissions)),
    )


# ── Sessions ──────────────────────────────────────────────────────────────────


class SignInRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class NewSession(BaseModel):
    """A session just started. Send `token` as a bearer token."""

    id: str
    user_id: str
    email: str
    #: The session token (`salli_st_…`). This is the only time it is returned.
    token: str
    #: When it stops working, however much it is used.
    expires_at: datetime


class Session(BaseModel):
    id: str
    #: What signed in, as its User-Agent said.
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    #: Whether this is the session making the request.
    current: bool


def _address(request: Request) -> str | None:
    return request.client.host if request.client else None


def _refused_sign_in(exc: SignInRefused | SignInThrottled) -> HTTPException:
    if isinstance(exc, SignInThrottled):
        return HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        )
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=REFUSED)


@router.post(
    "/sessions",
    status_code=201,
    responses={
        401: {"description": "The email and password didn't match (which, is not said)"},
        429: {"description": "Too many failed sign-ins; `Retry-After` says when to try again"},
    },
)
async def sign_in(
    body: SignInRequest,
    request: Request,
    svc: AppServices,
    user_agent: Annotated[str | None, Header()] = None,
) -> NewSession:
    """Sign in with an email and password, and start a session."""
    try:
        started = await svc.logins.sign_in(
            body.email, body.password, address=_address(request), user_agent=user_agent
        )
    except (SignInRefused, SignInThrottled) as exc:
        raise _refused_sign_in(exc) from None
    return NewSession(
        id=started.id,
        user_id=started.user_id,
        email=started.email,
        token=started.token,
        expires_at=started.expires_at,
    )


@router.get("/sessions")
async def list_sessions(
    user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> list[Session]:
    """Your live sessions, newest first."""
    return [
        Session.model_validate({**s, "current": s["id"] == principal.session_id})
        for s in await svc.logins.list_sessions(user_id)
    ]


@router.delete("/sessions/current", status_code=204)
async def sign_out(user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices) -> None:
    """Sign out: end the session making the request."""
    if principal.session_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This request is not signed in with a session. Revoke an OAuth token "
            "with `salli logout`, or a personal access token with `salli tokens revoke`.",
        )
    await svc.logins.revoke_session(user_id, principal.session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(session_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    """End one of your sessions."""
    if not await svc.logins.revoke_session(user_id, session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")


# ── Password ──────────────────────────────────────────────────────────────────


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: At least 12 characters, and not your email.
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class PasswordChanged(BaseModel):
    #: How many of your other sessions it ended. The one making the request,
    #: OAuth sign-ins (the CLI's) and personal access tokens keep working.
    sessions_ended: int


@router.post(
    "/password",
    responses={
        403: {"description": "The current password is wrong, or this sign-in may not change it"},
        429: {"description": "Too many failed attempts; `Retry-After` says when to try again"},
    },
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user_id: CurrentUser,
    principal: CurrentPrincipal,
    svc: AppServices,
) -> PasswordChanged:
    """Change your password. Ends your other sessions."""
    if not is_first_party(principal.method, first_party_client=principal.first_party_client):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only your own sign-in to Salli can change your password; "
            "other applications never can.",
        )
    try:
        ended = await svc.logins.change_password(
            user_id,
            body.current_password,
            body.new_password,
            address=_address(request),
            keep_session=principal.session_id,
        )
    except SignInRefused:
        # 403, not 401: the request is signed in; it is the password that's wrong.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="The current password is wrong."
        ) from None
    except SignInThrottled as exc:
        raise _refused_sign_in(exc) from None
    except LoginNotFound as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except PasswordRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    return PasswordChanged(sessions_ended=ended)
