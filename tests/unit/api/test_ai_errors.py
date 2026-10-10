"""An AI provider that cannot serve a request, as the API says it: a problem
response before any stream opens, the stream's own `error` event after. A
ChatGPT plan at its usage limit always says where to change it."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from salli.domain.llm import LLMSignInRequired, chatgpt_usage_limit

from .conftest import AUTH


def _events(text: str) -> list[dict]:
    return [json.loads(c.removeprefix("data: ")) for c in text.split("\n\n") if c.strip()]


async def test_quick_add_at_the_plans_limit_is_a_429_that_says_where_to_change_it(
    client, mock_services
):
    mock_services.entry_parse.parse_draft.side_effect = chatgpt_usage_limit()

    r = await client.post("/v1/entries/parse", json={"text": "lunch 12"}, headers=AUTH)

    assert r.status_code == 429
    problem = r.json()
    assert problem["type"] == "/problems/chatgpt-usage-limit"
    assert problem["detail"]["error"] == "chatgpt_usage_limit"
    assert problem["detail"]["link"] == "https://chatgpt.com/settings/usage"
    assert "ChatGPT settings" in problem["detail"]["message"]


async def test_a_statement_upload_the_plan_cannot_sort_is_refused_with_the_message(
    client, mock_services
):
    mock_services.parsing.parse_statement.side_effect = chatgpt_usage_limit()

    r = await client.post(
        "/v1/statements/upload",
        files={"file": ("s.csv", b"date,amount\n", "text/csv")},
        headers=AUTH,
    )

    assert r.status_code == 429
    assert r.json()["detail"]["error"] == "chatgpt_usage_limit"


async def test_a_chat_on_a_plan_that_needs_signing_in_is_refused_before_streaming(
    client, mock_services
):
    mock_services.llm_credentials.resolve.side_effect = LLMSignInRequired(
        "Your ChatGPT sign-in needs renewing. Run `salli ai connect chatgpt`.",
        provider="chatgpt",
    )
    mock_services.agent.stream_chat = MagicMock()

    r = await client.post("/v1/agent/chat", json={"thread_id": "t1", "message": "hi"}, headers=AUTH)

    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "ai_sign_in_required"
    mock_services.agent.stream_chat.assert_not_called()
    mock_services.usage.charge.assert_not_awaited()


async def test_a_limit_reached_mid_chat_is_the_streams_error_event(client, mock_services):
    async def stream(**_: object):
        yield ("token", "Let me")
        yield (
            "error",
            {
                "message": chatgpt_usage_limit().message,
                "code": "chatgpt_usage_limit",
                "link": "https://chatgpt.com/settings/usage",
            },
        )
        yield ("done", None)

    mock_services.agent.stream_chat = MagicMock(side_effect=lambda **kw: stream(**kw))

    r = await client.post("/v1/agent/chat", json={"thread_id": "t1", "message": "hi"}, headers=AUTH)

    events = _events(r.text)
    error = next(e for e in events if e["type"] == "error")
    assert error["code"] == "chatgpt_usage_limit"
    assert error["link"] == "https://chatgpt.com/settings/usage"
    assert events[-1] == {"type": "done"}


async def test_the_strategy_stream_ends_with_the_plans_limit():
    """FiService turns a model error into the stream's last event."""
    from salli.application.services.fi_service import FiService

    service = FiService(uow_factory=None)  # type: ignore[arg-type]

    async def nothing(*_: object, **__: object):
        return None

    async def failing_llm_for(*_: object, **__: object):
        raise chatgpt_usage_limit()

    service.build_snapshot = _snapshot  # type: ignore[method-assign]
    service.list_goals = nothing  # type: ignore[method-assign]
    service.get_strategy = nothing  # type: ignore[method-assign]
    service.llm_for = failing_llm_for  # type: ignore[method-assign]
    service._uow_factory = _EmptyLedger  # type: ignore[assignment]

    events = [json.loads(c.removeprefix("data: ")) async for c in service.generate_strategy("u1")]

    assert events[-1]["type"] == "error"
    assert events[-1]["error"] == "chatgpt_usage_limit"
    assert events[-1]["link"] == "https://chatgpt.com/settings/usage"


async def _snapshot(user_id: str):
    from decimal import Decimal
    from types import SimpleNamespace

    return SimpleNamespace(
        currency="USD",
        monthly_income=Decimal("5000"),
        monthly_expenses=Decimal("3000"),
        liquid_savings=Decimal("1000"),
        investments=Decimal("0"),
        total_assets=Decimal("1000"),
        total_liabilities=Decimal("0"),
    )


class _EmptyLedger:
    class ledger:  # noqa: N801
        @staticmethod
        async def get_accounts(user_id: str) -> list:
            return []

        @staticmethod
        async def get_entries(user_id: str, from_date: str | None = None) -> list:
            return []

    class user_profiles:  # noqa: N801
        @staticmethod
        async def get(user_id: str) -> None:
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None
