"""
Salli's own MCP consent page — where you approve an AI client (Claude, ChatGPT,
…) connecting to your Salli over MCP, or the salli CLI signing in — and the
device page, where you approve a sign-in with a code.

The OAuth authorize step redirects here with a short-lived signed request
token (`rt`). The page shows which client is asking, takes your Salli email and
password, checks them against Salli's own accounts (throttled like any
sign-in), and records your Allow or Deny — exactly what a web app's consent
screen does through /mcp/oauth/consent-info and /mcp/oauth/consent, without
needing a web app.

Plain server-rendered HTML with no script and no session: every decision is
authenticated by the password submitted with it, so there is no cookie for a
cross-site request to ride on. The password is never written back into the
page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from salli.application.services.login_service import SignInRefused, SignInThrottled
from salli.application.services.mcp_oauth_service import ConsentError
from salli.config import Settings, get_settings, insecure_dev_auth
from salli.interfaces.api.deps import AppServices

router = APIRouter(tags=["mcp-oauth"])

_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    # No form-action: after a decision the browser is redirected to the
    # client's own callback, and Chrome applies form-action to that redirect.
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
    "frame-ancestors 'none'; base-uri 'none'",
    "Referrer-Policy": "no-referrer",
}

_STYLE = """
body{font:16px/1.5 system-ui,sans-serif;max-width:26rem;margin:4rem auto;padding:0 1rem;
color:#1b1b1b;background:#fafaf7}
h1{font-size:1.3rem}label{display:block;margin:.8rem 0 .2rem}
input{width:100%;padding:.55rem;font:inherit;box-sizing:border-box;border:1px solid #bbb;
border-radius:6px}
.row{display:flex;gap:.6rem;margin-top:1.2rem}
button{flex:1;padding:.6rem;font:inherit;border-radius:6px;border:1px solid #2E7D6B;
background:#2E7D6B;color:#fff;cursor:pointer}
button[value=deny]{background:#fff;color:#2E7D6B}
.err{color:#a33;margin-top:1rem}.muted{color:#666;font-size:.9rem}
@media (prefers-color-scheme:dark){body{background:#151515;color:#eee}
input{background:#222;color:#eee;border-color:#444}button[value=deny]{background:#151515}}
"""


def _page(body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>Connect to Salli</title><style>{_STYLE}</style></head>"
        f"<body>{body}</body></html>",
        status_code=status_code,
        headers=_HEADERS,
    )


def _who(dev: bool, autofocus: bool = True) -> str:
    focus = " autofocus" if autofocus else ""
    if dev:
        return f"<label for=user_id>User id</label><input id=user_id name=user_id required{focus}>"
    return (
        "<label for=email>Email</label>"
        f"<input id=email name=email type=email autocomplete=username required{focus}>"
        "<label for=password>Password</label>"
        "<input id=password name=password type=password autocomplete=current-password required>"
    )


def _asking(client: str, audience: str, scope: str) -> str:
    """What the client wants, in words: an AI client acting on your data over
    MCP, or one of your own Salli clients (the CLI) signing in as you."""
    e = html.escape
    if audience == "api":
        return f"{e(client)} is asking to sign in to your Salli account as you."
    return (
        f"{e(client)} is asking to read your Salli data and act on it for you"
        + (f" (scope: <code>{e(scope)}</code>)" if scope else "")
        + ". You can disconnect it at any time."
    )


def _form(
    rt: str, client: str, scope: str, dev: bool, error: str = "", audience: str = "mcp"
) -> str:
    e = html.escape
    title = (
        f"Sign in to {e(client)}?" if audience == "api" else f"Connect {e(client)} to your Salli?"
    )
    return (
        f"<h1>{title}</h1><p>{_asking(client, audience, scope)}</p>"
        "<form method=post>"
        f'<input type=hidden name=rt value="{e(rt)}">{_who(dev)}'
        "<div class=row><button name=decision value=allow>Allow</button>"
        "<button name=decision value=deny formnovalidate>Deny</button></div>"
        + (f"<p class=err role=alert>{e(error)}</p>" if error else "")
        + "<p class=muted>Sign in with the account you use for Salli.</p></form>"
    )


@dataclass(frozen=True)
class _Refusal:
    """Why the page won't act on a decision, and the status to show it with."""

    message: str
    status_code: int = status.HTTP_401_UNAUTHORIZED


async def _signed_in(
    svc: Any, settings: Settings, request: Request, email: str, password: str, user_id: str
) -> str | _Refusal:
    """The user id these credentials belong to, or why not."""
    if insecure_dev_auth(settings):
        if not user_id:
            return _Refusal("Enter a user id.")
        caller = user_id
    else:
        try:
            who = await svc.logins.authenticate(
                email, password, address=request.client.host if request.client else None
            )
        except SignInRefused as exc:
            return _Refusal(str(exc))
        except SignInThrottled as exc:
            return _Refusal(str(exc), status.HTTP_429_TOO_MANY_REQUESTS)
        caller = who.user_id
    if not await svc.profile.ensure_user(caller, None, may_create=False):
        return _Refusal("This account is not a member of this Salli instance.", 403)
    return caller


@router.get("/mcp/oauth/consent-page", response_class=HTMLResponse)
async def consent_page(
    rt: str, svc: AppServices, settings: Annotated[Settings, Depends(get_settings)]
):
    try:
        info = await svc.mcp_oauth.get_consent_info(rt, user_id="")
    except ConsentError as exc:
        return _page(f"<h1>Can't connect</h1><p>{html.escape(str(exc))}</p>", 400)
    return _page(
        _form(
            rt,
            info["client_name"],
            info["scope"],
            insecure_dev_auth(settings),
            audience=info.get("audience", "mcp"),
        )
    )


@router.post("/mcp/oauth/consent-page", response_class=HTMLResponse)
async def consent_page_decision(
    request: Request,
    svc: AppServices,
    settings: Annotated[Settings, Depends(get_settings)],
    rt: Annotated[str, Form()],
    decision: Annotated[str, Form()],
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    user_id: Annotated[str, Form()] = "",
):
    try:
        info = await svc.mcp_oauth.get_consent_info(rt, user_id="")
    except ConsentError as exc:
        return _page(f"<h1>Can't connect</h1><p>{html.escape(str(exc))}</p>", 400)
    dev = insecure_dev_auth(settings)

    def again(refusal: _Refusal) -> HTMLResponse:
        return _page(
            _form(
                rt,
                info["client_name"],
                info["scope"],
                dev,
                refusal.message,
                audience=info.get("audience", "mcp"),
            ),
            refusal.status_code,
        )

    approve = decision == "allow"
    if approve:
        who = await _signed_in(svc, settings, request, email, password, user_id)
        if isinstance(who, _Refusal):
            return again(who)
        caller = who
        # Connecting an AI client from here is consent to MCP, so switch it on
        # for them. Signing in the CLI is not, and leaves MCP as it was.
        if info.get("audience", "mcp") == "mcp":
            await svc.mcp_oauth.set_mcp_enabled(caller, True)
    else:
        # Denying needs no sign-in: it grants nothing, and the client learns
        # only that access was refused.
        caller = ""

    try:
        target = await svc.mcp_oauth.complete_consent(rt, caller, approve)
    except ConsentError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


# ── Device sign-in (RFC 8628) ───────────────────────────────────────────────


def _device_form(user_code: str, dev: bool, error: str = "", client: str = "") -> str:
    e = html.escape
    what = (
        f"<p>{e(client)} on another device is waiting to be signed in.</p>"
        if client
        else "<p>Enter the code your other device shows to sign it in.</p>"
    )
    return (
        "<h1>Sign in a device</h1>" + what + "<form method=post>"
        "<label for=user_code>Code</label>"
        f'<input id=user_code name=user_code value="{e(user_code)}" required '
        'autocomplete=off autocapitalize=characters spellcheck=false placeholder="ABCD-EFGH">'
        + _who(dev, autofocus=bool(user_code))
        + "<div class=row><button name=decision value=allow>Allow</button>"
        "<button name=decision value=deny formnovalidate>Deny</button></div>"
        + (f"<p class=err role=alert>{e(error)}</p>" if error else "")
        + "<p class=muted>Only approve a code you asked for, on a device you are using.</p>"
        "</form>"
    )


@router.get("/mcp/oauth/device", response_class=HTMLResponse)
async def device_page(
    svc: AppServices, settings: Annotated[Settings, Depends(get_settings)], user_code: str = ""
):
    info = await svc.mcp_oauth.device_request(user_code) if user_code else None
    client = info["client_name"] if info else ""
    return _page(_device_form(user_code, insecure_dev_auth(settings), client=client))


@router.post("/mcp/oauth/device", response_class=HTMLResponse)
async def device_page_decision(
    request: Request,
    svc: AppServices,
    settings: Annotated[Settings, Depends(get_settings)],
    user_code: Annotated[str, Form()],
    decision: Annotated[str, Form()],
    email: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    user_id: Annotated[str, Form()] = "",
):
    dev = insecure_dev_auth(settings)
    info = await svc.mcp_oauth.device_request(user_code)
    if info is None:
        return _page(
            _device_form(user_code, dev, "That code is not valid, or it has expired."), 400
        )

    def again(refusal: _Refusal) -> HTMLResponse:
        return _page(
            _device_form(user_code, dev, refusal.message, client=info["client_name"]),
            refusal.status_code,
        )

    approve = decision == "allow"
    caller = ""
    if approve:
        who = await _signed_in(svc, settings, request, email, password, user_id)
        if isinstance(who, _Refusal):
            return again(who)
        caller = who
        if info.get("audience", "mcp") == "mcp":
            await svc.mcp_oauth.set_mcp_enabled(caller, True)
    try:
        await svc.mcp_oauth.decide_device(user_code, caller, approve)
    except ConsentError as exc:
        return again(_Refusal(str(exc)))
    if not approve:
        return _page("<h1>Declined</h1><p>The device was not signed in.</p>")
    return _page(
        "<h1>Signed in</h1><p>You can close this page and go back to your other device.</p>"
    )
