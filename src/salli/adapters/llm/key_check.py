"""
Live validation of a user-supplied provider key, before it is stored.

Checked at save time so a bad key surfaces as "that key was rejected" on the
settings screen, rather than as a mysterious failure mid-conversation hours
later. The model-list endpoint costs nothing, so this verifies the key without
spending the user's tokens.

Anthropic is the only provider now that speech-to-text runs on the device. The
table keeps its auth-style column so adding one back is a single line rather
than a rewrite.
"""

from __future__ import annotations

import httpx

_TIMEOUT = 10.0

_ENDPOINTS: dict[str, tuple[str, str]] = {
    # provider -> (url, auth style)
    "anthropic": ("https://api.anthropic.com/v1/models", "x-api-key"),
}


class InvalidProviderKey(Exception):
    """The provider rejected the key. Deliberately carries no provider text — an
    upstream message can echo the key itself (see domain/secrets.py)."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"{provider} rejected this API key")


class KeyValidationUnavailable(Exception):
    """The provider could not be reached, so the key is neither confirmed nor
    disproved. Distinct from rejection: the right response is "try again", not
    "your key is wrong"."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Could not reach {provider} to verify this key")


def supported_providers() -> tuple[str, ...]:
    return tuple(_ENDPOINTS)


async def validate_provider_key(provider: str, key: str) -> None:
    """Return normally when the key works; raise otherwise."""
    if provider not in _ENDPOINTS:
        raise ValueError(f"Unknown provider '{provider}'")
    url, style = _ENDPOINTS[provider]

    headers = (
        {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if style == "x-api-key"
        else {"Authorization": f"Bearer {key}"}
    )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise KeyValidationUnavailable(provider) from exc

    if response.status_code in (401, 403):
        raise InvalidProviderKey(provider)
    if response.status_code >= 500 or response.status_code == 429:
        # The provider is unhealthy or throttling us, which says nothing about
        # the key — don't tell the user their key is bad on our bad day.
        raise KeyValidationUnavailable(provider)
    if response.status_code >= 400:
        raise InvalidProviderKey(provider)
