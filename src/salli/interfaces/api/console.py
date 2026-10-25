"""
Serving the console: its built files at `/console`, with the headers that
keep a page of someone's ledger to itself (docs/design/console.md, sections 1
and 2; decisions 1, 7 and 23).

- **Paths.** `/console/assets/…` are the build's hashed files, served as
  files (404 when missing). Any other path under `/console` is a file of the
  build's when there is one (a favicon, the manifest), and otherwise the
  console's `index.html`, so a deep link (`/console/decisions/…`, the OAuth
  callback) opens the console at that page.
- **Nothing outside the build.** A path is resolved, symbolic links and all,
  and served only if it lands inside `SALLI_CONSOLE_DIR`; `..`, a dot file or
  directory, a backslash and a NUL are refused outright.
- **Caching.** `index.html` (and the other unhashed files) `no-cache`; hashed
  assets `public, max-age=31536000, immutable`, precompressed (`.br`, `.gz`
  beside them) when the browser accepts it.
- **Headers on every response,** a 404 included: a strict CSP with Trusted
  Types and no policy (so a sink like `innerHTML` throws), no framing, no
  referrer, no sniffing, and the browser features the console never uses
  switched off.
- **On and off.** `SALLI_CONSOLE=false`, or no built console, registers no
  route at all: `/console` is then what any unknown path is.

Every other response gets `Cache-Control: no-store` (`NoStoreMiddleware`)
unless it set its own; and every response, where SALLI_PUBLIC_URL is HTTPS,
`Strict-Transport-Security`.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response

from salli.config import Settings, console_index

#: The console's address under SALLI_PUBLIC_URL.
CONSOLE_PATH = "/console"

#: The CSP for every /console response (docs/design/console.md, section 2).
CONSOLE_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "font-src 'self'; connect-src 'self'; manifest-src 'self'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'; "
    "require-trusted-types-for 'script'; trusted-types 'none'"
)

#: What the browser may use on the console's pages: none of these.
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

CONSOLE_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CONSOLE_CSP,
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": PERMISSIONS_POLICY,
}

_NO_CACHE = "no-cache"
_IMMUTABLE = "public, max-age=31536000, immutable"

#: Types Python's table may lack or get wrong on some systems.
_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".webmanifest": "application/manifest+json",
    ".txt": "text/plain; charset=utf-8",
}

#: Precompressed copies the build writes beside a file, best first.
_ENCODINGS = (("br", ".br"), ("gzip", ".gz"))


def _content_type(path: Path) -> str:
    return _TYPES.get(path.suffix.lower()) or (
        mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    )


def is_unsafe(relative: str) -> bool:
    """Whether a path under /console tries to leave the build or reach a
    hidden file: `..`, `.` or empty segments, dot files, backslashes, NULs."""
    if "\x00" in relative or "\\" in relative:
        return True
    return any(part in ("", ".", "..") or part.startswith(".") for part in relative.split("/"))


def safe_path(root: Path, relative: str) -> Path | None:
    """The file `relative` names inside `root`, or None when it names
    nothing there or anything outside it (a symbolic link out included).
    `root` is already resolved."""
    if not relative or is_unsafe(relative):
        return None
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _not_found() -> Response:
    return PlainTextResponse("Not found", status_code=404, headers=CONSOLE_HEADERS)


def _serve(path: Path, request: Request, cache: str) -> Response:
    headers = {**CONSOLE_HEADERS, "Cache-Control": cache}
    media_type = _content_type(path)
    if cache == _IMMUTABLE:
        accepted = request.headers.get("accept-encoding", "").lower()
        headers["Vary"] = "Accept-Encoding"
        for encoding, suffix in _ENCODINGS:
            compressed = path.with_name(path.name + suffix)
            if encoding in accepted and compressed.is_file():
                headers["Content-Encoding"] = encoding
                return FileResponse(compressed, media_type=media_type, headers=headers)
    return FileResponse(path, media_type=media_type, headers=headers)


def console_router(settings: Settings) -> APIRouter | None:
    """The routes serving the console, or None when there is none to serve."""
    index = console_index(settings)
    if index is None:
        return None
    root = Path(settings.salli_console_dir).resolve()
    index_path = Path(index).resolve()

    async def console_home(request: Request) -> Response:
        return _serve(index_path, request, _NO_CACHE)

    async def console_page(path: str, request: Request) -> Response:
        page = path.rstrip("/")
        if not page:
            return _serve(index_path, request, _NO_CACHE)
        if is_unsafe(page):
            return _not_found()
        if page == "assets" or page.startswith("assets/"):
            found = safe_path(root, page)
            return _serve(found, request, _IMMUTABLE) if found else _not_found()
        found = safe_path(root, page)
        if found is not None:
            return _serve(found, request, _NO_CACHE)
        # Any other path is a page of the console's own: its router reads it.
        return _serve(index_path, request, _NO_CACHE)

    router = APIRouter()
    router.add_api_route(CONSOLE_PATH, console_home, methods=["GET", "HEAD"])
    router.add_api_route(CONSOLE_PATH + "/{path:path}", console_page, methods=["GET", "HEAD"])
    return router


#: A year of HTTPS only, once a browser has seen the server over HTTPS. Not
#: for subdomains: the operator's other sites are theirs to decide.
HSTS = (b"strict-transport-security", b"max-age=31536000")


class NoStoreMiddleware:
    """`Cache-Control: no-store` on every response that set none of its own,
    and, with `hsts` (SALLI_PUBLIC_URL is HTTPS), Strict-Transport-Security on
    every response. Pure ASGI, like RequestContextMiddleware, so streams pass
    through."""

    def __init__(self, app: Any, hsts: bool = False) -> None:
        self._app = app
        self._hsts = hsts

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        async def _send(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                if not any(name.lower() == b"cache-control" for name, _ in headers):
                    headers.append((b"cache-control", b"no-store"))
                if self._hsts:
                    headers.append(HSTS)
            await send(message)

        await self._app(scope, receive, _send)
