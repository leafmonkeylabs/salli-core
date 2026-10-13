"""
Salli's own sign-in and consent page — where you approve an AI client
(Claude, ChatGPT, …) connecting to your Salli over MCP, the salli CLI signing
in, or sign in to the console — and the device page, where you approve a
sign-in with a code.

The OAuth authorize step redirects here with a short-lived signed request
token (`rt`). The page shows which client is asking, takes your Salli email and
password, checks them against Salli's own accounts (throttled like any
sign-in), and records your Allow or Deny — exactly what a web app's consent
screen does through /mcp/oauth/consent-info and /mcp/oauth/consent, without
needing a web app.

Plain server-rendered HTML with no script and no session: every decision is
authenticated by the password submitted with it, so there is no cookie for a
cross-site request to ride on. The password is never written back into the
page. The only place the console's password is typed is here: the console
has no sign-in form of its own, and comes back here (`prompt=login`) for the
password again before activating tax rules.
"""

from __future__ import annotations

import base64
import hashlib
import html
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from salli.application.services.login_service import SignInRefused, SignInThrottled
from salli.application.services.mcp_oauth_service import CONSOLE_CLIENT_ID, ConsentError
from salli.config import Settings, get_settings, insecure_dev_auth
from salli.interfaces.api.deps import AppServices

router = APIRouter(tags=["mcp-oauth"])

# The brand (docs/brand/README.md): paper and ink, ledger green for the
# primary action, sand for the secondary, oxblood (clay at night) for an
# error; night, paper-on-dark and sand-on-dark in the dark. System fonts, so
# the page makes no font request. The focus ring is ledger green, and
# sand-on-dark at night, not the brand's brass: brass is 2.4:1 on paper, below
# the 3:1 a focus indicator needs (console decision 11).
_STYLE = (
    ":root{color-scheme:light dark;--paper:#F6F3EC;--bone:#ECE6D9;--hairline:#DCD4C4;"
    "--ink:#1C1B19;--graphite:#57524A;--green:#173B33;--sand:#D8CBAE;--error:#6B2620;"
    "--on-green:#F6F3EC;--focus:#173B33;--mark:#173B33}"
    "@media (prefers-color-scheme:dark){:root{--paper:#0E1513;--bone:#0F2924;"
    "--hairline:#2B3A35;--ink:#F2ECDF;--graphite:#9AAAA2;--green:#CDBF9F;--sand:#0F2924;"
    "--error:#E2A58F;--on-green:#0E1513;--focus:#CDBF9F;--mark:#CDBF9F}}"
    "*{box-sizing:border-box}"
    "body{margin:0;background:var(--paper);color:var(--ink);"
    "font:16px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif}"
    "main{max-width:26rem;margin:0 auto;padding:4rem 1rem}"
    ".brand{display:flex;align-items:center;gap:.6rem;margin:0 0 2rem;color:var(--graphite);"
    "font-size:.8rem;font-weight:500;letter-spacing:.12em;text-transform:uppercase}"
    ".brand svg{width:28px;height:20px;fill:var(--mark)}"
    "h1{font-size:1.4rem;line-height:1.3;letter-spacing:-.01em;font-weight:600;margin:0 0 .6rem}"
    "p{margin:0 0 1rem}"
    "label{display:block;margin:1rem 0 .3rem;font-size:.875rem;font-weight:500;"
    "color:var(--graphite)}"
    "input{width:100%;height:40px;padding:0 .7rem;font:inherit;color:var(--ink);"
    "background:var(--bone);border:1px solid var(--hairline);border-radius:0}"
    ".row{display:flex;gap:.6rem;margin-top:1.4rem}"
    "button{flex:1;height:40px;padding:0 1rem;font:inherit;font-weight:500;cursor:pointer;"
    "border-radius:0;border:1px solid var(--green);background:var(--green);"
    "color:var(--on-green)}"
    "button[value=deny]{background:var(--sand);border-color:var(--hairline);color:var(--ink)}"
    "input:focus-visible,button:focus-visible{outline:2px solid var(--focus);"
    "outline-offset:2px}"
    "code{font-family:ui-monospace,'SF Mono',Menlo,monospace;font-size:.9em}"
    ".err{color:var(--error);margin-top:1rem}"
    ".muted{color:var(--graphite);font-size:.875rem;margin-top:1.4rem}"
)

