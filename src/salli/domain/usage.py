"""
The vocabulary for gating AI work — pure domain, no I/O.

Salli itself never limits anything: every feature is available to every user,
and the default `UsageMeter` lets every action through. These names exist so a
deployment that *does* meter (a hosted service paying for inference on its
users' behalf) can do so through one seam, rather than through branches
scattered across routers and tools.

Lives in `domain/` because the agent tools need to catch `UsageLimitReached`,
and the domain must not import from `application/`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class AIAction(StrEnum):
    """Every place Salli spends model inference on a user's behalf.

    The values are stable identifiers, persisted by whatever meters them —
    rename a member if you like, but never change a value.
    """

    CHAT_MESSAGE = "agent_message"
    ENTRY_PARSE = "entry_parse"
    ADVISOR_RUN = "advisor_run"
    STATEMENT_IMPORT = "statement_upload"
    FIRE_STRATEGY = "fire_strategy"


class UsageLimitReached(Exception):
    """An installed `UsageMeter` refused an AI action.

    Salli never raises this itself. Whoever does decides what the user sees:

    - `message` is plain text for surfaces that can only show a sentence — the
      agent's own tools and the MCP server hand it straight to the model.
    - `status_code` and `detail` are what the HTTP API returns, verbatim, so a
      client that understands the meter's payload can act on it.
    """

    def __init__(
        self,
        action: AIAction,
        *,
        message: str,
        status_code: int = 429,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.action = action
        self.message = message
        self.status_code = status_code
        self.detail: dict[str, Any] = detail if detail is not None else {"error": message}
        super().__init__(message)
