"""
The page an invitation link opens (`salli-server members invite`): the person
the owner invited chooses their password, and may turn on two-step sign-in,
here. There is no sign-up: without a good invitation the page does nothing.

Like the consent page, plain server-rendered HTML with no script, under the
same headers (its stylesheet allowed by hash). The token is in the link and
in a hidden field, never stored but as a hash, and good once. The
authenticator secret is made when the page is shown and only kept if the
person proves their app has it with a code.
"""

from __future__ import annotations

import html
from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import HTMLResponse

from salli.application import totp
from salli.application.services.login_service import (
    CodeRefused,
    LoginExists,
    LoginNotFound,
    PasswordRejected,
    TwoStepUnavailable,
)
from salli.interfaces.api.deps import AppServices
from salli.interfaces.api.routers.mcp_consent_page import (
    _page,  # pyright: ignore[reportPrivateUsage]
)

router = APIRouter(tags=["mcp-oauth"])

_TITLE = "Join Salli"
_GONE = (
    "<h1>This link doesn't work</h1><p>The invitation has been used or has expired. "
    "Ask the person who runs this Salli server for a new one.</p>"
)


def _form(token: str, email: str, secret: str, error: str = "") -> str:
    e = html.escape
    two_step = (
        "<p class=muted>Optional: add this key to an authenticator app and enter its "
        "code to turn on two-step sign-in.</p>"
        f"<p><code>{e(secret)}</code></p>"
        f'<input type=hidden name=totp_secret value="{e(secret)}">'
        "<label for=code>Authenticator code (optional)</label>"
        "<input id=code name=code autocomplete=one-time-code autocapitalize=none "
        "spellcheck=false maxlength=64>"
        if secret
        else ""
    )
    return (
        f"<h1>{_TITLE}</h1><p>You've been invited as {e(email)}. Choose a password to "
        "finish: at least 12 characters.</p><form method=post>"
        f'<input type=hidden name=t value="{e(token)}">'
        f'<input type=hidden name=email value="{e(email)}" autocomplete=username>'
        "<label for=password>Password</label>"
        "<input id=password name=password type=password autocomplete=new-password "
        "minlength=12 required autofocus>"
        + two_step
        + "<div class=row><button name=decision value=allow>Join</button></div>"
        + (f"<p class=err role=alert>{e(error)}</p>" if error else "")
        + "</form>"
    )


@router.get("/join", response_class=HTMLResponse)
async def join_page(svc: AppServices, t: str = ""):
    found = await svc.logins.invitation(t) if t else None
    if found is None:
        return _page(_GONE, status.HTTP_404_NOT_FOUND, title=_TITLE)
    secret = totp.new_secret() if svc.logins.two_step_available else ""
    return _page(_form(t, found["email"], secret), title=_TITLE)


@router.post("/join", response_class=HTMLResponse)
async def join(
    svc: AppServices,
    t: Annotated[str, Form()],
    password: Annotated[str, Form()],
    totp_secret: Annotated[str, Form(max_length=64)] = "",
    code: Annotated[str, Form(max_length=64)] = "",
):
    found = await svc.logins.invitation(t)
    if found is None:
        return _page(_GONE, status.HTTP_404_NOT_FOUND, title=_TITLE)
    try:
        joined = await svc.logins.accept_invitation(t, password, totp_secret=totp_secret, code=code)
    except LoginNotFound:
        return _page(_GONE, status.HTTP_404_NOT_FOUND, title=_TITLE)
    except LoginExists as exc:
        return _page(f"<h1>Already a member</h1><p>{html.escape(str(exc))}</p>", 409, title=_TITLE)
    except (PasswordRejected, CodeRefused, TwoStepUnavailable) as exc:
        return _page(_form(t, found["email"], totp_secret, str(exc)), 400, title=_TITLE)
    codes = joined["recovery_codes"]
    recovery = (
        "<p>Two-step sign-in is on. Keep these recovery codes somewhere safe; each "
        "works once, and you won't see them again:</p><p><code>"
        + "<br>".join(html.escape(c) for c in codes)
        + "</code></p>"
        if codes
        else ""
    )
    return _page(
        f"<h1>You're in</h1><p>Sign in as {html.escape(joined['email'])} from the "
        f"Salli app, the console or <code>salli login</code>.</p>{recovery}",
        title=_TITLE,
    )
