"""The workflows' checkpointer when none is injected."""

from __future__ import annotations

from typing import Any


def checkpointer_or_memory(checkpointer: Any = None) -> Any:
    """Return `checkpointer`, or an in-memory one outside production.

    In memory, a briefing or return awaiting review and every conversation
    would vanish on a restart and escape the export and erasure, so production
    (ENVIRONMENT, as main.py reads it) refuses to build without PostgreSQL's.
    """
    if checkpointer is not None:
        return checkpointer
    from salli.config import get_settings

    if get_settings().environment == "production":
        raise RuntimeError("the PostgreSQL checkpointer is required in production")
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
