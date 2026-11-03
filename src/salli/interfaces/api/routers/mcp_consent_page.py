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
password again before activating tax rules. Beside the password is a field
for an authenticator app's code (or a recovery code), which a login with
two-step sign-in on must fill in; for anyone else it stays empty.

A client that registered itself is named as it named itself, beside "Not
verified by Salli". An AI client is let in to read. Changing anything is a
separate permission for each part (the ledger, planning, documents,
settings: `mcp:ledger` and so on), given only by ticking that part, which
starts unticked. The Salli app's own AI asks the person
before each change in the app, so it has no tick box and may change.
"""

from __future__ import annotations

import base64
import hashlib
import html
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from salli.application.acting import act_as
from salli.application.services.login_service import SignInRefused, SignInThrottled
from salli.application.services.mcp_oauth_service import (
    CONSOLE_CLIENT_ID,
    MOBILE_CLIENT_ID,
    ConsentError,
)
from salli.config import Settings, get_settings, insecure_dev_auth
from salli.interfaces.api.deps import AppServices

router = APIRouter(tags=["mcp-oauth"])

# The brand, rounded (docs/brand/README.md, v2): a centred card on the ground
# colour, ink for the main button, green for focus and the checked box, red
# (a softer red at night) for an error; the v2 dark palette under
# prefers-color-scheme. System fonts, so the page makes no font request.
# Fields and buttons are 48 px; a field is a fill with a visible green focus
# ring; the secondary button has its own ring, so it reads on dark too. One
# <style> block, no style= attribute, no script, no image: its size matters,
# every response carries it.
_STYLE = (
    ":root{color-scheme:light dark;--g:#F3F2EF;--s:#fff;--f:#EFEEEA;--ln:#ECEBE7;"
    "--ink:#18201C;--mut:#5F6661;--acc:#2E6A55;--at:#E4EFE9;--neg:#A8483A;--nt:#F8E9E5;"
    "--btx:#fff;--bth:#2F3A34;--edge:#8C928E;--q:#EFEEEA;--qr:transparent;"
    "--sh:0 2px 6px rgba(24,32,28,.06),0 16px 40px rgba(24,32,28,.10)}"
    "@media (prefers-color-scheme:dark){:root{--g:#0E1110;--s:#171B19;--f:#232825;"
    "--ln:rgba(255,255,255,.08);--ink:#ECEFEC;--mut:#9BA39D;--acc:#7CC0A5;--at:#1F3A30;"
    "--neg:#E58E7C;--nt:#3B2622;--btx:#0E1110;--bth:#fff;--edge:#6F7773;--q:#2B322E;"
    "--qr:#4D5651;--sh:inset 0 1px 0 rgba(255,255,255,.07),0 20px 50px rgba(0,0,0,.5)}}"
    "*{box-sizing:border-box}"
    "body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--g);"
    "color:var(--ink);font:16px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif}"
    "main{width:min(100%,26rem);margin:1.5rem 1rem;padding:1.75rem;background:var(--s);"
    "border-radius:24px;box-shadow:var(--sh)}"
    ".top{display:flex;align-items:center;justify-content:space-between;gap:.6rem;"
    "margin:0 0 1.5rem}"
    ".brand{margin:0}.brand svg{display:block;width:89px;height:26px}"
    ".brand .m,.brand .w{fill:var(--ink)}"
    ".srv{display:inline-flex;align-items:center;gap:.4rem;height:28px;padding:0 .65rem;"
    "border-radius:999px;background:var(--f);color:var(--mut);min-width:0;"
    "font:12.5px ui-monospace,'SF Mono',Menlo,monospace}"
    ".srv span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
    "svg.i{flex:none;width:1em;height:1em;fill:none;stroke:currentColor;stroke-width:2;"
    "stroke-linecap:round;stroke-linejoin:round}"
    "h1{font-size:1.5rem;line-height:1.25;letter-spacing:-.02em;font-weight:600;margin:0 0 .6rem}"
    "p{margin:0 0 1rem}"
    ".lede{color:var(--mut);font-size:.97rem}"
    "label{display:flex;justify-content:space-between;align-items:baseline;gap:.5rem;"
    "margin:1.1rem .15rem .4rem;font-size:.875rem;font-weight:500;color:var(--mut)}"
    ".opt{padding:0 .5rem;border-radius:999px;background:var(--g);font-size:.75rem}"
    "input{width:100%;height:48px;padding:0 .9rem;font:inherit;color:var(--ink);"
    "background:var(--f);border:0;border-radius:14px;outline:2px solid transparent}"
    "input:focus-visible{background:var(--s);outline:2px solid transparent;"
    "box-shadow:inset 0 0 0 1.5px var(--acc),0 0 0 4px var(--at)}"
    ".help{margin:.4rem .15rem 0;font-size:.8125rem;color:var(--mut)}"
    ".row{display:flex;gap:.6rem;margin-top:1.4rem}"
    "button,.btn{display:flex;align-items:center;justify-content:center;gap:.5rem;width:100%;"
    "height:48px;padding:0 1.1rem;font:inherit;font-weight:600;cursor:pointer;border:0;"
    "border-radius:999px;background:var(--ink);color:var(--btx);text-decoration:none}"
    ".row button{flex:1;width:auto}"
    "button:hover{background:var(--bth)}"
    "button[value=deny],.btn.q{background:var(--q);color:var(--ink);box-shadow:inset 0 0 0 1px var(--qr)}"
    "button.q{height:40px;margin-top:.4rem;background:none;color:var(--mut);box-shadow:none;"
    "font-weight:500}"
    "button.q:hover{background:var(--f)}"
    ".btn.q{color:var(--acc);margin-top:1rem}"
    "button:focus-visible,.btn:focus-visible{outline:2px solid var(--acc);outline-offset:2px}"
    ".err{display:flex;gap:.6rem;align-items:flex-start;margin:1rem 0 0;padding:.75rem .9rem;"
    "border-radius:14px;background:var(--nt);font-size:.9rem;line-height:1.45}"
    ".err svg{margin-top:.2rem;color:var(--neg)}"
    ".muted{color:var(--mut);font-size:.84rem;line-height:1.5;margin:1.1rem .15rem 0;"
    "padding-top:1rem;border-top:1px solid var(--ln)}"
    ".muted+.muted{margin-top:.4rem;padding-top:0;border:0}"
    ".allow{border:0;margin:1.2rem 0 0;padding:.9rem 1rem .3rem;border-radius:18px;"
    "background:var(--g)}"
    ".allow legend{float:left;width:100%;padding:0;font-weight:600}"
    ".allow legend+*{clear:both}"
    ".allow small{display:block;color:var(--mut);font-size:.84rem;font-weight:400}"
    ".allow p{display:flex;gap:.7rem;align-items:flex-start;margin:0;padding:.65rem 0}"
    ".allow p+p{border-top:1px solid var(--ln)}"
    ".allow label{display:block;margin:0;font-size:1rem;font-weight:400;color:var(--ink)}"
    "input[type=checkbox]{appearance:none;flex:none;width:22px;height:22px;margin:1px 0 0;"
    "padding:0;display:grid;place-content:center;border-radius:7px;background:var(--s);"
    "box-shadow:inset 0 0 0 1.5px var(--edge);cursor:pointer}"
    "input[type=checkbox]::before{content:'';width:10px;height:5px;margin-top:-2px;"
    "border:solid var(--btx);border-width:0 0 2.5px 2.5px;border-radius:1px;"
    "transform:rotate(-45deg);visibility:hidden}"
    "input[type=checkbox]:checked{background:var(--acc);box-shadow:none}"
    "input[type=checkbox]:checked::before{visibility:visible}"
    "input[type=checkbox]:focus-visible{outline:2px solid var(--acc);outline-offset:2px;"
    "box-shadow:inset 0 0 0 1.5px var(--acc)}"
    ".badge{display:inline-flex;align-items:center;gap:.4rem;height:26px;padding:0 .65rem;"
    "margin:0 0 .7rem;border-radius:999px;background:var(--f);color:var(--mut);"
    "font-size:.78rem;font-weight:500}"
    "code{font:.9rem ui-monospace,'SF Mono',Menlo,monospace;overflow-wrap:anywhere}"
    ".key,.codes{margin:1rem 0;padding:.8rem 1rem;border-radius:16px;background:var(--g)}"
    ".key small{display:block;color:var(--mut);font-size:.78rem}"
    ".codes{display:grid;grid-template-columns:1fr 1fr;gap:.6rem 1rem}"
    ".ok{text-align:center}"
    ".ok .disc{display:grid;place-items:center;width:56px;height:56px;margin:0 auto 1rem;"
    "border-radius:50%;background:var(--acc);color:var(--btx);font-size:1.6rem}"
)

#: The logo, outlined (docs/brand/assets/salli-logo.svg; the wordmark is never
#: retyped), inline so the page loads nothing; the stylesheet colours it for
#: light and dark: ink for both. The bars have round ends (rx is half a
#: bar's height); two rows split differently, the same length in all.
_LOGO = (
    '<svg viewBox="0 0 472.214 137.829" role="img" aria-label="Salli">'
    '<rect class=m x="28.71" y="28.71" width="74.66" height="28.71" rx="14.355"/>'
    '<rect class=m x="113.42" y="28.71" width="30.15" height="28.71" rx="14.355"/>'
    '<rect class=m x="28.71" y="80.40" width="30.15" height="28.71" rx="14.355"/>'
    '<rect class=m x="68.91" y="80.40" width="74.66" height="28.71" rx="14.355"/>'
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


#: A small icon, an inline SVG (the page loads no image); `svg.i` in the style.
_ICON_LOCK = (
    '<svg class=i viewBox="0 0 24 24" aria-hidden=true><rect x=5 y=11 width=14 height=9.5 rx=3 />'
    '<path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>'
)
_ICON_ALERT = (
    '<svg class=i viewBox="0 0 24 24" aria-hidden=true><circle cx=12 cy=12 r=8.5 />'
    '<path d="M12 7.5v5.5M12 16.2h.01"/></svg>'
)
_ICON_INFO = (
    '<svg class=i viewBox="0 0 24 24" aria-hidden=true><circle cx=12 cy=12 r=8.5 />'
    '<path d="M12 11v5M12 8h.01"/></svg>'
)
_ICON_KEY = (
    '<svg class=i viewBox="0 0 24 24" aria-hidden=true><circle cx=8 cy=15 r=4 />'
    '<path d="M11 12l8-8M16 7l2 2M14 9l2 2"/></svg>'
)
_ICON_TICK = (
    '<svg class=i viewBox="0 0 24 24" aria-hidden=true><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
)


def _server_host() -> str:
    """The server's address as people know it: SALLI_PUBLIC_URL's host."""
    try:
        return urlsplit(get_settings().salli_public_url).netloc
    except Exception:  # a page must render even with settings unreadable
        return ""


def _page(body: str, status_code: int = 200, title: str = "Connect to Salli") -> HTMLResponse:
    host = _server_host()
    server = f"<span class=srv>{_ICON_LOCK}<span>{html.escape(host)}</span></span>" if host else ""
    return HTMLResponse(
        "<!doctype html><html lang=en-GB><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><main><div class=top><p class=brand>{_LOGO}</p>{server}</div>"
        f"{body}</main></body></html>",
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


def _who(dev: bool, autofocus: bool = True, kept: str = "") -> str:
    """The sign-in fields. `kept` is the email (or user id) the person typed,
    put back after a refusal; the password never is, so focus goes to it."""
    e = html.escape
    focus = " autofocus" if autofocus and not kept else ""
    value = f' value="{e(kept)}"' if kept else ""
    if dev:
        return (
            f"<label for=user_id>User id</label>"
            f"<input id=user_id name=user_id{value} required{focus}>"
        )
    on_password = " autofocus" if autofocus and kept else ""
    return (
        "<label for=email>Email</label>"
        f"<input id=email name=email type=email autocomplete=username{value} required{focus}>"
        "<label for=password>Password</label>"
        "<input id=password name=password type=password autocomplete=current-password "
        f"required{on_password}>"
        "<label for=code>Authenticator code <span class=opt>optional</span></label>"
        "<input id=code name=code autocomplete=one-time-code autocapitalize=none "
        "spellcheck=false maxlength=64>"
        "<p class=help>Only if you've turned on two-step sign-in. A recovery code works too.</p>"
    )


def _error(message: str) -> str:
    """A refusal, above the form: a rounded notice with an icon."""
    return f"<div class=err role=alert>{_ICON_ALERT}<span>{html.escape(message)}</span></div>"


def _asking(client: str, audience: str, client_id: str = "") -> str:
    """What the client wants, in words: an AI client reading your data over
    MCP, or one of your own Salli clients (the CLI) signing in as you."""
    e = html.escape
    if client_id == MOBILE_CLIENT_ID and audience == "mcp":
        return "It reads your books and asks you in the app before any change."
    if audience == "api":
        return f"{e(client)} is asking to sign in to your Salli account as you."
    return f"{e(client)} is asking to read your Salli data. You can disconnect it at any time."


#: The parts an AI client may be let change (MCP_WRITE_SCOPES), offered to
#: one other than the Salli app's, and never ticked for the person.
_PARTS = (
    ("ledger", "Change the books", "Book, recategorise, reverse and discard transactions; "
     "import statements; add accounts and rules."),
    ("planning", "Change plans", "Set the monthly budget, debts, planning assumptions and "
     "principles; record decisions."),
    ("documents", "Change documents", "Save, update and delete documents and memories; "
     "add reminders."),
    ("settings", "Change settings", "Draft and propose tax rule sets and add the accounts "
     "they suggest."),
)  # fmt: skip
_ALLOW_CHANGES = (
    "<fieldset class=allow><legend>Allow changes "
    "<small>Without these it can only read.</small></legend>"
    + "".join(
        f"<p><input type=checkbox id=allow_{part} name=allow value={part}>"
        f"<label for=allow_{part}>{label}<small>{what}</small></label></p>"
        for part, label, what in _PARTS
    )
    + "</fieldset>"
)


def _allowed(ticked: list[str]) -> list[str]:
    """The scopes for the parts ticked, ignoring anything else sent."""
    return [f"mcp:{part}" for part, _, _ in _PARTS if part in ticked]


def _offers_changes(info: dict[str, Any]) -> bool:
    """Whether the page asks about changes: an AI client, not the app's own."""
    return info.get("audience", "mcp") == "mcp" and not _is_apps_ai(info)


