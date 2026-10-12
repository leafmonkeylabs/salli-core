"""
The defaults for the extension seams in application/ports.py.

Salli's own behaviour: nothing is metered, every user sees everything, anyone
may use their ChatGPT plan, and nothing is sent. An extension
(salli/extensions.py) can replace any of them.
"""

from __future__ import annotations

from typing import Any

from salli.application.ports import (
    ChatGPTPlanPolicy,
    Delivery,
    EntitlementPolicy,
    Notification,
    Notifier,
    PayloadView,
    Surface,
    UsageMeter,
)
from salli.domain.usage import AIAction


class UnmeteredUsage(UsageMeter):
    """Every AI action is allowed."""

    async def charge(
        self,
        user_id: str,
        action: AIAction,
        *,
        model_id: str | None = None,
        email: str | None = None,
    ) -> None:
        return None


class _FullView:
    def shape(self, surface: Surface, payload: dict[str, Any]) -> dict[str, Any]:
        return payload


class FullAccess(EntitlementPolicy):
    """Every user sees every surface exactly as the service computed it."""

    _VIEW = _FullView()

    async def for_user(self, user_id: str, email: str | None = None) -> PayloadView:
        return self._VIEW


class ChatGPTPlanAllowed(ChatGPTPlanPolicy):
    """Every user may use their ChatGPT plan, as an open-source, self-hosted
    app may offer it (Settings.salli_chatgpt_plan_usage can still turn it off)."""

    async def allows(self, user_id: str) -> bool:
        return True


class NoNotifier(Notifier):
    """Sends nothing: Salli ships no sender. Preferences still save and the
    preview still works, so a person can set up their digest before the
    operator enables a notifier; the digest job sends nothing without one."""

    async def send(self, notification: Notification) -> Delivery:
        return Delivery.NO_DESTINATION
