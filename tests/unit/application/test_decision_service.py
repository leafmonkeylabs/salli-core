"""
PrincipleService and DecisionService over the household's books, in memory:
what they refuse and why (each problem with its path), what an entry
records, and that every figure in it is Salli's own.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from salli.application.ports import DecisionNotFound
from salli.application.services.baseline_service import BaselineService
from salli.application.services.decision_service import DecisionService
from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.domain.decisions import journal
from salli.domain.decisions.journal import JournalError
from salli.domain.decisions.principles import PrincipleError
from salli.domain.scenarios.engine import ScenarioError
from tests.fakes import FakeUoW
from tests.golden import household as h

pytestmark = pytest.mark.asyncio

NOW = dt.datetime(2026, 10, 11, 9, tzinfo=dt.UTC)
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


class Books:
    def __init__(self, today: dt.date = h.AS_OF) -> None:
        self.uow: FakeUoW = h.uow()
        self.today = today
        baselines = BaselineService(self.uow.factory(), fx=h.fx(), today=lambda: self.today)
        scenarios = ScenarioService(self.uow.factory(), baselines=baselines)
        self.principles = PrincipleService(self.uow.factory(), scenarios)
        self.decisions = DecisionService(
            self.uow.factory(), scenarios, self.principles, now=lambda: NOW
        )


def decision(**more: Any) -> dict[str, Any]:
    return {
        "question": "Laptop: pay cash now, or wait?",
        "options": [CASH, WAIT],
        "chosen": "Pay cash",
        "reasons": "The old one is dying.",
        "review_on": "2027-04-11",
        **more,
    }


def paths(error: pytest.ExceptionInfo[Any]) -> list[str]:
    return [p.path for p in error.value.problems]


# ── Principles ───────────────────────────────────────────────────────────────


async def test_a_principle_is_kept_with_its_hash_and_author():
    books = Books()
    stored = await books.principles.add(
        h.USER, {"label": "Six months", "check": "emergency_months >= 6"}
    )
    assert stored["schema"] == "salli.principle/1"
    assert (stored["version"], stored["status"], stored["author"]) == (1, "active", "user")
    by_agent = await books.principles.add(
        h.USER,
        {"label": "No dear debt", "check": "max_debt_rate_while_investing <= 0.07"},
        author="agent",
        agent="Claude",
    )
    assert (by_agent["author"], by_agent["agent"]) == ("agent", "Claude")


async def test_a_principle_names_only_a_cash_account_of_ones_own():
    books = Books()
    with pytest.raises(PrincipleError) as caught:
        await books.principles.add(
            h.USER, {"label": "x", "check": "account_lowest >= 0", "account": "brk"}
        )
    assert [(p.path, p.message) for p in caught.value.problems] == [
        ("account", "Brokerage is not one of your cash accounts")
    ]


async def test_checking_is_never_a_ranking_and_reads_salli_figures():
    books = Books()
    await books.principles.add(h.USER, {"label": "Six months", "check": "emergency_months >= 6"})
    await books.principles.add(
        h.USER,
        {"label": "Checking above 5,000", "check": "account_lowest >= 5000", "account": "chk"},
    )
    checked = await books.principles.check(h.USER, [CASH, WAIT])
    statuses = {
        o["label"]: [r["status"] for r in o["results"]]
        for o in [{"label": "baseline", **checked["baseline"]}, *checked["options"]]
    }
    # Paying cash takes checking's low from 6,063.46 to 4,883.77, under 5,000.
    assert statuses == {
        "baseline": ["keeps", "keeps"],
        "Pay cash": ["keeps", "breaks"],
        "Wait": ["keeps", "keeps"],
    }
    pay = checked["options"][0]
    assert pay["results"][1]["figures"] == {"account_lowest": "4883.77"}
    assert "rank" not in str(checked) and "score" not in str(checked)


async def test_a_scenario_problem_is_under_its_option():
    books = Books()
    bad = {**CASH, "changes": [{**CASH["changes"][0], "date": "2026-01-01"}]}
    with pytest.raises(ScenarioError) as caught:
        await books.principles.check(h.USER, [WAIT, bad])
    assert paths(caught) == ["options[1].changes[0].date"]


# ── Recording ────────────────────────────────────────────────────────────────


async def test_an_entry_records_what_salli_ran_and_the_persons_words():
    books = Books()
    await books.principles.add(h.USER, {"label": "Six months", "check": "emergency_months >= 6"})
    recorded = await books.decisions.record(
        h.USER,
        decision(agent_summary="Cash costs no interest.", agent="Claude"),
        via={"channel": "api"},
    )
    entry = recorded["entry"]
    assert recorded["hash"] == journal.digest(entry) and recorded["verified"]
    assert recorded["status"] == "awaiting_review"
    assert (entry["schema"], entry["recorded_at"], entry["as_of"]) == (
        "salli.decision/1",
        NOW.isoformat(),
        "2026-10-11",
    )
    assert (entry["chosen"], entry["reasons"]) == ("Pay cash", "The old one is dying.")
    assert entry["agent_summary"] == {
        "text": "Cash costs no interest.",
        "author": "agent",
        "agent": "Claude",
    }
    pay, wait = entry["options"]
    assert pay["figures"]["lowest_cash"] == "11598.91"
    assert wait["figures"]["lowest_cash"] == entry["baseline"]["figures"]["lowest_cash"]
    assert pay["principles"][0]["status"] == "keeps"
    # The projection runs a year past the review month: October 2026 to
    # April 2028, and the as-of point.
    assert (pay["projection"][0]["date"], pay["projection"][-1]["month"]) == (
        "2026-10-11",
        "2028-04",
    )
    assert entry["basis"]["placeholders"] == [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation",
    ]
    assert entry["principles"][0]["label"] == "Six months"


async def test_a_decision_is_refused_with_every_problem():
    books = Books()
    with pytest.raises(JournalError) as caught:
        await books.decisions.record(
            h.USER,
            decision(chosen="Lease", reasons=" ", review_on="2026-10-20"),
            via={"channel": "api"},
        )
    assert sorted(paths(caught)) == ["chosen", "reasons", "review_on"]
    assert books.uow.decisions.entries == {}


async def test_options_need_their_own_labels():
    books = Books()
    with pytest.raises(JournalError) as caught:
        await books.decisions.record(
            h.USER,
            decision(options=[CASH, {**WAIT, "label": "Pay cash"}]),
            via={"channel": "api"},
        )
    assert paths(caught) == ["options[1].label"]


async def test_a_review_waits_for_its_date_and_then_appends():
    books = Books()
    recorded = await books.decisions.record(h.USER, decision(), via={"channel": "api"})
    with pytest.raises(JournalError) as caught:
        await books.decisions.review(h.USER, recorded["id"], "Too soon.")
    assert paths(caught) == ["as_of"]
    assert (await books.decisions.due(h.USER))["reviews"] == []

    books.today = dt.date(2027, 4, 12)
    [due] = (await books.decisions.due(h.USER))["reviews"]
    assert (due["id"], due["status"], due["reasons"]) == (
        recorded["id"],
        "review_due",
        "The old one is dying.",
    )
    assert due["comparison"]["at"] == "2027-03-31"
    reviewed = await books.decisions.review(
        h.USER, recorded["id"], "Glad I did.", author="agent", agent="Claude"
    )
    document = reviewed["review"]
    assert (document["author"], document["agent"], document["entry_hash"]) == (
        "agent",
        "Claude",
        recorded["hash"],
    )
    assert (await books.decisions.due(h.USER))["reviews"] == []
    read = await books.decisions.get(h.USER, recorded["id"])
    assert read["status"] == "reviewed" and read["entry"] == recorded["entry"]


async def test_another_users_decision_is_not_found():
    books = Books()
    recorded = await books.decisions.record(h.USER, decision(), via={"channel": "api"})
    for attempt in (
        books.decisions.get("someone-else", recorded["id"]),
        books.decisions.add_note("someone-else", recorded["id"], "Hi."),
        books.decisions.review("someone-else", recorded["id"], "Hi."),
    ):
        with pytest.raises(DecisionNotFound):
            await attempt


async def test_the_journal_exports_as_json_and_markdown():
    books = Books()
    recorded = await books.decisions.record(h.USER, decision(), via={"channel": "api"})
    await books.decisions.add_note(h.USER, recorded["id"], "Bought it.")
    exported = await books.decisions.export(h.USER, "json")
    assert isinstance(exported, dict)
    [item] = exported["entries"]
    assert (item["entry"], item["hash"]) == (recorded["entry"], recorded["hash"])
    assert journal.verify(item["notes"][0]["note"], item["notes"][0]["hash"])
    text = await books.decisions.export(h.USER, "markdown", recorded["id"])
    assert isinstance(text, str) and "## Laptop: pay cash now, or wait?" in text


async def test_a_due_review_is_synced_with_the_other_alerts():
    from salli.application.services.reminder_service import ReminderService

    books = Books()
    recorded = await books.decisions.record(h.USER, decision(), via={"channel": "api"})
    [reminder] = books.uow.reminders.rows.values()
    assert (reminder["source_domain"], reminder["source_id"], reminder["due_date"]) == (
        "decision",
        recorded["id"],
        "2027-04-11",
    )
    reminder["status"] = "done"  # dismissed by the person before it was due
    reminders = ReminderService(books.uow.factory())
    assert await reminders.sync_alerts(h.USER, "2027-04-10") == {}
    assert await reminders.sync_alerts(h.USER, "2027-04-11") == {"decision_review": 1}
    [reminder] = books.uow.reminders.rows.values()
    assert reminder["status"] == "pending"
