"""
LLM keys router — a user's own Anthropic credentials (BYOK).

Supplying a key lifts AI usage metering: the user pays for their own inference,
so there is nothing left for Salli to ration. The key powers every AI surface —
the agent, statement parsing and advisor runs.

The key is write-only over HTTP. Nothing here ever returns it — the only
readback is the last four characters, enough for the UI to show which key is
stored without being able to reveal it.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from salli.adapters.llm.key_check import InvalidProviderKey, KeyValidationUnavailable
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/llm-keys", tags=["llm-keys"])

Provider = Literal["anthropic"]

_PROVIDER_LABEL = {"anthropic": "Anthropic"}


class SaveKeyRequest(BaseModel):
    # No max_length: providers change key formats, and rejecting a valid key on
    # a guessed length would be a worse failure than passing it through to the
    # provider, which is the real authority on whether it's usable.
    key: str = Field(min_length=1)


@router.get("")
async def get_llm_keys(user_id: CurrentUser, svc: AppServices):
    """Which keys this user has stored, and whether BYOK is usable at all here.

    `available: false` means the deployment can't accept keys (no encryption key
    configured, or authentication isn't real enough to trust a user id) — the UI
    should hide the section rather than offer a control that will 503.
    """
    return {
        "available": svc.llm_credentials.available,
        "keys": await svc.llm_credentials.status(user_id),
    }


@router.put("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def save_llm_key(
    provider: Provider, body: SaveKeyRequest, user_id: CurrentUser, svc: AppServices
):
    """Validate the key against the provider, then store it encrypted.

    Validated before storing so a typo is rejected here, on the settings screen,
    rather than surfacing later as a broken conversation — and so unusable rows
    never enter the table.
    """
    try:
        await svc.llm_credentials.save(user_id, provider, body.key)
    except InvalidProviderKey:
        # Deliberately our own wording, not the provider's: an upstream error
        # message can echo the key that was rejected.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_key",
                "provider": provider,
                "message": f"{_PROVIDER_LABEL[provider]} rejected this key. "
                "Check you pasted it whole, and that it's still active.",
            },
        ) from None
    except KeyValidationUnavailable:
        # Distinct from rejection: don't tell someone their key is wrong because
        # the provider was having a bad minute.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "validation_unavailable",
                "provider": provider,
                "message": f"Couldn't reach {_PROVIDER_LABEL[provider]} to check that key. "
                "Please try again in a moment.",
            },
        ) from None
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "byok_unavailable", "message": str(exc)},
        ) from None


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_key(provider: Provider, user_id: CurrentUser, svc: AppServices):
    """Remove the key. The user reverts to platform metering on the next request."""
    removed = await svc.llm_credentials.delete(user_id, provider)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No key stored")
