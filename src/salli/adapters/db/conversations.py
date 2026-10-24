"""
CheckpointConversations — a person's conversations with Salli's AI as the
agents' checkpointer (LangGraph's AsyncPostgresSaver, in the same database)
keeps them: read for their export, deleted with their account.

Every thread the agents write starts with the user's id: chat's are
"{user id}:{thread}", the review workflows' "{user id}:{workflow}:{thread}"
(application/services/agent_service.py). So a person's threads are those
whose id starts with "{user id}:"; Salli's user ids are UUIDs, so no one's
prefix is the start of another's.
"""

from __future__ import annotations

from typing import Any, cast

from salli.application.ports import ConversationStore

# Every table the checkpointer writes a thread to, so nothing is missed.
_THREADS = """
    select thread_id from checkpoints where starts_with(thread_id, %(prefix)s)
    union select thread_id from checkpoint_blobs where starts_with(thread_id, %(prefix)s)
    union select thread_id from checkpoint_writes where starts_with(thread_id, %(prefix)s)
"""

_ROLES = {"human": "user", "ai": "assistant"}


def _text(content: str | list[Any]) -> str:
    if isinstance(content, str):
        return content.strip()
    blocks = [cast(dict[str, Any], b) for b in content if isinstance(b, dict)]
    return " ".join(
        str(b.get("text", "")).strip() for b in blocks if b.get("type") == "text"
    ).strip()


def _message(message: Any) -> dict[str, Any] | None:
    """The person's and the assistant's words, and the tools it called by
    name. Tool results and system text are not the conversation."""
    role = _ROLES.get(getattr(message, "type", ""))
    if role is None:
        return None
    text = _text(message.content)
    calls: list[dict[str, Any]] = getattr(message, "tool_calls", None) or []
    tools = [str(call["name"]) for call in calls]
    if not text and not tools:
        return None
    return {"role": role, "text": text, "tools": tools}


class CheckpointConversations(ConversationStore):
    def __init__(self, checkpointer: Any) -> None:
        self._saver = checkpointer

    async def _threads(self, user_id: str) -> list[str]:
        # The checkpointer has no way to list threads; its own cursor (its
        # lock and connection) reads its tables.
        async with self._saver._cursor() as cur:
            await cur.execute(_THREADS, {"prefix": f"{user_id}:"})
            return [row["thread_id"] for row in await cur.fetchall()]

    async def export(self, user_id: str) -> list[dict[str, Any]]:
        prefix = f"{user_id}:"
        conversations: list[dict[str, Any]] = []
        for thread_id in await self._threads(user_id):
            saved = await self._saver.aget_tuple({"configurable": {"thread_id": thread_id}})
            if saved is None:
                continue
            values = saved.checkpoint["channel_values"]
            messages = [m for m in map(_message, values.get("messages") or []) if m]
            # A review workflow's thread holds its working state, made from
            # the data the export already has, and no messages.
            if messages:
                conversations.append(
                    {
                        "thread_id": thread_id.removeprefix(prefix),
                        "updated_at": saved.checkpoint["ts"],
                        "messages": messages,
                    }
                )
        return sorted(conversations, key=lambda c: c["updated_at"], reverse=True)

    async def delete_all(self, user_id: str) -> int:
        threads = await self._threads(user_id)
        for thread_id in threads:
            await self._saver.adelete_thread(thread_id)
        return len(threads)
