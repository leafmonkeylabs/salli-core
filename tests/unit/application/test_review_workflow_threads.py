"""Review workflows (the monthly briefing, the return) on a real in-memory
checkpointer: a thread belongs to the user who started it, whatever thread id
another user sends."""

from __future__ import annotations

from typing import Any

import pytest

from salli.application.services.agent_service import AgentService
from salli.domain.agents.advisor import Advice

pytestmark = pytest.mark.asyncio


class FakeAdvisor:
    """The parts of AdvisorService the briefing workflow calls."""

    def __init__(self) -> None:
        self.gathered: list[str] = []
        self.persisted: list[str] = []

    async def gather_context(self, user_id: str, email: str | None) -> dict[str, Any]:
        self.gathered.append(user_id)
        return {"currency": "LKR"}

    async def llm_for(self, user_id: str) -> None:
        return None

    async def persist_report(self, user_id: str, trigger: str, advice: Advice) -> dict[str, Any]:
        self.persisted.append(user_id)
        return {"id": f"report-for-{user_id}", "summary": advice.summary}


@pytest.fixture
def advisor(monkeypatch) -> FakeAdvisor:
    async def generate_advice(context: dict[str, Any], llm: Any = None) -> Advice:
        return Advice(summary="A's month", fire_tier_assessment="Tier 2", recommendations=[])

    monkeypatch.setattr("salli.domain.agents.advisor.generate_advice", generate_advice)
    return FakeAdvisor()


@pytest.fixture
def agent(advisor: FakeAdvisor) -> AgentService:
    # No checkpointer passed: the workflows fall back to a MemorySaver, which
    # keeps state across prepare and resume exactly as Postgres does.
    return AgentService(ledger_svc=None, tax_svc=None, advisor_svc=advisor)


async def test_a_briefing_thread_is_kept_under_its_owner_and_handed_back_as_sent(agent):
    prepared = await agent.prepare_briefing("user-a", None, thread_id="thread-1")

    assert prepared["thread_id"] == "thread-1"
    workflow = agent._get_briefing_workflow()
    owned = await workflow.aget_state({"configurable": {"thread_id": "user-a:thread-1"}})
    bare = await workflow.aget_state({"configurable": {"thread_id": "thread-1"}})
    assert owned.next == ("review",)
    assert bare.next == ()


async def test_another_user_resuming_a_briefing_thread_approves_nothing_of_the_owners(
    agent, advisor
):
    await agent.prepare_briefing("user-a", None, thread_id="thread-1")

    stolen = await agent.resume_briefing("user-b", "thread-1", "approve")

    assert stolen["report"] == {}
    assert stolen["error"]
    assert advisor.persisted == []
    # Nothing ran for user B either: no gather, no model call.
    assert advisor.gathered == ["user-a"]

    # The owner's draft is still waiting, and is theirs to approve.
    mine = await agent.resume_briefing("user-a", "thread-1", "approve")
    assert mine["report"]["id"] == "report-for-user-a"
    assert advisor.persisted == ["user-a"]


async def test_resuming_a_briefing_that_was_never_prepared_runs_nothing(agent, advisor):
    result = await agent.resume_briefing("user-a", "no-such-thread", "approve")

    assert result["report"] == {}
    assert result["error"]
    assert advisor.gathered == []
    assert advisor.persisted == []
