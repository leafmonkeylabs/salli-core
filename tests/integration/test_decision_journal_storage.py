"""
Principles and the decision journal against a real database:

- an entry comes back exactly as recorded, through JSONB, so its hash
  checks;
- the journal is append-only: the repository has no way to change or
  delete anything, and the database refuses an UPDATE, DELETE or TRUNCATE
  on its tables, except erasing the user's own account;
- every user's principles and decisions are their own: another user's are
  not found, can't be noted or reviewed, and never listed or due.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from salli.adapters.db.decisions import SQLDecisionRepository
from salli.application.ports import AccountNotFound, DecisionNotFound, PrincipleNotFound
from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.decisions import journal
from tests.fakes import FakeFx
from tests.integration.pg import _sync, requires_postgres
from tests.integration.test_baseline_service import AS_OF, _books

pytestmark = [requires_postgres, pytest.mark.asyncio]


def _services(uow_factory, today: dt.date = AS_OF) -> tuple[PrincipleService, DecisionService]:
    fx = FakeFx({("USD", "ZAR", None): (Decimal("17.25"), "sarb")})
    baselines = BaselineService(uow_factory, fx=fx, today=lambda: today)
    scenarios = ScenarioService(uow_factory, baselines=baselines)
    principles = PrincipleService(uow_factory, scenarios)
    clock = iter(dt.datetime(2026, 9, 15, 9, minute, tzinfo=dt.UTC) for minute in range(60))
    return principles, DecisionService(uow_factory, scenarios, principles, now=lambda: next(clock))


def _decision(bank: str) -> dict:
    return {
        "question": "A new fridge now, or wait?",
        "options": [
            {
                "schema": "salli.scenario/1",
                "label": "Now",
                "changes": [
                    {
                        "type": "one_off",
                        "date": "2026-09-20",
                        "amount": "-1500.00",
                        "account": bank,
                        "label": "Fridge",
                    }
                ],
            },
            {"schema": "salli.scenario/1", "label": "Wait"},
        ],
        "chosen": "Now",
        "reasons": "The old one leaks.",
        "agent_summary": "Buying now lowers the cash low by 1,500.00.",
        "review_on": "2026-09-30",
    }


async def test_an_entry_comes_back_exactly_as_recorded(uow_factory):
    alice = await _books(uow_factory, "alice")
    principles, decisions = _services(uow_factory)
    await principles.add(
        "alice",
        {"label": "Bank above 1,000", "check": "account_lowest >= 1000", "account": alice["bank"]},
    )
    recorded = await decisions.record("alice", _decision(alice["bank"]), via={"channel": "api"})
    read = await decisions.get("alice", recorded["id"])
    assert read["entry"] == recorded["entry"]
    assert read["verified"] and read["hash"] == journal.digest(read["entry"])
    [check] = read["entry"]["options"][0]["principles"]
    assert (check["label"], check["status"]) == ("Bank above 1,000", "keeps")
    # The review reminder, under the decision's id.
    async with uow_factory() as uow:
        [reminder] = [
            r
            for r in await uow.reminders.list_reminders("alice")
            if r["source_domain"] == "decision"
        ]
    assert (reminder["source_id"], reminder["due_date"], reminder["status"]) == (
        recorded["id"],
        "2026-09-30",
        "pending",
    )


async def test_notes_and_reviews_append_and_the_entry_never_changes(uow_factory):
    alice = await _books(uow_factory, "alice")
    _, decisions = _services(uow_factory)
    recorded = await decisions.record("alice", _decision(alice["bank"]), via={"channel": "api"})
    await decisions.add_note("alice", recorded["id"], "Delivered on the 22nd.")
    await decisions.add_note("alice", recorded["id"], "Cheaper than quoted.")
    later = _services(uow_factory, dt.date(2026, 10, 2))[1]
    assert [d["id"] for d in (await later.due("alice"))["reviews"]] == [recorded["id"]]
    await later.review("alice", recorded["id"], "Worth it.")
    read = await decisions.get("alice", recorded["id"])
    assert read["entry"] == recorded["entry"] and read["hash"] == recorded["hash"]
    assert [n["note"]["text"] for n in read["notes"]] == [
        "Delivered on the 22nd.",
        "Cheaper than quoted.",
    ]
    assert all(n["verified"] and n["note"]["entry_hash"] == recorded["hash"] for n in read["notes"])
    [reviewed] = read["reviews"]
    assert reviewed["verified"] and reviewed["review"]["comparison"]["at"] == "2026-09-30"
    assert (await later.due("alice"))["reviews"] == []
    async with uow_factory() as uow:
        [reminder] = [
            r
            for r in await uow.reminders.list_reminders("alice")
            if r["source_domain"] == "decision"
        ]
    assert reminder["status"] == "done"


async def test_the_repository_has_no_way_to_change_or_delete():
    allowed = {"record", "get", "list", "list_full", "due", "add_note", "add_review"}
    public = {name for name in vars(SQLDecisionRepository) if not name.startswith("_")}
    assert public == allowed


@pytest.mark.parametrize(
    "statement",
    [
        "update decisions set question = 'edited'",
        'update decisions set content = content || \'{"chosen": "Wait"}\'::jsonb',
        "delete from decisions",
        "update decision_notes set content = '{}'::jsonb",
        "delete from decision_notes",
        "update decision_reviews set as_of = '2000-01-01'",
        "delete from decision_reviews",
        "truncate decision_reviews",
    ],
)
async def test_the_database_refuses_to_change_the_journal(uow_factory, db, statement):
    alice = await _books(uow_factory, "alice")
    _, decisions = _services(uow_factory)
    recorded = await decisions.record("alice", _decision(alice["bank"]), via={"channel": "api"})
    await decisions.add_note("alice", recorded["id"], "A note.")
    later = _services(uow_factory, dt.date(2026, 10, 2))[1]
    await later.review("alice", recorded["id"], "A review.")
    engine = create_engine(_sync(db))
    try:
        with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
            conn.execute(text(statement))
        # Not even while erasing someone else's account.
        with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
            conn.execute(text("select set_config('salli.erase_user', 'bob', true)"))
            conn.execute(text("delete from decision_notes"))
    finally:
        engine.dispose()
    assert (await decisions.get("alice", recorded["id"]))["verified"]


async def test_erasing_an_account_erases_its_journal_and_no_one_elses(uow_factory):
    alice = await _books(uow_factory, "alice")
    bob = await _books(uow_factory, "bob")
    principles, decisions = _services(uow_factory)
    await principles.add("alice", {"label": "Six months", "check": "emergency_months >= 6"})
    mine = await decisions.record("alice", _decision(alice["bank"]), via={"channel": "api"})
    await decisions.add_note("alice", mine["id"], "Mine.")
    theirs = await decisions.record("bob", _decision(bob["bank"]), via={"channel": "api"})
    await decisions.add_note("bob", theirs["id"], "Theirs.")
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all("alice")
    assert (counts["decisions"], counts["decision_notes"], counts["principles"]) == (1, 1, 1)
    with pytest.raises(DecisionNotFound):
        await decisions.get("alice", mine["id"])
    assert len((await decisions.get("bob", theirs["id"]))["notes"]) == 1


async def test_everyones_principles_and_decisions_are_their_own(uow_factory):
    alice = await _books(uow_factory, "alice")
    bob = await _books(uow_factory, "bob")
    principles, decisions = _services(uow_factory)
    hers = await principles.add("alice", {"label": "Six months", "check": "emergency_months >= 6"})
    recorded = await decisions.record("alice", _decision(alice["bank"]), via={"channel": "api"})

    assert (await principles.list("bob"))["principles"] == []
    for attempt in (
        principles.update("bob", hers["id"], {"label": "Mine now"}),
        principles.archive("bob", hers["id"]),
    ):
        with pytest.raises(PrincipleNotFound):
            await attempt
    # A principle can't name someone else's account.
    with pytest.raises(AccountNotFound):
        await principles.add(
            "bob", {"label": "x", "check": "account_lowest >= 0", "account": alice["bank"]}
        )
    # Nor a decision.
    with pytest.raises(AccountNotFound):
        await decisions.record("bob", _decision(alice["bank"]), via={"channel": "api"})

    assert (await decisions.list("bob"))["decisions"] == []
    for attempt in (
        decisions.get("bob", recorded["id"]),
        decisions.add_note("bob", recorded["id"], "Mine now."),
        decisions.export("bob", "markdown", recorded["id"]),
    ):
        with pytest.raises(DecisionNotFound):
            await attempt
    async with uow_factory() as uow:
        assert await uow.decisions.due("bob", dt.date(2027, 1, 1)) == []
        assert (
            await uow.decisions.add_review(
                "bob",
                recorded["id"],
                {
                    "id": "r-x",
                    "as_of": dt.date(2026, 10, 2),
                    "content": {"x": 1},
                    "hash": "sha256:" + "0" * 64,
                    "created_at": dt.datetime.now(dt.UTC),
                },
            )
            is None
        )
    assert bob and (await decisions.get("alice", recorded["id"]))["notes"] == []


async def test_principles_are_edited_and_archived_never_deleted(uow_factory):
    await _books(uow_factory, "alice")
    principles, _ = _services(uow_factory)
    added = await principles.add("alice", {"label": "Six months", "check": "emergency_months >= 6"})
    edited = await principles.update("alice", added["id"], {"check": "emergency_months >= 4"})
    assert (edited["version"], edited["check"]) == (2, "emergency_months >= 4")
    assert edited["hash"] != added["hash"]
    archived = await principles.archive("alice", added["id"])
    assert archived["status"] == "archived"
    assert (await principles.list("alice"))["principles"] == []
    [kept] = (await principles.list("alice", include_archived=True))["principles"]
    assert kept["id"] == added["id"]
