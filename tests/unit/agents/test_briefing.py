"""
The monthly briefing describes Salli's own figures and never advises: the
model writes slots, never numbers, and a draft that advises, judges, names a
product or writes a figure of its own is refused (domain/agents/briefing.py).
"""

from __future__ import annotations

import json

import pytest

from salli.domain.agents.briefing import (
    BRIEFING_PROMPT,
    Draft,
    Note,
    check,
    figures_of,
    narrate,
    view,
)
from salli.domain.llm import LLMUnreadableAnswer
from tests.fakes import FakeLLM
from tests.guardrails import assert_never_urges

SCORE = {
    "currency": "EUR",
    "monthly_income": "4200.00",
    "monthly_expenses": "2650.5",
    "monthly_surplus": "1549.5",
    "savings_rate": "0.36892857",
    "emergency_fund_months": "4.26",
    "net_worth": "61200.00",
    "fi_asset_base": "48000.00",
    "fi_number": "795150.00",
    "progress_to_fi": "0.0604",
    "projected_fi_month": "2049-03",
}
PROJECTIONS = {
    "currency": "EUR",
    "fi_by": {
        "conservative": {"months": 330, "month": "2054-04"},
        "base": {"months": 269, "month": "2049-03"},
        "growth": {"months": None, "month": None},
    },
}
GOALS = [
    {"name": "Kitchen", "current_amount": "1200.00", "target_amount": "8000.00", "progress": 0.15}
]


def _figures():
    return figures_of(SCORE, PROJECTIONS, GOALS)


def test_the_figures_are_salli_s_own_formatted_for_reading():
    figures = _figures()
    assert figures["spending"]["value"] == "2,650.50 EUR"
    assert figures["savings_rate"]["value"] == "36.9%"
    assert figures["cash_cover"]["value"] == "4.3 months"
    assert figures["fi_month"]["value"] == "March 2049"
    assert figures["fi_month_cautious"]["value"] == "April 2054"
    # Not reached within the timeline: no figure, rather than an empty one.
    assert "fi_month_growth" not in figures
    assert figures["goal_1"]["value"] == "Kitchen"
    assert figures["goal_1_progress"]["value"] == "15%"
    # Nothing that scores or grades: a briefing describes.
    assert not {"score", "grade", "overall_score"} & set(figures)


def _draft(summary: str, *notes: str) -> Draft:
    return Draft(summary=summary, notes=[Note(topic="spending", text=n) for n in notes])


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("You spent 2,650 EUR a month.", "number"),
        ("You spent {spending}, so you should cut back.", "advises"),
        ("Consider moving {surplus} into savings.", "advises"),
        ("Your best month was this one.", "advises"),
        ("Your score went up.", "advises"),
        ("A good month: you kept {savings_rate}.", "advises"),
        ("Pay down the card before {fi_month}.", "advises"),
        ("You spent {spending}. Move what is left over.", "advises"),
        ("You may want to look at {spending}.", "advises"),
        ("Your cash covers three months of spending.", "number"),
        ("You kept half of your income.", "number"),
        ("Idle cash could sit in a fixed deposit.", "product"),
        ("Index funds are where the {surplus} goes.", "product"),
        ("Your pension holds {invested}.", "product"),
        ("You spent {groceries} on food.", "slots"),
        ("You saved {surplus}!", "exclamation"),
    ],
)
def test_a_draft_that_breaks_the_rules_is_refused(text, why):
    reason = check(_draft("Where things stand.", text), _figures())
    assert reason is not None and why in reason


def test_the_reason_never_repeats_the_word_it_caught():
    reason = check(_draft("You should save more."), _figures())
    assert reason is not None and "should" not in reason


def test_salli_s_own_words_for_its_figures_pass():
    for text in (
        "Your emergency fund covers {cash_cover}.",
        "Your net worth is {net_worth}.",
        "Kitchen holds {goal_1_saved} of {goal_1_target}.",
    ):
        assert check(_draft(text), _figures()) is None, text


def test_a_draft_that_describes_with_slots_is_kept_and_filled():
    figures = _figures()
    draft = _draft(
        "You spent {spending} a month on average and kept {savings_rate} of income.",
        "Your cash covers {cash_cover} of spending.",
    )
    assert check(draft, figures) is None
    shown = view(draft, {"figures": figures, "signals": [], "assumptions": {}})
    assert shown["summary"] == (
        "You spent 2,650.50 EUR a month on average and kept 36.9% of income."
    )
    assert shown["briefing"]["notes"] == [
        {"topic": "spending", "text": "Your cash covers 4.3 months of spending."}
    ]
    # What a person reads ranks, urges and advises nothing.
    assert_never_urges({"summary": shown["summary"], "notes": shown["briefing"]["notes"]})


def test_the_prompt_forbids_advice_and_numbers():
    for phrase in (
        "never advise",
        "Never write a digit",
        "No recommendation, no next step, no",
        "no kind of investment, product,",
        "placeholders, not forecasts",
    ):
        assert phrase in BRIEFING_PROMPT, phrase


def _answer(summary: str) -> str:
    return json.dumps({"summary": summary, "notes": []})


async def test_a_refused_draft_is_asked_for_once_more_with_the_reason():
    llm = FakeLLM(replies=[_answer("You should save more."), _answer("You spent {spending}.")])
    draft = await narrate({"figures": _figures()}, llm=llm)
    assert draft.summary == "You spent {spending}."
    assert "refused" in llm.requests[1]["input"]
    assert "advises" in llm.requests[1]["input"]


async def test_a_second_refusal_is_an_unreadable_answer():
    llm = FakeLLM(replies=[_answer("You should save more."), _answer("Spend 100 less.")])
    with pytest.raises(LLMUnreadableAnswer):
        await narrate({"figures": _figures()}, llm=llm)
