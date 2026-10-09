"""
A scripted stand-in for OpenAI, on httpx.MockTransport: no request leaves the
process. `POST /v1/responses` answers with the next scripted reply, as the
server-sent events the Responses API streams; `GET /v1/models` with a catalogue.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from salli.adapters.llm.openai_adapter import ApiKeySession, OpenAIResponsesClient
from salli.adapters.llm.responses import API_KEY_ROUTE, CHATGPT_ROUTE, ResponsesRoute
from salli.domain.secrets import Secret

Reply = bytes | httpx.Response | Callable[[dict[str, Any]], "bytes | httpx.Response"]


def sse(*events: dict[str, Any]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _completed(output: list[dict[str, Any]], model: str = "gpt-test") -> dict[str, Any]:
    return {
        "type": "response.completed",
        "response": {
            "id": "resp_1",
            "object": "response",
            "status": "completed",
            "model": model,
            "output": output,
            "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        },
    }


def text_reply(text: str, *, pieces: int = 2) -> bytes:
    """A streamed answer: `text` in a few deltas, then response.completed."""
    message = {
        "type": "message",
        "id": "msg_1",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    size = max(1, -(-len(text) // pieces))
    deltas = [text[i : i + size] for i in range(0, len(text), size)] or [""]
    return sse(
        {"type": "response.created", "response": {"id": "resp_1", "status": "in_progress"}},
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**message, "content": []},
        },
        *(
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "delta": d,
            }
            for d in deltas
        ),
        {"type": "response.output_item.done", "output_index": 0, "item": message},
        _completed([message]),
    )


def tool_reply(
    name: str, args: dict[str, Any], *, call_id: str = "call_1", namespace: str | None = None
) -> bytes:
    """A streamed function call, then response.completed."""
    item: dict[str, Any] = {
        "type": "function_call",
        "id": "fc_1",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(args),
        "status": "completed",
    }
    if namespace:
        item["namespace"] = namespace
    return sse(
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "arguments": ""},
        },
        {
            "type": "response.function_call_arguments.delta",
            "item_id": "fc_1",
            "output_index": 0,
            "delta": json.dumps(args),
        },
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        _completed([item]),
    )


def failed_after(text: str, code: str) -> bytes:
    """Some text streams, then the response fails with `code`: a usage limit
    can arrive this way, after streaming has begun."""
    return sse(
        {"type": "response.output_text.delta", "output_index": 0, "delta": text},
        {
            "type": "response.failed",
            "response": {
                "id": "resp_1",
                "status": "failed",
                "error": {"code": code, "message": "x"},
            },
        },
    )


CATALOGUE = {
    "models": [
        {"slug": "gpt-test-best", "display_name": "Best", "visibility": "list"},
        {"slug": "gpt-test-mini", "display_name": "Mini", "visibility": "list"},
    ]
}


class FakeOpenAI:
    """Answers each Responses request with the next reply in `replies`."""

    def __init__(self, *replies: Reply, models: dict[str, Any] | None = None) -> None:
        self.replies: list[Reply] = list(replies)
        self.models = models if models is not None else CATALOGUE
        self.requests: list[httpx.Request] = []

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path.endswith("/responses")]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx.Response(200, json=self.models)
        if not self.replies:
            raise AssertionError(f"FakeOpenAI has no reply left for {request.url}")
        reply = self.replies.pop(0)
        if callable(reply):
            reply = reply(json.loads(request.content))
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=reply)

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def client(
        self,
        route: ResponsesRoute = CHATGPT_ROUTE,
        *,
        session: Any = None,
        models: dict[str, str] | None = None,
    ) -> OpenAIResponsesClient:
        return OpenAIResponsesClient(
            route,
            session or StaticSession(),
            models=models or {"fast": "gpt-test-mini", "best": "gpt-test-best"},
            fingerprint=f"{route.provider}:test",
            http_factory=self.http,
        )


class StaticSession:
    """A bearer that renews to a new token when asked, and records usage limits."""

    def __init__(self, token: str = "test-access-token") -> None:
        self.token = token
        self.renewals = 0
        self.limited = 0

    async def bearer(self, force_refresh: bool = False) -> str:
        if force_refresh:
            self.renewals += 1
            return f"{self.token}-renewed-{self.renewals}"
        return self.token

    async def usage_limited(self) -> None:
        self.limited += 1


def api_key_client(fake: FakeOpenAI, key: str = "sk-test-key") -> OpenAIResponsesClient:
    return fake.client(API_KEY_ROUTE, session=ApiKeySession(Secret(key)))


class Signer:
    """An RSA key made for the test run (never committed), and ID tokens
    signed with it the way OpenAI signs them (RS256, with a `kid`)."""

    def __init__(self, kid: str = "test-key-1") -> None:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.kid = kid
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._pem = self._key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

    @property
    def jwk(self) -> dict[str, Any]:
        import base64

        numbers = self._key.public_key().public_numbers()

        def b64(value: int) -> str:
            raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        return {
            "kty": "RSA",
            "kid": self.kid,
            "use": "sig",
            "alg": "RS256",
            "n": b64(numbers.n),
            "e": b64(numbers.e),
        }

    def id_token(self, **claims: Any) -> str:
        import time

        from jose import jwt

        now = int(time.time())
        body: dict[str, Any] = {
            "iss": "https://auth.openai.com",
            "aud": "oaiapp_test",
            "sub": "user-sub-1",
            "email": "me@example.com",
            "iat": now,
            "exp": now + 3600,
        }
        body.update(claims)
        body = {k: v for k, v in body.items() if v is not None}
        return jwt.encode(body, self._pem, algorithm="RS256", headers={"kid": self.kid})


_SIGNER: Signer | None = None


def default_signer() -> Signer:
    """One key for the whole run: making an RSA key is slow."""
    global _SIGNER
    if _SIGNER is None:
        _SIGNER = Signer()
    return _SIGNER


class FakeAuthServer:
    """OpenAI's accounts service, enough of it: the authorization-code
    exchange (checking PKCE), rotating refresh tokens (each one works once, as
    OpenAI's do), revocation, the published signing keys, and `GET /v1/models`."""

    def __init__(self, *, refresh_token: str = "refresh-1", delay: float = 0.0) -> None:
        self.signer = default_signer()
        self.valid_refresh = refresh_token
        self.delay = delay
        self.refreshes: list[dict[str, str]] = []
        self.exchanges: list[dict[str, str]] = []
        self.revoked: list[dict[str, str]] = []
        self.model_requests: list[httpx.Request] = []
        self.jwks_fetches = 0
        self.revoke_status = 200
        self.models_status = 200
        #: Set to an OAuth error code to refuse every refresh with it.
        self.refuse_with: str | None = None
        self.fail_status: int | None = None
        self.grant_plan = True
        self.counter = 1
        #: code -> (code_challenge, redirect_uri, nonce, client_id): what an
        #: authorization request registered, for the exchange to check.
        self.codes: dict[str, tuple[str, str, str, str]] = {}
        self.id_claims: dict[str, Any] = {}

    def authorize(
        self, url: str, *, code: str = "code-1", client_id: str = "oaiapp_test"
    ) -> dict[str, str]:
        """What the browser comes back with, for an authorization URL: the
        query of the redirect to the loopback callback."""
        from urllib.parse import parse_qs, urlsplit

        params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        self.codes[code] = (
            params["code_challenge"],
            params["redirect_uri"],
            params["nonce"],
            client_id,
        )
        query = {"code": code, "state": params["state"], "scope": params["scope"]}
        if params["client_id"] == "dynamic_agent_client":
            query["client_id"] = client_id
        return query

    def _scope(self) -> str:
        scope = "openid profile email offline_access resource.invoke"
        return scope + (" chatgpt.tokens.use.direct" if self.grant_plan else "")

    async def handler(self, request: httpx.Request) -> httpx.Response:
        import asyncio
        from urllib.parse import parse_qsl

        from salli.adapters.llm.chatgpt_oauth import pkce_challenge

        path = request.url.path
        if path.endswith("/.well-known/jwks.json"):
            self.jwks_fetches += 1
            return httpx.Response(200, json={"keys": [self.signer.jwk]})
        if path.endswith("/v1/models"):
            self.model_requests.append(request)
            if self.models_status != 200:
                return httpx.Response(self.models_status, json={"detail": "no"})
            return httpx.Response(200, json=CATALOGUE)
        form = dict(parse_qsl(request.content.decode()))
        if path.endswith("/oauth/revoke"):
            self.revoked.append(form)
            return httpx.Response(self.revoke_status)
        assert path.endswith("/oauth/token"), request.url
        if form.get("grant_type") == "authorization_code":
            self.exchanges.append(form)
            known = self.codes.pop(form.get("code", ""), None)
            if known is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            challenge, redirect_uri, nonce, client_id = known
            assert pkce_challenge(form["code_verifier"]) == challenge
            assert form["redirect_uri"] == redirect_uri
            assert form["client_id"] == client_id
            assert form["resource"] == "https://api.openai.com/v1"
            claims = {"aud": client_id, "nonce": nonce, **self.id_claims}
            return httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": self.valid_refresh,
                    "id_token": self.signer.id_token(**claims),
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": self._scope(),
                },
            )
        if form.get("grant_type") != "refresh_token":
            raise AssertionError(f"unexpected grant {form.get('grant_type')}")
        self.refreshes.append(form)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_status:
            return httpx.Response(self.fail_status, json={"detail": "down"})
        if self.refuse_with:
            return httpx.Response(400, json={"error": self.refuse_with})
        if form.get("refresh_token") != self.valid_refresh:
            return httpx.Response(400, json={"error": "refresh_token_reused"})
        self.counter += 1
        self.valid_refresh = f"refresh-{self.counter}"
        return httpx.Response(
            200,
            json={
                "access_token": f"access-{self.counter}",
                "refresh_token": self.valid_refresh,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self._scope(),
            },
        )

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def oauth(self) -> Any:
        from salli.adapters.llm.chatgpt_oauth import ChatGPTOAuth

        async def no_sleep(_: float) -> None:
            return None

        return ChatGPTOAuth(self.http, sleep=no_sleep)
