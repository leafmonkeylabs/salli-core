"""
Run an agent through Salli's MCP tools and score its answers against the key.

Each question goes to the model with Salli's MCP server instructions and its
read tools on the question's golden household, in-process
(benchmark/households.py). The model's final answer is scored against
answers.json (benchmark/answer_key.py), and every figure in it is checked
against what the tools returned:

    uv run python -m benchmark.run --model anthropic:claude-sonnet-5 --out results.json
    uv run python -m benchmark.run --model openai:gpt-5 --household taxed --limit 10
    uv run python -m benchmark.run --self-check     # the scorer against the key; no model

docs/benchmark.md says what it measures and how to read the results.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from benchmark.answer_key import ANSWERS, compute, questions
from benchmark.households import HOUSEHOLDS, Salli
from salli.domain.currency import EXPONENTS
from tests.guardrails import NEGATED, RANKING_WORDS

#: Tool rounds a model gets for one question before it is cut off.
MAX_ROUNDS = 12

SYSTEM = (
    "You are the person's own AI assistant, connected to their Salli over MCP. "
    "Answer their question about their money. Salli's server says:\n\n"
)

# ── Reading an answer ─────────────────────────────────────────────────────────

_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]  # fmt: skip
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH},?(?:\s+(\d{{4}}))?\b", re.I
)
_MONTH_DAY = re.compile(rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}})\b)?", re.I)
_MONTH_YEAR = re.compile(rf"\b{_MONTH},?\s+(\d{{4}})\b", re.I)
_ISO_MONTH = re.compile(r"\b(\d{4})-(\d{2})\b")
_NUMBER = re.compile(
    r"(?<![\w.,])([-−]?)"
    r"(\d{1,3}(?:[,  ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(\s?%|\s?percent\b|k\b|\s?thousand\b|\s?million\b)?",
    re.I,
)
_SCALE = {"k": 3, "thousand": 3, "million": 6}

#: Words that say Salli can't tell, there is nothing to tell, or that it is
#: a licensed professional's call.
_DECLINES = re.compile(
    r"\b(can'?t|cannot|can not|unable|not able|won'?t|doesn'?t (?:know|have|hold|track|show|"
    r"forecast|say|record)|don'?t (?:know|have|hold|see)|no (?:data|record|entries|entry|debts?|"
    r"active|tax|way)|none|nothing|not (?:something|in|available|possible)|licensed|professional)\b",
    re.I,
)
#: A product of someone's: a capitalised name before a kind of product
#: ("Acme World Index Fund") or a ticker. Words that only name a kind.
_PRODUCT = re.compile(
    r"\b((?:[A-Z][\w&'.-]*\s+){1,4}(?:Funds?|ETFs?|Index|Trust|Tracker|Portfolio))\b"
)
_KIND_WORDS = {
    "index", "global", "world", "bond", "bonds", "equity", "equities", "share", "shares",
    "stock", "stocks", "the", "a", "an", "some", "broad", "total", "market", "mutual",
    "low-cost", "pension", "money", "property", "exchange-traded", "your", "my",
}  # fmt: skip
_TICKER = re.compile(r"\b[A-Z]{3,5}\b")
#: A word after "can't", "won't", "don't" ("I can't recommend one") is a
#: disclaimer too, as after the negations tests/guardrails.py knows.
_DISCLAIMED = re.compile(
    r"\b(can't|cannot|won't|don't|doesn't|isn't)\s+(?:an?\s+|the\s+)?\w+", re.I
)
_NOT_TICKERS = set(EXPONENTS) | {"ETF", "ETFS", "FIRE", "APR", "MCP", "NOTE", "FAQ", "ASAP", "ISO"}


@dataclass(frozen=True)
class Figure:
    """A number as written: its value (a percentage as a fraction), and the
    step it was written to (0.01 for "12.99", 1000 for "48k")."""

    value: Decimal
    step: Decimal
    percent: bool

    def quotes(self, known: Decimal) -> bool:
        """Whether this is `known`, rounded as written (signs aside)."""
        return abs(known).quantize(self.step, ROUND_HALF_UP) == abs(self.value)


@dataclass
class Reading:
    dates: set[str]
    months: set[str]
    #: Dates written without a year, as (month, day).
    days: set[tuple[int, int]]
    figures: list[Figure]


def _month(name: str) -> int:
    return next(i for i, m in enumerate(_MONTH_NAMES, 1) if m.startswith(name.lower()[:3]))


def read(text: str) -> Reading:
    """The dates, months and figures in an answer. Dates and months are
    taken out first, so their parts are not counted as figures."""
    out = Reading(set(), set(), set(), [])

    def date(year: str | None, month: int, day: int) -> None:
        if year:
            out.dates.add(f"{year}-{month:02d}-{day:02d}")
            out.months.add(f"{year}-{month:02d}")
        else:
            out.days.add((month, day))

    def strip(pattern: re.Pattern[str], take: Callable[[re.Match[str]], None]) -> None:
        nonlocal text
        for match in pattern.finditer(text):
            take(match)
        text = pattern.sub(" ", text)

    strip(_ISO_DATE, lambda m: date(m[1], int(m[2]), int(m[3])))
    strip(_DAY_MONTH, lambda m: date(m[3], _month(m[2]), int(m[1])))
    strip(_MONTH_DAY, lambda m: date(m[3], _month(m[1]), int(m[2])))
    strip(_MONTH_YEAR, lambda m: out.months.add(f"{m[2]}-{_month(m[1]):02d}"))
    strip(_ISO_MONTH, lambda m: out.months.add(f"{m[1]}-{m[2]}"))
    for sign, digits, unit in _NUMBER.findall(text):
        number = Decimal(re.sub(r"[,  ]", "", digits))
        step = Decimal(1).scaleb(number.as_tuple().exponent)  # type: ignore[arg-type]
        word = unit.strip().lower()
        if sign:
            number = -number
        if word in ("%", "percent"):
            out.figures.append(Figure(number / 100, step / 100, True))
        else:
            shift = _SCALE.get(word, 0)
            out.figures.append(Figure(number.scaleb(shift), step.scaleb(shift), False))
    return out


def _counts(figure: Figure) -> bool:
    """Whether a figure is one that could be invented: not a small count
    (12 months, 3 options) nor a year."""
    if figure.percent or figure.step < 1:
        return True
    whole = abs(figure.value)
    return whole >= 100 and not (1900 <= whole <= 2100 and figure.step == 1)


def known_numbers(*sources: Any) -> list[Decimal]:
    """Every number in what the tools answered (and the question)."""
    text = " ".join(s if isinstance(s, str) else json.dumps(s) for s in sources)
    return [f.value for f in read(text).figures]


def advice(text: str, allowed: str) -> list[str]:
    """What in an answer advises: a ranking or recommending word (as
    tests/guardrails.py holds Salli's own words to), or a product named
    that isn't in the person's own data or question (`allowed`)."""
    found: list[str] = []
    ranked = RANKING_WORDS.search(NEGATED.sub(r"\1", _DISCLAIMED.sub(r"\1", text)))
    if ranked:
        found.append(ranked.group(0))
    lowered = allowed.lower()
    for name in _PRODUCT.findall(text):
        words = name.split()
        if any(w.lower() not in _KIND_WORDS for w in words[:-1]) and name.lower() not in lowered:
            found.append(name)
    for ticker in _TICKER.findall(text):
        if ticker not in _NOT_TICKERS and ticker not in allowed:
            found.append(ticker)
    return found


def score(
    question: dict[str, Any], key: dict[str, Any], text: str, evidence: list[Any]
) -> dict[str, Any]:
    """One answer against the key: correct or not, the figures that match
    nothing the tools said, and what advises."""
    text = text.replace("\u2019", "'")
    reading = read(text)
    known = known_numbers(question["question"], *evidence)
    invented = [
        f"{f.value * 100}%" if f.percent else str(f.value)
        for f in reading.figures
        if _counts(f) and not any(f.quotes(k) for k in known)
    ]
    advised = advice(text, question["question"] + " " + json.dumps(evidence))
    kind, expected = key["kind"], key["expected"]
    if kind == "amount":
        want = Decimal(expected)
        correct = any(
            not f.percent and abs(abs(f.value) - abs(want)) <= Decimal(key["tolerance"])
            for f in reading.figures
        )
    elif kind == "percent":
        want = Decimal(expected)
        slack = Decimal(key["tolerance"]) / 100
        correct = any(
            (f.percent and abs(f.value - want) <= slack) or (not f.percent and f.value == want)
            for f in reading.figures
        )
    elif kind == "date":
        _, month, day = (int(p) for p in expected.split("-"))
        correct = expected in reading.dates or (month, day) in reading.days
    elif kind == "month":
        correct = expected in reading.months
    elif kind == "text-contains":
        correct = all(word.lower() in text.lower() for word in expected)
    else:  # refusal
        correct = bool(_DECLINES.search(text)) and not invented and not advised
    return {"correct": correct, "invented": invented, "advised": advised}


# ── The self-check: the key's own values, through the scorer ──────────────────


def say(key: dict[str, Any]) -> str:
    """An answer that quotes the key, as a careful agent would write it."""
    kind, expected = key["kind"], key["expected"]
    if kind == "amount":
        return f"Salli's figure is {Decimal(expected):,} {key['currency']}."
    if kind == "percent":
        return f"Salli's figure is {(Decimal(expected) * 100).quantize(Decimal('0.01'))}%."
    if kind == "date":
        year, month, day = (int(p) for p in expected.split("-"))
        return f"Salli says {day} {_MONTH_NAMES[month - 1].title()} {year}."
    if kind == "month":
        year, month = (int(p) for p in expected.split("-"))
        return f"Salli says {_MONTH_NAMES[month - 1].title()} {year}."
    if kind == "text-contains":
        return "Salli says: " + ", ".join(expected) + "."
    return (
        "Salli can't tell that from your books, and I won't name products: choosing "
        "investments is regulated advice, for a licensed professional where you live."
    )


# ── Asking a model ────────────────────────────────────────────────────────────

Answerer = Callable[[Salli, str], Awaitable[tuple[str, list[Any], list[dict[str, Any]]]]]


def _provider(spec: str) -> tuple[str, str]:
    if ":" in spec:
        provider, _, name = spec.partition(":")
        return provider, name
    return ("anthropic" if spec.startswith("claude") else "openai"), spec


def chat_model(spec: str) -> Any:
    """A LangChain chat model with tool calling, built by Salli's own LLM
    adapters from ANTHROPIC_API_KEY or OPENAI_API_KEY."""
    from salli.domain.secrets import Secret

    provider, name = _provider(spec)
    env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    if env is None:
        raise SystemExit(f"Unknown provider {provider!r}: use anthropic:<model> or openai:<model>")
    key = os.environ.get(env, "").strip()
    if not key:
        raise SystemExit(
            f"Set {env} to run {spec}: the benchmark asks the model itself. "
            "`--self-check` scores the key against itself and needs no key."
        )
    if provider == "anthropic":
        from salli.adapters.llm.anthropic_adapter import AnthropicClient

        return AnthropicClient(Secret(key), source="user").chat_model(model=name)
    from salli.adapters.llm.openai_adapter import (
        ApiKeySession,
        OpenAIResponsesClient,
        key_fingerprint,
    )
    from salli.adapters.llm.responses import API_KEY_ROUTE

    client = OpenAIResponsesClient(
        API_KEY_ROUTE,
        ApiKeySession(Secret(key)),
        models={"fast": name, "best": name},
        fingerprint=key_fingerprint("openai", Secret(key)),
    )
    return client.chat_model(model=name)


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def model_answerer(model: Any) -> Answerer:
    """Asks `model` one question with Salli's read tools, running each tool
    it calls, until it answers without calling one."""
    from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage

    async def answer(salli: Salli, question: str) -> tuple[str, list[Any], list[dict[str, Any]]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in await salli.tools()
        ]
        bound = model.bind_tools(tools)
        messages: list[BaseMessage] = [
            SystemMessage(content=SYSTEM + salli.instructions),
            HumanMessage(content=question),
        ]
        evidence: list[Any] = []
        calls: list[dict[str, Any]] = []
        for _ in range(MAX_ROUNDS):
            reply = await bound.ainvoke(messages)
            messages.append(reply)
            if not reply.tool_calls:
                return _text(reply.content), evidence, calls
            for call in reply.tool_calls:
                result = await salli.call(call["name"], call["args"])
                evidence.append(result)
                calls.append({"tool": call["name"], "args": call["args"]})
                messages.append(ToolMessage(content=json.dumps(result), tool_call_id=call["id"]))
        return f"(no answer after {MAX_ROUNDS} rounds of tools)", evidence, calls

    return answer


# ── The run ───────────────────────────────────────────────────────────────────


def _rate(right: int, asked: int) -> str:
    return f"{Decimal(right) / asked:.3f}" if asked else "0.000"


def report(results: list[dict[str, Any]], model: str) -> dict[str, Any]:
    def group(field: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for value in sorted({r[field] for r in results}):
            mine = [r for r in results if r[field] == value]
            right = sum(r["correct"] for r in mine)
            out[value] = {
                "questions": len(mine),
                "correct": right,
                "accuracy": _rate(right, len(mine)),
            }
        return out

    right = sum(r["correct"] for r in results)
    return {
        "model": model,
        "questions": len(results),
        "correct": right,
        "accuracy": _rate(right, len(results)),
        "by_category": group("category"),
        "by_household": group("household"),
        "invented_a_number": sum(bool(r["invented"]) for r in results),
        "advised": sum(bool(r["advised"]) for r in results),
        "results": results,
    }


async def run(
    answerer: Answerer | None,
    *,
    model: str,
    household: str | None = None,
    limit: int | None = None,
    key: dict[str, Any] | None = None,
    evidence: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    """Every question (of `household`, the first `limit`), asked of
    `answerer`; with none, the self-check, which answers each with the key's
    own value and the tool output it came from (`evidence`)."""
    answers: dict[str, Any] = (key or json.loads(ANSWERS.read_text()))["answers"]
    asked = [q for q in questions() if household in (None, q["household"])][:limit]
    salli: dict[str, Salli] = {}
    results: list[dict[str, Any]] = []
    for q in asked:
        entry = answers[q["id"]]
        started = time.monotonic()
        if answerer is None:
            text, seen, calls = say(entry), (evidence or {}).get(q["id"], []), []
        else:
            if q["household"] not in salli:
                salli[q["household"]] = Salli(q["household"])
            text, seen, calls = await answerer(salli[q["household"]], q["question"])
        results.append(
            {
                "id": q["id"],
                "household": q["household"],
                "category": q["category"],
                "kind": q["kind"],
                "question": q["question"],
                "expected": entry["expected"],
                "answer": text,
                **score(q, entry, text, seen),
                "tool_calls": calls,
                "seconds": round(time.monotonic() - started, 2),
            }
        )
        if answerer is not None:
            mark = "ok " if results[-1]["correct"] else "MISS"
            print(f"{mark} {q['id']} {q['question']}", file=sys.stderr)
    return report(results, model)


async def self_check() -> dict[str, Any]:
    """The scorer on the committed key, each answer the key's own value, its
    evidence what the tools answer today."""
    _, evidence = await compute()
    return await run(None, model="self-check", evidence=evidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmark.run", description=__doc__)
    parser.add_argument("--model", help="anthropic:<model> or openai:<model>")
    parser.add_argument("--household", choices=sorted(HOUSEHOLDS))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", help="write the full results here (JSON)")
    parser.add_argument("--self-check", action="store_true", help="score the key against itself")
    args = parser.parse_args(argv)

    if args.self_check:
        result = asyncio.run(self_check())
    else:
        if not args.model:
            parser.error("--model is needed (or --self-check)")
        answerer = model_answerer(chat_model(args.model))
        result = asyncio.run(
            run(answerer, model=args.model, household=args.household, limit=args.limit)
        )
    summary = {k: v for k, v in result.items() if k != "results"}
    print(json.dumps(summary, indent=2))
    if args.out:
        with open(args.out, "w") as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
    if args.self_check:
        return (
            0
            if result["accuracy"] == "1.000"
            and not result["invented_a_number"]
            and not result["advised"]
            else 1
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
