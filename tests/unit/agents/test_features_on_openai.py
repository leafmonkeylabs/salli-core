"""
Every AI feature, run on a stand-in for OpenAI (httpx.MockTransport) through
the ChatGPT plan route: statement sorting, quick add, the FIRE strategy, the
advisor and its briefing, naming a conversation, and the chat agent with its
tools. Each request it sends keeps to the plan route's contract.
"""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from salli.adapters.parsing.llm_classifier import classify_transactions
from salli.application.services.agent_service import AgentService
from salli.application.services.entry_parse_service import EntryParseService
from salli.application.services.llm_credential_service import ResolvedCredentials
from salli.domain.agents import advisor, fire_strategy
from salli.domain.agents.briefing_workflow import BriefingState, _narrate
from salli.domain.llm import LLMUnreadableAnswer
from salli.domain.parsing.models import RawRow
from salli.domain.secrets import Secret
from tests.openai_fakes import FakeOpenAI, text_reply, tool_reply

UNSUPPORTED = {
    "background",
    "conversation",
    "max_output_tokens",
    "max_tool_calls",
    "metadata",
    "moderation",
    "multi_agent",
    "prompt",
    "prompt_cache_retention",
    "safety_identifier",
    "temperature",
    "top_logprobs",
    "top_p",
    "truncation",
    "user",
    "previous_response_id",
}


def _contract(fake: FakeOpenAI) -> None:
    assert fake.bodies, "nothing was sent"
    for body in fake.bodies:
        assert body["store"] is False and body["stream"] is True
        assert not UNSUPPORTED & body.keys()
        assert all(item.get("role") != "system" for item in body["input"])


CHART = [
    SimpleNamespace(id="checking", code="1000", name="Checking", type="asset"),
    SimpleNamespace(id="food", code="5000", name="Food", type="expense"),
]


def _account(id: str, name: str, type: str) -> Any:
    return SimpleNamespace(id=id, code="1000", name=name, type=type, currency="USD", is_active=True)


# ── Statement sorting ─────────────────────────────────────────────────────────


async def test_statement_sorting_runs_on_the_plans_fast_model():
    fake = FakeOpenAI(
        text_reply(
            json.dumps(
                [{"index": 0, "account_id": "food", "category": "groceries", "confidence": 0.9}]
            )
        )
    )
    row = RawRow("2026-10-02", "WHOLE FOODS", Decimal("84.17"), False, "USD")

    [txn] = await classify_transactions([row], CHART, llm=fake.client(), money_account=CHART[0])

    assert (txn.debit_account_id, txn.credit_account_id) == ("food", "checking")
    assert txn.raw.amount == Decimal("84.17")  # the model never touches the amount
    _contract(fake)
    assert fake.bodies[0]["model"] == "gpt-test-mini"


# ── Quick add ─────────────────────────────────────────────────────────────────


class _Creds:
    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def resolve(self, user_id: str) -> ResolvedCredentials:
        return ResolvedCredentials(anthropic=Secret(""), anthropic_is_user_key=False, llm=self.llm)


async def test_quick_add_runs_on_the_plan():
    fake = FakeOpenAI(
        text_reply(
            "```json\n"
            + json.dumps(
                {
                    "entry_type": "expense",
                    "amount": "1,250.00",
                    "description": "Groceries",
                    "debit_account_id": "food",
                    "credit_account_id": "checking",
                    "debit_account_hint": None,
                    "credit_account_hint": None,
                    "currency": "usd",
                    "confidence": 0.8,
                }
            )
            + "\n```"
        )
    )
    ledger = SimpleNamespace(
        list_accounts=AsyncMock(
            return_value=[
                _account("checking", "Checking", "asset"),
                _account("food", "Food", "expense"),
            ]
        ),
        base_currency=AsyncMock(return_value="USD"),
    )
    service = EntryParseService(ledger, credentials=_Creds(fake.client()))

    draft = await service.parse_draft("u1", "groceries 1,250 from checking")

    assert draft["amount"] == "1250.00"
    assert (draft["debit_account_id"], draft["credit_account_id"]) == ("food", "checking")
    assert draft["currency"] == "USD"
    _contract(fake)
    body = fake.bodies[0]
    assert body["model"] == "gpt-test-mini"
    assert "JSON Schema" in body["instructions"]


