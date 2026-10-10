"""The return workflow: forms from the user's own rules, filled in by the
engine, reviewed by the user. The LLM never runs in it."""

from __future__ import annotations

from typing import Any

import pytest

from salli.application.services.agent_service import AgentService
from salli.domain.agents.return_workflow import ReturnState, _build_draft, _finalize
from tests.tax_views import computation_view

FORM = {
    "key": "return",
    "label": "Annual return",
    "instructions": "Sign in to the authority's portal and enter each box.",
    "url": "https://example.org/file",
    "fields": [{"id": "box_1", "label": "Tax", "value": "3000"}],
}


class FakeTax:
    """TaxService.prepare_return, recording each call."""

    def __init__(self, *, forms: list[dict[str, Any]] | None = None, error: str = "") -> None:
        self.forms = [FORM] if forms is None else forms
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def prepare_return(self, user_id: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"user_id": user_id, **kwargs})
        if self.error:
            return {"error": self.error}
        income = (kwargs.get("answers") or {}).get("income", "25000")
        view = computation_view(income=income)
        if not self.forms:
            return {"error": "Your rules define no return form", "computation": view}
        return {
            "error": "",
            "country": view["country"],
            "region": view["region"],
            "year": view["year"],
            "computation": view,
            "forms": self.forms,
        }


@pytest.fixture
def tax() -> FakeTax:
    return FakeTax()


@pytest.fixture
def agent(tax: FakeTax) -> AgentService:
    # No checkpointer: the workflow falls back to a MemorySaver, which keeps
    # state across prepare and resume exactly as Postgres does.
    return AgentService(ledger_svc=None, tax_svc=tax)


async def test_preparing_stops_at_review_with_the_rules_forms(agent, tax):
    prepared = await agent.prepare_return("u1", thread_id="t1")

    draft = prepared["draft_return"]
    assert prepared["error"] == ""
    assert draft["forms"] == [FORM]
    assert draft["year"] == "2031" and draft["country"] == "XZ"
    assert draft["computation_id"] == "computation-1"
    assert (draft["version"], draft["tax_payable"]) == (2, "3000.00")
    assert "Salli doesn't vouch for the law" in draft["note"]
    # The jurisdiction and year are derived by the service: none given.
    assert tax.calls == [
        {"user_id": "u1", "country": None, "region": None, "year": None, "answers": {}}
    ]


async def test_approving_gives_the_worksheet_ready_to_file(agent):
    await agent.prepare_return("u1", thread_id="t1")

    resumed = await agent.resume_return("u1", "t1", "approve")

    worksheet = resumed["worksheet"]
    assert resumed["error"] == "" and resumed["draft_return"] == {}
    assert worksheet["status"] == "ready_to_file"
    assert worksheet["forms"][0]["instructions"].startswith("Sign in")
    assert worksheet["forms"][0]["url"] == "https://example.org/file"


async def test_the_draft_waiting_for_review_can_be_read_back_by_its_owner_only(agent):
    prepared = await agent.prepare_return("u1", thread_id="t1")

    mine = await agent.get_return("u1", "t1")
    assert mine["waiting"] is True
    assert mine["draft_return"] == prepared["draft_return"]
    assert await agent.get_return("u2", "t1") == {
        "thread_id": "t1",
        "waiting": False,
        "draft_return": {},
    }

    await agent.resume_return("u1", "t1", "approve")
    assert (await agent.get_return("u1", "t1"))["waiting"] is False


async def test_rejecting_files_nothing(agent):
    await agent.prepare_return("u1", thread_id="t1")

    resumed = await agent.resume_return("u1", "t1", "reject")

    assert resumed["worksheet"] == {}
    assert "not approved" in resumed["error"]


async def test_editing_computes_again_with_the_new_answers_and_reviews_again(agent, tax):
    await agent.prepare_return("u1", year="2031", country="XZ", thread_id="t1")

    edited = await agent.resume_return("u1", "t1", "edit", answers={"income": "35000"})

    # The same return (its year and country kept), the answers merged in.
    assert tax.calls[-1] == {
        "user_id": "u1",
        "country": "XZ",
        "region": None,
        "year": "2031",
        "answers": {"income": "35000"},
    }
    assert edited["worksheet"] == {}
    assert edited["draft_return"]["tax_payable"] == "5000.00"

    approved = await agent.resume_return("u1", "t1", "approve")
    assert approved["worksheet"]["tax_payable"] == "5000.00"


async def test_rules_without_forms_have_no_return(agent):
    no_forms = AgentService(ledger_svc=None, tax_svc=FakeTax(forms=[]))
    prepared = await no_forms.prepare_return("u1", thread_id="t1")

    assert prepared["draft_return"] == {}
    assert "no return form" in prepared["error"]
    assert (await no_forms.resume_return("u1", "t1", "approve"))["error"]


async def test_no_active_rules_is_said_in_the_services_words():
    none = AgentService(ledger_svc=None, tax_svc=FakeTax(error="You have no tax rules for GB."))
    prepared = await none.prepare_return("u1", thread_id="t1")

    assert prepared == {
        "thread_id": "t1",
        "draft_return": {},
        "error": "You have no tax rules for GB.",
    }


async def test_an_unexpected_failure_keeps_only_its_class():
    class Broken:
        async def prepare_return(self, user_id, **kwargs):
            raise RuntimeError("provider said: sk-secret")

    prepared = await AgentService(ledger_svc=None, tax_svc=Broken()).prepare_return(
        "u1", thread_id="t1"
    )
    assert prepared["error"] == "RuntimeError"


def test_the_draft_carries_no_figure_the_engine_did_not_produce():
    state = ReturnState(user_id="u1", computation=computation_view(), forms=[FORM])
    draft = _build_draft(state)["draft_return"]
    assert draft["lines"] == computation_view()["lines"]
    assert draft["forms"] == [FORM]


def test_finalize_needs_an_approval():
    state = ReturnState(draft_return={"year": "2031"}, review_decision="edit")
    assert _finalize(state) == {"worksheet": {}, "error": "Return not approved (decision: edit)"}


def test_agent_service_builds_the_workflow_lazily(tax):
    svc = AgentService(None, tax)
    assert svc._workflow is None
    assert svc._get_workflow() is svc._get_workflow()
