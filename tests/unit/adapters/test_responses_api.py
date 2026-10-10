"""
What Salli sends to OpenAI's Responses API, and how it reads the stream back,
on both OpenAI routes: an API key, and a ChatGPT plan.

The plan route's preview limitations are a contract, so the request bodies are
asserted field by field: `store: false` and `stream: true` on every request,
none of the unsupported fields, the prompt in `instructions` and never a
system-role item, function tools in a namespace. And only `response.completed`
is an answer.
"""

from __future__ import annotations

import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from salli.adapters.llm import responses
from salli.adapters.llm.responses import (
    API_KEY_ROUTE,
    CHATGPT_ROUTE,
    FORBIDDEN_FIELDS,
    sse_events,
)
from salli.domain.llm import (
    CHATGPT_USAGE_URL,
    LLMIncomplete,
    LLMKeyRejected,
    LLMNotEligible,
    LLMProviderUnavailable,
    LLMRequestRejected,
    LLMUsageLimit,
    LLMUsageUnavailable,
)
from tests.openai_fakes import (
    FakeOpenAI,
    StaticSession,
    api_key_client,
    failed_after,
    sse,
    text_reply,
    tool_reply,
)

#: The fields the plan route's preview limitations list as unsupported.
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
}


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(responses, "_BACKOFF", (0.0, 0.0))


def _assert_route_contract(body: dict) -> None:
    assert body["store"] is False
    assert body["stream"] is True
    assert isinstance(body["input"], list)
    for field in UNSUPPORTED | {"previous_response_id"}:
        assert field not in body, field
    for item in body["input"]:
        assert item.get("role") != "system", item


@tool
async def get_accounts() -> dict:
    """List the user's accounts."""
    return {"accounts": []}


# ── One-shot generation ───────────────────────────────────────────────────────


@pytest.mark.parametrize("route", [CHATGPT_ROUTE, API_KEY_ROUTE], ids=["plan", "api-key"])
async def test_a_one_shot_request_keeps_to_the_plan_routes_contract(route):
    fake = FakeOpenAI(text_reply('{"ok": true}'))
    client = fake.client(route)

    answer = await client.generate(
        instructions="Sort these.",
        input="the rows",
        tier="fast",
        schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        # Hints Anthropic honours; neither OpenAI route may send them.
        max_output_tokens=4096,
        temperature=0.3,
    )

    assert answer == '{"ok": true}'
    (request,) = fake.requests
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.method == "POST"
    body = json.loads(request.content)
    _assert_route_contract(body)
    assert body["model"] == "gpt-test-mini"
    # The instructions, then what shape to answer in: never a system message.
    assert body["instructions"].startswith("Sort these.")
    assert '"ok"' in body["instructions"]
    assert body["input"] == [{"type": "message", "role": "user", "content": "the rows"}]
    assert FORBIDDEN_FIELDS >= UNSUPPORTED


async def test_the_plan_route_sends_the_plans_bearer_token():
    fake = FakeOpenAI(text_reply("hi"))
    await fake.client(CHATGPT_ROUTE, session=StaticSession("plan-token")).generate(
        instructions="", input="hi"
    )
    assert fake.requests[0].headers["authorization"] == "Bearer plan-token"


async def test_the_api_key_route_sends_the_key():
    fake = FakeOpenAI(text_reply("hi"))
    await api_key_client(fake, "sk-test-userkey").generate(instructions="", input="hi")
    assert fake.requests[0].headers["authorization"] == "Bearer sk-test-userkey"


async def test_no_instructions_means_no_instructions_field():
    fake = FakeOpenAI(text_reply("hi"))
    await fake.client().generate(instructions="", input="hi")
    assert "instructions" not in fake.bodies[0]


# ── The chat model ────────────────────────────────────────────────────────────


def _history() -> list:
    return [
        SystemMessage("You are Salli."),
        SystemMessage("Today is Friday."),
        HumanMessage("What accounts do I have?"),
        AIMessage(content="", tool_calls=[{"name": "get_accounts", "args": {}, "id": "call_9"}]),
        ToolMessage(content='{"accounts": []}', tool_call_id="call_9"),
        AIMessage(content="None yet."),
        SystemMessage("Tone note: be brief."),
        HumanMessage("And now?"),
    ]


async def test_the_plan_route_turns_system_messages_into_instructions_and_developer_items():
    fake = FakeOpenAI(text_reply("Still none."))
    model = fake.client(CHATGPT_ROUTE).chat_model(temperature=0, max_tokens=500)

    reply = await model.bind_tools([get_accounts]).ainvoke(_history())

    assert reply.content == "Still none."
    body = fake.bodies[0]
    _assert_route_contract(body)
    assert body["model"] == "gpt-test-best"
    # Leading system messages are the instructions; a later one is a developer
    # message ("Use instructions or developer messages").
    assert body["instructions"] == "You are Salli.\n\nToday is Friday."
    assert body["input"] == [
        {"type": "message", "role": "user", "content": "What accounts do I have?"},
        {
            "type": "function_call",
            "call_id": "call_9",
            "name": "get_accounts",
            "arguments": "{}",
            "namespace": "salli",
        },
        {"type": "function_call_output", "call_id": "call_9", "output": '{"accounts": []}'},
        {"type": "message", "role": "assistant", "content": "None yet."},
        {"type": "message", "role": "developer", "content": "Tone note: be brief."},
        {"type": "message", "role": "user", "content": "And now?"},
    ]


