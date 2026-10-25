"""The push relay: HTTPS only, and every post signed over its body."""

from __future__ import annotations

import hashlib
import hmac
from contextlib import asynccontextmanager

import httpx
import pytest

from salli.adapters.net import push
from salli.application.ports import Delivery, Notification


@pytest.mark.parametrize(
    ("url", "secret", "environment", "ok"),
    [
        ("https://relay.example.org/push", "s", "production", True),
        ("http://relay.example.org/push", "s", "production", False),
        ("http://localhost:9000/push", "s", "production", False),
        ("http://localhost:9000/push", "s", "development", True),
        ("http://relay.example.org/push", "s", "development", False),
        ("https://relay.example.org/push", "", "production", False),
    ],
)
def test_the_relay_must_be_https_and_have_a_secret(url, secret, environment, ok):
    assert (push.relay_problem(url, secret, environment) is None) is ok


async def test_each_post_carries_a_bearer_signed_over_its_body(monkeypatch):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        push.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )

    @asynccontextmanager
    async def uow_factory():
        class Notes:
            async def devices(self, user_id):
                return [{"token": "sealed"}]

        class Uow:
            notifications = Notes()

        yield Uow()

    notifier = push.RelayPushNotifier(
        "https://relay.example.org/push", uow_factory, lambda d: "ExponentPushToken[a]", secret="k"
    )
    note = Notification(
        id="n1", user_id="u", kind="push", period="p", subject="s", text="t", items=(), link=None
    )
    assert await notifier.send(note) == Delivery.SENT
    (request,) = seen
    scheme, value = request.headers["authorization"].split(" ", 1)
    fields = dict(part.split("=", 1) for part in value.split(","))
    expected = hmac.new(b"k", f"{fields['t']}.".encode() + request.content, hashlib.sha256)
    assert scheme == "Bearer" and hmac.compare_digest(fields["v1"], expected.hexdigest())
