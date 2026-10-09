"""
OpenAI's Responses API, as both OpenAI routes speak it: an OpenAI API key, and
a user's ChatGPT plan through Sign in with ChatGPT.

One request shape serves both, built to the stricter contract: the plan
route's preview limitations
(https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).
What that page asks for, and where it is honoured below:

- Every request sets `store: false` and `stream: true`, and sends `input` as an
  array: `request_body`.
- No `{type: "message", role: "system"}` item: the page says to use
  "`instructions` or developer messages". Leading system messages become
  `instructions`, any later one a developer message: `to_input`.
- None of the fields it lists as unsupported is ever sent (FORBIDDEN_FIELDS),
  nor `previous_response_id`: the history goes in `input` each time.
- Function tools are grouped "in namespaces" on the plan route: `_tools`.
- Only `response.completed` counts as success; `response.failed`,
  `response.incomplete`, an `error` event and a stream that just stops are all
  errors (models-and-inference): `ResponseState`.

The API-key route has none of these limits, but nothing Salli needs is lost by
keeping to them, and one shape is one thing to test. Its only difference is
that function tools stay at the top level, where every model takes them.

Errors become the typed ones in domain/llm.py, in our own words. The
provider's message is never passed on: it can quote the credential.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterable, Sequence
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

import httpx

from salli.domain.llm import (
    PROVIDER_NAMES,
    LLMError,
    LLMIncomplete,
    LLMKeyRejected,
    LLMNotEligible,
    LLMProviderUnavailable,
    LLMRateLimited,
    LLMRequestRejected,
    LLMSignInRequired,
    LLMUsageLimit,
    LLMUsageUnavailable,
    chatgpt_usage_limit,
)

_log = logging.getLogger(__name__)

OPENAI_API = "https://api.openai.com/v1"


@dataclass(frozen=True)
class ResponsesRoute:
    """How one route speaks the Responses API."""

    provider: Literal["openai", "chatgpt"]
    #: Function tools go inside one namespace of this name, when set.
    tool_namespace: str | None = None
    base_url: str = OPENAI_API


#: An OpenAI API key, the user's own.
API_KEY_ROUTE = ResponsesRoute("openai")

#: The user's ChatGPT plan. The preview page asks to "group function/custom
#: tools in namespaces", so Salli's tools go under one.
CHATGPT_ROUTE = ResponsesRoute("chatgpt", tool_namespace="salli")

_NAMESPACE_DESCRIPTION = (
    "Salli's tools: the user's own ledger, accounts, tax, plans, documents and memories."
)

#: Request fields the plan route rejects (preview-limitations, "Unsupported
#: fields"), plus `previous_response_id`, which it says to omit over HTTP.
#: Salli never sends any of them on either route.
FORBIDDEN_FIELDS = frozenset(
    {
        "background",
        "conversation",
        "max_output_tokens",
        "max_tool_calls",
        "metadata",
        "moderation",
        "multi_agent",
        "prompt",
        "prompt_cache_retention",
        "safety_identifier",
        "temperature",
        "top_logprobs",
        "top_p",
        "truncation",
        "user",
        "previous_response_id",
    }
)


class BearerSession(Protocol):
    """What a request is authorised with, and who hears about a usage limit."""

    async def bearer(self, force_refresh: bool = False) -> str:
        """The bearer token to send. `force_refresh` renews it first, once,
        after the provider answered 401 to the one it had."""
        ...

    async def usage_limited(self) -> None:
        """The plan's usage limit was reached: pause new requests on it."""
        ...


# ── The request ───────────────────────────────────────────────────────────────


def request_body(
    route: ResponsesRoute,
    *,
    model: str,
    instructions: str,
    items: Sequence[dict[str, Any]],
    tools: Sequence[dict[str, Any]] = (),
    tool_choice: Any = None,
    parallel_tool_calls: bool | None = None,
) -> dict[str, Any]:
    """The JSON body of one `POST /v1/responses`."""
    body: dict[str, Any] = {
        "model": model,
        "input": list(items),
        # models-and-inference: "Set store to false and stream to true on
        # each HTTP inference request in this flow."
        "store": False,
        "stream": True,
    }
    if instructions:
        body["instructions"] = instructions
    if tools:
        body["tools"] = _tools(route, tools)
        if parallel_tool_calls is not None:
            body["parallel_tool_calls"] = parallel_tool_calls
        if tool_choice is not None:
            body["tool_choice"] = _tool_choice(tool_choice)
    assert not FORBIDDEN_FIELDS & body.keys()
    return body


