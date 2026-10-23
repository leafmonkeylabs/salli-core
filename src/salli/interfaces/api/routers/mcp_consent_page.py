"""
Salli's own sign-in and consent page, and the device page.

The consent page is where you approve an AI client (Claude, ChatGPT, and the
like) connecting to your Salli over MCP, the salli CLI signing in, or a sign-in
to the console. The device page is where you approve a sign-in with a code.

The OAuth authorize step redirects here with a short-lived signed request
token (`rt`). The page shows which client is asking, takes your Salli email and
password, checks them against Salli's own accounts (throttled like any
sign-in), and records your Allow or Deny: exactly what a web app's consent
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
# the 3:1 a focus indicator needs (console decision 11). A field's border is
# stone (muted on dark), not hairline, so its edge is at least 3:1. Inputs and
# buttons are 44 px, a touch target.
_STYLE = (
    ":root{color-scheme:light dark;--paper:#F6F3EC;--bone:#ECE6D9;--hairline:#DCD4C4;"
    "--field:#8A8378;--ink:#1C1B19;--graphite:#57524A;--green:#173B33;--sand:#D8CBAE;"
    "--error:#6B2620;--on-green:#F6F3EC;--focus:#173B33;--mark:#173B33}"
    "@media (prefers-color-scheme:dark){:root{--paper:#0E1513;--bone:#0F2924;"
    "--hairline:#2B3A35;--field:#9AAAA2;--ink:#F2ECDF;--graphite:#9AAAA2;--green:#CDBF9F;"
    "--sand:#0F2924;--error:#E2A58F;--on-green:#0E1513;--focus:#CDBF9F;--mark:#CDBF9F}}"
    "*{box-sizing:border-box}"
    "body{margin:0;background:var(--paper);color:var(--ink);"
    "font:16px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif}"
    "main{max-width:26rem;margin:0 auto;padding:4rem 1rem}"
    ".brand{margin:0 0 2rem}"
    ".brand svg{display:block;width:89px;height:26px}"
    ".brand .m{fill:var(--mark)}.brand .w{fill:var(--ink)}"
    "h1{font-size:1.4rem;line-height:1.3;letter-spacing:-.01em;font-weight:600;margin:0 0 .6rem}"
    "p{margin:0 0 1rem}"
    "label{display:block;margin:1rem 0 .3rem;font-size:.875rem;font-weight:500;"
    "color:var(--graphite)}"
    "input{width:100%;height:44px;padding:0 .7rem;font:inherit;color:var(--ink);"
    "background:var(--bone);border:1px solid var(--field);border-radius:0}"
    ".row{display:flex;gap:.6rem;margin-top:1.4rem}"
    "button{flex:1;height:44px;padding:0 1rem;font:inherit;font-weight:500;cursor:pointer;"
    "border-radius:0;border:1px solid var(--green);background:var(--green);"
    "color:var(--on-green)}"
    "button[value=deny]{background:var(--sand);border-color:var(--hairline);color:var(--ink)}"
    "input:focus-visible,button:focus-visible{outline:2px solid var(--focus);"
    "outline-offset:2px}"
    "code{font-family:ui-monospace,'SF Mono',Menlo,monospace;font-size:.9em}"
    ".err{color:var(--error);margin-top:1rem}"
    ".muted{color:var(--graphite);font-size:.875rem;margin-top:1.4rem}"
    ".muted+.muted{margin-top:0}"
)

#: The logo, outlined (docs/brand/assets/salli-logo.svg; the wordmark is never
#: retyped), inline so the page loads nothing; the stylesheet colours it for
#: light and dark: the mark ledger green (sand on dark), the wordmark ink
#: (paper on dark).
_LOGO = (
    '<svg viewBox="0 0 472.214 137.829" role="img" aria-label="Salli">'
    '<rect class=m x="28.71" y="28.71" width="74.66" height="28.71"/>'
    '<rect class=m x="113.42" y="28.71" width="30.15" height="28.71"/>'
    '<rect class=m x="28.71" y="80.40" width="30.15" height="28.71"/>'
    '<rect class=m x="68.91" y="80.40" width="74.66" height="28.71"/>'
    '<path class=w transform="translate(193.42 109.11)" d="'
    "M30.72 1.92Q22.92 1.92 16.02 0.12Q9.12 -1.68 4.92 -4.08L5.28 -22.32H14.16L17.76 "
    "-3.96L9.6 -5.52V-12.12Q12.84 -9.96 16.02 -8.46Q19.2 -6.96 22.68 -6.12Q26.16 -5.28 30.36 "
    "-5.28Q36.12 -5.28 39.84 -6.9Q43.56 -8.52 45.36 -11.46Q47.16 -14.4 47.16 -18Q47.16 -21.48 "
    "45.78 -23.88Q44.4 -26.28 41.46 -28.14Q38.52 -30 33.72 -31.8L29.52 -33.6Q22.68 -36.36 "
    "17.4 -39.66Q12.12 -42.96 9.12 -47.58Q6.12 -52.2 6.12 -59.04Q6.12 -66.24 9.96 -71.28Q13.8 "
    "-76.32 20.4 -78.96Q27 -81.6 35.4 -81.6Q42.72 -81.6 48.48 -79.92Q54.24 -78.24 57.72 "
    "-75.96L57.24 -58.8H48.6L45 -76.56L53.28 -74.64V-68.04Q49.08 -71.16 45 -72.84Q40.92 "
    "-74.52 35.64 -74.52Q31.08 -74.52 27.84 -73.02Q24.6 -71.52 22.8 -68.88Q21 -66.24 21 "
    "-62.76Q21 -59.4 22.44 -57Q23.88 -54.6 26.82 -52.74Q29.76 -50.88 34.2 -49.08L38.64 "
    "-47.28Q46.08 -44.28 51.36 -40.92Q56.64 -37.56 59.4 -33Q62.16 -28.44 62.16 -21.84Q62.16 "
    "-14.52 58.26 -9.18Q54.36 -3.84 47.34 -0.96Q40.32 1.92 30.72 1.92ZM87.36 1.8Q80.4 1.8 "
    "75.66 -2.28Q70.92 -6.36 70.92 -13.92Q70.92 -18.36 72.9 -21.9Q74.88 -25.44 79.56 "
    "-28.2Q84.24 -30.96 92.16 -33Q95.52 -33.96 98.76 -34.8Q102 -35.64 105.24 -36.54Q108.48 "
    "-37.44 111.72 -38.16V-33.12Q107.76 -31.92 103.74 -30.66Q99.72 -29.4 95.76 -28.2Q91.68 "
    "-27 89.4 -25.26Q87.12 -23.52 86.22 -21.42Q85.32 -19.32 85.32 -16.8Q85.32 -12.6 87.9 "
    "-10.26Q90.48 -7.92 94.8 -7.92Q97.2 -7.92 99.36 -8.82Q101.52 -9.72 103.92 -11.4Q106.32 "
    "-13.08 109.56 -15.72L110.28 -9.12H105.48Q103.2 -6.12 100.8 -3.66Q98.4 -1.2 95.22 "
    "0.3Q92.04 1.8 87.36 1.8ZM119.64 1.56Q113.76 1.56 110.4 -1.74Q107.04 -5.04 106.56 "
    "-11.28L106.2 -11.52V-40.68Q106.2 -45.96 104.94 -48.96Q103.68 -51.96 101.1 -53.22Q98.52 "
    "-54.48 94.56 -54.48Q91.68 -54.48 88.98 -54Q86.28 -53.52 83.4 -52.44L89.04 -57.6L87.72 "
    "-47.52Q87.36 -42.72 85.2 -40.56Q83.04 -38.4 79.92 -38.4Q76.68 -38.4 74.94 -40.02Q73.2 "
    "-41.64 72.6 -44.16Q73.92 -51.96 80.82 -56.46Q87.72 -60.96 98.88 -60.96Q106.08 -60.96 111 "
    "-58.8Q115.92 -56.64 118.5 -51.96Q121.08 -47.28 121.08 -39.6V-12.96Q121.08 -10.08 122.16 "
    "-8.76Q123.24 -7.44 125.28 -7.44Q126.6 -7.44 127.74 -7.92Q128.88 -8.4 129.84 -9.12L132 "
    "-4.8Q130.08 -1.92 126.96 -0.18Q123.84 1.56 119.64 1.56ZM135.24 0V-6.36L148.32 "
    "-7.56H154.56L167.88 -6.36V0ZM143.88 0Q143.88 -4.32 143.94 -8.64Q144 -12.96 144 "
    "-17.28Q144 -21.6 144 -25.8V-75.84L134.64 -77.64V-83.04L155.52 -87.48L159.24 -86.88L159 "
    "-71.04V-25.8Q159 -21.6 159.06 -17.28Q159.12 -12.96 159.12 -8.64Q159.12 -4.32 159.24 "
    "0ZM174.48 0V-6.36L187.56 -7.56H193.8L207.12 -6.36V0ZM183.12 0Q183.12 -4.32 183.18 "
    "-8.64Q183.24 -12.96 183.24 -17.28Q183.24 -21.6 183.24 -25.8V-75.84L173.88 "
    "-77.64V-83.04L194.76 -87.48L198.48 -86.88L198.24 -71.04V-25.8Q198.24 -21.6 198.3 "
    "-17.28Q198.36 -12.96 198.36 -8.64Q198.36 -4.32 198.48 0ZM214.2 0V-6.36L227.04 "
    "-7.56H233.4L246.12 -6.36V0ZM222.6 0Q222.6 -3.6 222.66 -8.04Q222.72 -12.48 222.72 "
    "-17.16Q222.72 -21.84 222.72 -25.8V-32.04Q222.72 -36.36 222.72 -39.96Q222.72 -43.56 222.6 "
    "-47.28L213.48 -47.88V-53.64L234.12 -60.24L237.96 -59.64L237.84 -43.92V-25.8Q237.84 "
    "-21.84 237.84 -17.16Q237.84 -12.48 237.9 -8.04Q237.96 -3.6 237.96 0ZM229.92 "
    "-70.56Q226.08 -70.56 223.38 -73.14Q220.68 -75.72 220.68 -79.44Q220.68 -83.28 223.38 "
    "-85.8Q226.08 -88.32 229.92 -88.32Q233.88 -88.32 236.52 -85.8Q239.16 -83.28 239.16 "
    "-79.44Q239.16 -75.72 236.52 -73.14Q233.88 -70.56 229.92 -70.56Z"
    '"/>'
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
        f"<body><main><p class=brand>{_LOGO}</p>{body}</main></body></html>",
        status_code=status_code,
        headers=_HEADERS,
    )


#: There is no email and no sign-up (decision D13): the owner resets passwords.
_FORGOTTEN = (
    "<p class=muted>Forgotten your password? "
    "The person who runs this Salli server can reset it.</p>"
)


def _forgotten(dev: bool) -> str:
    return "" if dev else _FORGOTTEN


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
        + "<p class=muted>Sign in with the account you use for Salli.</p>"
        + _forgotten(dev)
        + "</form>"
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


# Device sign-in (RFC 8628).

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
        + _forgotten(dev)
        + "</form>"
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