# ── The FIRE strategy and the advisor ────────────────────────────────────────

STRATEGY = {
    "fire_style": "standard",
    "swr": 0.04,
    "real_return_conservative": 0.02,
    "real_return_base": 0.04,
    "real_return_growth": 0.06,
    "target_monthly_expenses": None,
    "target_age": 55,
    "buckets": [
        {
            "key": "emergency_moat",
            "name": "Emergency Moat",
            "target_pct": 0.25,
            "description": "Six months of costs.",
            "color": "emerald",
        },
        {
            "key": "growth",
            "name": "Growth",
            "target_pct": 0.75,
            "description": "Index funds.",
            "color": "blue",
        },
    ],
    "ai_rationale": "Because.",
    "theories_applied": ["Trinity Study"],
}


async def test_the_fire_strategy_runs_on_the_plans_best_model():
    fake = FakeOpenAI(text_reply(json.dumps(STRATEGY)))

    result = await fire_strategy.generate_strategy({"currency": "USD"}, llm=fake.client())

    assert result.fire_style == "standard"
    assert result.swr == pytest.approx(0.04)
    _contract(fake)
    body = fake.bodies[0]
    assert body["model"] == "gpt-test-best"
    assert body["instructions"].startswith("You are Salli's FIRE Strategy Architect")


async def test_the_model_the_meter_was_told_is_the_model_that_runs():
    fake = FakeOpenAI(text_reply(json.dumps(STRATEGY)))
    await fire_strategy.generate_strategy({}, llm=fake.client(), model="gpt-chosen")
    assert fake.bodies[0]["model"] == "gpt-chosen"


async def test_a_strategy_outside_the_bounds_is_refused_not_repaired():
    """`swr: 4` where 0.04 is meant would shrink the Freedom Number 100x."""
    fake = FakeOpenAI(text_reply(json.dumps({**STRATEGY, "swr": 4})))
    with pytest.raises(LLMUnreadableAnswer):
        await fire_strategy.generate_strategy({}, llm=fake.client())


ADVICE = {
    "summary": "On track.",
    "fire_tier_assessment": "Standard FIRE.",
    "recommendations": [
        {
            "title": "Fund the moat",
            "rationale": "It is short.",
            "category": "emergency_fund",
            "priority": 1,
            "bucket_key": "emergency_moat",
            "action": {"type": "reminder", "label": "Move money", "due_in_days": 7},
        }
    ],
}


async def test_the_advisor_runs_on_the_plan():
    fake = FakeOpenAI(text_reply(json.dumps(ADVICE)))

    advice = await advisor.generate_advice({"currency": "USD"}, llm=fake.client())

    assert advice.recommendations[0].title == "Fund the moat"
    _contract(fake)
    assert fake.bodies[0]["instructions"].startswith("You are Salli's Financial Independence")


async def test_the_briefing_narrates_on_the_users_own_model():
    fake = FakeOpenAI(text_reply(json.dumps(ADVICE)))
    asked: list[str] = []

    class AdvisorSvc:
        async def llm_for(self, user_id: str) -> Any:
            asked.append(user_id)
            return fake.client()

    result = await _narrate(BriefingState(user_id="u1", context={"currency": "USD"}), AdvisorSvc())

    assert result["advice"].summary == "On track."
    assert asked == ["u1"]
    _contract(fake)


# ── The chat agent ────────────────────────────────────────────────────────────


