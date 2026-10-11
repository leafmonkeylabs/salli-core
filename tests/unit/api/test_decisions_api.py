"""
`/v1/decisions` over HTTP: the real services over the household ledger,
held as the caller's. An entry comes back exactly as recorded, so its hash
can be recomputed from the response; there is no route that changes or
deletes one; notes and reviews append.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.domain import canonical
from salli.interfaces.api.contract import OPERATION_IDS
from tests.fakes import FakeUoW
from tests.golden import household as h
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER, _household_of

pytestmark = pytest.mark.asyncio

CASH = {
    "schema": "salli.scenario/1",
    "label": "Pay cash",
    "changes": [
        {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "label": "Laptop",
        }
    ],
}
WAIT = {"schema": "salli.scenario/1", "label": "Wait"}


class Clock:
    today = h.AS_OF


@pytest.fixture
def uow(mock_services) -> FakeUoW:
    books = _household_of(USER)
    Clock.today = h.AS_OF
    baselines = BaselineService(books.factory(), fx=h.fx(), today=lambda: Clock.today)
    scenarios = ScenarioService(books.factory(), baselines=baselines)
    principles = PrincipleService(books.factory(), scenarios)
    mock_services.principles = principles
    mock_services.decisions = DecisionService(
        books.factory(),
        scenarios,
        principles,
        now=lambda: dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC),
    )
    return books


def _decision(**more: Any) -> dict[str, Any]:
    return {
        "question": "Laptop: pay cash now, or wait?",
        "options": [CASH, WAIT],
        "chosen": "Pay cash",
        "reasons": "The old one is dying.",
        "agent_summary": "Paying cash keeps interest at zero.",
        "agent": "Claude",
        "review_on": "2027-04-11",
        **more,
    }


async def test_every_route_is_named_and_none_changes_or_deletes(app):
    paths = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/v1/decisions")
        for method in operations
    }
    assert {method for method, _ in paths} == {"GET", "POST"}
    for method, path in paths:
        assert (method, path.removeprefix("/v1")) in OPERATION_IDS
    assert ("POST", "/v1/decisions/{decision_id}/notes") in paths


async def test_a_decision_is_recorded_and_comes_back_exactly(client, uow):
    r = await client.post("/v1/decisions", json=_decision(), headers=AUTH)
    assert r.status_code == 201, r.text
    recorded = r.json()
    entry = recorded["entry"]
    # Anyone holding the response can recompute the hash.
    assert canonical.digest(entry) == recorded["hash"] and recorded["verified"]
    assert entry["recorded_via"] == {"channel": "api"}
    assert entry["agent_summary"] == {
        "text": "Paying cash keeps interest at zero.",
        "author": "agent",
        "agent": "Claude",
    }
    read = (await client.get(f"/v1/decisions/{recorded['id']}", headers=AUTH)).json()
    assert read["entry"] == entry and canonical.digest(read["entry"]) == read["hash"]
    listed = (await client.get("/v1/decisions", headers=AUTH)).json()["decisions"]
    assert [(d["id"], d["status"], d["notes"]) for d in listed] == [
        (recorded["id"], "awaiting_review", 0)
    ]


async def test_what_cant_be_recorded_is_a_422_with_paths(client, uow):
    r = await client.post(
        "/v1/decisions", json=_decision(chosen="Lease", review_on="2026-10-20"), headers=AUTH
    )
    assert r.status_code == 422
    assert r.json()["type"].endswith("invalid-decision")
    assert sorted(p["loc"][-1] for p in r.json()["detail"]) == ["chosen", "review_on"]
    # A scenario Salli can't run is the scenario's own 422, under its option.
    bad = {**CASH, "changes": [{**CASH["changes"][0], "account": "brk"}]}
    r = await client.post("/v1/decisions", json=_decision(options=[bad, WAIT]), headers=AUTH)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "options", 0, "changes", 0, "account"]


async def test_notes_append_and_the_entry_doesnt_change(client, uow):
    recorded = (await client.post("/v1/decisions", json=_decision(), headers=AUTH)).json()
    r = await client.post(
        f"/v1/decisions/{recorded['id']}/notes", json={"text": "Bought it."}, headers=AUTH
    )
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["note"]["entry_hash"] == recorded["hash"]
    assert canonical.digest(note["note"]) == note["hash"]
    read = (await client.get(f"/v1/decisions/{recorded['id']}", headers=AUTH)).json()
    assert read["hash"] == recorded["hash"] and read["entry"] == recorded["entry"]
    assert [n["note"]["text"] for n in read["notes"]] == ["Bought it."]


async def test_reviews_come_due_and_append(client, uow):
    recorded = (await client.post("/v1/decisions", json=_decision(), headers=AUTH)).json()
    early = await client.post(
        f"/v1/decisions/{recorded['id']}/review", json={"reflection": "Soon."}, headers=AUTH
    )
    assert early.status_code == 422
    assert (await client.get("/v1/decisions/reviews", headers=AUTH)).json()["reviews"] == []

    Clock.today = dt.date(2027, 4, 12)
    due = (await client.get("/v1/decisions/reviews", headers=AUTH)).json()
    [item] = due["reviews"]
    assert (item["id"], item["comparison"]["at"]) == (recorded["id"], "2027-03-31")
    assert [row["figure"] for row in item["comparison"]["figures"]] == [
        "cash",
        "investments",
        "owed",
        "net_worth",
    ]
    r = await client.post(
        f"/v1/decisions/{recorded['id']}/review",
        json={"reflection": "Glad I did."},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    review = r.json()
    assert canonical.digest(review["review"]) == review["hash"]
    assert review["review"]["comparison"] == item["comparison"]
    assert (await client.get("/v1/decisions/reviews", headers=AUTH)).json()["reviews"] == []


async def test_the_journal_exports(client, uow):
    recorded = (await client.post("/v1/decisions", json=_decision(), headers=AUTH)).json()
    exported = (await client.get("/v1/decisions/export", headers=AUTH)).json()
    assert exported["schema"] == "salli.decision-journal/1"
    [item] = exported["entries"]
    assert canonical.digest(item["entry"]) == item["hash"] == recorded["hash"]
    md = await client.get("/v1/decisions/export/markdown", headers=AUTH)
    assert md.headers["content-type"].startswith("text/markdown")
    assert "## Laptop: pay cash now, or wait?" in md.text
    one = await client.get(f"/v1/decisions/{recorded['id']}/markdown", headers=AUTH)
    assert recorded["hash"] in one.text


async def test_another_users_decision_is_not_found(client, uow):
    recorded = (await client.post("/v1/decisions", json=_decision(), headers=AUTH)).json()
    other = {"Authorization": "Bearer someone-else"}
    for r in (
        await client.get(f"/v1/decisions/{recorded['id']}", headers=other),
        await client.post(
            f"/v1/decisions/{recorded['id']}/notes", json={"text": "x"}, headers=other
        ),
        await client.get(f"/v1/decisions/{recorded['id']}/markdown", headers=other),
    ):
        assert r.status_code == 404
    assert (await client.get("/v1/decisions", headers=other)).json() == {"decisions": []}


async def test_a_due_review_is_a_signal(client, uow, mock_services):
    from salli.application.services.insights_service import InsightsService

    mock_services.insights = InsightsService(
        uow.factory(),
        today=lambda: Clock.today,
        baselines=BaselineService(uow.factory(), fx=h.fx(), today=lambda: Clock.today),
    )
    recorded = (await client.post("/v1/decisions", json=_decision(), headers=AUTH)).json()
    Clock.today = dt.date(2027, 4, 12)
    signals = (await client.get("/v1/insights/signals", headers=AUTH)).json()["signals"]
    [due] = [s for s in signals if s["kind"] == "decision_review_due"]
    assert (due["severity"], due["action"], due["refs"], due["date"]) == (
        "info",
        "review_decision",
        [recorded["id"]],
        "2027-04-11",
    )