async def test_the_plan_route_groups_function_tools_in_a_namespace():
    fake = FakeOpenAI(text_reply("ok"))
    model = fake.client(CHATGPT_ROUTE).chat_model()

    await model.bind_tools([get_accounts], parallel_tool_calls=False).ainvoke([HumanMessage("hi")])

    body = fake.bodies[0]
    (namespace,) = body["tools"]
    assert namespace["type"] == "namespace"
    assert namespace["name"] == "salli"
    assert namespace["tools"] == [
        {
            "type": "function",
            "name": "get_accounts",
            "description": "List the user's accounts.",
            "parameters": {"properties": {}, "type": "object"},
        }
    ]
    assert body["parallel_tool_calls"] is False


async def test_the_api_key_route_keeps_function_tools_at_the_top_level():
    fake = FakeOpenAI(text_reply("ok"))
    model = api_key_client(fake).chat_model()

    await model.bind_tools([get_accounts]).ainvoke([HumanMessage("hi")])

    body = fake.bodies[0]
    _assert_route_contract(body)
    assert [t["type"] for t in body["tools"]] == ["function"]
    assert body["tools"][0]["name"] == "get_accounts"
    # The replayed calls carry no namespace on this route.
    fake.replies.append(text_reply("ok"))
    await model.bind_tools([get_accounts]).ainvoke(_history())
    call = next(i for i in fake.bodies[1]["input"] if i["type"] == "function_call")
    assert "namespace" not in call


async def test_a_namespaced_call_comes_back_as_a_tool_call():
    fake = FakeOpenAI(tool_reply("get_accounts", {"kind": "asset"}, namespace="salli"))
    model = fake.client(CHATGPT_ROUTE).chat_model()

    reply = await model.bind_tools([get_accounts]).ainvoke([HumanMessage("accounts?")])

    assert reply.tool_calls == [
        {"name": "get_accounts", "args": {"kind": "asset"}, "id": "call_1", "type": "tool_call"}
    ]
    assert reply.usage_metadata["total_tokens"] == 18


async def test_attachments_go_as_files_and_images():
    fake = FakeOpenAI(text_reply("ok"))
    model = fake.client().chat_model()
    message = HumanMessage(
        content=[
            {"type": "text", "text": "Read these"},
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": "UERG"},
                "title": "statement.pdf",
            },
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "image/png", "data": "UE5H"},
                "title": "receipt.png",
            },
        ]
    )

    await model.ainvoke([message])

    assert fake.bodies[0]["input"][0]["content"] == [
        {"type": "input_text", "text": "Read these"},
        {
            "type": "input_file",
            "filename": "statement.pdf",
            "file_data": "data:application/pdf;base64,UERG",
        },
        {"type": "input_image", "image_url": "data:image/png;base64,UE5H"},
    ]


async def test_tokens_stream_as_they_arrive():
    fake = FakeOpenAI(text_reply("Hello there, Scrooge", pieces=3))
    model = fake.client().chat_model()

    chunks = [c.content async for c in model.astream([HumanMessage("hi")])]

    assert "".join(chunks) == "Hello there, Scrooge"
    assert len([c for c in chunks if c]) == 3


# ── Only response.completed is an answer ─────────────────────────────────────


async def test_a_stream_that_stops_without_completing_is_not_an_answer():
    fake = FakeOpenAI(
        sse({"type": "response.output_text.delta", "output_index": 0, "delta": "Half an"})
    )
    with pytest.raises(LLMIncomplete):
        await fake.client().generate(instructions="", input="hi")


async def test_an_incomplete_response_is_not_an_answer():
    fake = FakeOpenAI(
        sse(
            {"type": "response.output_text.delta", "delta": "Half"},
            {
                "type": "response.incomplete",
                "response": {"incomplete_details": {"reason": "max_output_tokens"}},
            },
        )
    )
    with pytest.raises(LLMIncomplete, match="ran out of room"):
        await fake.client().generate(instructions="", input="hi")


async def test_a_usage_limit_mid_stream_is_typed_and_pauses_the_plan():
    session = StaticSession()
    fake = FakeOpenAI(failed_after("Your money bin", "subscription_sharing_usage_limit_exceeded"))
    model = fake.client(session=session).chat_model()

    seen: list[str] = []
    with pytest.raises(LLMUsageLimit) as raised:
        async for chunk in model.astream([HumanMessage("hi")]):
            seen.append(chunk.content)

    assert seen == ["Your money bin"]  # it had begun streaming
    assert raised.value.link == CHATGPT_USAGE_URL
    assert "ChatGPT settings" in raised.value.message
    assert raised.value.status == 429
    assert session.limited == 1