def _function(tool: dict[str, Any]) -> dict[str, Any]:
    """A function tool in the Responses shape, from either LangChain's (the
    Chat Completions shape, `{"type": "function", "function": {...}}`) or its own."""
    spec = cast(dict[str, Any], tool["function"]) if "function" in tool else tool
    out: dict[str, Any] = {"type": "function", "name": spec["name"]}
    if spec.get("description"):
        out["description"] = spec["description"]
    out["parameters"] = spec.get("parameters") or {"type": "object", "properties": {}}
    return out


def _tools(route: ResponsesRoute, tools: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    functions = [_function(tool) for tool in tools]
    if route.tool_namespace is None:
        return functions
    return [
        {
            "type": "namespace",
            "name": route.tool_namespace,
            "description": _NAMESPACE_DESCRIPTION,
            "tools": functions,
        }
    ]


def _tool_choice(choice: Any) -> Any:
    if choice in ("auto", "none", "required"):
        return choice
    if choice == "any":
        return "required"
    if isinstance(choice, str):
        return {"type": "function", "name": choice}
    return choice


# ── Messages → input ──────────────────────────────────────────────────────────


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in cast(list[Any], content):
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                entry = cast(dict[str, Any], block)
                if entry.get("type") in ("text", "output_text", "input_text"):
                    parts.append(str(entry.get("text", "")))
        return "".join(parts)
    return "" if content is None else str(content)


def _data_url(mime: str, data: str) -> str:
    return f"data:{mime};base64,{data}"


def _user_part(block: Any) -> dict[str, Any] | None:
    """One block of a user message as a Responses input part. Images and files
    go as data URLs ("Text, images, and files are supported when the selected
    model accepts them"); anything else is left out rather than guessed at."""
    if isinstance(block, str):
        return {"type": "input_text", "text": block}
    if not isinstance(block, dict):
        return None
    entry = cast(dict[str, Any], block)
    kind = entry.get("type")
    if kind in ("text", "input_text"):
        return {"type": "input_text", "text": str(entry.get("text", ""))}
    if kind == "image_url":
        url: Any = entry.get("image_url")
        if isinstance(url, dict):
            url = cast(dict[str, Any], url).get("url")
        return {"type": "input_image", "image_url": str(url)} if url else None
    # Anthropic-shaped blocks, which the chat agent builds for attachments:
    # {"type": "document" | "image", "source": {"type": "base64", ...}}.
    source = entry.get("source")
    if isinstance(source, dict) and cast(dict[str, Any], source).get("type") == "base64":
        src = cast(dict[str, Any], source)
        mime, data = str(src.get("media_type", "")), str(src.get("data", ""))
    elif "base64" in entry:
        mime, data = str(entry.get("mime_type", "")), str(entry["base64"])
    else:
        return None
    if mime.startswith("image/"):
        return {"type": "input_image", "image_url": _data_url(mime, data)}
    return {
        "type": "input_file",
        "filename": str(entry.get("title") or entry.get("filename") or "attachment"),
        "file_data": _data_url(mime or "application/octet-stream", data),
    }


def _user_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p for p in (_user_part(b) for b in cast(list[Any], content)) if p is not None]
        return parts or ""
    return _text(content)


def _tool_output(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return _text(content)
    return json.dumps(content, default=str)


def to_input(messages: Iterable[Any], route: ResponsesRoute) -> tuple[str, list[dict[str, Any]]]:
    """LangChain messages as (`instructions`, `input` items).

    The system messages before the conversation (an agent's prompt) become
    `instructions`; one later on (the chat agent's tone note) becomes a
    developer message. Never a system-role item, which the plan route rejects.
    History is sent whole every time, because nothing is stored with OpenAI.
    """
    instructions: list[str] = []
    items: list[dict[str, Any]] = []
    for message in messages:
        kind = str(getattr(message, "type", ""))
        if kind == "chat":
            # A ChatMessage carries its role instead of a type.
            kind = {"assistant": "ai", "user": "human"}.get(
                str(getattr(message, "role", "")), str(getattr(message, "role", ""))
            )
        content = getattr(message, "content", "")
        if kind in ("system", "developer"):
            text = _text(content)
            if not items:
                if text:
                    instructions.append(text)
            elif text:
                items.append({"type": "message", "role": "developer", "content": text})
        elif kind in ("human", "user"):
            items.append({"type": "message", "role": "user", "content": _user_content(content)})
        elif kind in ("ai", "AIMessageChunk"):
            text = _text(content)
            if text:
                items.append({"type": "message", "role": "assistant", "content": text})
            for call in cast(list[dict[str, Any]], getattr(message, "tool_calls", None) or []):
                item: dict[str, Any] = {
                    "type": "function_call",
                    "call_id": str(call.get("id") or ""),
                    "name": str(call["name"]),
                    "arguments": json.dumps(call.get("args") or {}),
                }
                if route.tool_namespace:
                    item["namespace"] = route.tool_namespace
                items.append(item)
        elif kind == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": str(getattr(message, "tool_call_id", "") or ""),
                    "output": _tool_output(content),
                }
            )
    return "\n\n".join(instructions), items


