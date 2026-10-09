"""
LLMPort adapter — wraps Anthropic via LangChain.

This is the single point through which the domain touches the LLM.
Tiering: fast → haiku-class; strong → sonnet-class.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from salli.application.ports import LLMPort
from salli.domain.ai_models import DEFAULT_MODEL, EXTRACTION_MODEL

# Values come from the catalogue rather than being spelled out again here.
# This table had already drifted from model_factory's constants — it still named
# Sonnet 4.6 after the default moved — which is exactly the failure a second
# copy invites.
_MODEL_TIERS = {
    "fast": EXTRACTION_MODEL,
    "strong": DEFAULT_MODEL,
}


class AnthropicLLMAdapter(LLMPort):
    """One instance per resolved credential.

    The key stays on the constructor rather than moving onto
    `LLMPort.extract_structured`: the port exists so the domain never has to know
    which provider is behind it, and a provider credential in its signature would
    leak that back out and oblige every future implementation to pretend it has
    an Anthropic key. Constructing one is two field assignments, so callers build
    a fresh adapter per request instead (see EntryParseService).
    """

    def __init__(self, api_key: Any, langsmith_project: str | None = None) -> None:
        self._api_key = api_key
        self._langsmith_project = langsmith_project

    def _get_model(self, tier: str = "fast"):
        from salli.domain.agents.model_factory import chat_model

        model_id = _MODEL_TIERS.get(tier, _MODEL_TIERS["fast"])
        return chat_model(api_key=self._api_key, model=model_id, temperature=0)

    async def extract_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        model_tier: str = "fast",
    ) -> dict[str, Any]:
        """
        Run structured extraction using Claude tool-use / with_structured_output.
        The JSON schema is enforced by the model — malformed output triggers a retry.
        """
        from langchain_core.prompts import ChatPromptTemplate

        model = self._get_model(model_tier)
        structured = model.with_structured_output(schema)

        prompt_template = ChatPromptTemplate.from_template("{input}")
        chain = prompt_template | structured
        result = await chain.ainvoke({"input": prompt})
        return result  # type: ignore[return-value]

    async def stream_agent(
        self,
        thread_id: str,
        user_message: str,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Not used directly — the agent graph handles streaming via LangGraph."""
        raise NotImplementedError("Use the agent graph directly for streaming")
