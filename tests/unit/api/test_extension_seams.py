"""
The usage meter and entitlement policy, as the HTTP API uses them.

Two halves:

- Salli as shipped: every metered route passes, every shapeable surface comes
  back exactly as the service computed it.
- An extension's meter and policy: the route tells the meter the right action
  and model, a refusal reaches the client exactly as the meter shaped it (and
  nothing downstream runs), and the policy shapes every surface — list items
  and the streamed `done` event included — from one lookup per request.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.ports import EntitlementPolicy, PayloadView, Surface
from salli.domain.ai_models import DEFAULT_MODEL
from salli.domain.usage import AIAction, UsageLimitReached
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio


def _projections() -> dict[str, Any]:
    return {
        # As the service sends them: in a currency, with its decimals.
        "currency": "LKR",
        "points": [{"year": 1, "conservative": "100.00", "base": "110.00", "growth": "120.00"}],
        "fire_year_conservative": 14,
        "fire_year_base": 12,
        "fire_year_growth": 10,
    }


def _strategy() -> dict[str, Any]:
    return {
        "buckets": [{"key": "equity", "target_pct": 60}],
        "ai_rationale": "Save aggressively. Invest the surplus.",
        "theories_applied": ["4% rule", "Coast FIRE"],
    }


def _report() -> dict[str, Any]:
    return {"id": "report-1", "recommendations": [{"id": "1", "title": "t", "priority": 1}]}


async def _fake_stream():
    yield 'data: {"type": "status", "message": "Working..."}\n\n'
    yield f"data: {json.dumps({'type': 'done', 'strategy': _strategy()})}\n\n"


async def _no_events():
    return
    yield


def _events(text: str) -> list[dict[str, Any]]:
    return [json.loads(c.removeprefix("data: ")) for c in text.split("\n\n") if c.strip()]


def _stub_surfaces(svc: MagicMock) -> None:
    svc.fi.get_projections.return_value = _projections()
    svc.fi.get_strategy.return_value = _strategy()
    svc.fi.get_strategy_history.return_value = [_strategy(), _strategy()]
    svc.fi.generate_strategy = MagicMock(side_effect=lambda *a, **kw: _fake_stream())
    svc.advisor.run_advisor.return_value = _report()
    svc.advisor.get_latest_report.return_value = _report()
    svc.advisor.list_reports.return_value = [_report(), _report()]


# ── Salli as shipped ────────────────────────────────────────────────────────


async def test_every_surface_is_returned_untouched(client, mock_services):
    _stub_surfaces(mock_services)

    assert (await client.get("/fi/projections", headers=AUTH)).json() == _projections()
    assert (await client.get("/fi/strategy", headers=AUTH)).json() == _strategy()
    assert (await client.get("/fi/strategy/history", headers=AUTH)).json() == {
        "history": [_strategy(), _strategy()]
    }
    assert (await client.post("/advisor/run", headers=AUTH)).json() == _report()
    assert (await client.get("/advisor/reports/latest", headers=AUTH)).json() == _report()
    assert (await client.get("/advisor/reports", headers=AUTH)).json() == {
        "reports": [_report(), _report()]
    }
    events = _events((await client.post("/fi/strategy/generate", headers=AUTH)).text)
    assert events[1] == {"type": "done", "strategy": _strategy()}


# ── Metering ────────────────────────────────────────────────────────────────


def _metered_requests(svc: MagicMock):
    """(action, model the meter should hear about, request) for every HTTP
    route that meters before doing AI work."""
    svc.llm_credentials = AsyncMock()
    svc.entry_parse = AsyncMock()
    svc.entry_parse.parse_draft.return_value = {"description": "x", "postings": []}
    svc.parsing = AsyncMock()
    svc.parsing.parse_statement.return_value = SimpleNamespace(
        statement_id="st-1",
        bank="",
        period_start=None,
        period_end=None,
        raw_rows=[],
        errors=[],
        transactions=[],
    )
    svc.agent.stream_chat = MagicMock(side_effect=lambda **kw: _no_events())
    svc.fi.generate_strategy = MagicMock(side_effect=lambda *a, **kw: _fake_stream())
    return [
        (
            AIAction.CHAT_MESSAGE,
            DEFAULT_MODEL,
            lambda c: c.post(
                "/agent/chat", json={"thread_id": "t1", "message": "hi"}, headers=AUTH
            ),
            lambda: svc.agent.stream_chat,
        ),
        (
            AIAction.FIRE_STRATEGY,
            DEFAULT_MODEL,
            lambda c: c.post("/fi/strategy/generate", headers=AUTH),
            lambda: svc.fi.generate_strategy,
        ),
        (
            AIAction.ENTRY_PARSE,
            None,
            lambda c: c.post("/entries/parse", json={"text": "lunch 1500"}, headers=AUTH),
            lambda: svc.entry_parse.parse_draft,
        ),
        (
            AIAction.STATEMENT_IMPORT,
            None,
            lambda c: c.post(
                "/statements/upload",
                files={"file": ("s.csv", b"date,amount\n", "text/csv")},
                headers=AUTH,
            ),
            lambda: svc.parsing.parse_statement,
        ),
    ]


async def test_each_metered_route_names_its_action_and_model(client, mock_services):
    for action, model, send, _ in _metered_requests(mock_services):
        mock_services.usage.charge.reset_mock()
        await send(client)
        mock_services.usage.charge.assert_awaited_once_with(
            "test-user-1", action, **({"model_id": model} if model else {}), email=None
        )


async def test_a_refusal_reaches_the_client_as_the_meter_shaped_it(client, mock_services):
    detail = {"error": "limit_reached", "anything": ["the", "meter", "chose"]}
    for action, _, send, downstream in _metered_requests(mock_services):
        mock_services.usage.charge.side_effect = UsageLimitReached(
            action, message="no", status_code=402, detail=detail
        )
        r = await send(client)
        assert r.status_code == 402, action
        # The meter's detail passes through untouched, inside problem details.
        assert r.json() == _refusal(402, detail), action
        downstream().assert_not_called()


async def test_a_refusal_without_a_status_is_a_429(client, mock_services):
    mock_services.fi.generate_strategy = MagicMock(side_effect=lambda *a, **kw: _fake_stream())
    mock_services.usage.charge.side_effect = UsageLimitReached(
        AIAction.FIRE_STRATEGY, message="Slow down."
    )
    r = await client.post("/fi/strategy/generate", headers=AUTH)
    assert r.status_code == 429
    assert r.json() == _refusal(429, {"error": "Slow down."})


async def test_the_advisor_meters_inside_the_service_and_still_maps(client, mock_services):
    """/advisor/run meters in AdvisorService (the cron and the briefing share
    it), so the refusal arrives from the service rather than the router."""
    mock_services.advisor.run_advisor.side_effect = UsageLimitReached(
        AIAction.ADVISOR_RUN, message="no", status_code=402, detail={"error": "x"}
    )
    r = await client.post("/advisor/run", headers=AUTH)
    assert r.status_code == 402
    assert r.json() == _refusal(402, {"error": "x"})


def _refusal(status: int, detail: dict) -> dict:
    return {
        "type": "/problems/usage-limit",
        "title": "Usage limit reached",
        "status": status,
        "detail": detail,
    }


async def test_the_daily_run_skips_a_refused_user_and_carries_on():
    from salli.interfaces.api.routers.advisor import _run_due

    svc = MagicMock()
    svc.advisor = AsyncMock()
    svc.advisor.due_users.return_value = [{"user_id": "a"}, {"user_id": "b"}]

    async def run(user_id, email, trigger):
        if user_id == "a":
            raise UsageLimitReached(AIAction.ADVISOR_RUN, message="no")
        return {}

    svc.advisor.run_advisor.side_effect = run
    await _run_due(svc)
    assert [c.args[0] for c in svc.advisor.run_advisor.await_args_list] == ["a", "b"]


# ── Shaping ─────────────────────────────────────────────────────────────────


class _MarkingView:
    def shape(self, surface: Surface, payload: dict[str, Any]) -> dict[str, Any]:
        return {**payload, "shaped_for": surface.value}


class _CountingPolicy(EntitlementPolicy):
    def __init__(self) -> None:
        self.lookups: list[tuple[str, str | None]] = []

    async def for_user(self, user_id: str, email: str | None = None) -> PayloadView:
        self.lookups.append((user_id, email))
        return _MarkingView()


@pytest.mark.parametrize(
    ("method", "path", "surface", "pick"),
    [
        ("get", "/fi/projections", Surface.FI_PROJECTIONS, lambda j: [j]),
        ("get", "/fi/strategy", Surface.FIRE_STRATEGY, lambda j: [j]),
        ("get", "/fi/strategy/history", Surface.FIRE_STRATEGY, lambda j: j["history"]),
        ("post", "/advisor/run", Surface.ADVISOR_REPORT, lambda j: [j]),
        ("get", "/advisor/reports/latest", Surface.ADVISOR_REPORT, lambda j: [j]),
        ("get", "/advisor/reports", Surface.ADVISOR_REPORT, lambda j: j["reports"]),
    ],
)
async def test_the_policy_shapes_each_surface_once_per_request(
    client, mock_services, method, path, surface, pick
):
    _stub_surfaces(mock_services)
    policy = _CountingPolicy()
    mock_services.entitlements = policy

    r = await getattr(client, method)(path, headers=AUTH)

    assert r.status_code == 200
    items = pick(r.json())
    assert items and all(item["shaped_for"] == surface.value for item in items)
    assert policy.lookups == [("test-user-1", None)]


async def test_only_the_streamed_done_event_is_shaped(client, mock_services):
    _stub_surfaces(mock_services)
    mock_services.entitlements = _CountingPolicy()

    events = _events((await client.post("/fi/strategy/generate", headers=AUTH)).text)

    assert events[0] == {"type": "status", "message": "Working..."}
    assert events[1]["strategy"]["shaped_for"] == Surface.FIRE_STRATEGY.value


async def test_nothing_is_looked_up_when_there_is_nothing_to_shape(client, mock_services):
    mock_services.fi.get_strategy.return_value = None
    mock_services.advisor.get_latest_report.return_value = None
    policy = _CountingPolicy()
    mock_services.entitlements = policy

    assert (await client.get("/fi/strategy", headers=AUTH)).status_code == 404
    assert (await client.get("/advisor/reports/latest", headers=AUTH)).json() == {}
    assert policy.lookups == []
