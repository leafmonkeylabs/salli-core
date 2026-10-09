"""
Request correlation — the minimum that makes a user's bug report joinable to a
server-side failure.

Every response carries `X-Request-Id`, every unhandled exception is logged with
it, and the 500 body quotes it back so the user has something to paste into a
report. Without this an unhandled error returns a bare Starlette 500 with no body
at all, and there is nothing to correlate a complaint against.

Two implementation choices here are deliberate and easy to get wrong:

1. **Pure ASGI, not `BaseHTTPMiddleware`.** This app streams SSE from
   `/agent/chat` (with a `BackgroundTask`) and mounts FastMCP's streamable-HTTP
   app at "/". `BaseHTTPMiddleware` wraps the response in an anyio task group,
   which is the usual cause of buffered-SSE and background-task-ordering breakage.

2. **The exception is handled here, not by `@app.exception_handler(Exception)`.**
   A handler registered for `Exception` is consumed by Starlette's
   `ServerErrorMiddleware`, which sits *outside* every user middleware —
   including `CORSMiddleware` — and always re-raises. Its 500 response would
   therefore carry no `Access-Control-Allow-Origin`, the browser would discard
   it, and the client would report a generic network error instead of showing the
   user a quotable request id. Handling it inside a middleware that CORS wraps
   fixes that, and also means tests see a clean 500 rather than a raised
   exception.

Consequently this middleware MUST be registered before `CORSMiddleware` in
`create_app()`: `add_middleware` inserts at index 0, so the last-added middleware
ends up outermost.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

_request_id: ContextVar[str] = ContextVar("salli_request_id", default="")
_log = logging.getLogger("salli.request")

_HEADER = b"x-request-id"


def get_request_id() -> str:
    """The current request's correlation id, or "" outside a request."""
    return _request_id.get()


class RequestContextMiddleware:
    """Mints (or honours) a request id, exposes it, and logs unhandled errors."""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        rid = _incoming_id(scope) or str(uuid.uuid4())
        token = _request_id.set(rid)
        started = False

        async def _send(message: Any) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = message.setdefault("headers", [])
                headers.append((_HEADER, rid.encode("latin-1")))
            await send(message)

        try:
            await self._app(scope, receive, _send)
        except Exception:
            _log.exception(
                "unhandled_error method=%s path=%s request_id=%s",
                scope.get("method"),
                scope.get("path"),
                rid,
            )
            if started:
                # Headers are already on the wire (e.g. mid-SSE); there is no
                # response left to replace, so let it propagate.
                raise
            from fastapi.responses import JSONResponse

            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": rid},
                headers={"X-Request-Id": rid},
            )
            await response(scope, receive, send)
        finally:
            _request_id.reset(token)


def _incoming_id(scope: Any) -> str:
    """
    A client-supplied id, so a browser-side log line and the server-side line can
    share one key. Truncated because it is untrusted input that ends up in both a
    log line and a response header.
    """
    headers: list[tuple[bytes, bytes]] = scope.get("headers") or []
    for key, value in headers:
        if key == _HEADER:
            return value.decode("latin-1", errors="replace")[:36]
    return ""
