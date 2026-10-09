"""
LlmCredentialService — decides what a request's AI runs on, and who pays.

The single choke point for that decision. Every LLM path (agent chat, statement
classification, quick-add parsing, the FIRE strategy, advisor runs) resolves
here by user id, so the HTTP routes and the MCP server — which reaches the same
services with a user id off its OAuth token — cannot diverge.

What it can run on: the user's own Anthropic or OpenAI API key, the user's
ChatGPT plan (ChatGPTConnectionService), or the deployment's Anthropic key.
The user's setting picks one: "auto", "anthropic", "openai" or "chatgpt".

"auto" prefers what the user brought over the platform's key, in this order:

1. Their ChatGPT plan, when it is connected. It is a flat price they already
   pay, so using it costs them nothing more per request, where both kinds of
   API key bill every token; and connecting it is a deliberate act that only
   makes sense if they want it used. A plan they signed in to but did not
   allow Salli to use is not picked.
2. Their own Anthropic key. Between the two pay-per-use keys, Claude is what
   Salli's prompts and tools are written and tested against, and someone who
   already brought one keeps what they had when they add an OpenAI key.
3. Their own OpenAI key.
4. The platform's Anthropic key, when the user brought nothing.

Whatever is chosen is what runs. A chosen ChatGPT plan that needs signing in
again, or has hit its usage limit, is an error that says so: Salli never moves
to another way of paying on its own, which is also how OpenAI treats a plan
usage error on its side (errors-and-recovery: an error stops the request; it
is never quietly charged elsewhere).

On the OpenAI routes, each tier ("fast", "best") gets a model from the
account's own catalogue (`GET /v1/models`, cached per user for a while), or
the one the user chose (domain/model_choice.py). Anthropic's are the catalogue's.

Plaintext keys leave this module only as `Secret` (see domain/secrets.py), so a
key cannot reach a log line, an SSE frame, or an exception message by accident.
Reading one is a deliberate `.reveal()` at the point the provider client is
constructed.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from salli.application.ports import LLMClient
from salli.domain.llm import (
    PROVIDER_CHOICES,
    LLMError,
    LLMNotConfigured,
    LLMNotEligible,
    Tier,
)
from salli.domain.model_choice import CatalogModel, api_catalogue, choose, plan_catalogue
from salli.domain.secrets import Secret

_log = logging.getLogger(__name__)

#: The providers a user may store an API key for. (A ChatGPT plan is signed
#: in to instead: ChatGPTConnectionService.)
PROVIDERS = ("anthropic", "openai")

#: How long an account's model catalogue is reused before it is fetched again.
_CATALOGUE_TTL = 30 * 60.0
_CATALOGUE_MAX = 1024


@dataclass(frozen=True)
class ResolvedCredentials:
    """What this request's AI runs on, and whose it is.

    Immutable and resolved once per request: the usage meter runs before the
    stream opens, so it has to see the same answer the LLM call will later act
    on. Resolving twice invites the two to disagree.

    `llm` is the provider-neutral client every AI feature runs on (None when
    there is nothing to run on). Built from the Anthropic key when not given,
    so code that only knows about that key keeps working unchanged.
    `provider` says which provider that is, `source` who pays: "user" (their
    own key or plan), "platform" (the deployment's key) or "none".
    """

    anthropic: Secret
    anthropic_is_user_key: bool
    llm: LLMClient | None = None
    provider: str = "anthropic"
    source: str = ""

    def __post_init__(self) -> None:
        if not self.source:
            source = (
                "user" if self.anthropic_is_user_key else "platform" if self.anthropic else "none"
            )
            object.__setattr__(self, "source", source)
        if self.llm is None and self.anthropic and self.provider == "anthropic":
            from salli.adapters.llm.anthropic_adapter import AnthropicClient

            object.__setattr__(self, "llm", AnthropicClient(self.anthropic, source=self.source))

    @property
    def byok(self) -> bool:
        """Whether AI usage metering should be lifted: the user's own key or
        ChatGPT plan pays for this request, not the platform."""
        return self.source == "user"

    def model_for(self, tier: Tier) -> str | None:
        """The model a tier runs on for this request (None: nothing to run on)."""
        return self.llm.model_for(tier) if self.llm is not None else None


@dataclass(frozen=True)
class Route:
    """Which provider a user's AI runs on and who pays, decided from what is
    stored: no decryption, no network."""

    #: The user's setting: "auto", "anthropic", "openai" or "chatgpt".
    choice: str
    provider: str
    source: str


def _chosen(settings: dict[str, Any], provider: str) -> dict[str, Any]:
    """The models a user named for one provider, by tier."""
    models: dict[str, Any] = settings.get("models") or {}
    return dict(models.get(provider) or {})


def as_llm(credential: Any) -> LLMClient | None:
    """An already-resolved credential as an LLMClient: a client as it is, an
    Anthropic key (a Secret or a string) wrapped as one, and nothing (None, or
    an empty key) as None.

    Callers that resolved at a boundary (an HTTP route, a test) hand either
    kind down; the services take both, so neither has to know which it got.
    """
    if credential is None:
        return None
    from salli.domain.agents.model_factory import is_llm_client

    if isinstance(credential, LLMClient) or is_llm_client(credential):
        return credential
    if not credential:
        return None
    from salli.adapters.llm.anthropic_adapter import AnthropicClient

    return AnthropicClient(credential)


class LlmCredentialService:
    def __init__(
        self,
        uow_factory: Any,
        keyring: Any,
        *,
        platform_anthropic_key: str = "",
        validator: Any = None,
        feature_enabled: bool = True,
        chatgpt: Any = None,
        http_factory: Any = None,
        plan_allowed: Callable[[str], Awaitable[bool]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._uow_factory = uow_factory
        self._keyring = keyring
        self._platform_anthropic = platform_anthropic_key
        self._validator = validator
        self._feature_enabled = feature_enabled
        # ChatGPTConnectionService: the user's ChatGPT plan, when connected.
        self._chatgpt = chatgpt
        # Makes the httpx client OpenAI requests go through (tests: a MockTransport).
        self._http_factory = http_factory
        # Whether this deployment lets a user's ChatGPT plan be used at all.
        self._plan_allowed = plan_allowed
        self._clock = clock
        self._catalogues: dict[tuple[str, str, str], tuple[float, list[CatalogModel]]] = {}

    @property
    def available(self) -> bool:
        """Whether users may supply their own keys at all.

        False when no encryption key is configured (storing plaintext is not an
        acceptable fallback) or when the deployment fails the safety checks
        composed in composition.py — notably the dev-auth fallback, where any
        bearer token is accepted as a user id and BYOK would therefore let a
        caller spend an arbitrary user's key.
        """
        return bool(self._feature_enabled and self._keyring.available)

    # ── Deciding ──────────────────────────────────────────────────────────────

    async def _state(self, user_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """The user's AI settings and their stored key rows (still sealed)."""
        try:
            async with self._uow_factory() as uow:
                settings: dict[str, Any] = await uow.user_profiles.get_ai_settings(user_id)
                rows: list[dict[str, Any]] = (
                    await uow.llm_credentials.list_for_user(user_id) if self.available else []
                )
        except Exception:
            _log.exception("Could not read a user's AI settings or stored keys")
            return {"provider": None, "models": {}}, []
        return settings, rows

    async def _plan_present(self, user_id: str) -> str | None:
        if self._chatgpt is None:
            return None
        return await self._chatgpt.presence(user_id)

    def _route_from(
        self, settings: dict[str, Any], rows: list[dict[str, Any]], plan: str | None
    ) -> Route:
        choice = str(settings.get("provider") or "auto")
        stored = {str(row["provider"]) for row in rows}
        platform = "platform" if self._platform_anthropic else "none"
        if choice == "auto":
            # A plan signed in to without allowing plan use is not picked: the
            # user said no to it.
            if plan in ("active", "needs_sign_in"):
                return Route(choice, "chatgpt", "user")
            if "anthropic" in stored:
                return Route(choice, "anthropic", "user")
            if "openai" in stored:
                return Route(choice, "openai", "user")
            return Route(choice, "anthropic", platform)
        if choice in ("chatgpt", "openai"):
            return Route(choice, choice, "user")
        return Route(choice, "anthropic", "user" if "anthropic" in stored else platform)

    async def route(self, user_id: str) -> Route:
        """Which provider would run this user's AI, and who would pay. Cheap
        enough for every request: indexed reads, no decryption, no network."""
        settings, rows = await self._state(user_id)
        return self._route_from(settings, rows, await self._plan_present(user_id))

    async def has_byok(self, user_id: str) -> bool:
        """Whether the user's own key or ChatGPT plan pays for their AI, which
        is what a usage meter needs to know to lift metering. As cheap as
        `route`."""
        return (await self.route(user_id)).source == "user"

    # ── Resolving ─────────────────────────────────────────────────────────────

    async def resolve(self, user_id: str) -> ResolvedCredentials:
        """What this user's AI runs on for this request: the provider, the
        credential, and a model per tier. Raises the typed error when the
        chosen provider cannot run (domain/llm.py), never falling back to
        another way of paying."""
        settings, rows = await self._state(user_id)
        route = self._route_from(settings, rows, await self._plan_present(user_id))
        keys = self._open_keys(user_id, rows)
        anthropic = keys.get("anthropic")
        base: dict[str, Any] = {
            "anthropic": anthropic or Secret(self._platform_anthropic),
            "anthropic_is_user_key": anthropic is not None,
        }
        if route.provider == "anthropic":
            # Unchanged from before providers: the user's key when it can be
            # read, else the platform's (an unreadable key is our storage
            # problem, and status() asks the user to enter it again).
            return ResolvedCredentials(**base, provider="anthropic")

        overrides = _chosen(settings, route.provider)
        llm = await self._openai_client(user_id, route.provider, keys, overrides)
        return ResolvedCredentials(**base, llm=llm, provider=route.provider, source="user")

    async def _openai_client(
        self, user_id: str, provider: str, keys: dict[str, Secret], overrides: dict[str, Any]
    ) -> LLMClient:
        from salli.adapters.llm.openai_adapter import OpenAIResponsesClient

        route, session, fingerprint = await self._session(user_id, provider, keys)
        models = choose(await self._catalogue(user_id, route, session, fingerprint), overrides)
        return OpenAIResponsesClient(
            route,
            session,
            models=models,
            fingerprint=fingerprint,
            source="user",
            http_factory=self._http_factory,
        )

    async def _session(
        self, user_id: str, provider: str, keys: dict[str, Secret] | None = None
    ) -> tuple[Any, Any, str]:
        """(route, bearer session, fingerprint) for an OpenAI provider, or the
        typed error saying why this user cannot use it."""
        from salli.adapters.llm.openai_adapter import ApiKeySession, key_fingerprint
        from salli.adapters.llm.responses import API_KEY_ROUTE, CHATGPT_ROUTE

        if provider == "openai":
            if keys is None:
                _, rows = await self._state(user_id)
                keys = self._open_keys(user_id, rows)
            key = keys.get("openai")
            if key is None:
                raise LLMNotConfigured(
                    "Salli is set to use OpenAI, but there is no OpenAI API key it can use. "
                    "Add one with `salli llm-keys set openai`, or choose another provider "
                    "with `salli ai use`.",
                    provider="openai",
                )
            return API_KEY_ROUTE, ApiKeySession(key), key_fingerprint("openai", key)
        if self._chatgpt is None:
            raise LLMNotConfigured(
                "This Salli server can't use a ChatGPT plan.", provider="chatgpt"
            )
        if self._plan_allowed is not None and not await self._plan_allowed(user_id):
            raise LLMNotEligible(
                "Using a ChatGPT plan is switched off on this Salli server. Disconnect ChatGPT, "
                "or choose another AI provider with `salli ai use`.",
                provider="chatgpt",
            )
        session = self._chatgpt.session(user_id)
        # Ask for the token now: a plan that needs signing in again, or is
        # paused at its usage limit, says so before anything starts streaming.
        await session.bearer()
        digest = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        return CHATGPT_ROUTE, session, f"chatgpt:{digest}"

    async def _catalogue(
        self, user_id: str, route: Any, session: Any, fingerprint: str
    ) -> list[CatalogModel]:
        """The account's models, reused for a while: one `GET /v1/models` per
        user every half hour, not one per request. A stale list beats none
        when OpenAI cannot be reached."""
        from salli.adapters.llm.responses import fetch_catalogue

        key = (user_id, route.provider, fingerprint)
        cached = self._catalogues.get(key)
        now = self._clock()
        if cached is not None and now - cached[0] < _CATALOGUE_TTL:
            return cached[1]
        try:
            body = await fetch_catalogue(route, session, http_factory=self._http_factory)
        except LLMError:
            if cached is not None:
                return cached[1]
            raise
        models = plan_catalogue(body) if route.provider == "chatgpt" else api_catalogue(body)
        if len(self._catalogues) >= _CATALOGUE_MAX:
            oldest = min(self._catalogues, key=lambda k: self._catalogues[k][0])
            del self._catalogues[oldest]
        self._catalogues[key] = (now, models)
        return models

    def _open_keys(self, user_id: str, rows: list[dict[str, Any]]) -> dict[str, Secret]:
        out: dict[str, Secret] = {}
        for row in rows:
            provider = row["provider"]
            try:
                out[provider] = Secret(self._open(user_id, row))
            except Exception:
                # An unreadable row means our storage is wrong, not the user's
                # key: an encryption key was rotated away, or the row moved (the
                # AAD check refusing to open it is the feature working). For
                # Anthropic this falls back to the platform key, keeping the user
                # working rather than locking them out of chat entirely, and
                # status() reports readable=False so the UI can ask them to
                # re-enter it. Never log the exception body — it may quote
                # ciphertext.
                _log.error("Stored %s credential for a user could not be decrypted", provider)
        return out

    def _open(self, user_id: str, row: dict[str, Any]) -> str:
        from salli.adapters.crypto.keyring import aad_for

        return self._keyring.open(
            row["ciphertext"],
            aad=aad_for(user_id, row["provider"]),
            key_version=row.get("key_version", 1),
        )

    # ── The user's settings ───────────────────────────────────────────────────

    async def settings(self, user_id: str) -> dict[str, Any]:
        """The user's AI setting, what it resolves to now, and what they have
        to choose from. Cheap: no decryption, no network."""
        settings, rows = await self._state(user_id)
        plan = await self._plan_present(user_id)
        route = self._route_from(settings, rows, plan)
        plan_on = (
            self._chatgpt is not None
            and self._chatgpt.available
            and (self._plan_allowed is None or await self._plan_allowed(user_id))
        )
        return {
            "provider": route.choice,
            "active": {"provider": route.provider, "source": route.source},
            "keys": sorted({str(row["provider"]) for row in rows}),
            "chatgpt": plan,
            "chatgpt_available": plan_on,
            "platform_key": bool(self._platform_anthropic),
            "models": dict(settings.get("models") or {}),
        }

    async def set_provider(self, user_id: str, choice: str) -> dict[str, Any]:
        """Choose what powers this user's AI: "auto", or one provider."""
        if choice not in PROVIDER_CHOICES:
            raise ValueError(f"Unknown AI provider '{choice}': auto, anthropic, openai or chatgpt")
        settings, _ = await self._state(user_id)
        async with self._uow_factory() as uow:
            await uow.user_profiles.set_ai_settings(
                user_id,
                provider=None if choice == "auto" else choice,
                models=dict(settings.get("models") or {}),
            )
        return await self.settings(user_id)

    async def models(self, user_id: str, provider: str) -> dict[str, Any]:
        """The models a provider offers this user, and the one each tier runs on."""
        if provider == "anthropic":
            from salli.domain.ai_models import DEFAULT_MODEL, EXTRACTION_MODEL, MODELS

            return {
                "provider": "anthropic",
                "models": [{"id": m.id, "name": m.name} for m in MODELS.values()],
                "fast": EXTRACTION_MODEL,
                "best": DEFAULT_MODEL,
                "chosen": {},
            }
        if provider not in ("openai", "chatgpt"):
            raise ValueError(f"Unknown AI provider '{provider}'")
        settings, _ = await self._state(user_id)
        chosen = _chosen(settings, provider)
        route, session, fingerprint = await self._session(user_id, provider)
        catalogue = await self._catalogue(user_id, route, session, fingerprint)
        picks = choose(catalogue, chosen)
        return {
            "provider": provider,
            "models": [{"id": m.id, "name": m.name} for m in catalogue],
            "fast": picks["fast"],
            "best": picks["best"],
            "chosen": chosen,
        }

    async def set_models(
        self, user_id: str, provider: str, *, fast: str | None, best: str | None
    ) -> dict[str, Any]:
        """Name the model a tier runs on, for an OpenAI provider (None: let
        Salli pick). Checked against the account's models when they can be
        listed, so a typo is caught here rather than mid-conversation."""
        if provider not in ("openai", "chatgpt"):
            raise ValueError(
                "Claude's models are fixed in Salli; a model can be chosen for openai or chatgpt."
            )
        wanted = {tier: model for tier, model in (("fast", fast), ("best", best)) if model}
        if wanted:
            try:
                route, session, fingerprint = await self._session(user_id, provider)
                known = {m.id for m in await self._catalogue(user_id, route, session, fingerprint)}
            except LLMError:
                known = None  # cannot check now; OpenAI will refuse a wrong one
            for model in wanted.values():
                if known is not None and model not in known:
                    raise ValueError(
                        f"'{model}' isn't one of the models your {provider} account can use. "
                        f"See them with `salli ai models {provider}`."
                    )
        settings, _ = await self._state(user_id)
        models: dict[str, Any] = dict(settings.get("models") or {})
        if wanted:
            models[provider] = wanted
        else:
            models.pop(provider, None)
        async with self._uow_factory() as uow:
            await uow.user_profiles.set_ai_settings(
                user_id, provider=settings.get("provider"), models=models
            )
        return await self.models(user_id, provider)

    # ── Keys ──────────────────────────────────────────────────────────────────

    async def status(self, user_id: str) -> list[dict[str, Any]]:
        """What the settings screen shows. Never includes the key itself — the
        only readback is the last four characters."""
        if not self.available:
            return []
        async with self._uow_factory() as uow:
            rows = await uow.llm_credentials.list_for_user(user_id)
        out: list[dict[str, Any]] = []
        for row in rows:
            readable = True
            try:
                self._open(user_id, row)
            except Exception:
                readable = False
            out.append(
                {
                    "provider": row["provider"],
                    "last4": row["last4"],
                    "validated_at": row["validated_at"],
                    "readable": readable,
                }
            )
        return out

    async def save(self, user_id: str, provider: str, key: str) -> dict[str, Any]:
        """Validate against the provider, then store encrypted.

        Validating first means a typo is rejected on the settings screen instead
        of surfacing as a broken conversation later, and it keeps unusable rows
        out of the table entirely.
        """
        if not self.available:
            raise RuntimeError("BYOK is not configured on this deployment")
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'")
        key = key.strip()
        if not key:
            raise ValueError("API key is required")

        if self._validator is not None:
            await self._validator(provider, key)
            validated_at = datetime.datetime.now(datetime.UTC)
        else:
            validated_at = None

        from salli.adapters.crypto.keyring import aad_for

        sealed, version = self._keyring.seal(key, aad=aad_for(user_id, provider))
        async with self._uow_factory() as uow:
            await uow.llm_credentials.upsert(
                user_id,
                provider,
                ciphertext=sealed,
                last4=key[-4:],
                validated_at=validated_at,
                key_version=version,
            )
        return {
            "provider": provider,
            "last4": key[-4:],
            "validated_at": validated_at.isoformat() if validated_at else None,
        }

    async def delete(self, user_id: str, provider: str) -> bool:
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'")
        async with self._uow_factory() as uow:
            return await uow.llm_credentials.delete(user_id, provider)