# ── The stream ────────────────────────────────────────────────────────────────


async def sse_events(lines: AsyncIterator[str]) -> AsyncGenerator[dict[str, Any], None]:
    """Server-sent events as the JSON objects they carry. Every Responses event
    names its own `type` in its data, so the `event:` field is not needed."""
    data: list[str] = []

    def flush() -> dict[str, Any] | None:
        payload = "\n".join(data).strip()
        data.clear()
        if not payload or payload == "[DONE]":
            return None
        try:
            parsed = json.loads(payload)
        except ValueError:
            _log.warning("Skipped an unreadable event in a Responses stream")
            return None
        return cast(dict[str, Any], parsed) if isinstance(parsed, dict) else None

    async for line in lines:
        if line == "":
            event = flush()
            if event is not None:
                yield event
        elif line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
    event = flush()
    if event is not None:
        yield event


@dataclass
class FunctionCall:
    call_id: str
    name: str
    arguments: str


@dataclass
class FinalResponse:
    """A response OpenAI said was complete."""

    text: str
    calls: list[FunctionCall]
    usage: dict[str, Any] | None
    response_id: str | None
    model: str | None


@dataclass
class ResponseState:
    """What a stream has said so far. Only `response.completed` makes it final."""

    provider: str
    namespace: str | None = None
    deltas: list[str] = field(default_factory=list[str])
    done_items: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    response: dict[str, Any] | None = None

    @property
    def completed(self) -> bool:
        return self.response is not None

    def apply(self, event: dict[str, Any]) -> str | None:
        """Take in one event; return text to stream on, if it carried some.
        Raises the typed error a failure maps to."""
        kind = event.get("type")
        if kind == "response.output_text.delta":
            delta = str(event.get("delta") or "")
            self.deltas.append(delta)
            return delta or None
        if kind == "response.output_item.done":
            item = event.get("item")
            if isinstance(item, dict):
                self.done_items.append(cast(dict[str, Any], item))
        elif kind == "response.completed":
            response = event.get("response")
            self.response = cast(dict[str, Any], response) if isinstance(response, dict) else {}
        elif kind == "response.failed":
            # A usage limit can arrive here after streaming has begun
            # (models-and-inference, "Wait for completed inference").
            response = cast(dict[str, Any], event.get("response") or {})
            error = cast(dict[str, Any], response.get("error") or {})
            raise error_for(
                self.provider,
                status=None,
                code=_str_or_none(error.get("code")),
                param=_str_or_none(error.get("param")),
            )
        elif kind == "response.incomplete":
            response = cast(dict[str, Any], event.get("response") or {})
            details = cast(dict[str, Any], response.get("incomplete_details") or {})
            reason = str(details.get("reason") or "")
            raise LLMIncomplete(
                "The AI stopped before finishing its answer"
                + (" (it ran out of room)" if reason == "max_output_tokens" else "")
                + ". Please try again.",
                provider=self.provider,
            )
        elif kind == "error":
            raise error_for(
                self.provider,
                status=None,
                code=_str_or_none(event.get("code")),
                param=_str_or_none(event.get("param")),
            )
        return None

    def finish(self) -> FinalResponse:
        """The complete answer. LLMIncomplete when the stream ended without
        `response.completed`: an answer is never used on less."""
        if self.response is None:
            raise LLMIncomplete(
                "The connection ended before the AI finished its answer. Please try again.",
                provider=self.provider,
            )
        output = self.response.get("output")
        items = cast(list[Any], output) if isinstance(output, list) and output else self.done_items
        text_parts: list[str] = []
        calls: list[FunctionCall] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = cast(dict[str, Any], raw)
            if item.get("type") == "message":
                for part in cast(list[Any], item.get("content") or []):
                    if not isinstance(part, dict):
                        continue
                    piece = cast(dict[str, Any], part)
                    if piece.get("type") == "output_text":
                        text_parts.append(str(piece.get("text", "")))
                    elif piece.get("type") == "refusal":
                        text_parts.append(str(piece.get("refusal", "")))
            elif item.get("type") == "function_call":
                calls.append(
                    FunctionCall(
                        call_id=str(item.get("call_id") or item.get("id") or ""),
                        name=_bare_name(str(item.get("name", "")), self.namespace),
                        arguments=str(item.get("arguments") or "{}"),
                    )
                )
        text = "".join(text_parts) if text_parts else "".join(self.deltas)
        usage = self.response.get("usage")
        return FinalResponse(
            text=text,
            calls=calls,
            usage=cast(dict[str, Any], usage) if isinstance(usage, dict) else None,
            response_id=_str_or_none(self.response.get("id")),
            model=_str_or_none(self.response.get("model")),
        )


