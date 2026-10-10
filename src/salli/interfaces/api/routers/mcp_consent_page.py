"""
Salli's own MCP consent page — where you approve an AI client (Claude, ChatGPT,
…) connecting to your Salli over MCP.

The OAuth authorize step redirects here with a short-lived signed request
token (`rt`). The page shows which client is asking, takes your Salli email and
password, signs you in against Supabase Auth, and records your Allow or Deny —
exactly what a web app's consent screen does through /mcp/oauth/consent-info
and /mcp/oauth/consent, without needing a web app.

Plain server-rendered HTML with no script and no session: every decision is
authenticated by the password submitted with it, so there is no cookie for a
cross-site request to ride on.
"""

from __future__ import annotations

import html
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from salli.application.services.mcp_oauth_service import ConsentError
from salli.config import Settings, get_settings
from salli.interfaces.api.deps import AppServices, _decode_jwt, insecure_dev_auth

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


async def _signed_in(
    svc: Any, settings: Settings, email: str, password: str, user_id: str
) -> tuple[str, str | None] | str:
    """(user id, email) for these credentials, or the error to show."""
    if insecure_dev_auth(settings):
        if not user_id:
            return "Enter a user id."
        caller, caller_email = user_id, None
    else:
        token = await _sign_in(settings, email, password)
        if token is None:
            return "That email and password didn't match."
        try:
            caller, caller_email = _decode_jwt(token, settings)
        except HTTPException:
            return "Couldn't verify your sign-in. Try again."
    if not await svc.profile.ensure_user(
        caller, caller_email, may_create=settings.salli_registration == "open"
    ):
        return "This account is not a member of this Salli instance."
    return caller, caller_email


async def _sign_in(settings: Settings, email: str, password: str) -> str | None:
    """A Supabase access token for these credentials, or None if refused."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            settings.supabase_url.rstrip("/") + "/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": settings.supabase_anon_key},
            json={"email": email, "password": password},
        )
    if resp.status_code != 200:
        return None
    token: Any = resp.json().get("access_token")
    return str(token) if token else None


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

    def again(error: str) -> HTMLResponse:
        return _page(
            _form(
                rt,
                info["client_name"],
                info["scope"],
                dev,
                error,
                audience=info.get("audience", "mcp"),
            ),
            401,
        )

    approve = decision == "allow"
    if approve:
        who = await _signed_in(svc, settings, email, password, user_id)
        if isinstance(who, str):
            return again(who)
        caller, _ = who
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

    def again(error: str) -> HTMLResponse:
        return _page(_device_form(user_code, dev, error, client=info["client_name"]), 401)

    approve = decision == "allow"
    caller = ""
    if approve:
        who = await _signed_in(svc, settings, email, password, user_id)
        if isinstance(who, str):
            return again(who)
        caller, _ = who
        if info.get("audience", "mcp") == "mcp":
            await svc.mcp_oauth.set_mcp_enabled(caller, True)
    try:
        await svc.mcp_oauth.decide_device(user_code, caller, approve)
    except ConsentError as exc:
        return again(str(exc))
    if not approve:
        return _page("<h1>Declined</h1><p>The device was not signed in.</p>")
    return _page(
        "<h1>Signed in</h1><p>You can close this page and go back to your other device.</p>"
    )
