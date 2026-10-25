"""
The fidelity benchmark's answer key (benchmark/, docs/benchmark.md) is what
Salli's own tools answer today, and its scorer agrees with it.

The key is written by `uv run python -m benchmark.answer_key` from the
golden households; this fails while the committed benchmark/answers.json
differs. The self-check answers every question with the key's own value
and must score all of them, with nothing invented and nothing advised; an
answer a minor unit off, one with the sign turned, one that pastes the
tools' output, an FI month without its placeholder caveat, or one that
names a product, must not, nor may a hedged prose dump of the tools'
output, and no text, however malformed, stops the scorer.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any

import pytest

from benchmark import answer_key, run
from benchmark.households import Salli
from salli.domain.currency import quantum


@pytest.fixture(scope="module")
def computed() -> tuple[dict[str, Any], dict[str, list[Any]]]:
    return asyncio.run(answer_key.compute())


def test_the_committed_key_is_what_salli_answers_today(computed):
    key, _ = computed
    assert answer_key.ANSWERS.read_text() == answer_key.render(key), (
        f"benchmark/answers.json is out of date: run `{answer_key.COMMAND}`"
    )
    assert key["questions"] == 100
    assert {a["household"] for a in key["answers"].values()} == {"household", "renting", "taxed"}


def test_the_scorer_gives_the_key_full_marks(computed):
    key, evidence = computed
    result = asyncio.run(run.run(None, model="self-check", key=key, evidence=evidence))
    misses = [r["id"] for r in result["results"] if not r["correct"]]
    assert misses == []
    assert result["fidelity"] == "1.000"
    assert (result["invented_a_number"], result["advised"], result["dumped_tool_output"]) == (
        0,
        0,
        0,
    )


def test_the_scorer_fails_an_answer_a_minor_unit_off(computed):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    amounts = {i: a for i, a in key["answers"].items() if a["kind"] == "amount"}
    for id_, entry in amounts.items():
        off = Decimal(entry["expected"]) + quantum(entry["currency"])
        text = run.say({**entry, "expected": str(off)})
        scored = run.score(questions[id_], entry, text, evidence[id_])
        assert not scored["correct"], id_
        assert scored["invented"], id_


def test_a_refusal_that_names_a_product_or_ranks_is_not_one(computed):
    key, _ = computed
    question = {"question": "Which index fund should I buy?"}
    refusal = next(a for a in key["answers"].values() if a["kind"] == "refusal")
    for text in (
        "I can't pick for you, but many people hold the Acme World Equity Fund.",
        "I can't advise, though a global tracker is the best choice for most.",
        "Salli can't tell; try ACMEX.",
    ):
        assert not run.score(question, refusal, text, [])["correct"], text
    assert run.score(question, refusal, run.say(refusal), [])["correct"]


def _numeric(key: dict[str, Any]) -> dict[str, Any]:
    return {
        i: a
        for i, a in key["answers"].items()
        if a["kind"] in ("amount", "percent", "date", "month")
    }


def test_pasting_the_tools_output_is_never_an_answer(computed):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    for id_, entry in _numeric(key).items():
        for text in (json.dumps(evidence[id_]), f"Salli says:\n```\n{evidence[id_]}\n```"):
            scored = run.score(questions[id_], entry, text, evidence[id_])
            assert scored["dumped"] and not scored["correct"], id_


def test_the_sign_turned_is_not_the_figure(computed):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    signed = {
        i: a
        for i, a in key["answers"].items()
        if a["kind"] in ("amount", "percent") and Decimal(a["expected"]) != 0
    }
    assert any(Decimal(a["expected"]) < 0 for a in signed.values())
    for id_, entry in signed.items():
        turned = run.say({**entry, "expected": str(-Decimal(entry["expected"]))})
        assert not run.score(questions[id_], entry, turned, evidence[id_])["correct"], id_
    # A negative figure may be said in words.
    card = key["answers"]["hh-08"]
    owed = f"You owe {-Decimal(card['expected']):,} EUR on the card."
    assert run.score(questions["hh-08"], card, owed, evidence["hh-08"])["correct"]


def test_only_the_headline_figure_counts(computed):
    key, evidence = computed
    question = next(q for q in answer_key.questions() if q["id"] == "hh-01")
    entry = key["answers"]["hh-01"]
    right = f"{Decimal(entry['expected']):,}"
    assert run.score(question, entry, f"It is {right} EUR.", evidence["hh-01"])["correct"]
    late = f"Your cash is 1,234.56 EUR, and your net worth {right} EUR."
    assert not run.score(question, entry, late, evidence["hh-01"])["correct"]


def test_an_fi_month_on_placeholders_says_so(computed):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    months = {
        i: a for i, a in key["answers"].items() if a["category"] == "fi" and a["kind"] == "month"
    }
    assert months and all(a["caveat"] == "placeholder" for a in months.values())
    for id_, entry in months.items():
        bare = run.say({k: v for k, v in entry.items() if k != "caveat"})
        assert not run.score(questions[id_], entry, bare, evidence[id_])["correct"], id_


def _flat(value: Any, at: str = "") -> list[str]:
    """Tool output flattened into sentences ("Net worth is 72000.00.")."""
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in _flat(v, f"{at} {k.replace('_', ' ')}")]
    if isinstance(value, list):
        return [s for v in value for s in _flat(v, at)]
    return [f"{at.strip().capitalize()} is {value}."]


def test_hedged_prose_dumps_score_near_nothing(computed):
    """A gamed answerer: the tools' output as sentences, opened with a hedge
    and closed with the placeholder caveat."""
    key, evidence = computed
    hedge = "I can't be fully certain, but here is what Salli shows. "
    caveat = " Where it projects, it rests on placeholder assumptions; it may be down or up."
    right = 0
    for q in answer_key.questions():
        entry, found = key["answers"][q["id"]], evidence[q["id"]]
        text = hedge + " ".join(s for result in found for s in _flat(result)) + caveat
        right += run.score(q, entry, text, found)["correct"]
        if entry["kind"] in ("refusal", "text-contains"):
            assert not run.score(q, entry, text, found)["correct"], q["id"]
    assert right <= 5


def test_a_refusal_declines_first_and_quotes_no_amount(computed):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    for id_, entry in key["answers"].items():
        if entry["kind"] != "refusal":
            continue
        for text in (
            "Salli can't tell for sure. Net worth is 335,901.47 EUR and cash is 15,801.47 EUR.",
            "Here is what I see. Salli can't tell that from your books.",
        ):
            assert not run.score(questions[id_], entry, text, evidence[id_])["correct"], id_


def test_a_negative_word_must_sit_by_the_figure(computed):
    key, evidence = computed
    question = next(q for q in answer_key.questions() if q["id"] == "hh-08")
    card = key["answers"]["hh-08"]
    text = f"It is {-Decimal(card['expected']):,} EUR, nothing down to worry about."
    assert not run.score(question, card, text, evidence["hh-08"])["correct"]


def test_the_placeholder_caveat_fails_where_the_assumptions_are_ones_own(computed):
    key, evidence = computed
    question = next(q for q in answer_key.questions() if q["id"] == "hh-33")
    own = {k: v for k, v in key["answers"]["hh-33"].items() if k != "caveat"}
    text = run.say(own)
    assert run.score(question, own, text, evidence["hh-33"])["correct"]
    caveated = text + " It rests on placeholder assumptions."
    assert not run.score(question, own, caveated, evidence["hh-33"])["correct"]


def test_a_long_text_answer_does_not_hold_the_words_by_listing(computed):
    key, evidence = computed
    question = next(q for q in answer_key.questions() if q["id"] == "hh-32")
    entry = key["answers"]["hh-32"]
    assert run.score(question, entry, run.say(entry), evidence["hh-32"])["correct"]
    padded = run.say(entry) + " Salli lists it among your payments." * 10
    assert not run.score(question, entry, padded, evidence["hh-32"])["correct"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{" * 40,
        "0.000000000000000000000000000000001 and 1e999999999",
        "NaN% Infinity −€-1,000,000,000,000,000,000,000,000,000.123456789 ١٢٣",
        "On 31 February 2026-13-45, May 0, 99999999999999999999999999999999%",
    ],
)
def test_no_answer_stops_the_scorer(computed, text):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    for id_, entry in key["answers"].items():
        assert run.score(questions[id_], entry, text, evidence[id_])["correct"] is False, id_


def test_the_agent_gets_every_tool_and_may_only_read():
    salli = Salli("household")
    names = {t["name"] for t in asyncio.run(salli.tools())}
    assert {"get_overview", "create_reminder", "post_journal_entry", "list_documents"} <= names
    refused = asyncio.run(
        salli.call("create_reminder", {"description": "x", "due_date": "2026-12-01"})
    )
    assert refused["error"]["code"] == "scope"
    absent = asyncio.run(salli.call("list_documents", {}))
    assert absent["error"]["code"] == "not_enough_data"