def _bare_name(name: str, namespace: str | None) -> str:
    """A namespaced call's function name. The call names its namespace in its
    own field, but a name that also carries it is read either way."""
    if namespace:
        for sep in (".", "__", "/"):
            prefix = f"{namespace}{sep}"
            if name.startswith(prefix):
                return name[len(prefix) :]
    return name


def _str_or_none(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


# ── Errors ────────────────────────────────────────────────────────────────────


def error_for(
    provider: str, *, status: int | None, code: str | None, param: str | None = None
) -> LLMError:
    """The typed error for a failed request: by OpenAI's machine-readable code
    where there is one (errors-and-recovery, "Structured Responses errors"),
    else by HTTP status ("Before a stream opens": a body like `{"detail": ...}`
    is diagnostic text, not a code, and is not read)."""
    name = PROVIDER_NAMES.get(provider, provider)
    plan = provider == "chatgpt"
    if code == "subscription_sharing_usage_limit_exceeded":
        return chatgpt_usage_limit()
    if code in ("subscription_sharing_usage_unavailable", "subscription_sharing_user_unavailable"):
        return LLMUsageUnavailable(
            "ChatGPT couldn't check your plan's usage just now. Please try again in a few minutes.",
            provider=provider,
            retry_after=60,
        )
    if code == "subscription_sharing_user_not_eligible":
        return LLMNotEligible(
            "Your ChatGPT account or workspace can't use its plan in Salli. Choose another "
            "AI provider in Salli's settings, such as your own API key.",
            provider=provider,
        )
    if code in ("chatpass_v2_scope_not_authorized", "chatpass_v2_invalid_authorization_context"):
        return LLMSignInRequired(
            "ChatGPT didn't allow Salli to use your plan for this. Sign in with ChatGPT "
            "again and allow plan use.",
            provider=provider,
        )
    if code in (
        "subscription_sharing_unsupported_capability",
        "subscription_sharing_route_not_supported",
    ):
        return LLMRequestRejected(
            "ChatGPT plan use doesn't support part of this request"
            + (f" ({param})" if param else "")
            + ".",
            provider=provider,
        )
    if code == "model_not_found" or status == 404:
        return LLMRequestRejected(
            f"That model isn't available to your {name} account. Choose another in "
            "Salli's AI settings.",
            provider=provider,
        )
    if code == "subscription_sharing_invalid_user" or status == 401:
        return LLMKeyRejected(
            "ChatGPT didn't accept your sign-in. Sign in with ChatGPT again."
            if plan
            else "OpenAI rejected your API key. Check it in Salli's settings.",
            provider=provider,
        )
    if status == 403:
        return (
            LLMNotEligible(
                "ChatGPT plan use isn't available here (your region, or a policy on your "
                "account). Choose another AI provider in Salli's settings.",
                provider=provider,
            )
            if plan
            else LLMKeyRejected(
                "OpenAI refused this request for your API key. Check the key's project "
                "permissions.",
                provider=provider,
            )
        )
    if code == "insufficient_quota":
        return LLMRateLimited(
            "Your OpenAI account is out of credit for this API key.", provider=provider
        )
    if status == 429 or code == "rate_limit_exceeded":
        return LLMRateLimited(
            f"{name} is limiting requests right now. Please try again shortly.",
            provider=provider,
            retry_after=30,
        )
    if status is not None and 400 <= status < 500:
        return LLMRequestRejected(f"{name} refused the request.", provider=provider)
    if status is None and code not in (None, "server_error"):
        return LLMIncomplete(
            "The AI stopped before finishing its answer. Please try again.", provider=provider
        )
    return LLMProviderUnavailable(
        f"{name} isn't answering right now. Please try again in a moment.",
        provider=provider,
        retry_after=30,
    )


def _error_from_body(provider: str, status: int, raw: bytes) -> LLMError:
    code: str | None = None
    param: str | None = None
    try:
        body: Any = json.loads(raw) if raw else None
    except ValueError:
        body = None
    if isinstance(body, dict):
        error: Any = cast(dict[str, Any], body).get("error")
        if isinstance(error, dict):
            err = cast(dict[str, Any], error)
            code = _str_or_none(err.get("code")) or _str_or_none(err.get("type"))
            param = _str_or_none(err.get("param"))
        elif isinstance(error, str):
            code = error
    return error_for(provider, status=status, code=code, param=param)


# ── Sending it ────────────────────────────────────────────────────────────────

HttpFactory = Callable[[], httpx.AsyncClient]

#: Seconds before each retry of a temporary failure, before a stream opens
#: (errors-and-recovery: "use bounded backoff for temporary failures").
_BACKOFF = (0.5, 2.0)


def default_http() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0))


