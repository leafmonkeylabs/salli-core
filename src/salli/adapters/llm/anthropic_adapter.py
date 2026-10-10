"""
The LLM port on Anthropic, with an API key: the platform's, or the user's own.

This is the behaviour Salli has always had, moved behind the port and otherwise
unchanged. Every model is a ChatAnthropic built by `model_factory.chat_model`,
the one place an Anthropic key is unwrapped; an answer with a shape uses
Anthropic tool use through `with_structured_output`; and the tiers are the
catalogue's (domain/ai_models.py), never spelled out again here.

Anthropic offers no sign-in with a Claude plan to apps like this one, and its
terms forbid using one through a third party, so this route is API keys only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from pydantic import BaseModel

from salli.application.ports import LLMClient
from salli.domain.ai_models import DEFAULT_MODEL, EXTRACTION_MODEL
from salli.domain.llm import Tier

# Values come from the catalogue rather than being spelled out again here.
# This table had already drifted from model_factory's constants once (it still
# named Sonnet 4.6 after the default moved), which is exactly the failure a
# second copy invites.
_MODEL_TIERS: dict[str, str] = {
    "fast": EXTRACTION_MODEL,
    "best": DEFAULT_MODEL,
}


def _text(content: Any) -> str:
    """A message's text, whether LangChain hands back a string or content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        blocks = cast(list[Any], content)
        return "".join(
            str(cast(dict[str, Any], block).get("text", ""))
            for block in blocks
            if isinstance(block, dict) and cast(dict[str, Any], block).get("type") == "text"
        )
    return ""


class AnthropicClient(LLMClient):
    """One per resolved key. Building one is two assignments, so callers make a
    fresh one per request rather than caching it (see LlmCredentialService)."""

    provider = "anthropic"

    def __init__(self, api_key: Any, *, source: str = "platform") -> None:
        self._api_key = api_key
        self.source = source

    @property
    def fingerprint(self) -> str:
        # The same fingerprint the agent cache has always used for a key, so
        # moving behind the port does not rebuild everyone's graphs.
        raw = (
            self._api_key.reveal() if hasattr(self._api_key, "reveal") else str(self._api_key or "")
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16] if raw else "none"

    def model_for(self, tier: Tier) -> str:
        return _MODEL_TIERS[tier]

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
        from langchain_core.messages import HumanMessage, SystemMessage

        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_output_tokens is not None:
            options["max_tokens"] = max_output_tokens
        llm = self.chat_model(model=model, tier=tier, **options)
        messages: list[Any] = [SystemMessage(content=instructions)] if instructions else []
        messages.append(HumanMessage(content=input))

        if schema is None:
            response = await llm.ainvoke(messages)
            return _text(response.content)
        # Tool use enforces the shape, as it always has; the caller parses the
        # JSON this hands back exactly as it parses any other provider's.
        result = await llm.with_structured_output(schema).ainvoke(messages)
        if isinstance(result, BaseModel):
            return result.model_dump_json()
        return json.dumps(result, default=str)

    def chat_model(
        self,
        *,
        model: str | None = None,
        tier: Tier = "best",
        cache: bool = False,
        **options: Any,
    ) -> Any:
        from salli.domain.agents.model_factory import chat_model

        return chat_model(
            api_key=self._api_key, model=model or self.model_for(tier), cache=cache, **options
        )
