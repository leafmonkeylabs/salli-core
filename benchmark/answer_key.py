"""
The fidelity benchmark's answer key, computed by Salli.

Each question in questions.yaml says which read tool answers it, with what
arguments, and where in the tool's result the answer is. This calls each
tool on the question's golden household, in-process, through Salli's own
MCP server over the real services (benchmark/households.py), and writes
what it finds to answers.json. No expected value is typed by hand, so the
key changes only when Salli's figures do, and
tests/contract/test_benchmark_key.py fails until it is written again. An
FI month that rests on the household's placeholder assumptions carries the
caveat an answer must give (`caveat`: "placeholder", from
get_fi_assumptions):

    uv run python -m benchmark.answer_key            # write answers.json
    uv run python -m benchmark.answer_key --check    # what the contract test does
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from benchmark.households import HOUSEHOLDS, Salli

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.yaml"
ANSWERS = HERE / "answers.json"
COMMAND = "uv run python -m benchmark.answer_key"

KINDS = ("amount", "date", "month", "percent", "text-contains", "refusal")
#: How far an answer may be from the key: amounts exactly, in the currency's
#: minor units; percentages to half a tenth of a point (so 49.1% quotes
#: 0.4907); dates and months exactly.
TOLERANCE = {"amount": "0", "percent": "0.05", "date": "0", "month": "0"}


def questions() -> list[dict[str, Any]]:
    """The questions, checked: unique ids, a known household and kind, and
    an answer's source for every kind but refusal."""
    listed: list[dict[str, Any]] = yaml.safe_load(QUESTIONS.read_text())
    seen: set[str] = set()
    for q in listed:
        where = q.get("id", "?")
        assert where not in seen, f"{where}: the id is used twice"
        seen.add(where)
        assert q.get("household") in HOUSEHOLDS, f"{where}: no such household"
        assert q.get("kind") in KINDS, f"{where}: kind is one of {KINDS}"
        assert q.get("question") and q.get("category"), f"{where}: a question and a category"
        assert ("answer" in q) == (q["kind"] != "refusal"), f"{where}: an answer, unless a refusal"
    return listed


def pick(value: Any, path: list[Any]) -> Any:
    """Follow `path` into a tool's result: a key, a list index, or
    {field: value} for the first item of a list that has it."""
    for step in path:
        if isinstance(step, dict):
            [(field, wanted)] = step.items()
            value = next(item for item in value if _text(item.get(field)) == wanted)
        else:
            value = value[step]
    return _text(value)


def _text(value: Any) -> Any:
    """Outside text (a payee, a label) comes fenced: the key is its text."""
    if isinstance(value, dict) and "untrusted_text" in value:
        return value["untrusted_text"]
    return value


def expected(kind: str, value: Any, words: dict[str, str] | None) -> Any:
    """The key's value for a kind, checked to be one."""
    if kind == "text-contains":
        found = value if isinstance(value, list) else [value]
        return [(words or {}).get(str(v), str(v)) for v in found]
    text = str(value)
    if kind in ("amount", "percent"):
        try:
            Decimal(text)
        except InvalidOperation:
            raise ValueError(f"{text!r} is not a number") from None
    elif kind == "date":
        dt.date.fromisoformat(text)
    elif kind == "month":
        dt.date.fromisoformat(f"{text}-01")
    return text


async def compute() -> tuple[dict[str, Any], dict[str, list[Any]]]:
    """The key, and for each question what the tool it comes from answered
    (the evidence the self-check scores against)."""
    salli: dict[str, Salli] = {}
    calls: dict[tuple[str, str], Any] = {}

    async def call(household: str, tool: str, args: dict[str, Any]) -> Any:
        key = (household, json.dumps({"tool": tool, "args": args}, sort_keys=True))
        if key not in calls:
            if household not in salli:
                salli[household] = Salli(household)
            calls[key] = await salli[household].call(tool, args)
        return calls[key]

    answers: dict[str, Any] = {}
    evidence: dict[str, list[Any]] = {}
    for q in questions():
        overview = await call(q["household"], "get_overview", {})
        entry: dict[str, Any] = {
            "household": q["household"],
            "category": q["category"],
            "kind": q["kind"],
            "currency": overview["currency"],
        }
        evidence[q["id"]] = []
        if q["kind"] == "refusal":
            entry["expected"] = None
        else:
            source = q["answer"]
            args = source.get("args", {})
            result = await call(q["household"], source["tool"], args)
            try:
                value = pick(result, source["path"])
            except (KeyError, IndexError, StopIteration, TypeError):
                raise LookupError(f"{q['id']}: {source['tool']} has no {source['path']}") from None
            entry["expected"] = expected(q["kind"], value, source.get("words"))
            entry["from"] = {"tool": source["tool"], "args": args, "path": shown(source["path"])}
            evidence[q["id"]] = [result]
            if q["kind"] != "text-contains" and provisional(result, source["path"]):
                entry["caveat"] = "placeholder"
            elif q["kind"] != "text-contains" and (q["category"] == "fi" or "fi" in source["path"]):
                # every FI figure rests on the FI assumptions
                assumptions = await call(q["household"], "get_fi_assumptions", {})
                if assumptions["applied"]["status"] == "placeholder":
                    entry["caveat"] = "placeholder"
        if q["kind"] in TOLERANCE:
            entry["tolerance"] = TOLERANCE[q["kind"]]
        answers[q["id"]] = entry
    key = {
        "about": (
            "What Salli's own tools answer each question in benchmark/questions.yaml, on "
            f"its golden household. Written by `{COMMAND}`; never edit it by hand."
        ),
        "questions": len(answers),
        "answers": answers,
    }
    return key, evidence


def provisional(value: Any, path: list[Any]) -> bool:
    """Whether the figure at `path` rests on a placeholder or provisional
    value: a step on the way to it (the result itself included) whose
    status or origin says so, or that lists provisional tax values or
    placeholder sources."""

    def marked(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        flags = [node.get("status"), node.get("origin")]
        sources = node.get("sources")
        return (
            "placeholder" in flags
            or bool(node.get("provisional"))
            or (isinstance(sources, dict) and "placeholder" in sources.values())
        )

    for step in path:
        if marked(value):
            return True
        if isinstance(step, dict):
            [(field, wanted)] = step.items()
            value = next(item for item in value if _text(item.get(field)) == wanted)
        else:
            value = value[step]
    return False


def shown(path: list[Any]) -> str:
    """`path` as one readable string: `lines[Rent].total`, an item picked by
    its key in brackets, a list index likewise."""
    out = ""
    for step in path:
        if isinstance(step, dict):
            out += "".join(f"[{v}]" for v in step.values())
        elif isinstance(step, int):
            out += f"[{step}]"
        else:
            out += f".{step}" if out else str(step)
    return out


def render(key: dict[str, Any]) -> str:
    return json.dumps(key, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    key, _ = asyncio.run(compute())
    if "--check" in argv:
        if not ANSWERS.exists() or ANSWERS.read_text() != render(key):
            print(f"benchmark/answers.json is out of date: run `{COMMAND}`", file=sys.stderr)
            return 1
        return 0
    ANSWERS.write_text(render(key))
    print(f"Wrote {key['questions']} answers to {ANSWERS.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
