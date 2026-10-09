"""
AI providers — `/v1/ai`: which provider powers a user's AI, and their ChatGPT
plan connection.

Salli can run its AI on Anthropic or OpenAI with the user's own API key
(`/v1/llm-keys`), on the user's ChatGPT plan, or on the deployment's own key.
A ChatGPT plan is connected by signing in with ChatGPT (OpenAI's Sign in with
ChatGPT plan usage, for open-source and self-hosted apps).

The sign-in has to happen where the browser is: its callback is a 127.0.0.1
loopback. On the server's own machine, `salli ai connect chatgpt` does it all.
For a server elsewhere, a client on the user's computer (the TypeScript CLI)
signs in there, sending this instance's host id (`GET /v1/ai/host`), and hands
the result to `PUT /v1/ai/connections/chatgpt`. The server checks it before
keeping it, keeps its own host id, and renews it from then on (OpenAI's guide
for self-hosted VMs).

Nothing here ever returns a token.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from salli.adapters.llm.chatgpt_oauth import OAuthUnavailable, SignInError
from salli.application.services.chatgpt_connection_service import ChatGPTUnavailable
from salli.domain.llm import CHATGPT_USAGE_URL, LLMError
from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/ai", tags=["ai"])


class AiHost(BaseModel):
    """This instance's host id for Sign in with ChatGPT."""

    #: Stable and opaque (`urn:uuid:` and a UUIDv4), generated once per
    #: instance. A sign-in for a user of this instance sends it as
    #: `ext_agent_host_id`, whichever computer the browser is on. Not a
    #: credential.
    ext_agent_host_id: str


class ChatGPTConnection(BaseModel):
    """A user's ChatGPT plan connection, described without any token."""

    #: Whether this server can hold one at all (an encryption key is
    #: configured, and sign-in is real).
    available: bool
    #: `active`: Salli can use the plan. `needs_sign_in`: ChatGPT ended the
    #: sign-in (`detail` says how to renew it). `needs_consent`: signed in,
    #: but plan use was not allowed. `signed_out`: disconnected.
    status: Literal["not_connected", "active", "needs_sign_in", "needs_consent", "signed_out"]
    connected: bool
    #: The ChatGPT account's email, from its verified ID token.
    email: str | None
    #: The client id OpenAI issued Salli for this account: send it, not
    #: `dynamic_agent_client`, to sign the same account in again. An
    #: identifier, not a secret.
    client_id: str | None
    #: The scopes ChatGPT granted.
    scopes: list[str]
    #: When the current access token expires (Salli renews it before then).
    expires_at: str | None
    #: Set while new requests wait after the plan's usage limit was reached.
    paused_until: str | None
    #: What the user needs to do, in a sentence.
    detail: str | None
    #: False when this server can no longer decrypt it: sign in again.
    readable: bool
    #: Where the user reviews and limits what Salli uses of their plan.
    manage_usage_url: str = CHATGPT_USAGE_URL
    #: On connecting: true the first time this user connects their plan, when
    #: a client should confirm "You're using your ChatGPT plan" once.
    first_time: bool | None = None


class ChatGPTCredential(BaseModel):
    """A ChatGPT sign-in completed on another computer, for this server to keep.

    The token endpoint's answer to the authorization-code exchange, as it
    came, plus the issued `client_id`. OpenAI's example credential record is
    accepted too (`scopes` as a list, and `saved_at`).
    """

    model_config = ConfigDict(extra="ignore")

    #: The client id OpenAI issued (from the registration callback, or the
    #: one this account already had), never `dynamic_agent_client`.
    client_id: str = Field(min_length=1)
    access_token: str = Field(min_length=1)
    refresh_token: str = Field(min_length=1)
    #: Verified here against OpenAI's published keys: the issuer, the
    #: audience (`client_id`) and that it has not expired, so hand it over
    #: soon after signing in.
    id_token: str = Field(min_length=1)
    token_type: str | None = None
    #: Seconds, as the token endpoint said.
    expires_in: int | None = None
    #: Space-separated, as the token endpoint said. Must include
    #: `chatgpt.tokens.use.direct`.
    scope: str | None = None
    scopes: list[str] | None = None
    earliest_refresh_at: int | str | None = None
    #: When the token response was received (ISO 8601); defaults to now.
    saved_at: str | None = None
    #: Accepted and ignored: this server keeps its own (`GET /v1/ai/host`).
    ext_agent_host_id: str | None = None


class ChatGPTDisconnected(BaseModel):
    disconnected: bool
    #: Whether OpenAI confirmed the sign-in was ended. When not, `message`
    #: says to disconnect Salli in ChatGPT's settings to be sure.
    revoked: bool
    message: str


def _problem(exc: Exception) -> HTTPException:
    if isinstance(exc, ChatGPTUnavailable):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "chatgpt_unavailable", "message": str(exc)},
        )
    if isinstance(exc, SignInError):
        return HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"error": "sign_in_rejected", "message": exc.message},
        )
    if isinstance(exc, OAuthUnavailable):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "openai_unreachable",
                "message": "Couldn't reach OpenAI to check this sign-in. Please try again.",
            },
        )
    if isinstance(exc, LLMError):
        return HTTPException(exc.status, detail=exc.detail())
    raise exc


@router.get("/host")
async def get_host(user_id: CurrentUser, svc: AppServices) -> AiHost:
    """This instance's `ext_agent_host_id`, for a sign-in done on another
    computer on behalf of this server."""
    return AiHost(ext_agent_host_id=await svc.chatgpt.host_id())


@router.get("/connections/chatgpt")
async def get_chatgpt(user_id: CurrentUser, svc: AppServices) -> ChatGPTConnection:
    """The user's ChatGPT plan connection: which account, what was granted,
    and whether it needs them. Never a token."""
    return ChatGPTConnection.model_validate(await svc.chatgpt.status(user_id))


@router.put("/connections/chatgpt")
async def connect_chatgpt(
    body: ChatGPTCredential, user_id: CurrentUser, svc: AppServices
) -> ChatGPTConnection:
    """Keep a ChatGPT sign-in completed on the user's own computer.

    Checked before it is kept: the issued client id, the ID token (signature
    against OpenAI's keys, issuer, audience, expiry), that the scopes include
    `chatgpt.tokens.use.direct`, and that `GET /v1/models` works with the
    access token. From then on this server renews it, with its own host id.
    """
    credential: dict[str, Any] = body.model_dump(exclude_none=True)
    try:
        result = await svc.chatgpt.import_credential(user_id, credential)
    except (ChatGPTUnavailable, SignInError, OAuthUnavailable, LLMError) as exc:
        raise _problem(exc) from None
    return ChatGPTConnection.model_validate(result)


@router.delete("/connections/chatgpt")
async def disconnect_chatgpt(user_id: CurrentUser, svc: AppServices) -> ChatGPTDisconnected:
    """Sign out: end the sign-in with OpenAI, then clear its tokens here. The
    account and its issued client id are kept for the next sign-in."""
    result = await svc.chatgpt.disconnect(user_id)
    if not result["disconnected"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ChatGPT is not connected")
    return ChatGPTDisconnected.model_validate(result)
