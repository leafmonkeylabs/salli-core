"""
Push alerts through a relay (`SALLI_PUSH_RELAY_URL`): the deployment's
service that forwards Expo push messages to Apple's and Google's services,
so core never holds their keys. One POST per alert, a JSON list of Expo
messages, one per device the person registered; a 2xx answer is SENT.

The relay must be HTTPS (plain HTTP only to this machine, in development),
and each POST carries `Authorization: Bearer t=<unix seconds>,v1=<hex>`,
where v1 is HMAC-SHA256 under SALLI_PUSH_RELAY_SECRET of `<t>.<body>`: the
relay recomputes it over the raw body and refuses a stale `t`
(docs/self-host.md#push-alerts).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from salli.application.ports import Delivery, Notification, Notifier
from salli.config import is_secure_origin

_log = logging.getLogger(__name__)


def relay_problem(url: str, secret: str, environment: str) -> str | None:
    """Why this relay can't be used, or None."""
    if not url.startswith("https://") and not (
        environment == "development" and is_secure_origin(url)
    ):
        return "SALLI_PUSH_RELAY_URL must be https:// (http only to localhost in development)"
    if not secret:
        return "SALLI_PUSH_RELAY_SECRET is needed with SALLI_PUSH_RELAY_URL"
    return None


def relay_authorization(secret: str, body: bytes, at: int) -> str:
    """The bearer the relay checks: when, and an HMAC of when and the body."""
    mac = hmac.new(secret.encode(), f"{at}.".encode() + body, hashlib.sha256).hexdigest()
    return f"Bearer t={at},v1={mac}"


class RelayPushNotifier(Notifier):
    def __init__(
        self,
        relay_url: str,
        uow_factory: Callable[[], Any],
        open_token: Callable[[dict[str, Any]], str],
        *,
        secret: str,
        timeout: float = 10.0,
    ) -> None:
        self._url = relay_url
        self._secret = secret
        self._uow_factory = uow_factory
        self._open = open_token
        self._timeout = timeout

    async def send(self, notification: Notification) -> Delivery:
        async with self._uow_factory() as uow:
            devices = await uow.notifications.devices(notification.user_id)
        if not devices:
            return Delivery.NO_DESTINATION
        messages = [
            {
                "to": self._open(device),
                "title": notification.subject,
                "body": notification.text,
                "data": {"id": notification.id, "link": notification.link},
            }
            for device in devices
        ]
        body = json.dumps(messages).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": relay_authorization(self._secret, body, int(time.time())),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            _log.warning("push_relay_failed error=%s", type(exc).__name__)
            return Delivery.FAILED
        if response.is_success:
            return Delivery.SENT
        _log.warning("push_relay_refused status=%s", response.status_code)
        return Delivery.FAILED