#: The mark (docs/brand/assets/salli-mark.svg), inline so the page loads
#: nothing; coloured by the stylesheet for light and dark.
_MARK = (
    '<svg viewBox="0 0 200 140" aria-hidden="true" focusable="false">'
    '<rect width="130" height="50"/><rect x="147.5" width="52.5" height="50"/>'
    '<rect y="90" width="52.5" height="50"/><rect x="70" y="90" width="130" height="50"/>'
    "</svg>"
)


def _style_hash(css: str) -> str:
    digest = hashlib.sha256(css.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    # Stricter than the console's: no script at all, and only this page's
    # own stylesheet, by its hash. No form-action: after a decision the
    # browser is redirected to the client's own callback, and Chrome applies
    # form-action to that redirect.
    "Content-Security-Policy": "default-src 'none'; "
    f"style-src {_style_hash(_STYLE)}; frame-ancestors 'none'; base-uri 'none'; "
    "require-trusted-types-for 'script'; trusted-types 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


def _page(body: str, status_code: int = 200, title: str = "Connect to Salli") -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang=en-GB><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><main><p class=brand>{_MARK}<span>Salli</span></p>{body}</main></body></html>",
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


def _is_console(info: dict[str, Any]) -> bool:
    return info.get("client_id") == CONSOLE_CLIENT_ID


def _title(info: dict[str, Any]) -> str:
    if info.get("reauthenticate"):
        return "Confirm it's you"
    if _is_console(info):
        return "Sign in to Salli"
    client = str(info.get("client_name") or "An application")
    if info.get("audience", "mcp") == "api":
        return f"Sign in to {client}?"
    return f"Connect {client} to your Salli?"


def _form(rt: str, info: dict[str, Any], dev: bool, error: str = "") -> str:
    """The sign-in form. Salli's console reads plainly as signing in to
    Salli, with one button; a client asking the person to confirm it's them
    again says so; any other client is allowed or denied by name."""
    e = html.escape
    audience = info.get("audience", "mcp")
    if info.get("reauthenticate"):
        intro = "<p>Enter your password again to continue.</p>"
    elif _is_console(info):
        intro = ""
    else:
        intro = f"<p>{_asking(info['client_name'], audience, info.get('scope') or '')}</p>"
    if info.get("reauthenticate") or _is_console(info):
        label = "Continue" if info.get("reauthenticate") else "Sign in"
        buttons = f"<div class=row><button name=decision value=allow>{label}</button></div>"
    else:
        buttons = (
            "<div class=row><button name=decision value=allow>Allow</button>"
            "<button name=decision value=deny formnovalidate>Deny</button></div>"
        )
    return (
        f"<h1>{e(_title(info))}</h1>{intro}"
        "<form method=post>"
        f'<input type=hidden name=rt value="{e(rt)}">{_who(dev)}'
        + buttons
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
    return _page(_form(rt, info, insecure_dev_auth(settings)), title=_title(info))


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
        return _page(_form(rt, info, dev, refusal.message), refusal.status_code, title=_title(info))

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
        # The password was checked just now: the sign-in records that.
        target = await svc.mcp_oauth.complete_consent(rt, caller, approve, password_checked=approve)
    except ConsentError as exc:
        return again(_Refusal(str(exc), status.HTTP_403_FORBIDDEN))
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


# ── Device sign-in (RFC 8628) ───────────────────────────────────────────────

_DEVICE_TITLE = "Sign in a device"


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
    return _page(
        _device_form(user_code, insecure_dev_auth(settings), client=client), title=_DEVICE_TITLE
    )


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
            _device_form(user_code, dev, "That code is not valid, or it has expired."),
            400,
            title=_DEVICE_TITLE,
        )

    def again(refusal: _Refusal) -> HTMLResponse:
        return _page(
            _device_form(user_code, dev, refusal.message, client=info["client_name"]),
            refusal.status_code,
            title=_DEVICE_TITLE,
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
        return _page("<h1>Declined</h1><p>The device was not signed in.</p>", title=_DEVICE_TITLE)
    return _page(
        "<h1>Signed in</h1><p>You can close this page and go back to your other device.</p>",
        title=_DEVICE_TITLE,
    )
