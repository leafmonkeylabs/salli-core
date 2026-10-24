"""
The accuracy benchmark's answer key (benchmark/, docs/benchmark.md) is what
Salli's own tools answer today, and its scorer agrees with it.

The key is written by `uv run python -m benchmark.answer_key` from the
golden households; this fails while the committed benchmark/answers.json
differs. The self-check answers every question with the key's own value
and must score all of them, with nothing invented and nothing advised; an
answer a minor unit off, or one that names a product, must not.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from benchmark import answer_key, run
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
    assert result["accuracy"] == "1.000"
    assert (result["invented_a_number"], result["advised"]) == (0, 0)


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
