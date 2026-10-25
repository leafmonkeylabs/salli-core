"""
The `Idempotency-Key` header on POST writes: sent again with the same key,
a write is not made twice, and the first answer comes back.

Kept in the same table as MCP's client_refs (`mcp_client_refs`), under the
tool `rest:<route name>`. The middleware holds a slot in the request's state
and keeps what the route answered; `deps.get_principal`, which knows who is
calling, claims the key before the route runs (`claim`).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from salli.application.services.ledger_service import CLIENT_REF_MAX

HEADER = "idempotency-key"
_SLOT = "idempotency"


class Replay(Exception):
    """A key already answered: its first answer, sent again."""

    def __init__(self, answer: dict[str, Any]) -> None:
        super().__init__()
        self.answer = answer


async def claim(request: Request, user_id: str, services: Any) -> None:
    """Claims the request's key for `user_id`, or raises Replay with what
    the first request with it answered (a 409 while it still runs)."""
    slot = request.scope.get("state", {}).get(_SLOT)
    if slot is None or "claimed" in slot:
        return
    uow_factory = services.ledger._uow_factory
    key = slot["key"]
    if not 0 < len(key) <= CLIENT_REF_MAX:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Idempotency-Key is 1 to {CLIENT_REF_MAX} characters",
        )
    route = request.scope.get("route")
    tool = f"rest:{getattr(route, 'name', request.url.path)}"[:50]
    async with uow_factory() as uow:
        done = await uow.client_refs.claim(user_id, tool, key)
    if done == {}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The request first sent with this Idempotency-Key is still running",
        )
    if done is not None:
        raise Replay(done)
    slot.update(claimed=(user_id, tool, key), uow_factory=uow_factory)


class IdempotencyMiddleware:
    """Keeps the answer of a POST sent with an Idempotency-Key that
    `claim` claimed: a success is settled, anything else released."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        key = dict(scope["headers"]).get(HEADER.encode())
        if key is None:
            await self.app(scope, receive, send)
            return
        slot: dict[str, Any] = {"key": key.decode("latin-1")}
        scope.setdefault("state", {})[_SLOT] = slot
        sent: dict[str, Any] = {"status": 500, "body": b""}

        async def keep(message: Message) -> None:
            if message["type"] == "http.response.start":
                sent["status"] = message["status"]
            elif message["type"] == "http.response.body":
                sent["body"] += message.get("body", b"")
            await send(message)

        try:
            await self.app(scope, receive, keep)
        finally:
            if "claimed" in slot:
                async with slot["uow_factory"]() as uow:
                    if 200 <= sent["status"] < 300:
                        try:
                            body = json.loads(sent["body"] or b"null")
                        except ValueError:
                            body = None
                        await uow.client_refs.settle(
                            *slot["claimed"], {"status": sent["status"], "body": body}
                        )
                    else:
                        await uow.client_refs.release(*slot["claimed"])