def _is_salli(info: dict[str, Any]) -> bool:
    """Salli's console or its app signing in to Salli itself, not letting
    another application in. The app's AI asking for MCP is an AI connection,
    asked for by name like any other."""
    return info.get("client_id") in (CONSOLE_CLIENT_ID, MOBILE_CLIENT_ID) and (
        info.get("audience", "mcp") == "api"
    )


def _is_apps_ai(info: dict[str, Any]) -> bool:
    """The AI the person set up in the Salli app, asking for MCP."""
    return info.get("client_id") == MOBILE_CLIENT_ID and info.get("audience", "mcp") == "mcp"


def _title(info: dict[str, Any]) -> str:
    if info.get("reauthenticate"):
        return "Confirm it's you"
    if _is_salli(info):
        return "Sign in to Salli"
    client = str(info.get("client_name") or "An application")
    if _is_apps_ai(info):
        return "Connect the AI in the Salli app?"
    if info.get("audience", "mcp") == "api":
        return f"Sign in to {client}?"
    return f"Connect {client} to your Salli?"


def _form(rt: str, info: dict[str, Any], dev: bool, error: str = "", kept: str = "") -> str:
    """The sign-in form. Salli's console and its app read plainly as signing
    in to Salli, with one main button and a Cancel; a client asking the person
    to confirm it's them again says so; any other client is allowed or denied
    by name. A refusal is shown above the form and the email is kept.

    Cancel is the existing deny path (`decision=deny`, no sign-in needed): it
    sends the browser to the client's own registered redirect with
    `error=access_denied`, which the console, the app and the CLI handle."""
    e = html.escape
    audience = info.get("audience", "mcp")
    if info.get("reauthenticate"):
        intro = "<p class=lede>Enter your password again to continue.</p>"
    elif _is_salli(info):
        intro = ""
    else:
        asking = _asking(info["client_name"], audience, str(info.get("client_id") or ""))
        intro = f"<p class=lede>{asking}</p>"
    if info.get("reauthenticate") or _is_salli(info):
        label = "Continue" if info.get("reauthenticate") else "Sign in"
        buttons = (
            f"<div class=row><button name=decision value=allow>{label}</button></div>"
            "<button class=q name=decision value=deny formnovalidate>Cancel</button>"
        )
    else:
        buttons = (
            "<div class=row><button name=decision value=allow>Allow</button>"
            "<button name=decision value=deny formnovalidate>Deny</button></div>"
        )
    # A client that registered itself chose its own name: say Salli hasn't
    # checked it, beside it.
    unverified = (
        ""
        if info.get("first_party") or info.get("reauthenticate")
        else f"<span class=badge>{_ICON_INFO}Not verified by Salli</span>"
    )
    return (
        f"<h1>{e(_title(info))}</h1>{unverified}{intro}"
        + (_error(error) if error else "")
        + "<form method=post>"
        f'<input type=hidden name=rt value="{e(rt)}">{_who(dev, kept=kept)}'
        + (_ALLOW_CHANGES if _offers_changes(info) and not info.get("reauthenticate") else "")
        + buttons
        + (
            "<p class=muted>You can disconnect it any time.</p>"
            if _is_apps_ai(info) and not info.get("reauthenticate")
            else "<p class=muted>Sign in with the account you use for Salli.</p>"
        )
        + _forgotten(dev)
        + "</form>"
    )


