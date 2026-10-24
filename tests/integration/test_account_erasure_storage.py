"""
Erase then search: a person's conversations in LangGraph's checkpoint tables
and their uploaded files are exported, then gone after the account is
erased, and someone else's are not touched.
"""

from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from sqlalchemy.engine import make_url

from salli.adapters.db.conversations import CheckpointConversations
from salli.adapters.storage.local import LocalStorageAdapter
from salli.application.services.data_portability_service import DataPortabilityService
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

ERASED = "6f1d2c3b-4a5e-4f60-8b7a-9c0d1e2f3a4b"
KEPT = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"


def _reply(state: MessagesState) -> dict[str, list]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "search_entries", "args": {"text": "bakery"}, "id": "c1"}],
            ),
            ToolMessage(content='{"total": "41.20"}', tool_call_id="c1", name="search_entries"),
            AIMessage(content=[{"type": "text", "text": "Your bakery entries are listed."}]),
        ]
    }


def _graph(saver: AsyncPostgresSaver):
    graph = StateGraph(MessagesState)
    graph.add_node("reply", _reply)
    graph.add_edge(START, "reply")
    graph.add_edge("reply", END)
    return graph.compile(checkpointer=saver)


async def _thread_rows(saver: AsyncPostgresSaver, prefix: str) -> int:
    async with saver._cursor() as cur:
        await cur.execute(
            "select (select count(*) from checkpoints where starts_with(thread_id, %(p)s))"
            " + (select count(*) from checkpoint_blobs where starts_with(thread_id, %(p)s))"
            " + (select count(*) from checkpoint_writes where starts_with(thread_id, %(p)s))"
            " as n",
            {"p": prefix},
        )
        row = await cur.fetchone()
    assert row is not None
    return row["n"]


async def test_erase_then_search_finds_nothing(db, uow_factory, tmp_path):
    url = make_url(db).set(drivername="postgresql").render_as_string(hide_password=False)
    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        await saver.setup()
        graph = _graph(saver)
        for user in (ERASED, KEPT):
            await graph.ainvoke(
                {"messages": [HumanMessage("What did I spend at the bakery?")]},
                {"configurable": {"thread_id": f"{user}:t1"}},
            )
        # A review workflow's thread: the same checkpointer, no messages.
        await graph.aupdate_state(
            {"configurable": {"thread_id": f"{ERASED}:briefing:b1"}}, {"messages": []}
        )

        storage = LocalStorageAdapter(tmp_path / "storage")
        await storage.upload(ERASED, "stmt-1/october.csv", b"date,amount")
        kept_file = await storage.upload(KEPT, "stmt-2/october.csv", b"date,amount")
        conversations = CheckpointConversations(saver)

        [exported] = await conversations.export(ERASED)
        assert exported["thread_id"] == "t1"
        assert exported["messages"] == [
            {"role": "user", "text": "What did I spend at the bakery?", "tools": []},
            {"role": "assistant", "text": "", "tools": ["search_entries"]},
            {"role": "assistant", "text": "Your bakery entries are listed.", "tools": []},
        ]

        service = DataPortabilityService(
            uow_factory,
            SimpleNamespace(forget=lambda user_id: None),
            *([None] * 11),
            storage=storage,
            conversations=conversations,
        )
        counts = await service.delete_account(ERASED)

        assert counts["stored_files"] == 1
        assert counts["conversations"] == 2
        assert await _thread_rows(saver, f"{ERASED}:") == 0
        assert await conversations.export(ERASED) == []
        assert not (tmp_path / "storage" / ERASED).exists()

        assert await _thread_rows(saver, f"{KEPT}:") > 0
        assert [c["thread_id"] for c in await conversations.export(KEPT)] == ["t1"]
        assert await storage.download(kept_file) == b"date,amount"
