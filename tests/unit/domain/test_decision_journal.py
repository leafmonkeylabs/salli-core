"""
The decision journal's documents (domain/decisions/journal.py): content
hashes over canonical JSON, notes and reviews that point at the entry
without changing it, what a decision must say, the Markdown export; and a
review's comparison, worked by hand (domain/decisions/review.py).
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest

from salli.domain import canonical
from salli.domain.baseline.models import Baseline, MonthFlow
from salli.domain.decisions import journal, review

D = Decimal
AT = dt.datetime(2026, 10, 11, 9, 0, tzinfo=dt.UTC)


def _projection(*cash: str) -> list[dict[str, str | None]]:
    """Month-ends from 2026-10-11, each with the given cash and fixed others."""
    months = ["2026-10", "2026-10", "2026-11", "2026-12", "2027-01"]
    dates = ["2026-10-11", "2026-10-31", "2026-11-30", "2026-12-31", "2027-01-31"]
    return [
        {
            "month": months[i],
            "date": dates[i],
            "cash": value,
            "investments": "40000.00",
            "owed": "17000.00",
            "net_worth": str(D(value) + D("40000.00") - D("17000.00")),
            "spending": None if i < 2 else "2000.00",
        }
        for i, value in enumerate(cash)
    ]


def _entry(**more: Any) -> dict[str, Any]:
    option = {
        "label": "Pay cash",
        "scenario": {"schema": "salli.scenario/1", "changes": []},
        "scenario_hash": "sha256:" + "a" * 64,
        "figures": {"lowest_cash": "11598.91", "emergency_months": "6.11", "fi_months": 188},
        "unavailable": {},
        "principles": [],
        "projection": _projection("15000.00", "12500.00", "12000.00", "11800.00", "11500.00"),
        "notes": [],
    }
    other = {
        **copy.deepcopy(option),
        "label": "Wait",
        "projection": _projection("15000.00", "15000.00", "15200.00", "15400.00", "15600.00"),
    }
    content = {
        "schema": journal.SCHEMA_ID,
        "id": "d-1",
        "recorded_at": AT.isoformat(),
        "recorded_via": {"channel": "api"},
        "question": "Laptop: now or later?",
        "as_of": "2026-10-11",
        "currency": "EUR",
        "basis": {
            "baseline_fingerprint": "sha256:" + "b" * 64,
            "versions": {"engine": "2"},
            "assumptions": {},
            "placeholders": ["inflation"],
            "data_as_of": "2026-10-09",
            "is_stale": False,
        },
        "principles": [],
        "baseline": {"figures": {"lowest_cash": "13998.91"}, "unavailable": {}, "principles": []},
        "options": [option, other],
        "chosen": "Pay cash",
        "reasons": "I'd rather not owe.\nAnd it's on sale.",
        "agent_summary": {"text": "Cash costs no interest.", "author": "agent", "agent": "Claude"},
        "review_on": "2026-12-31",
    }
    content.update(more)
    return content


# ── Hashes ───────────────────────────────────────────────────────────────────


def test_an_entrys_hash_is_its_canonical_json_and_survives_storage():
    entry = _entry()
    digest = journal.digest(entry)
    assert digest == "sha256:" + hashlib.sha256(canonical.dumps(entry).encode("ascii")).hexdigest()
    # Key order, and a round trip through JSON (as JSONB stores it), change nothing.
    shuffled = json.loads(json.dumps(entry, sort_keys=False))
    reordered = dict(reversed(list(shuffled.items())))
    assert journal.verify(reordered, digest)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("reasons",), "I changed my mind."),
        (("chosen",), "Wait"),
        (("options", 0, "figures", "lowest_cash"), "11598.92"),
        (("options", 0, "projection", 3, "cash"), "11800.01"),
        (("agent_summary",), None),
    ],
)
def test_any_change_shows(path: tuple[str | int, ...], value: Any):
    entry = _entry()
    digest = journal.digest(entry)
    changed = copy.deepcopy(entry)
    target: Any = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert not journal.verify(changed, digest)


def test_a_note_and_a_review_point_at_the_entry_and_leave_it_as_it_was():
    entry = _entry()
    before = copy.deepcopy(entry)
    digest = journal.digest(entry)
    note = journal.note(
        note_id="n-1", decision_id="d-1", entry_hash=digest, at=AT, text=" Bought it. ",
        author="user",
    )  # fmt: skip
    assert note == {
        "schema": "salli.decision-note/1",
        "id": "n-1",
        "decision_id": "d-1",
        "entry_hash": digest,
        "at": AT.isoformat(),
        "text": "Bought it.",
        "author": "user",
        "agent": None,
    }
    reviewed = journal.review(
        review_id="r-1",
        decision_id="d-1",
        entry_hash=digest,
        at=AT,
        as_of=dt.date(2027, 1, 2),
        reflection="Fine.",
        comparison={"option": "Pay cash"},
        author="agent",
        agent="Claude",
    )
    assert (reviewed["entry_hash"], reviewed["agent"]) == (digest, "Claude")
    assert entry == before and journal.verify(entry, digest)


# ── What a decision must say ─────────────────────────────────────────────────


def _problems(**kw: Any) -> list[tuple[str, str]]:
    args: dict[str, Any] = {
        "question": "Q?",
        "labels": ["A", "B"],
        "chosen": "A",
        "reasons": "Because.",
        "agent_summary": None,
        "review_on": dt.date(2027, 4, 11),
        "as_of": dt.date(2026, 10, 11),
        "earliest_review": review.earliest_review(dt.date(2026, 10, 11)),
    }
    args.update(kw)
    return [(p.path, p.message) for p in journal.entry_problems(**args)]


def test_a_decision_well_formed():
    assert _problems() == []


def test_a_decision_needs_reasons_in_the_persons_own_words():
    assert _problems(reasons="  ") == [("reasons", "is required: write it in your own words")]


def test_options_are_labelled_once_and_the_choice_is_one_of_them():
    found = dict(_problems(labels=["A", "A", None], chosen="C"))
    assert set(found) == {"options[1].label", "options[2].label", "chosen"}


def test_the_review_date_is_at_a_months_end_or_after():
    assert review.earliest_review(dt.date(2026, 10, 11)) == dt.date(2026, 10, 31)
    [(path, message)] = _problems(review_on=dt.date(2026, 10, 30))
    assert path == "review_on" and "2026-10-31" in message
    assert _problems(review_on=dt.date(2026, 10, 31)) == []


# ── The Markdown export ──────────────────────────────────────────────────────


def test_the_markdown_says_whose_words_are_whose_and_every_hash():
    entry = _entry()
    digest = journal.digest(entry)
    text = journal.markdown([{"entry": entry, "hash": digest, "notes": [], "reviews": []}], AT)
    assert "## Laptop: now or later?" in text
    assert (
        "**Reasons, in the person's words**\n\n> I'd rather not owe.\n> And it's on sale." in text
    )
    assert "**The agent's summary** (Claude), written by the agent, not the person" in text
    assert "| Lowest cash, next 12 months | 13998.91 | 11598.91 | 11598.91 |" in text
    assert f"Entry hash `{digest}`" in text


def test_a_table_cell_cant_break_the_table():
    entry = _entry(options=[{**_entry()["options"][0], "label": "A | B\nC"}], chosen="A | B\nC")
    text = journal.markdown(
        [{"entry": entry, "hash": journal.digest(entry), "notes": [], "reviews": []}], AT
    )
    assert "| Figure | Baseline | A \\| B C |" in text


# ── A review's comparison, by hand ───────────────────────────────────────────


def _actual(**kw: Any) -> Baseline:
    values = {
        "cash": D("11234.50"),
        "savings": D("0"),
        "investments": D("39000.00"),
        "other_assets": D("0"),
        "debts_owed": D("16900.00"),
        "other_liabilities": D("100.00"),
        "latest_entry": "2026-12-28",
        "notes": (),
        "fingerprint": "sha256:" + "c" * 64,
    }
    values.update(kw)
    return cast(Baseline, SimpleNamespace(**values))


def _month(month: str, expenses: str) -> MonthFlow:
    return MonthFlow(month, D(0), D(expenses), -D(expenses), D(0), D(0))


def test_comparing_at_a_months_end():
    assert review.comparison_date(dt.date(2027, 1, 2)) == dt.date(2026, 12, 31)
    assert review.comparison_date(dt.date(2026, 12, 31)) == dt.date(2026, 12, 31)
    assert review.comparison_date(dt.date(2027, 3, 1)) == dt.date(2027, 2, 28)


def test_what_was_projected_against_what_happened():
    """Reviewed on 2027-01-02, so compared at 2026-12-31: the projection's
    fourth point (cash 11,800.00, investments 40,000.00, owed 17,000.00, net
    worth 34,800.00) against the books that day."""
    entry = _entry()
    at, notes = review.compared_at(entry, dt.date(2027, 1, 2))
    assert (at, notes) == (dt.date(2026, 12, 31), [])
    compared = review.compare(
        entry,
        at=at,
        actual=_actual(),
        spent=[_month("2026-10", "1900.00"), _month("2026-11", "2150.25"), _month("2026-12", "2300.75")],
    )  # fmt: skip
    assert compared["figures"] == [
        # 11,234.50 - 11,800.00
        {"figure": "cash", "projected": "11800.00", "actual": "11234.50", "difference": "-565.50"},
        {
            "figure": "investments",
            "projected": "40000.00",
            "actual": "39000.00",
            "difference": "-1000.00",
        },
        # What is owed: the debts' 16,900.00 and the other liabilities' 100.00.
        {"figure": "owed", "projected": "17000.00", "actual": "17000.00", "difference": "0.00"},
        # 11,234.50 + 39,000.00 - 17,000.00 = 33,234.50, against 34,800.00.
        {
            "figure": "net_worth",
            "projected": "34800.00",
            "actual": "33234.50",
            "difference": "-1565.50",
        },
    ]
    # November and December, the full months since the decision (October,
    # its as-of month, was partly over): 2,000.00 a month projected, and
    # (2,150.25 + 2,300.75) / 2 = 2,225.50 spent.
    assert compared["spending"] == {
        "months": ["2026-11", "2026-12"],
        "projected": "2000.00",
        "actual": "2225.50",
        "difference": "225.50",
    }
    # The other option's expectation for the same day, never "what would
    # have happened".
    assert compared["others"] == [
        {
            "option": "Wait",
            "cash": "15400.00",
            "investments": "40000.00",
            "owed": "17000.00",
            "net_worth": "38400.00",
        }
    ]
    assert (compared["is_stale"], compared["data_as_of"]) == (False, "2026-12-28")


def test_a_review_past_the_projection_compares_at_its_end():
    at, notes = review.compared_at(_entry(), dt.date(2027, 6, 15))
    assert at == dt.date(2027, 1, 31)
    assert notes and "runs to 2027-01-31" in notes[0]


def test_a_stale_ledger_is_said_first():
    compared = review.compare(
        _entry(), at=dt.date(2026, 12, 31), actual=_actual(latest_entry="2026-10-01"), spent=[]
    )
    assert compared["is_stale"] is True
    assert compared["notes"][0].startswith("Your ledger's newest entry is from 2026-10-01")
