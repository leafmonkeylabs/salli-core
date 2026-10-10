"""
Prompts that end with what the agents know about the user (jurisdiction.py).

The compiled graphs are shared: one per persona, day, credential and model,
so every user on the platform key runs the same graph. A prompt baked in at
build time could not say which country or currency *this* user has, so the
prompt is a function LangGraph calls before each model call instead. The
static text stays the same prefix for everyone, which keeps prompt caching
useful; the user's section goes after it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from salli.domain.agents.jurisdiction import UserContext, user_context


def dynamic_prompt(
    static: str, section: Callable[[UserContext], str]
) -> Callable[[Any], list[Any]]:
    """A LangGraph `prompt`: `static`, this run's section for the user, then
    the conversation."""

    def prompt(state: Any) -> list[Any]:
        from langchain_core.messages import SystemMessage

        text = f"{static}\n\n{section(user_context())}"
        return [SystemMessage(content=text), *_messages(state)]

    return prompt


def _messages(state: Any) -> list[Any]:
    """The conversation: a mapping from create_react_agent, an object from a
    custom state schema."""
    if isinstance(state, Mapping):
        return list(cast("Mapping[str, Any]", state).get("messages", []))
    return list(getattr(state, "messages", []))
