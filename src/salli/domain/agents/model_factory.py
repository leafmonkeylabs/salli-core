"""
The one place a chat model is constructed, and therefore the one place an API
key is unwrapped.

Every agent, worker, and one-shot LLM call goes through `chat_model()`. That
matters for two reasons:

1. `Secret.reveal()` is called here and nowhere else, so "where can a key
   escape?" has a single, greppable answer.
2. `api_key` is a required keyword argument with no default. Any call site that
   forgets it raises TypeError immediately, rather than falling through to
   ChatAnthropic's own `ANTHROPIC_API_KEY` environment lookup and silently
   running on the instance's key for a user who was supposed to be on their own.
   That fail-loud property is the whole point — it is why composition.py no
   longer seeds that environment variable.
"""

from __future__ import annotations

from typing import Any

from salli.domain.ai_models import DEFAULT_MODEL, EXTRACTION_MODEL

# Re-exported from the catalogue so there is one list of models in the codebase
# rather than three; the values come from `domain.ai_models` alongside their
# relative costs, so a model and its price cannot drift apart.
#
# This constant was called SONNET until conversations were pinned to the
# cheapest model. It is an alias for whatever DEFAULT_MODEL is, and naming it
# after one particular model made it a lie the moment that changed — the six
# agent modules that default to it would have read as "runs on Sonnet" while
# running on Haiku.
CONVERSATION_MODEL = DEFAULT_MODEL
HAIKU = EXTRACTION_MODEL


def reveal(api_key: Any) -> str:
    """Accept a `Secret` or a plain string, return the raw key.

    Tolerates both so callers that already hold a plain string (the CLI, tests)
    don't have to wrap it, while the request path keeps its key wrapped right up
    to this boundary.
    """
    revealed = api_key.reveal() if hasattr(api_key, "reveal") else api_key
    if not revealed:
        raise ValueError(
            "No Anthropic API key available for this request. Either the user's "
            "own key could not be resolved or no platform key is configured."
        )
    return str(revealed)


def chat_model(
    *, api_key: Any, model: str = CONVERSATION_MODEL, cache: bool = False, **kwargs: Any
) -> Any:
    """Build a ChatAnthropic bound to exactly this key.

    `cache` turns on Anthropic's automatic prompt caching by putting a
    top-level `cache_control` on the request, which caches the longest stable
    prefix it can find: the system prompt and the tool schemas. For the
    conversational agents that prefix is around 3,600 tokens, resent on every
    one of the several round trips a single turn makes, so caching it is the
    largest cost lever the app has. Cache reads bill at about a tenth of input.

    It is opt-in rather than the default because a cache *write* costs 1.25x.
    That pays for itself the moment the prefix is read again, which inside one
    agent turn is guaranteed. On a one-shot call with a small prompt it is
    simply a 25% surcharge on something nobody reads back, so those call sites
    leave it off until volume makes the five-minute window worth betting on.

    Two things to watch, neither of which can be asserted from here:
    the minimum cacheable prefix is model dependent (roughly 512 to 4096
    tokens), so a short prompt may silently never cache; and any volatile byte
    in the prefix invalidates it. `usage.cache_read_input_tokens` is the only
    proof it is working. See UNIT_ECONOMICS.md.
    """
    from langchain_anthropic import ChatAnthropic

    if cache:
        # Merged, not assigned: a caller may already be passing model_kwargs,
        # and clobbering it here would drop whatever they set.
        kwargs["model_kwargs"] = {
            **kwargs.get("model_kwargs", {}),
            "cache_control": {"type": "ephemeral"},
        }

    return ChatAnthropic(model=model, api_key=reveal(api_key), **kwargs)