@dataclass(frozen=True)
class _Refusal:
    """Why the page won't act on a decision, and the status to show it with."""

    message: str
    status_code: int = status.HTTP_401_UNAUTHORIZED


async def _signed_in(
    svc: Any,
    settings: Settings,
    request: Request,
    email: str,
    password: str,
    user_id: str,
    code: str = "",
) -> str | _Refusal:
    """The user id these credentials belong to, or why not."""
    if insecure_dev_auth(settings):
        if not user_id:
            return _Refusal("Enter a user id.")
        caller = user_id
    else:
        try:
            who = await svc.logins.authenticate(
                email,
                password,
                address=request.client.host if request.client else None,
                code=code or None,
            )
        except SignInRefused as exc:
            return _Refusal(str(exc))
        except SignInThrottled as exc:
            return _Refusal(str(exc), status.HTTP_429_TOO_MANY_REQUESTS)
        caller = who.user_id
    # Signed in: the rest of the request acts for them (application/acting.py).
    act_as(caller)
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
        return _page(f"<h1>Can't connect</h1><p class=lede>{html.escape(str(exc))}</p>", 400)
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
    code: Annotated[str, Form(max_length=64)] = "",
    allow: Annotated[list[str] | None, Form()] = None,
):
    try:
        info = await svc.mcp_oauth.get_consent_info(rt, user_id="")
    except ConsentError as exc:
        return _page(f"<h1>Can't connect</h1><p class=lede>{html.escape(str(exc))}</p>", 400)
    dev = insecure_dev_auth(settings)

    def again(refusal: _Refusal) -> HTMLResponse:
        return _page(
            _form(rt, info, dev, refusal.message, kept=user_id if dev else email.strip()),
            refusal.status_code,
            title=_title(info),
        )

    approve = decision == "allow"
    if approve:
        who = await _signed_in(svc, settings, request, email, password, user_id, code)
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
        target = await svc.mcp_oauth.complete_consent(
            rt,
            caller,
            approve,
            password_checked=approve,
            allow_changes=_allowed(allow or []) if _offers_changes(info) else False,
        )
    except ConsentError as exc:
        return again(_Refusal(str(exc), status.HTTP_403_FORBIDDEN))
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


