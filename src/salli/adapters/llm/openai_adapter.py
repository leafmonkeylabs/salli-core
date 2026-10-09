"""
The LLM port on OpenAI's Responses API: with the user's own OpenAI API key, or
with their ChatGPT plan (Sign in with ChatGPT plan usage).

Both routes send the same request (adapters/llm/responses.py) to the same
public endpoint, `POST https://api.openai.com/v1/responses`; they differ in
the bearer token (an API key; or the plan's OAuth access token, renewed as it
nears expiry) and in how function tools are grouped. The models come from the
account's own catalogue (`GET /v1/models`), chosen per tier when the request
is resolved (LlmCredentialService), so no model name is fixed here.

An answer with a shape is asked for in the instructions and read leniently by
the caller. The Responses API's structured-output setting is left alone: the
plan route's preview limitations do not name it, and a field a route might
reject is a failure every user on it would hit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from salli.adapters.llm.responses import (
    BearerSession,
    HttpFactory,
    ResponsesRoute,
    complete,
    request_body,
)
from salli.application.ports import LLMClient
from salli.domain.llm import Tier
from salli.domain.secrets import Secret


class ApiKeySession:
    """An API key as a bearer: nothing to renew, and no plan to pause."""

    def __init__(self, key: Secret) -> None:
        self._key = key

    async def bearer(self, force_refresh: bool = False) -> str:
        return self._key.reveal()

    async def usage_limited(self) -> None:
        return None


def key_fingerprint(provider: str, key: Secret) -> str:
    """Names a key without containing it, for the agent cache."""
    return f"{provider}:{hashlib.sha256(key.reveal().encode()).hexdigest()[:16]}"


def _schema_note(schema: dict[str, Any] | type[BaseModel]) -> str:
    json_schema = schema if isinstance(schema, dict) else schema.model_json_schema()
    return (
        "Answer with one JSON value that matches this JSON Schema, and nothing else: "
        "no prose, no code fences.\n" + json.dumps(json_schema, separators=(",", ":"))
    )


class OpenAIResponsesClient(LLMClient):
    """One per resolved credential and request."""

    def __init__(
        self,
        route: ResponsesRoute,
        session: BearerSession,
        *,
        models: Mapping[str, str],
        fingerprint: str,
        source: str = "user",
        http_factory: HttpFactory | None = None,
    ) -> None:
        self._route = route
        self._session = session
        self._models = dict(models)
        self._fingerprint = fingerprint
        self.provider = route.provider
        self.source = source
        self._http_factory = http_factory

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    @property
    def route(self) -> ResponsesRoute:
        return self._route

    def model_for(self, tier: Tier) -> str:
        return self._models[tier]

    async def generate(
        self,
        *,
        instructions: str,
        input: str,
        tier: Tier = "fast",
        model: str | None = None,
        schema: dict[str, Any] | type[BaseModel] | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        # `max_output_tokens` and `temperature` are deliberately dropped: the
        # plan route lists both as unsupported, and the reasoning models on the
        # API route reject `temperature`.
        if schema is not None:
            note = _schema_note(schema)
            instructions = f"{instructions}\n\n{note}" if instructions else note
        body = request_body(
            self._route,
            model=model or self.model_for(tier),
            instructions=instructions,
            items=[{"type": "message", "role": "user", "content": input}],
        )
        final = await complete(
            self._route, body, session=self._session, http_factory=self._http_factory
        )
        return final.text

    def chat_model(
        self,
        *,
        model: str | None = None,
        tier: Tier = "best",
        cache: bool = False,
        **options: Any,
    ) -> Any:
        # `cache`: OpenAI caches long prompt prefixes by itself, with no
        # request field to ask for it. `options` (Anthropic's temperature and
        # max_tokens) are not sent, for the reasons in `generate`.
        from salli.adapters.llm.responses_chat import ResponsesChatModel

        return ResponsesChatModel(
            route=self._route,
            model=model or self.model_for(tier),
            session=self._session,
            http_factory=self._http_factory,
        )
