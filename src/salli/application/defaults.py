"""
The defaults for the extension seams in application/ports.py.

Salli's own behaviour: nothing is metered and every user sees everything. An
extension (salli/extensions.py) can replace either one.
"""

from __future__ import annotations

from typing import Any

from salli.application.ports import EntitlementPolicy, PayloadView, Surface, UsageMeter
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
