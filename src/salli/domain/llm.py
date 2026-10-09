"""
Language models, in Salli's words, whichever company runs one. Pure domain,
no I/O.

Lives in domain/ for the reason usage.py does: the agents (domain/agents) and
the services (application/) both name these tiers and errors, and the domain
must not import from application/.

Every error carries our own sentence for the user, never the provider's text:
an upstream message can quote the credential it rejected (see secrets.py), and
a person needs to be told what to do next, not what went wrong on the wire.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Literal

Provider = Literal["anthropic", "openai", "chatgpt"]
PROVIDERS: tuple[Provider, ...] = ("anthropic", "openai", "chatgpt")

#: What a user may choose: one provider, or "auto" (LlmCredentialService
#: documents the order auto goes in).
ProviderChoice = Literal["auto", "anthropic", "openai", "chatgpt"]
PROVIDER_CHOICES: tuple[ProviderChoice, ...] = ("auto", "anthropic", "openai", "chatgpt")

#: The kind of model a task needs. "fast": sorting statement rows, quick add,
#: naming a conversation. "best": the chat agent, the FIRE strategy, advice.
Tier = Literal["fast", "best"]

#: Who pays for a request's model: the user (their own API key, or their
#: ChatGPT plan), the platform (the deployment's own key), or nobody, because
#: there is nothing to run on.
Source = Literal["user", "platform", "none"]

PROVIDER_NAMES: dict[str, str] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "chatgpt": "ChatGPT",
}

#: Where a person reviews what Salli uses of their ChatGPT plan, and changes
#: the limit (OpenAI's UI/UX guidelines: "Manage usage" links here).
CHATGPT_USAGE_URL = "https://chatgpt.com/settings/usage"


class LLMError(Exception):
    """A model request that could not be served, said in words a person can act on.

    `code` is stable for clients to branch on; `status` is the HTTP status the
    API answers with; `link` is where the user can fix it, when there is one.
    """

    code = "ai_error"
    status = 502

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        link: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        self.message = message
        self.provider = provider
        self.link = link
        self.retry_after = retry_after
        super().__init__(message)

    def detail(self) -> dict[str, Any]:
        """What the API sends in a problem's `detail`, and the chat stream in
        its `error` event."""
        out: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.provider:
            out["provider"] = self.provider
        if self.link:
            out["link"] = self.link
        return out


class LLMNotConfigured(LLMError):
    """There is nothing to run on: no key of the user's, no ChatGPT plan, and
    no platform key."""

    code = "ai_not_configured"
    status = 503


class LLMSignInRequired(LLMError):
    """The ChatGPT connection needs the user to sign in again: its renewal was
    refused, it was disconnected in ChatGPT, or plan use was not allowed."""

    code = "ai_sign_in_required"
    status = 409


class LLMUsageLimit(LLMError):
    """The ChatGPT plan's usage limit for Salli was reached: the plan's own, or
    the one the user set for Salli in ChatGPT."""

    code = "chatgpt_usage_limit"
    status = 429


class LLMUsageUnavailable(LLMError):
    """ChatGPT could not check the plan's usage just now. Temporary."""

    code = "chatgpt_usage_unavailable"
    status = 503


class LLMNotEligible(LLMError):
    """ChatGPT plan use is not available to this account, workspace or region."""

    code = "chatgpt_not_eligible"
    status = 403


class LLMKeyRejected(LLMError):
    """The provider rejected the credential: an API key that was revoked or
    mistyped, or a ChatGPT sign-in it no longer accepts."""

    code = "ai_credential_rejected"
    status = 502


class LLMRateLimited(LLMError):
    """The provider is throttling this credential, or its account is out of credit."""

    code = "ai_rate_limited"
    status = 429


class LLMRequestRejected(LLMError):
    """The provider refused the request itself (a model the account cannot
    use, a field this route does not take). Retrying the same thing will not help."""

    code = "ai_request_rejected"
    status = 502


class LLMProviderUnavailable(LLMError):
    """The provider could not be reached, or failed on its side. Temporary."""

    code = "ai_provider_unavailable"
    status = 503


class LLMIncomplete(LLMError):
    """The answer stopped before the provider said it was complete. Only a
    completed response counts: a partial one is never used."""

    code = "ai_incomplete"
    status = 502


class LLMUnreadableAnswer(LLMError):
    """The model answered, but not in the shape it was asked for."""

    code = "ai_unreadable_answer"
    status = 502


def chatgpt_usage_limit(*, paused: bool = False) -> LLMUsageLimit:
    """The plan's usage limit for Salli was reached (OpenAI's guidelines: send
    the user to ChatGPT's usage settings, and do not guess when it resets).
    `paused`: Salli is holding new requests for a few minutes because of it."""
    message = (
        "You've reached the usage limit for Salli on your ChatGPT plan. It may be your "
        "plan's own limit, or the one set for Salli in ChatGPT. Review or change it in "
        f"ChatGPT settings, under Usage: {CHATGPT_USAGE_URL}."
    )
    if paused:
        message += " Salli is holding new requests on your plan for a few minutes."
    message += (
        " Salli won't switch to another way of paying on its own; you can choose a "
        "different AI provider in Salli's settings."
    )
    return LLMUsageLimit(message, provider="chatgpt", link=CHATGPT_USAGE_URL)


def parse_json_answer(text: str) -> Any:
    """The JSON value a model was asked for, read leniently: a model may still
    wrap it in a code fence or a sentence despite being told not to.

    Numbers with a fraction are read as Decimal, never float: some of these
    answers carry an amount (quick add), and a float anywhere in the money path
    is a bug. Raises LLMUnreadableAnswer when there is no JSON value at all.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    try:
        return json.loads(cleaned, parse_float=Decimal)
    except ValueError:
        pass
    decoder = json.JSONDecoder(parse_float=Decimal)
    for start, char in enumerate(cleaned):
        if char in "{[":
            try:
                value, _ = decoder.raw_decode(cleaned, start)
            except ValueError:
                continue
            return value
    raise LLMUnreadableAnswer(
        "The AI's answer could not be read. Please try again.",
    )