# Device sign-in (RFC 8628).

_DEVICE_TITLE = "Sign in a device"


def _device_form(
    user_code: str,
    dev: bool,
    error: str = "",
    client: str = "",
    ai: bool = False,
    kept: str = "",
) -> str:
    e = html.escape
    what = (
        f"<p class=lede>{e(client)} on another device is waiting to be signed in.</p>"
        if client
        else "<p class=lede>Enter the code your other device shows to sign it in.</p>"
    )
    return (
        "<h1>Sign in a device</h1>" + what + (_error(error) if error else "") + "<form method=post>"
        "<label for=user_code>Code</label>"
        f'<input id=user_code name=user_code value="{e(user_code)}" required '
        'autocomplete=off autocapitalize=characters spellcheck=false placeholder="ABCD-EFGH">'
        + _who(dev, autofocus=bool(user_code), kept=kept)
        + (_ALLOW_CHANGES if ai else "")
        + "<div class=row><button name=decision value=allow>Allow</button>"
        "<button name=decision value=deny formnovalidate>Deny</button></div>"
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
        _device_form(user_code, insecure_dev_auth(settings), client=client, ai=_is_ai(info)),
        title=_DEVICE_TITLE,
    )


def _is_ai(info: dict[str, Any] | None) -> bool:
    """A device code an AI client asked for (MCP): the page asks about changes."""
    return bool(info) and (info or {}).get("audience", "mcp") == "mcp"


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
    code: Annotated[str, Form(max_length=64)] = "",
    allow: Annotated[list[str] | None, Form()] = None,
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
            _device_form(
                user_code,
                dev,
                refusal.message,
                client=info["client_name"],
                ai=_is_ai(info),
                kept=user_id if dev else email.strip(),
            ),
            refusal.status_code,
            title=_DEVICE_TITLE,
        )

    approve = decision == "allow"
    caller = ""
    if approve:
        who = await _signed_in(svc, settings, request, email, password, user_id, code)
        if isinstance(who, _Refusal):
            return again(who)
        caller = who
        if info.get("audience", "mcp") == "mcp":
            await svc.mcp_oauth.set_mcp_enabled(caller, True)
    try:
        await svc.mcp_oauth.decide_device(
            user_code,
            caller,
            approve,
            allow_changes=_allowed(allow or []) if _is_ai(info) else False,
        )
    except ConsentError as exc:
        return again(_Refusal(str(exc)))
    if not approve:
        return _page(
            "<h1>Declined</h1><p class=lede>The device was not signed in.</p>", title=_DEVICE_TITLE
        )
    return _page(
        f"<div class=ok><span class=disc>{_ICON_TICK}</span><h1>Signed in</h1>"
        "<p class=lede>You can close this page and go back to your other device.</p></div>",
        title=_DEVICE_TITLE,
    )
