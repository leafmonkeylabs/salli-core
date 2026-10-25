"""
Auth router — who you are, signing in with a password, every way you are
signed in, and changing your password (application/services/login_service.py).

Signing in (`POST /v1/auth/sessions`) returns a session token to send as a
bearer token, like any other. Nothing here sets a cookie, so there is nothing
for another site's page to ride on. The salli CLI and the console sign in
through Salli's own sign-in page instead (OAuth), which takes the same
password. `GET /v1/auth/sign-ins` lists all of these, sessions and OAuth
sign-ins alike, and `DELETE /v1/auth/sign-ins/{id}` ends one; AI connections
are listed with the MCP routes. `/v1/auth/totp` turns two-step sign-in (a code
from an authenticator app after the password) on and off.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from salli.application.permissions import Permission, is_first_party, is_recent
from salli.application.services.login_service import (
    MAX_PASSWORD_LENGTH,
    CodeNeeded,
    CodeRefused,
    LoginNotFound,
    PasswordRejected,
    SignInRefused,
    SignInThrottled,
    TwoStepState,
    TwoStepUnavailable,
)
from salli.application.services.mcp_oauth_service import (
    CLI_CLIENT_ID,
    CONSOLE_CLIENT_ID,
    MOBILE_CLIENT_ID,
)
from salli.interfaces.api.deps import (
    AppServices,
    CurrentEmail,
    CurrentPrincipal,
    CurrentUser,
    Principal,
    StepUpRequired,
)

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
    #: Whether signing in with your password also needs a code from an
    #: authenticator app (two-step sign-in, `/v1/auth/totp`).
    totp_enabled: bool = False


@router.get("/me")
async def me(
    user_id: CurrentUser, principal: CurrentPrincipal, email: CurrentEmail, svc: AppServices
) -> AuthIdentity:
    """Return the authenticated user's identity. Clients use this to confirm
    their token is valid and get their canonical id."""
    login = await svc.logins.get_login(user_id)
    return AuthIdentity(
        user_id=user_id,
        email=email,
        method=principal.method,
        permissions=cast("list[Permission]", sorted(principal.permissions)),
        totp_enabled=bool(login and login.get("totp_enabled_at")),
    )


# ── Sessions ──────────────────────────────────────────────────────────────────


#: An authenticator app's six digits, or a recovery code.
_CODE = Field(default=None, max_length=64)


class SignInRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: With two-step sign-in on: the authenticator app's code, or a recovery code.
    code: str | None = _CODE


class NewSession(BaseModel):
    """A session just started. Send `token` as a bearer token."""

    id: str
    user_id: str
    email: str
    #: The session token (`salli_st_…`). This is the only time it is returned.
    token: str
    #: When it stops working, however much it is used.
    expires_at: datetime


class SignIn(BaseModel):
    """One way you are signed in: a session, or an OAuth sign-in to the API."""

    #: What ending it takes (`DELETE /v1/auth/sign-ins/{id}`).
    id: str
    #: `session`: signed in with your password (`POST /v1/auth/sessions`);
    #: `cli`: the salli CLI, on one machine; `console`: the console, in one
    #: browser tab; `mobile`: the Salli app, on one phone; `app`: another
    #: application signed in to the API as you.
    kind: Literal["session", "cli", "console", "mobile", "app"]
    #: The OAuth client's name ("Salli CLI", "Salli console", or as another
    #: application named itself). None for a session.
    client_name: str | None
    #: What started a session, as its User-Agent said. None for OAuth.
    user_agent: str | None
    started_at: datetime
    #: When it was last used, to the minute; None if never since it started.
    last_used_at: datetime | None
    #: When it ends unless ended first; None for an OAuth sign-in with no
    #: fixed end that is between tokens.
    expires_at: datetime | None
    #: Whether this is the sign-in making the request.
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
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post(
    "/sessions",
    status_code=201,
    responses={
        401: {
            "description": "The email and password didn't match (which, is not said), or "
            "two-step sign-in is on and the code is missing or wrong"
        },
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
            body.email,
            body.password,
            address=_address(request),
            user_agent=user_agent,
            code=body.code,
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


@router.delete("/sessions/current", status_code=204)
async def sign_out(user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices) -> None:
    """Sign out: end the session making the request."""
    if principal.session_id is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This request is not signed in with a session. End an OAuth sign-in with "
            "`salli logout`, or a personal access token with `salli tokens revoke`.",
        )
    await svc.logins.revoke_session(user_id, principal.session_id)


# ── Every way in ──────────────────────────────────────────────────────────────


def _oauth_kind(client_id: str) -> Literal["cli", "console", "mobile", "app"]:
    if client_id == CLI_CLIENT_ID:
        return "cli"
    if client_id == CONSOLE_CLIENT_ID:
        return "console"
    if client_id == MOBILE_CLIENT_ID:
        return "mobile"
    return "app"


@router.get("/sign-ins")
async def list_sign_ins(
    user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> list[SignIn]:
    """Every way you are signed in, newest first: your sessions, the salli
    CLI on each machine, the console in each browser tab, and any other
    application signed in to the API as you. AI connections over MCP are
    listed at `GET /v1/mcp/connections`, personal access tokens at
    `GET /v1/tokens`."""
    sign_ins = [
        SignIn(
            id=str(s["id"]),
            kind="session",
            client_name=None,
            user_agent=s["user_agent"],
            started_at=s["created_at"],
            last_used_at=s["last_used_at"],
            expires_at=s["expires_at"],
            current=s["id"] == principal.session_id,
        )
        for s in await svc.logins.list_sessions(user_id)
    ]
    sign_ins += [
        SignIn(
            id=g["grant_id"],
            kind=_oauth_kind(g["client_id"]),
            client_name=g["client_name"],
            user_agent=None,
            started_at=g["created_at"],
            last_used_at=g["last_used_at"],
            expires_at=g["expires_at"],
            current=g["grant_id"] == principal.grant_id,
        )
        for g in await svc.mcp_oauth.list_sign_ins(user_id)
    ]
    return sorted(sign_ins, key=lambda s: s.started_at, reverse=True)


@router.delete("/sign-ins/{sign_in_id}", status_code=204)
async def revoke_sign_in(sign_in_id: str, user_id: CurrentUser, svc: AppServices) -> None:
    """End one of your sign-ins, this one included: a session, or an OAuth
    sign-in with every token it holds."""
    if await svc.logins.revoke_session(user_id, sign_in_id):
        return
    if await svc.mcp_oauth.revoke_sign_in(user_id, sign_in_id):
        return
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="sign-in not found")


# ── Password ──────────────────────────────────────────────────────────────────


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: At least 12 characters, and not your email.
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: With two-step sign-in on: the authenticator app's code, or a recovery code.
    code: str | None = _CODE


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
    _own(principal, "change your password")
    try:
        ended = await svc.logins.change_password(
            user_id,
            body.current_password,
            body.new_password,
            address=_address(request),
            keep_session=principal.session_id,
            code=body.code,
        )
    except SignInRefused as exc:
        # 403, not 401: the request is signed in; it is the password that's wrong.
        raise _wrong(exc) from None
    except SignInThrottled as exc:
        raise _refused_sign_in(exc) from None
    except LoginNotFound as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except PasswordRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    return PasswordChanged(sessions_ended=ended)


def _own(principal: Principal, what: str) -> None:
    if not is_first_party(principal.method, first_party_client=principal.first_party_client):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"Only your own sign-in to Salli can {what}; other applications never can.",
        )


def _wrong(exc: SignInRefused) -> HTTPException:
    detail = (
        str(exc) if isinstance(exc, CodeNeeded | CodeRefused) else "The current password is wrong."
    )
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


# ── Two-step sign-in ──────────────────────────────────────────────────────────


def _two_step_allowed(principal: Principal) -> None:
    """Your own sign-in, with a recent password where its client asks for
    one (the console's and the app's step-up)."""
    _own(principal, "change two-step sign-in")
    if principal.fresh_within and not is_recent(principal.sign_in_age, principal.fresh_within):
        raise StepUpRequired(
            "Changing two-step sign-in", int(principal.fresh_within.total_seconds())
        )


class TotpEnrolment(BaseModel):
    """A new authenticator secret, returned this once. Add it to the app
    (`uri`, or `secret` typed in), then confirm a code from it."""

    #: The secret, base32, to type into an authenticator app.
    secret: str
    #: The same as an `otpauth://` URI, which an app reads from a QR code.
    uri: str


class TotpConfirmRequest(BaseModel):
    #: The six digits the authenticator app shows now.
    code: str = Field(min_length=1, max_length=64)


class TotpEnabled(BaseModel):
    #: Ten recovery codes, each good once in place of the app's code. This
    #: is the only time they are returned.
    recovery_codes: list[str]


class TotpDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: The authenticator app's code, or a recovery code. Not needed to drop
    #: a setup that was never confirmed.
    code: str | None = _CODE


_TWO_STEP_REFUSALS: dict[int | str, dict[str, object]] = {
    403: {
        "description": "This sign-in may not; `/problems/step-up-required` when signing in "
        "again on Salli's page first would let it"
    },
    409: {"description": "Two-step sign-in is not in the state this needs"},
}


@router.post(
    "/totp",
    status_code=201,
    responses={
        **_TWO_STEP_REFUSALS,
        503: {"description": "This server has no encryption key to keep the secret with"},
    },
)
async def begin_totp(
    user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> TotpEnrolment:
    """Start turning on two-step sign-in: a new secret for an authenticator
    app. Nothing changes until a code from it is confirmed
    (`POST /v1/auth/totp/confirm`); starting again replaces the secret."""
    _two_step_allowed(principal)
    try:
        enrolment = await svc.logins.begin_totp(user_id)
    except TwoStepUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from None
    except (TwoStepState, LoginNotFound) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return TotpEnrolment(secret=enrolment.secret, uri=enrolment.uri)


@router.post("/totp/confirm", responses={**_TWO_STEP_REFUSALS, 422: {"description": "Wrong code"}})
async def confirm_totp(
    body: TotpConfirmRequest, user_id: CurrentUser, principal: CurrentPrincipal, svc: AppServices
) -> TotpEnabled:
    """Turn two-step sign-in on with a code from the new secret. From now on
    every password check also asks for a code."""
    _two_step_allowed(principal)
    try:
        codes = await svc.logins.confirm_totp(user_id, body.code)
    except TwoStepState as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except CodeRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    return TotpEnabled(recovery_codes=codes)


@router.delete(
    "/totp",
    status_code=204,
    responses={
        **_TWO_STEP_REFUSALS,
        429: {"description": "Too many failed attempts; `Retry-After` says when to try again"},
    },
)
async def disable_totp(
    body: TotpDisableRequest,
    request: Request,
    user_id: CurrentUser,
    principal: CurrentPrincipal,
    svc: AppServices,
) -> None:
    """Turn two-step sign-in off: your password and a code, checked like a
    sign-in. The recovery codes stop working."""
    _two_step_allowed(principal)
    try:
        await svc.logins.disable_totp(user_id, body.password, body.code, address=_address(request))
    except SignInRefused as exc:
        raise _wrong(exc) from None
    except SignInThrottled as exc:
        raise _refused_sign_in(exc) from None
    except (TwoStepState, LoginNotFound) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
