"""
A scripted stand-in for OpenAI, on httpx.MockTransport: no request leaves the
process. `POST /v1/responses` answers with the next scripted reply, as the
server-sent events the Responses API streams; `GET /v1/models` with a catalogue.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from salli.adapters.llm.openai_adapter import ApiKeySession, OpenAIResponsesClient
from salli.adapters.llm.responses import API_KEY_ROUTE, CHATGPT_ROUTE, ResponsesRoute
from salli.domain.secrets import Secret

Reply = bytes | httpx.Response | Callable[[dict[str, Any]], "bytes | httpx.Response"]


def sse(*events: dict[str, Any]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _completed(output: list[dict[str, Any]], model: str = "gpt-test") -> dict[str, Any]:
    return {
        "type": "response.completed",
        "response": {
            "id": "resp_1",
            "object": "response",
            "status": "completed",
            "model": model,
            "output": output,
            "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        },
    }


def text_reply(text: str, *, pieces: int = 2) -> bytes:
    """A streamed answer: `text` in a few deltas, then response.completed."""
    message = {
        "type": "message",
        "id": "msg_1",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    size = max(1, -(-len(text) // pieces))
    deltas = [text[i : i + size] for i in range(0, len(text), size)] or [""]
    return sse(
        {"type": "response.created", "response": {"id": "resp_1", "status": "in_progress"}},
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**message, "content": []},
        },
        *(
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "delta": d,
            }
            for d in deltas
        ),
        {"type": "response.output_item.done", "output_index": 0, "item": message},
        _completed([message]),
    )


def tool_reply(
    name: str, args: dict[str, Any], *, call_id: str = "call_1", namespace: str | None = None
) -> bytes:
    """A streamed function call, then response.completed."""
    item: dict[str, Any] = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(args),
        "status": "completed",
    }
    if namespace:
        item["namespace"] = namespace
    return sse(
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "arguments": ""},
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "fc_1",
            "output_index": 0,
            "delta": json.dumps(args),
        },
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        _completed([item]),
    )


def failed_after(text: str, code: str) -> bytes:
    """Some text streams, then the response fails with `code`: a usage limit
    can arrive this way, after streaming has begun."""
    return sse(
        {"type": "response.output_text.delta", "output_index": 0, "delta": text},
        {
            "type": "response.failed",
            "response": {
                "id": "resp_1",
                "status": "failed",
                "error": {"code": code, "message": "x"},
            },
        },
    )


CATALOGUE = {
    "models": [
        {"slug": "gpt-test-best", "display_name": "Best", "visibility": "list"},
        {"slug": "gpt-test-mini", "display_name": "Mini", "visibility": "list"},
    ]
}


class FakeOpenAI:
    """Answers each Responses request with the next reply in `replies`."""

    def __init__(self, *replies: Reply, models: dict[str, Any] | None = None) -> None:
        self.replies: list[Reply] = list(replies)
        self.models = models if models is not None else CATALOGUE
        self.requests: list[httpx.Request] = []

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path.endswith("/responses")]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx.Response(200, json=self.models)
        if not self.replies:
            raise AssertionError(f"FakeOpenAI has no reply left for {request.url}")
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(json.loads(request.content))
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=reply)

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def client(
        self,
        route: ResponsesRoute = CHATGPT_ROUTE,
        *,
        session: Any = None,
        models: dict[str, str] | None = None,
    ) -> OpenAIResponsesClient:
        return OpenAIResponsesClient(
            route,
            session or StaticSession(),
            models=models or {"fast": "gpt-test-mini", "best": "gpt-test-best"},
            fingerprint=f"{route.provider}:test",
            http_factory=self.http,
        )


class StaticSession:
    """A bearer that renews to a new token when asked, and records usage limits."""

    def __init__(self, token: str = "test-access-token") -> None:
        self.token = token
        self.renewals = 0
        self.limited = 0

    async def bearer(self, force_refresh: bool = False) -> str:
        if force_refresh:
            self.renewals += 1
            return f"{self.token}-renewed-{self.renewals}"
        return self.token

    async def usage_limited(self) -> None:
        self.limited += 1


def api_key_client(fake: FakeOpenAI, key: str = "sk-test-key") -> OpenAIResponsesClient:
    return fake.client(API_KEY_ROUTE, session=ApiKeySession(Secret(key)))


class FakeAuthServer:
    """auth.openai.com, enough of it: the token endpoint (rotating refresh
    tokens, as OpenAI's are: each one works once) and revocation."""

    def __init__(self, *, refresh_token: str = "refresh-1", delay: float = 0.0) -> None:
        self.valid_refresh = refresh_token
        self.delay = delay
        self.refreshes: list[dict[str, str]] = []
        self.revoked: list[dict[str, str]] = []
        self.revoke_status = 200
        #: Set to an OAuth error code to refuse every refresh with it.
        self.refuse_with: str | None = None
        self.fail_status: int | None = None
        self.grant_plan = True
        self.counter = 1

    async def handler(self, request: httpx.Request) -> httpx.Response:
        import asyncio
        from urllib.parse import parse_qsl

        form = dict(parse_qsl(request.content.decode()))
        if request.url.path.endswith("/oauth/revoke"):
            self.revoked.append(form)
            return httpx.Response(self.revoke_status)
        assert request.url.path.endswith("/oauth/token"), request.url
        if form.get("grant_type") != "refresh_token":
            raise AssertionError(f"unexpected grant {form.get('grant_type')}")
        self.refreshes.append(form)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_status:
            return httpx.Response(self.fail_status, json={"detail": "down"})
        if self.refuse_with:
            return httpx.Response(400, json={"error": self.refuse_with})
        if form.get("refresh_token") != self.valid_refresh:
            return httpx.Response(400, json={"error": "refresh_token_reused"})
        self.counter += 1
        self.valid_refresh = f"refresh-{self.counter}"
        scope = "openid profile email offline_access resource.invoke"
        if self.grant_plan:
            scope += " chatgpt.tokens.use.direct"
        return httpx.Response(
            200,
            json={
                "access_token": f"access-{self.counter}",
                "refresh_token": self.valid_refresh,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": scope,
            },
        )

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def oauth(self) -> Any:
        from salli.adapters.llm.chatgpt_oauth import ChatGPTOAuth

        async def no_sleep(_: float) -> None:
            return None

        return ChatGPTOAuth(self.http, sleep=no_sleep)
