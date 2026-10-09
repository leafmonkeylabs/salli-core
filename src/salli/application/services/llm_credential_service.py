"""
LlmCredentialService — resolves which LLM API key a request runs on.

The single choke point for that decision. Every LLM path (agent chat, statement
classification, quick-add parsing, advisor runs) resolves
here by user id, so the HTTP routes and the MCP server — which reaches the same
services with a user id off its OAuth token — cannot diverge.

Plaintext keys leave this module only as `Secret` (see domain/secrets.py), so a
key cannot reach a log line, an SSE frame, or an exception message by accident.
Reading one is a deliberate `.reveal()` at the point the provider client is
constructed.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from salli.domain.secrets import Secret

_log = logging.getLogger(__name__)

PROVIDERS = ("anthropic",)


@dataclass(frozen=True)
class ResolvedCredentials:
    """Which key each provider call should use, and whose it is.

    Immutable and resolved once per request: the usage meter runs before the
    stream opens, so it has to see the same answer the LLM call will later act
    on. Resolving twice invites the two to disagree.
    """

    anthropic: Secret
    anthropic_is_user_key: bool

    @property
    def byok(self) -> bool:
        """Whether AI usage metering should be lifted.

        Keyed on the Anthropic credential specifically, because that is what
        every metered path spends.
        """
        return self.anthropic_is_user_key


class LlmCredentialService:
    def __init__(
        self,
        uow_factory: Any,
        keyring: Any,
        *,
        platform_anthropic_key: str = "",
        validator: Any = None,
        feature_enabled: bool = True,
    ) -> None:
        self._uow_factory = uow_factory
        self._keyring = keyring
        self._platform_anthropic = platform_anthropic_key
        self._validator = validator
        self._feature_enabled = feature_enabled

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

    # ── Resolution ────────────────────────────────────────────────────────────

    async def resolve(self, user_id: str) -> ResolvedCredentials:
        user_keys = await self._user_keys(user_id)

        anthropic = user_keys.get("anthropic")

        return ResolvedCredentials(
            anthropic=anthropic or Secret(self._platform_anthropic),
            anthropic_is_user_key=anthropic is not None,
        )

    async def has_byok(self, user_id: str) -> bool:
        """Cheap enough to ask on every request: one indexed read, no decryption."""
        if not self.available:
            return False
        async with self._uow_factory() as uow:
            row = await uow.llm_credentials.get(user_id, "anthropic")
        return row is not None

    async def _user_keys(self, user_id: str) -> dict[str, Secret]:
        if not self.available:
            return {}
        try:
            async with self._uow_factory() as uow:
                rows = await uow.llm_credentials.list_for_user(user_id)
        except Exception:
            _log.exception("Could not read stored LLM credentials for a user")
            return {}

        out: dict[str, Secret] = {}
        for row in rows:
            provider = row["provider"]
            try:
                out[provider] = Secret(self._open(user_id, row))
            except Exception:
                # An unreadable row means our storage is wrong, not the user's
                # key: an encryption key was rotated away, or the row moved (the
                # AAD check refusing to open it is the feature working). Falling
                # back to the platform key keeps the user working rather than
                # locking them out of chat entirely, and status() reports
                # readable=False so the UI can ask them to re-enter it. Never
                # log the exception body — it may quote ciphertext.
                _log.error(
                    "Stored %s credential for a user could not be decrypted; "
                    "falling back to the platform key",
                    provider,
                )
        return out

    def _open(self, user_id: str, row: dict[str, Any]) -> str:
        from salli.adapters.crypto.keyring import aad_for

        return self._keyring.open(
            row["ciphertext"],
            aad=aad_for(user_id, row["provider"]),
            key_version=row.get("key_version", 1),
        )

    # ── Management ────────────────────────────────────────────────────────────

    async def status(self, user_id: str) -> list[dict[str, Any]]:
        """What the settings screen shows. Never includes the key itself — the
        only readback is the last four characters."""
        if not self.available:
            return []
        async with self._uow_factory() as uow:
            rows = await uow.llm_credentials.list_for_user(user_id)
        out = []
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
