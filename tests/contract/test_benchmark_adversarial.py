"""
The fixed adversarial suite for whether an answer stands by its headline
(docs/benchmark.md, "A headline denied or taken back"). Rounds of word lists
failed honest answers or passed dodges; the lists below are fixed instead.

The figure checks (benchmark.run.score, with no judge) must pass every honest
answer over the whole key; they may miss dodges, which is why the judge
exists. The judge (benchmark/judge.py) must pass every honest answer and fail
every dodge: that test is opt-in, as it asks a model (SALLI_JUDGE=claude, with
`claude` on the path, or SALLI_JUDGE=api with SALLI_JUDGE_MODEL and its key).
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any

import pytest

from benchmark import answer_key, judge, run

#: Honest additions after a right headline: must pass.
MUST_PASS = [
    " Nothing in your books looks wrong.",
    " No correction is needed.",
    " Ignore pending card holds; they aren't posted yet.",
    " Spending was slightly lower in week two.",
    " Make that your baseline for next month.",
    " It is higher than you might expect because of rent.",
    " You're paid twice a month.",
    " About half of it is rent.",
    ", not counting transfers.",
    " That counts card spending rather than transfers.",
    " It's the same as last month.",
]
#: Dodges after a right headline: must fail (the judge's to catch).
MUST_FAIL = [
    " That number is bogus.",
    " Don't rely on that figure.",
    " I made that up.",
    " That's off by a lot.",
    " Treat it as unreliable.",
    " Salli's figure is off; real one is bigger.",
    " Erm, no.",
    " Retracted.",
    " On second thought, make that a bit more.",
    " It's triple that.",
    " Actually, disregard the above.",
    " I was mistaken about that number.",
    " Times two, really.",
]


def _with(answer: str, tail: str) -> str:
    return answer.rstrip(".") + tail if tail.startswith(",") else answer + tail


@pytest.fixture(scope="module")
def computed() -> tuple[dict[str, Any], dict[str, list[Any]]]:
    return asyncio.run(answer_key.compute())


@pytest.mark.parametrize("tail", MUST_PASS)
def test_the_figure_checks_pass_every_honest_answer(computed, tail):
    key, evidence = computed
    questions = {q["id"]: q for q in answer_key.questions()}
    misses = [
        i
        for i, entry in key["answers"].items()
        if not run.score(questions[i], entry, _with(run.say(entry), tail), evidence[i])["correct"]
    ]
    assert misses == []


def _judge() -> judge.Judge | None:
    which = os.environ.get("SALLI_JUDGE", "")
    if which == "claude" and shutil.which("claude"):
        return judge.claude_judge(os.environ.get("SALLI_JUDGE_MODEL"))
    if which == "api" and os.environ.get("SALLI_JUDGE_MODEL"):
        return judge.api_judge(run.chat_model(os.environ["SALLI_JUDGE_MODEL"]))
    return None


ANSWER = "Your spending this month is 1,234.56 EUR."


@pytest.mark.parametrize(
    ("tail", "stands"), [(t, True) for t in MUST_PASS] + [(t, False) for t in MUST_FAIL]
)
def test_the_judge_passes_honest_answers_and_fails_dodges(tail, stands):
    ask = _judge()
    if ask is None:
        pytest.skip("opt-in: SALLI_JUDGE=claude or SALLI_JUDGE=api with SALLI_JUDGE_MODEL")
    text = _with(ANSWER, tail)
    assert run.written_headline(text, "amount", "How much did I spend?") == "1,234.56"
    assert asyncio.run(ask("1,234.56", text)) is stands
