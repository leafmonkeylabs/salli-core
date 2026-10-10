"""
The agent's JSON routes answer with the shapes the service builds, and the
two streams are documented as streams, naming every event they can send.
"""

from __future__ import annotations

import inspect
import re
from types import SimpleNamespace
from typing import Any, get_args
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from salli.application.services.agent_service import AgentService
from salli.interfaces.api.routers import agent as agent_router

from .conftest import AUTH

USER = "test-user-1"


class _StateReader:
    """Stands in for the compiled graph get_history reads checkpoints through."""

    def __init__(self, messages: list[Any]) -> None:
        self._messages = messages

    async def aget_state(self, config: dict[str, Any]) -> Any:
        return SimpleNamespace(values={"messages": self._messages})


def _service_with_history(messages: list[Any]) -> AgentService:
    service = AgentService(ledger_svc=None, tax_svc=None)
    service._state_reader = _StateReader(messages)
    return service


def _a_turn_with_a_specialist() -> list[Any]:
    return [
        HumanMessage(content="What's my tax?"),
        AIMessage(
            content="Let me check.",
            tool_calls=[{"name": "transfer_to_tax_specialist", "args": {}, "id": "c1"}],
        ),
        ToolMessage(content="Transferred", tool_call_id="c1"),
        AIMessage(
            content="",
            name="tax_specialist",
            tool_calls=[{"name": "compute_tax", "args": {"year": "2025/26"}, "id": "c2"}],
        ),
        ToolMessage(content="{}", tool_call_id="c2"),
        AIMessage(content="Taxable income is 3,000,000.", name="tax_specialist"),
        AIMessage(
            content="Transferring back.",
            name="tax_specialist",
            tool_calls=[{"name": "transfer_back_to_supervisor", "args": {}, "id": "c3"}],
        ),
        AIMessage(content="You owe 120,000."),
    ]


async def test_history_is_the_conversation_the_service_rebuilds(client, mock_services):
    service = _service_with_history(_a_turn_with_a_specialist())
    expected = await service.get_history(user_id=USER, thread_id="t-1")
    mock_services.agent = service

    r = await client.get("/v1/agent/history/t-1", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == {"thread_id": "t-1", "messages": expected}


async def test_history_keeps_its_part_shapes(client, mock_services):
    """Top-level text is `text`; a specialist's text inside its section is
    `token`. Both apps render them by those names."""
    mock_services.agent = _service_with_history(_a_turn_with_a_specialist())

    messages = (await client.get("/v1/agent/history/t-1", headers=AUTH)).json()["messages"]

    assert messages[0] == {"role": "user", "content": "What's my tax?"}
    parts = messages[1]["parts"]
    assert [p["type"] for p in parts] == ["text", "tool_call", "subagent_section", "text"]
    section = parts[2]
    assert (section["agent"], section["active"]) == ("tax_specialist", False)
    assert section["parts"] == [
        {"type": "tool_call", "name": "compute_tax", "input": {"year": "2025/26"}, "done": True},
        {"type": "token", "content": "Taxable income is 3,000,000."},
    ]


async def test_sessions_are_listed_as_stored(client, mock_services):
    session = {
        "id": "s-1",
        "user_id": USER,
        "thread_id": "t-1",
        "title": None,
        "persona": "buddy",
        "created_at": "2026-10-09T08:30:00+00:00",
        "last_active_at": "2026-10-09T08:31:00+00:00",
    }
    mock_services.agent.list_sessions.return_value = [session]

    r = await client.get("/v1/agent/sessions?persona=buddy", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == {"sessions": [session]}


async def test_the_audit_log_is_listed_as_stored(client, mock_services):
    entry = {
        "id": "l-1",
        "user_id": USER,
        "action": "post_journal_entry",
        "params": {"amount": "10000.00", "currency": "LKR"},
        "decision": "denied",
        "created_at": "2026-10-09T08:30:00+00:00",
    }
    mock_services.agent.get_audit_log.return_value = [entry]

    r = await client.get("/v1/agent/audit-log", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == {"entries": [entry]}


async def test_an_uploaded_file_comes_back_as_its_reference(client, mock_services):
    mock_services.documents = AsyncMock()
    mock_services.documents.save_file.return_value = {
        "id": "d-1",
        "title": "statement.pdf",
        "storage_key": f"{USER}/agent-uploads/d-1/statement.pdf",
        "mime_type": "application/pdf",
    }

    r = await client.post(
        "/v1/agent/files",
        files={"file": ("statement.pdf", b"%PDF-1.7", "application/pdf")},
        headers=AUTH,
    )

    assert r.status_code == 200
    assert r.json() == {
        "file_ref": "d-1",
        "name": "statement.pdf",
        "size": 8,
        "mime_type": "application/pdf",
    }


async def test_agent_resume_is_for_chat_only(client, mock_services):
    """A return is reviewed through /v1/tax/returns/resume; asking the agent
    route for one resumes nothing of it."""

    async def nothing(**kwargs):
        return
        yield

    mock_services.agent.resume_chat = MagicMock(side_effect=lambda **kw: nothing(**kw))
    r = await client.post(
        "/v1/agent/resume",
        json={"thread_id": "thread-1", "decision": "approved", "workflow": "return"},
        headers=AUTH,
    )

    assert r.status_code == 200
    mock_services.agent.resume_return.assert_not_awaited()
    assert mock_services.agent.resume_chat.call_args.kwargs["thread_id"] == "thread-1"


def test_the_api_speaks_every_persona_the_service_can_build():
    assert set(get_args(agent_router.Persona)) == set(AgentService._PERSONA_BUILDERS)


async def test_the_streams_are_documented_as_streams_with_every_event(client):
    """Clients generated from the schema learn the event vocabulary from it, so
    an event the router can send must be in the description."""
    sent = set(re.findall(r'"type": "(\w+)"', inspect.getsource(agent_router._emit_events)))
    assert {"token", "approval_required", "error", "done"} <= sent

    paths = (await client.get("/openapi.json")).json()["paths"]
    for path in ("/v1/agent/chat", "/v1/agent/resume"):
        ok = paths[path]["post"]["responses"]["200"]
        assert list(ok["content"]) == ["text/event-stream"], path
        assert {t for t in sent if f"`{t}`" not in ok["description"]} == set(), path