async def test_the_chat_agent_calls_a_tool_and_answers_on_the_plan():
    ledger = SimpleNamespace(
        list_accounts=AsyncMock(return_value=[_account("a1", "Cash", "asset")])
    )
    service = AgentService(ledger_svc=ledger, tax_svc=None)
    fake = FakeOpenAI(
        tool_reply("get_accounts", {}, call_id="call_7", namespace="salli"),
        text_reply("You have one account, Cash.", pieces=3),
    )

    events = [
        event
        async for event in service.stream_chat(
            "u1", "What accounts do I have?", thread_id="t1", api_key=fake.client()
        )
    ]

    assert not [p for kind, p in events if kind == "error"], events
    assert "".join(p for kind, p in events if kind == "token") == "You have one account, Cash."
    assert ("tool_call", {"name": "get_accounts", "input": {}}) in events
    ledger.list_accounts.assert_awaited_once_with("u1")

    _contract(fake)
    first, second = fake.bodies
    assert first["model"] == "gpt-test-best"
    assert "Scrooge McDuck" in first["instructions"]
    (namespace,) = first["tools"]
    assert namespace["type"] == "namespace"
    assert "get_accounts" in {t["name"] for t in namespace["tools"]}
    # The supervisor hands off one specialist at a time.
    assert first["parallel_tool_calls"] is False
    # The tool's result went back beside the call that asked for it.
    call = next(i for i in second["input"] if i["type"] == "function_call")
    output = next(i for i in second["input"] if i["type"] == "function_call_output")
    assert (call["name"], call["namespace"], call["call_id"]) == ("get_accounts", "salli", "call_7")
    assert output["call_id"] == "call_7" and "Cash" in output["output"]


async def test_a_plan_limit_in_the_chat_says_where_to_change_it():
    from tests.openai_fakes import failed_after

    service = AgentService(ledger_svc=None, tax_svc=None)
    fake = FakeOpenAI(failed_after("Let me", "subscription_sharing_usage_limit_exceeded"))

    events = [
        event
        async for event in service.stream_chat("u1", "hi", thread_id="t1", api_key=fake.client())
    ]

    [error] = [p for kind, p in events if kind == "error"]
    assert error["code"] == "chatgpt_usage_limit"
    assert error["link"] == "https://chatgpt.com/settings/usage"
    assert "ChatGPT settings" in error["message"]
    assert events[-1] == ("done", None)


async def test_a_conversation_is_named_on_the_fast_model():
    fake = FakeOpenAI(text_reply("Accounts overview"))
    titles: list[tuple[str, str, str]] = []

    class Sessions:
        async def set_title(self, user_id: str, thread_id: str, title: str) -> None:
            titles.append((user_id, thread_id, title))

    class UoW:
        agent_sessions = Sessions()

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

    service = AgentService(ledger_svc=None, tax_svc=None, uow_factory=UoW)
    await service._try_generate_title(
        "u1", "t1", "accounts?", "You have one.", api_key=fake.client()
    )

    assert titles == [("u1", "t1", "Accounts overview")]
    _contract(fake)
    assert fake.bodies[0]["model"] == "gpt-test-mini"


async def test_a_briefing_at_the_plans_limit_says_where_to_change_it():
    from tests.openai_fakes import failed_after

    fake = FakeOpenAI(failed_after("{", "subscription_sharing_usage_limit_exceeded"))

    class AdvisorSvc:
        async def llm_for(self, user_id: str) -> Any:
            return fake.client()

    result = await _narrate(BriefingState(user_id="u1", context={}), AdvisorSvc())

    assert "chatgpt.com/settings/usage" in result["error"]


async def test_the_agents_advisor_tool_reports_the_plans_limit_to_the_model():
    from salli.domain.agents.tools import make_manager_tools, set_current_user
    from salli.domain.llm import chatgpt_usage_limit

    class AdvisorSvc:
        async def run_advisor(self, *args: Any, **kwargs: Any) -> Any:
            raise chatgpt_usage_limit()

    tools = {t.name: t for t in make_manager_tools(None, None, None, advisor_svc=AdvisorSvc())}
    set_current_user("u1")

    result = await tools["run_wealth_advisor"].ainvoke({})

    assert "ChatGPT settings" in result["error"]


async def test_without_a_request_boundary_a_plan_that_cannot_run_is_an_error_event():
    """The CLI's chat resolves for itself; a plan needing a new sign-in is
    said on the stream, not raised as a traceback."""
    from salli.domain.llm import LLMSignInRequired

    class Creds:
        async def resolve(self, user_id: str) -> Any:
            raise LLMSignInRequired("Sign in with ChatGPT again.", provider="chatgpt")

    service = AgentService(ledger_svc=None, tax_svc=None, credentials=Creds())

    events = [e async for e in service.stream_chat("u1", "hi", thread_id="t1")]

    assert events[0] == (
        "error",
        {"message": "Sign in with ChatGPT again.", "code": "ai_sign_in_required"},
    )
    assert events[-1] == ("done", None)
