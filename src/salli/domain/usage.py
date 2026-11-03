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

import re
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Offer:
    """What a refused person may do next, in the extension's own words.

    Carried by `UsageLimitReached` and `CapabilityRefused` and shown in the
    problem as `offer`: `label` is the button, `panel` the id of a panel
    (docs/design/panels.md) the clients open for it. Core never writes one.
    """

    title: str
    detail: str
    label: str
    panel: str

    def as_json(self) -> dict[str, str]:
        return {
            "title": self.title,
            "detail": self.detail,
            "label": self.label,
            "panel": self.panel,
        }


_PROBLEM_TYPE = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _problem_type(wanted: str | None, default: str) -> str:
    return wanted if wanted and _PROBLEM_TYPE.fullmatch(wanted) else default


class UsageLimitReached(Exception):
    """An installed `UsageMeter` refused an AI action.

    Salli never raises this itself. Whoever does decides what the user sees:

    - `message` is plain text for surfaces that can only show a sentence — the
      agent's own tools and the MCP server hand it straight to the model.
    - `status_code` and `detail` are what the HTTP API returns, verbatim, so a
      client that understands the meter's payload can act on it.
    - `offer` says what the person may do about it (shown as the problem's
      `offer`), and `problem_type` is the problem's own type under
      `/problems/` (a lower-case slug) when the extension has a name for it.
    """

    problem_type = "usage-limit"

    def __init__(
        self,
        action: AIAction,
        *,
        message: str,
        status_code: int = 429,
        detail: dict[str, Any] | None = None,
        offer: Offer | None = None,
        problem_type: str | None = None,
    ) -> None:
        self.action = action
        self.offer = offer
        self.problem_type = _problem_type(problem_type, type(self).problem_type)
        self.message = message
        self.status_code = status_code
        self.detail: dict[str, Any] = detail if detail is not None else {"error": message}
        super().__init__(message)


class CapabilityRefused(Exception):
    """The deployment's entitlement policy does not allow what was asked
    (`PayloadView.allows`). The API answers 403 `/problems/capability-refused`
    with the `capability` and the `offer`, if the policy gave one."""

    def __init__(self, capability: str, offer: Offer | None = None) -> None:
        self.capability = capability
        self.offer = offer
        super().__init__(f"{capability} is not available here.")
