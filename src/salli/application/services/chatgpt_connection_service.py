"""
ChatGPTConnectionService — a user's ChatGPT plan, connected to Salli.

OpenAI lets open-source and self-hosted apps use a person's ChatGPT plan for
Responses API requests, through Sign in with ChatGPT
(https://developers.openai.com/siwc/token-sharing-open-source). This service
keeps what that sign-in produced and keeps it working:

- Sealed, never in the clear: the issued client id, the access token, the
  rotating refresh token, the ID token (kept for the next sign-in's
  `id_token_hint`), the granted scopes and the account's `sub` and email, as
  one blob sealed with the instance's key ring and bound to the user and
  provider, exactly as a stored API key is.
- Renewed before it expires, one request at a time: the renewal holds the
  row (SELECT ... FOR UPDATE) while it spends the refresh token, so a second
  request waits and then uses the new pair. OpenAI's refresh tokens rotate,
  and one spent twice is refused ("serialize refreshes for the same session
  so two processes do not race a rotating token").
- When OpenAI refuses a renewal for good, the connection is marked as needing
  the user to sign in again, and every request says so. Nothing ever falls
  back to the platform's key: who pays never changes behind the user's back.
- Off unless the deployment can hold it: an encryption key is configured and
  authentication is real (not the development fallback).

Tokens leave this module only toward OpenAI, and never into a log.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from salli.adapters.llm.chatgpt_oauth import (
    DYNAMIC_CLIENT_ID,
    ChatGPTOAuth,
    OAuthUnavailable,
    RefreshRefused,
    SignInError,
    TokenSet,
    token_set,
    unverified_claims,
)
from salli.domain.llm import (
    LLMError,
    LLMProviderUnavailable,
    LLMSignInRequired,
    chatgpt_usage_limit,
)

_log = logging.getLogger(__name__)

PROVIDER = "chatgpt"

#: Renew this long before the access token expires (they last an hour).
_RENEW_BEFORE = dt.timedelta(minutes=5)
#: How long new requests wait after the plan's usage limit was reached
#: ("Pause new requests that use the user's ChatGPT plan"). Not a guess at
#: when the limit resets, which OpenAI says not to infer.
_PAUSE = dt.timedelta(minutes=10)

_SIGN_IN = "Run `salli ai connect chatgpt`, or connect ChatGPT again in Settings."

#: The instance's host id, under this key in instance_settings.
HOST_ID_KEY = "ext_agent_host_id"

_PLAN_NOT_ALLOWED = (
    "Signed in, but ChatGPT plan use wasn't allowed, so Salli can't use your plan. To "
    "allow it, run `salli ai connect chatgpt` again and allow plan use. Or add your own "
    "API key instead: `salli llm-keys set openai` (or anthropic)."
)


class ChatGPTUnavailable(RuntimeError):
    """This deployment cannot hold a ChatGPT connection: no encryption key,
    or authentication is the development fallback (anyone could act as anyone)."""


@dataclass(frozen=True)
class SignInContext:
    """What a new sign-in on this host starts from: the instance's host id,
    and, for an account that registered before, its issued client id and hints."""

    host_id: str
    client_id: str | None = None
    login_hint: str | None = None
    id_token_hint: str | None = None
    #: Plan use was declined last time: ask for consent again.
    ask_consent: bool = False
    #: The account this sign-in must turn out to be (a sign-in again with a
    #: saved client id), or None when any account may register.
    expected_sub: str | None = None


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_instant(value: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


def _token_expiry(access_token: str) -> dt.datetime | None:
    """The access token's own `exp`, when the token response gave no
    `expires_in` (read, not trusted: it only decides when to renew)."""
    exp = unverified_claims(access_token).get("exp")
    return dt.datetime.fromtimestamp(exp, dt.UTC) if isinstance(exp, int) else None


def _instant(value: Any) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


@dataclass(frozen=True)
class ChatGPTRecord:
    """What a connection holds, all of it sealed together.

    OpenAI's guide keeps one protected record per issued client id and
    verified identity; this is that record ("Store credentials in a local
    file"), kept in the database instead of a file.
    """

    sub: str
    client_id: str | None
    email: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    scopes: tuple[str, ...] = ()
    expires_at: dt.datetime | None = None
    earliest_refresh_at: dt.datetime | None = None
    saved_at: dt.datetime | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "issuer": "https://auth.openai.com",
                "subject": self.sub,
                "client_id": self.client_id,
                "email": self.email,
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "id_token": self.id_token,
                "scopes": list(self.scopes),
                "expires_at": _iso(self.expires_at),
                "earliest_refresh_at": _iso(self.earliest_refresh_at),
                "saved_at": _iso(self.saved_at),
            }
        )

    @classmethod
    def from_json(cls, text: str) -> ChatGPTRecord:
        data: dict[str, Any] = json.loads(text)
        return cls(
            sub=str(data["subject"]),
            client_id=data.get("client_id"),
            email=data.get("email"),
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            id_token=data.get("id_token"),
            scopes=tuple(data.get("scopes") or ()),
            expires_at=_instant(data.get("expires_at")),
            earliest_refresh_at=_instant(data.get("earliest_refresh_at")),
            saved_at=_instant(data.get("saved_at")),
        )

    def renewed(self, tokens: TokenSet, now: dt.datetime) -> ChatGPTRecord:
        """After a refresh: the access token, expiry, scopes and rotated
        refresh token replaced together ("Replace the access token, expiry,
        granted scopes, and rotating refresh token together")."""
        return replace(
            self,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token or self.refresh_token,
            id_token=tokens.id_token or self.id_token,
            scopes=tokens.scopes or self.scopes,
            expires_at=tokens.expires_at(now),
            earliest_refresh_at=tokens.earliest_refresh_at,
            saved_at=now,
        )

    def without_tokens(self, *, keep_id_token: bool = True) -> ChatGPTRecord:
        """The account and its issued client id, with nothing usable left."""
        return replace(
            self,
            access_token=None,
            refresh_token=None,
            id_token=self.id_token if keep_id_token else None,
            expires_at=None,
            earliest_refresh_at=None,
        )


class ChatGPTSession:
    """A user's ChatGPT plan as a bearer for Responses requests
    (adapters/llm/responses.BearerSession): renewed as it nears expiry, renewed
    once more when OpenAI rejects it, and paused at the plan's usage limit."""

    def __init__(self, service: ChatGPTConnectionService, user_id: str) -> None:
        self._service = service
        self._user_id = user_id
        self._last: str | None = None

    async def bearer(self, force_refresh: bool = False) -> str:
        token = await self._service.access_token(
            self._user_id, rejected=self._last if force_refresh else None
        )
        self._last = token
        return token

    async def usage_limited(self) -> None:
        await self._service.pause(self._user_id)


class ChatGPTConnectionService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        keyring: Any,
        oauth: ChatGPTOAuth | None = None,
        *,
        feature_enabled: bool = True,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._keyring = keyring
        self._oauth = oauth or ChatGPTOAuth()
        self._feature_enabled = feature_enabled
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))

    @property
    def available(self) -> bool:
        """Whether this deployment may hold a ChatGPT connection at all."""
        return bool(self._feature_enabled and self._keyring.available)

    @property
    def oauth(self) -> ChatGPTOAuth:
        return self._oauth

    async def host_id(self) -> str:
        """This instance's `ext_agent_host_id`: generated once, as `urn:uuid:`
        and a UUIDv4 (an accepted format), and kept for good. Every sign-in for
        a user of this instance sends it, whichever computer the browser is on,
        so a credential brought from elsewhere never brings another host's id.
        Opaque, not a credential, identifying no one."""
        import uuid

        async with self._uow_factory() as uow:
            return await uow.instance_settings.get_or_create(
                HOST_ID_KEY, f"urn:uuid:{uuid.uuid4()}"
            )

    def _require_available(self) -> None:
        if not self._feature_enabled:
            raise ChatGPTUnavailable(
                "Connecting ChatGPT is off while authentication isn't real: anyone could "
                "act as anyone."
            )
        if not self._keyring.available:
            raise ChatGPTUnavailable(
                "Connecting ChatGPT needs an encryption key (BYOK_ENCRYPTION_KEYS), so its "
                "tokens are never stored in the clear."
            )

    # ── Sealing ───────────────────────────────────────────────────────────────

    def _seal(self, user_id: str, record: ChatGPTRecord) -> tuple[str, int]:
        from salli.adapters.crypto.keyring import aad_for

        return self._keyring.seal(record.to_json(), aad=aad_for(user_id, PROVIDER))

    def _open(self, user_id: str, row: dict[str, Any]) -> ChatGPTRecord:
        from salli.adapters.crypto.keyring import aad_for

        return ChatGPTRecord.from_json(
            self._keyring.open(
                row["sealed"], aad=aad_for(user_id, PROVIDER), key_version=row["key_version"]
            )
        )

    def _fields(
        self, user_id: str, record: ChatGPTRecord, status: str, detail: str | None = None
    ) -> dict[str, Any]:
        sealed, version = self._seal(user_id, record)
        return {
            "sealed": sealed,
            "key_version": version,
            "status": status,
            "status_detail": detail,
            "expires_at": record.expires_at,
        }

    # ── Reading ───────────────────────────────────────────────────────────────

    async def presence(self, user_id: str) -> str | None:
        """The connection's status, or None when there is none to use: what
        choosing a provider needs, with one indexed read and no decryption."""
        if not self.available:
            return None
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get(user_id, PROVIDER)
        if row is None or row["status"] == "signed_out":
            return None
        return str(row["status"])

    async def record(self, user_id: str) -> ChatGPTRecord | None:
        """The stored record, readable or not (None)."""
        if not self.available:
            return None
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get(user_id, PROVIDER)
        if row is None:
            return None
        try:
            return self._open(user_id, row)
        except Exception:
            return None

    async def status(self, user_id: str) -> dict[str, Any]:
        """What a settings screen shows. Never a token: the account it is,
        the issued client id (an identifier, needed to sign in again with the
        same registration), what was granted, and whether it needs the user."""
        out: dict[str, Any] = {
            "available": self.available,
            "status": "not_connected",
            "connected": False,
            "email": None,
            "client_id": None,
            "scopes": [],
            "expires_at": None,
            "paused_until": None,
            "detail": None,
            "readable": True,
        }
        if not self.available:
            return out
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get(user_id, PROVIDER)
        if row is None:
            return out
        out["status"] = row["status"]
        out["detail"] = row["status_detail"]
        paused = row["paused_until"]
        if paused and paused > self._clock():
            out["paused_until"] = paused.isoformat()
        try:
            record = self._open(user_id, row)
        except Exception:
            out["readable"] = False
            out["detail"] = (
                "Salli can no longer read this ChatGPT sign-in here (its encryption key "
                f"changed). {_SIGN_IN}"
            )
            return out
        out.update(
            connected=row["status"] == "active",
            email=record.email,
            client_id=record.client_id,
            scopes=list(record.scopes),
            expires_at=_iso(record.expires_at),
        )
        return out

    def _usable(self, user_id: str, row: dict[str, Any] | None, now: dt.datetime) -> ChatGPTRecord:
        """The record behind a usable connection, or the error that says what
        the user has to do. Never a quiet fallback to anything else."""
        if row is None or row["status"] == "signed_out":
            raise LLMSignInRequired(
                f"Salli isn't connected to your ChatGPT plan. {_SIGN_IN}", provider=PROVIDER
            )
        if row["status"] != "active":
            raise LLMSignInRequired(
                row["status_detail"] or f"Your ChatGPT sign-in needs renewing. {_SIGN_IN}",
                provider=PROVIDER,
            )
        paused = row["paused_until"]
        if paused and paused > now:
            raise chatgpt_usage_limit(paused=True)
        try:
            record = self._open(user_id, row)
        except Exception:
            _log.error("A stored ChatGPT connection could not be decrypted")
            raise LLMSignInRequired(
                "Salli can no longer read your ChatGPT sign-in here (its encryption key "
                f"changed). {_SIGN_IN}",
                provider=PROVIDER,
            ) from None
        if not record.access_token:
            raise LLMSignInRequired(
                f"Your ChatGPT sign-in needs renewing. {_SIGN_IN}", provider=PROVIDER
            )
        return record

    def _due(self, record: ChatGPTRecord, now: dt.datetime) -> bool:
        """Whether the access token should be renewed now. An expiry that is
        not known waits for OpenAI to reject the token instead."""
        if record.expires_at is None or now < record.expires_at - _RENEW_BEFORE:
            return False
        earliest = record.earliest_refresh_at
        return not (earliest and now < earliest and now < record.expires_at)

    # ── Using it ──────────────────────────────────────────────────────────────

    def session(self, user_id: str) -> ChatGPTSession:
        return ChatGPTSession(self, user_id)

    async def access_token(self, user_id: str, *, rejected: str | None = None) -> str:
        """A usable access token for this user's plan, renewed first when it
        is about to expire, or when OpenAI just rejected `rejected`.

        Typed errors (domain/llm.py) for everything else: not connected, a
        sign-in that needs renewing, the plan's usage limit (while paused),
        OpenAI out of reach.
        """
        if not self.available:
            raise LLMSignInRequired(
                "This Salli server can't use a ChatGPT plan right now.", provider=PROVIDER
            )
        now = self._clock()
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get(user_id, PROVIDER)
        record = self._usable(user_id, row, now)
        if rejected is None and not self._due(record, now):
            return str(record.access_token)

        failure: LLMError | None = None
        token = ""
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get_for_update(user_id, PROVIDER)
            record = self._usable(user_id, row, self._clock())
            if record.access_token != rejected and not self._due(record, self._clock()):
                # Renewed by another request while this one waited for the row.
                return str(record.access_token)
            if not record.refresh_token or not record.client_id:
                failure = LLMSignInRequired(
                    f"Your ChatGPT sign-in can't be renewed. {_SIGN_IN}", provider=PROVIDER
                )
                await uow.ai_connections.update(
                    user_id,
                    PROVIDER,
                    self._fields(
                        user_id, record.without_tokens(), "needs_sign_in", failure.message
                    ),
                )
            else:
                try:
                    tokens = await self._oauth.refresh(
                        client_id=record.client_id, refresh_token=record.refresh_token
                    )
                except RefreshRefused as refused:
                    # "Clear unusable tokens and repeat OAuth with the saved
                    # issued client ID": the client id is kept for that, unless
                    # it is the client itself OpenAI refused.
                    failure = LLMSignInRequired(
                        f"ChatGPT ended Salli's sign-in (it may have been disconnected in "
                        f"ChatGPT's settings). {_SIGN_IN}",
                        provider=PROVIDER,
                    )
                    kept = record.without_tokens()
                    if refused.invalid_client:
                        kept = replace(kept, client_id=None)
                    _log.warning("ChatGPT refused a token renewal (%s)", refused.code)
                    await uow.ai_connections.update(
                        user_id,
                        PROVIDER,
                        self._fields(user_id, kept, "needs_sign_in", failure.message),
                    )
                except OAuthUnavailable:
                    failure = LLMProviderUnavailable(
                        "Couldn't reach OpenAI to renew your ChatGPT sign-in. Please try again "
                        "in a moment.",
                        provider=PROVIDER,
                    )
                else:
                    renewed = record.renewed(tokens, self._clock())
                    if not tokens.plan_granted:
                        failure = LLMSignInRequired(
                            "ChatGPT no longer allows Salli to use your plan. Sign in with "
                            "ChatGPT again and allow plan use.",
                            provider=PROVIDER,
                        )
                        await uow.ai_connections.update(
                            user_id,
                            PROVIDER,
                            self._fields(
                                user_id, renewed.without_tokens(), "needs_consent", failure.message
                            ),
                        )
                    else:
                        await uow.ai_connections.update(
                            user_id, PROVIDER, self._fields(user_id, renewed, "active")
                        )
                        token = str(renewed.access_token)
        if failure is not None:
            raise failure
        return token

    async def pause(self, user_id: str) -> None:
        """The plan's usage limit for Salli was reached: hold new requests."""
        async with self._uow_factory() as uow:
            await uow.ai_connections.update(
                user_id, PROVIDER, {"paused_until": self._clock() + _PAUSE}
            )

    # ── Signing in ────────────────────────────────────────────────────────────

    async def sign_in_context(self, user_id: str, *, new_account: bool = False) -> SignInContext:
        """Where a sign-in for this user starts. An account that registered
        before signs in again with its issued client id and the retained hints
        ("Later sign-ins reuse the saved client ID"); `new_account` registers
        afresh, for a different ChatGPT account."""
        self._require_available()
        host_id = await self.host_id()
        if new_account:
            return SignInContext(host_id=host_id)
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get(user_id, PROVIDER)
        record = None
        if row is not None:
            try:
                record = self._open(user_id, row)
            except Exception:
                record = None
        if record is None or not record.client_id:
            return SignInContext(host_id=host_id)
        return SignInContext(
            host_id=host_id,
            client_id=record.client_id,
            login_hint=record.email,
            id_token_hint=record.id_token,
            ask_consent=row is not None and row["status"] == "needs_consent",
            expected_sub=record.sub,
        )

    async def connect(
        self,
        user_id: str,
        tokens: TokenSet,
        *,
        client_id: str,
        nonce: str | None = None,
        received_at: dt.datetime | None = None,
        expected_sub: str | None = None,
    ) -> dict[str, Any]:
        """Validate a completed sign-in, then keep it as the user's connection.

        Checked before anything is stored: an issued client id (never
        `dynamic_agent_client`); the ID token, verified against OpenAI's JWKS
        (and the nonce, when this server sent it); the account, when it must be
        a known one; the access token's own client id, when it names one, so
        one registration's tokens are never kept under another's id; the
        `chatgpt.tokens.use.direct` scope; and `GET /v1/models` with the access
        token. A sign-in without plan use is kept as signed in with plan use
        off, as OpenAI's errors guide asks, and refused with a choice.
        """
        self._require_available()
        if not client_id or client_id == DYNAMIC_CLIENT_ID:
            raise SignInError(
                "The sign-in has no issued client id: `dynamic_agent_client` starts a "
                "registration and is never the id to keep."
            )
        if not tokens.id_token:
            raise SignInError("The sign-in has no ID token, so it can't be verified.")
        claims = await self._oauth.verify_id_token(
            tokens.id_token, client_id=client_id, nonce=nonce, access_token=tokens.access_token
        )
        sub = str(claims["sub"])
        if expected_sub is not None and sub != expected_sub:
            raise SignInError(
                "You signed in as a different ChatGPT account from the one connected. To "
                "switch accounts, run `salli ai connect chatgpt --new-account`."
            )
        token_client = unverified_claims(tokens.access_token).get("client_id")
        if token_client is not None and token_client != client_id:
            raise SignInError("The access token belongs to a different registration of Salli.")

        now = received_at or self._clock()
        email = claims.get("email")
        record = ChatGPTRecord(
            sub=sub,
            client_id=client_id,
            email=email if isinstance(email, str) else None,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            id_token=tokens.id_token,
            scopes=tokens.scopes,
            expires_at=tokens.expires_at(now) or _token_expiry(tokens.access_token),
            earliest_refresh_at=tokens.earliest_refresh_at,
            saved_at=now,
        )
        async with self._uow_factory() as uow:
            previous_row = await uow.ai_connections.get(user_id, PROVIDER)
        previous = None
        if previous_row is not None:
            try:
                previous = self._open(user_id, previous_row)
            except Exception:
                previous = None

        if not tokens.plan_granted:
            await self._keep(user_id, record.without_tokens(), "needs_consent", _PLAN_NOT_ALLOWED)
            raise SignInError(_PLAN_NOT_ALLOWED)
        if not tokens.refresh_token:
            raise SignInError(
                "ChatGPT didn't allow Salli to stay signed in (no offline access), so the "
                "connection would stop within the hour. Please sign in again and allow it."
            )
        # It has to work for what it is for, before it replaces anything.
        await self._oauth.list_models(tokens.access_token)

        await self._keep(user_id, record, "active")
        if (
            previous is not None
            and previous.refresh_token
            and previous.client_id
            and previous.refresh_token != record.refresh_token
        ):
            # The sign-in this one replaces is ended at OpenAI, not left renewable.
            await self._oauth.revoke(
                client_id=previous.client_id, refresh_token=previous.refresh_token
            )
        status = await self.status(user_id)
        # OpenAI's guidelines: confirm plan use once, the first time.
        status["first_time"] = previous_row is None or previous_row["status"] == "needs_consent"
        return status

    async def import_credential(self, user_id: str, credential: dict[str, Any]) -> dict[str, Any]:
        """Keep a sign-in completed on another computer (OpenAI's guide for
        self-hosted VMs: sign in where the browser is, then move the credential
        to the server, which keeps its own host id and renews it from then on).

        `credential` is the token endpoint's answer plus the issued
        `client_id`, or OpenAI's example credential record (`scopes` as a list,
        `saved_at`). An `ext_agent_host_id` in it is ignored: this instance
        keeps its own. Validated exactly as a sign-in here is, except for the
        nonce, which only the computer that signed in knew.
        """
        body = dict(credential)
        if "scope" not in body and isinstance(body.get("scopes"), list):
            body["scope"] = " ".join(str(s) for s in body["scopes"])
        try:
            tokens = token_set(body)
        except ValueError as exc:
            raise SignInError("The credential has no access token.") from exc
        saved = body.get("saved_at")
        received_at = _parse_instant(saved) if isinstance(saved, str) else None
        return await self.connect(
            user_id, tokens, client_id=str(body.get("client_id") or ""), received_at=received_at
        )

    # ── Keeping and ending it ─────────────────────────────────────────────────

    async def _keep(
        self, user_id: str, record: ChatGPTRecord, status: str, detail: str | None = None
    ) -> bool:
        async with self._uow_factory() as uow:
            fields = self._fields(user_id, record, status, detail)
            fields["paused_until"] = None
            return await uow.ai_connections.save(user_id, PROVIDER, fields)

    async def save_record(self, user_id: str, record: ChatGPTRecord) -> bool:
        """Store a sign-in already validated (by `connect`) as the user's
        active connection, sealed. True when it is their first row."""
        self._require_available()
        return await self._keep(user_id, record, "active")

    async def disconnect(self, user_id: str) -> dict[str, Any]:
        """Sign out: end the renewable session with OpenAI, then clear the
        tokens. The account and its issued client id stay, for the next sign-in
        (accounts-and-sessions, "Sign out")."""
        async with self._uow_factory() as uow:
            row = await uow.ai_connections.get_for_update(user_id, PROVIDER)
            if row is None or row["status"] == "signed_out":
                return {"disconnected": False, "revoked": False, "message": "Not connected."}
            try:
                record: ChatGPTRecord | None = self._open(user_id, row)
            except Exception:
                record = None
            revoked = False
            if record is not None and record.refresh_token and record.client_id:
                revoked = await self._oauth.revoke(
                    client_id=record.client_id, refresh_token=record.refresh_token
                )
            if record is None:
                await uow.ai_connections.delete(user_id, PROVIDER)
            else:
                fields = self._fields(
                    user_id, record.without_tokens(keep_id_token=False), "signed_out"
                )
                fields["paused_until"] = None
                await uow.ai_connections.update(user_id, PROVIDER, fields)
        message = (
            "Disconnected from ChatGPT."
            if revoked
            else "Disconnected here, but OpenAI didn't confirm the sign-in was ended. To be "
            "sure, disconnect Salli in ChatGPT's settings."
        )
        return {"disconnected": True, "revoked": revoked, "message": message}
