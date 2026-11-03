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
    _ICON_KEY,  # pyright: ignore[reportPrivateUsage]
    _ICON_TICK,  # pyright: ignore[reportPrivateUsage]
    _error,  # pyright: ignore[reportPrivateUsage]
    _page,  # pyright: ignore[reportPrivateUsage]
)

router = APIRouter(tags=["mcp-oauth"])

_TITLE = "Join Salli"
_GONE = (
    "<h1>This link doesn't work</h1><p class=lede>The invitation has been used or has expired. "
    "Ask the person who runs this Salli server for a new one.</p>"
)


def _spaced(secret: str) -> str:
    """The key in groups of four, as it reads best in a box."""
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


def _form(token: str, email: str, secret: str, error: str = "") -> str:
    """The join form. There is no Cancel: an invitation has no client to
    return to, and no safe target exists, so closing the page is the way out."""
    e = html.escape
    two_step = (
        "<p class=muted>Optional: add this key to an authenticator app and enter its "
        "code to turn on two-step sign-in.</p>"
        f'<a class="btn q" href="{e(totp.provisioning_uri(secret, email))}">{_ICON_KEY}'
        "Add to an authenticator app</a>"
        f"<div class=key><small>Or type this key</small><code>{e(_spaced(secret))}</code></div>"
        f'<input type=hidden name=totp_secret value="{e(secret)}">'
        "<label for=code>Authenticator code <span class=opt>optional</span></label>"
        "<input id=code name=code autocomplete=one-time-code autocapitalize=none "
        "spellcheck=false maxlength=64>"
        if secret
        else ""
    )
    return (
        f"<h1>{_TITLE}</h1><p class=lede>You've been invited as {e(email)}. Choose a password "
        "to finish: at least 12 characters.</p>"
        + (_error(error) if error else "")
        + "<form method=post>"
        f'<input type=hidden name=t value="{e(token)}">'
        f'<input type=hidden name=email value="{e(email)}" autocomplete=username>'
        "<label for=password>Password</label>"
        "<input id=password name=password type=password autocomplete=new-password "
        "minlength=12 required autofocus>"
        + two_step
        + "<div class=row><button name=decision value=allow>Join</button></div>"
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
        return _page(
            f"<h1>Already a member</h1><p class=lede>{html.escape(str(exc))}</p>",
            409,
            title=_TITLE,
        )
    except (PasswordRejected, CodeRefused, TwoStepUnavailable) as exc:
        return _page(_form(t, found["email"], totp_secret, str(exc)), 400, title=_TITLE)
    codes = joined["recovery_codes"]
    recovery = (
        "<p class=lede>Two-step sign-in is on. Keep these recovery codes somewhere safe; each "
        "works once, and you won't see them again:</p><div class=codes>"
        + "".join(f"<code>{html.escape(c)}</code>" for c in codes)
        + "</div>"
        if codes
        else ""
    )
    return _page(
        f"<div class=ok><span class=disc>{_ICON_TICK}</span><h1>You're in</h1></div>"
        f"<p class=lede>Sign in as {html.escape(joined['email'])} from the "
        f"Salli app, the console or <code>salli login</code>.</p>{recovery}",
        title=_TITLE,
    )