async def test_usage_that_cannot_be_checked_mid_stream_is_temporary():
    fake = FakeOpenAI(failed_after("Half", "subscription_sharing_usage_unavailable"))
    with pytest.raises(LLMUsageUnavailable):
        await fake.client().generate(instructions="", input="hi")


async def test_an_error_event_is_an_error():
    fake = FakeOpenAI(sse({"type": "error", "code": "subscription_sharing_user_not_eligible"}))
    with pytest.raises(LLMNotEligible):
        await fake.client().generate(instructions="", input="hi")


# ── Before a stream opens ─────────────────────────────────────────────────────


def _error(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, headers={"x-request-id": "req_1"})


async def test_a_usage_limit_before_the_stream_is_typed_and_pauses_the_plan():
    session = StaticSession()
    fake = FakeOpenAI(_error(429, {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}))
    with pytest.raises(LLMUsageLimit):
        await fake.client(session=session).generate(instructions="", input="hi")
    assert session.limited == 1


async def test_an_unsupported_capability_is_not_retried():
    fake = FakeOpenAI(
        _error(
            400,
            {"error": {"code": "subscription_sharing_unsupported_capability", "param": "tools"}},
        )
    )
    with pytest.raises(LLMRequestRejected, match=r"\(tools\)"):
        await fake.client().generate(instructions="", input="hi")
    assert len(fake.requests) == 1


async def test_a_direct_admission_failure_is_retried_with_backoff_then_reported():
    """`{"detail": ...}` is diagnostic text, not a code: read by status."""
    fake = FakeOpenAI(*[_error(503, {"detail": "direct routing unavailable"})] * 3)
    with pytest.raises(LLMProviderUnavailable):
        await fake.client().generate(instructions="", input="hi")
    assert len(fake.requests) == 3  # the first, and two bounded retries


async def test_a_temporary_failure_that_clears_is_answered():
    fake = FakeOpenAI(_error(503, {"detail": "busy"}), text_reply("hi"))
    assert await fake.client().generate(instructions="", input="hi") == "hi"


async def test_a_401_on_the_plan_route_renews_the_token_once_and_retries():
    session = StaticSession("old-token")
    fake = FakeOpenAI(_error(401, {"detail": "expired"}), text_reply("hi"))

    assert await fake.client(session=session).generate(instructions="", input="hi") == "hi"

    assert session.rejected == ["old-token"]  # the token that was refused, by name
    assert fake.requests[1].headers["authorization"] == "Bearer old-token-renewed-1"


async def test_a_second_401_on_the_plan_route_is_a_rejected_sign_in():
    session = StaticSession()
    fake = FakeOpenAI(_error(401, {"detail": "no"}), _error(401, {"detail": "no"}))
    with pytest.raises(LLMKeyRejected, match="Sign in with ChatGPT again"):
        await fake.client(session=session).generate(instructions="", input="hi")
    assert session.renewals == 1


async def test_a_rejected_api_key_is_not_retried_and_never_echoed():
    key = "sk-test-SECRETSECRETSECRET"
    fake = FakeOpenAI(_error(401, {"error": {"message": f"Incorrect API key provided: {key}"}}))
    with pytest.raises(LLMKeyRejected) as raised:
        await api_key_client(fake, key).generate(instructions="", input="hi")
    assert len(fake.requests) == 1
    assert key not in raised.value.message
    assert key not in str(raised.value.detail())


async def test_a_region_refusal_on_the_plan_route_says_so():
    fake = FakeOpenAI(_error(403, {"detail": "region"}))
    with pytest.raises(LLMNotEligible, match="region"):
        await fake.client().generate(instructions="", input="hi")


async def test_an_unreachable_provider_is_temporary():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    client = FakeOpenAI().client()
    client._http_factory = lambda: httpx.AsyncClient(transport=httpx.MockTransport(down))
    with pytest.raises(LLMProviderUnavailable):
        await client.generate(instructions="", input="hi")


# ── Server-sent events ────────────────────────────────────────────────────────


async def test_events_are_read_whatever_the_line_layout():
    async def lines():
        for line in [
            ": a comment",
            "event: response.output_text.delta",
            'data: {"type": "response.output_text.delta",',
            'data:  "delta": "hi"}',
            "",
            "data: not json",
            "",
            "data: [DONE]",
            "",
            'data: {"type": "response.completed", "response": {}}',
        ]:
            yield line

    events = [e async for e in sse_events(lines())]

    assert events == [
        {"type": "response.output_text.delta", "delta": "hi"},
        {"type": "response.completed", "response": {}},
    ]


async def test_a_usage_limit_inside_an_error_events_error_object_is_read():
    session = StaticSession()
    fake = FakeOpenAI(
        sse({"type": "error", "error": {"code": "subscription_sharing_usage_limit_exceeded"}})
    )
    with pytest.raises(LLMUsageLimit):
        await fake.client(session=session).generate(instructions="", input="hi")
    assert session.limited == 1


async def test_a_request_too_long_is_not_called_retryable():
    fake = FakeOpenAI(failed_after("x", "context_length_exceeded"))
    with pytest.raises(LLMRequestRejected):
        await fake.client().generate(instructions="", input="hi")
