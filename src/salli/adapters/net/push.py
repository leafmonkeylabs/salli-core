"""
Push alerts through a relay (`SALLI_PUSH_RELAY_URL`): the deployment's
service that forwards Expo push messages to Apple's and Google's services,
so core never holds their keys. One POST per alert, a JSON list of Expo
messages, one per device the person registered; a 2xx answer is SENT.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import httpx

from salli.application.ports import Delivery, Notification, Notifier

_log = logging.getLogger(__name__)


class RelayPushNotifier(Notifier):
    def __init__(
        self,
        relay_url: str,
        uow_factory: Callable[[], Any],
        open_token: Callable[[dict[str, Any]], str],
        *,
        timeout: float = 10.0,
    ) -> None:
        self._url = relay_url
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
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=messages)
        except httpx.HTTPError as exc:
            _log.warning("push_relay_failed error=%s", type(exc).__name__)
            return Delivery.FAILED
        if response.is_success:
            return Delivery.SENT
        _log.warning("push_relay_refused status=%s", response.status_code)
        return Delivery.FAILED