@asynccontextmanager
async def _client(factory: HttpFactory | None) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with (factory or default_http)() as client:
        yield client


async def _events(
    route: ResponsesRoute,
    body: dict[str, Any],
    *,
    session: BearerSession,
    http: httpx.AsyncClient,
    sleep: Callable[[float], Awaitable[None]],
) -> AsyncGenerator[dict[str, Any], None]:
    url = f"{route.base_url}/responses"
    renewed = False
    retries = 0
    while True:
        token = await session.bearer(renewed)
        request = http.build_request(
            "POST",
            url,
            json=body,
            headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
        )
        try:
            response = await http.send(request, stream=True)
        except httpx.HTTPError:
            raise LLMProviderUnavailable(
                f"Couldn't reach {PROVIDER_NAMES[route.provider]}. Please try again in a moment.",
                provider=route.provider,
            ) from None
        try:
            if response.status_code >= 400:
                error = _error_from_body(
                    route.provider, response.status_code, await response.aread()
                )
                # Kept for diagnosis (errors-and-recovery: preserve the status,
                # the code and the request id), never the body's own text.
                _log.warning(
                    "Responses request failed: %s %s (request id %s)",
                    response.status_code,
                    error.code,
                    response.headers.get("x-request-id")
                    or response.headers.get("openai-request-id")
                    or "-",
                )
                if response.status_code == 401 and route.provider == "chatgpt" and not renewed:
                    # A token can lapse early; renew it once and try again
                    # before telling anyone to sign in.
                    renewed = True
                    continue
                if (
                    response.status_code in (502, 503, 504)
                    and isinstance(error, (LLMProviderUnavailable, LLMUsageUnavailable))
                    and retries < len(_BACKOFF)
                ):
                    await sleep(_BACKOFF[retries])
                    retries += 1
                    continue
                raise error
            try:
                async for event in sse_events(response.aiter_lines()):
                    yield event
            except httpx.HTTPError:
                raise LLMIncomplete(
                    "The connection dropped before the AI finished its answer. Please try again.",
                    provider=route.provider,
                ) from None
            return
        finally:
            await response.aclose()


async def stream_response(
    route: ResponsesRoute,
    body: dict[str, Any],
    *,
    session: BearerSession,
    http_factory: HttpFactory | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncGenerator[tuple[str, Any], None]:
    """Run one request: ("delta", text) while it streams, then ("final",
    FinalResponse) once OpenAI says it is complete. Raises a typed LLMError
    otherwise, and tells the session first when the plan's limit was reached,
    so it pauses new requests ("Pause new requests that use the user's ChatGPT
    plan", errors-and-recovery)."""
    state = ResponseState(route.provider, route.tool_namespace)
    try:
        async with (
            _client(http_factory) as http,
            aclosing(_events(route, body, session=session, http=http, sleep=sleep)) as events,
        ):
            async for event in events:
                delta = state.apply(event)
                if delta:
                    yield ("delta", delta)
                if state.completed:
                    break
        yield ("final", state.finish())
    except LLMUsageLimit:
        await session.usage_limited()
        raise


async def complete(
    route: ResponsesRoute,
    body: dict[str, Any],
    *,
    session: BearerSession,
    http_factory: HttpFactory | None = None,
) -> FinalResponse:
    """Run one request to its completed response."""
    async with aclosing(
        stream_response(route, body, session=session, http_factory=http_factory)
    ) as events:
        async for kind, value in events:
            if kind == "final":
                return cast(FinalResponse, value)
    raise LLMIncomplete("The AI's answer never completed. Please try again.")
