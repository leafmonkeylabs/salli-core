"""Unit tests for AgentService's message-construction helpers (no LLM calls)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from salli.application.services.agent_service import AgentService


def _service() -> AgentService:
    # ledger_svc/tax_svc are unused by _build_input_messages — pass placeholders.
    return AgentService(ledger_svc=None, tax_svc=None)


@pytest.mark.asyncio
async def test_neutral_message_has_no_tone_system_message():
    svc = _service()
    messages = await svc._build_input_messages("u1", "What's my account balance?")

    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)


@pytest.mark.asyncio
async def test_frustrated_message_prepends_tone_system_message():
    svc = _service()
    messages = await svc._build_input_messages("u1", "This is so frustrating, nothing works!!!")

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert "acknowledge" in messages[0].content.lower()
    assert isinstance(messages[1], HumanMessage)


@pytest.mark.asyncio
async def test_anxious_message_prepends_tone_system_message():
    svc = _service()
    messages = await svc._build_input_messages("u1", "I'm so worried about my debt")

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert "reassur" in messages[0].content.lower()


@pytest.mark.asyncio
async def test_positive_message_prepends_tone_system_message():
    svc = _service()
    messages = await svc._build_input_messages("u1", "Thank you, this is awesome!")

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert "momentum" in messages[0].content.lower()


@pytest.mark.asyncio
async def test_human_message_content_is_preserved():
    svc = _service()
    messages = await svc._build_input_messages("u1", "I'm worried about my savings")

    human = messages[-1]
    assert isinstance(human, HumanMessage)
    assert human.content == "I'm worried about my savings"


# ── Persona is server-owned on resume/replay ─────────────────────────────────


class _FakeSessionRepo:
    def __init__(self, session: dict | None) -> None:
        self._session = session

    async def get(self, user_id: str, thread_id: str) -> dict | None:
        return self._session


class _FakeUoW:
    def __init__(self, session: dict | None) -> None:
        self.agent_sessions = _FakeSessionRepo(session)

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _service_with_session(session: dict | None) -> AgentService:
    return AgentService(ledger_svc=None, tax_svc=None, uow_factory=lambda: _FakeUoW(session))


@pytest.mark.asyncio
async def test_stored_persona_wins_over_the_requested_one():
    """A client resuming a buddy thread without echoing persona must not get the
    scrooge graph. Both graphs have identical topology, so the mismatch wouldn't
    raise — it would silently run the wrong prompt over a pending write approval."""
    svc = _service_with_session({"persona": "buddy"})
    assert await svc._persona_for_thread("u1", "t1", "scrooge") == "buddy"


@pytest.mark.asyncio
async def test_falls_back_when_the_thread_predates_session_tracking():
    svc = _service_with_session(None)
    assert await svc._persona_for_thread("u1", "t1", "buddy") == "buddy"


@pytest.mark.asyncio
async def test_unknown_stored_persona_falls_back_rather_than_picking_no_graph():
    svc = _service_with_session({"persona": "not-a-persona"})
    assert await svc._persona_for_thread("u1", "t1", "buddy") == "buddy"


@pytest.mark.asyncio
async def test_no_db_falls_back_to_the_requested_persona():
    svc = AgentService(ledger_svc=None, tax_svc=None)
    assert await svc._persona_for_thread("u1", "t1", "buddy") == "buddy"


# ── Provider failures must reach the client ──────────────────────────────────


class _Boom:
    """A graph whose stream raises the way a rejected API key does."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def astream_events(self, *_a, **_kw):
        raise self._exc
        yield  # pragma: no cover - makes this an async generator

    async def aget_state(self, *_a, **_kw):
        raise AssertionError("should not be reached")


@pytest.mark.asyncio
async def test_a_provider_failure_emits_an_error_event_not_just_done():
    """Regression: _stream_events' `finally` yields ("done", None), and a yield
    inside a finally while an exception propagates *discards* that exception. So
    the old `raise` never reached the router and the client got a clean `done`
    with no reply and no explanation — a provider 401 looked exactly like a
    successful empty answer. Found by smoke-testing against a real key.
    """
    svc = _service()
    events = [
        e
        async for e in svc._stream_events(
            _Boom(RuntimeError("Error code: 401 - authentication_error")), "in", {}
        )
    ]
    kinds = [k for k, _ in events]

    assert "error" in kinds, f"a provider failure produced only {kinds}"
    assert kinds[-1] == "done"


@pytest.mark.asyncio
async def test_the_error_message_is_actionable_and_carries_no_key():
    from salli.application.services.agent_service import _provider_error_message

    msg = _provider_error_message(
        RuntimeError("Error code: 401 - invalid x-api-key: sk-ant-api03-LEAKED9999")
    )
    assert "sk-ant-api03-LEAKED9999" not in msg
    assert "Settings" in msg  # tells a BYOK user where to fix it


@pytest.mark.asyncio
async def test_rate_limits_and_credit_get_their_own_wording():
    from salli.application.services.agent_service import _provider_error_message

    assert "rate-limit" in _provider_error_message(RuntimeError("429 rate_limit_error"))
    assert "credit" in _provider_error_message(RuntimeError("400 insufficient credit balance"))


@pytest.mark.asyncio
async def test_an_unrecognised_failure_still_gets_a_generic_message():
    from salli.application.services.agent_service import _provider_error_message

    msg = _provider_error_message(RuntimeError("something odd"))
    assert "something odd" not in msg  # never echo the raw text
    assert msg
