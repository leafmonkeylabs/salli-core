"""
Every read tool's free text reaches the model fenced (domain/agents/untrusted.py):
each MCP read tool, called on the golden households (benchmark/households.py)
with no arguments and with every argument the benchmark asks with, answers no
string with a space in it outside {"untrusted_text": ...}, except under the
keys Salli writes itself (OWN_TEXT) or hands back as an argument
(PASSED_BACK), and in the tools that answer only Salli's own documents.
Codes, ids, amounts, dates and enums have no spaces, so need no list.
"""

from __future__ import annotations

import asyncio
from typing import Any

from benchmark.answer_key import questions
from benchmark.households import HOUSEHOLDS, Salli
from salli.domain.agents.untrusted import OWN_TEXT, PASSED_BACK
from salli.interfaces.api.mcp_server import OWN_DOCUMENTS


def _raw(value: Any, key: str | None = None, path: str = "$") -> list[str]:
    if key in PASSED_BACK:
        return []
    if isinstance(value, dict):
        if set(value) == {"untrusted_text"}:
            return []
        return [p for k, v in value.items() for p in _raw(v, k, f"{path}.{k}")]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _raw(v, key, f"{path}[{i}]")]
    if isinstance(value, str) and key not in OWN_TEXT and any(c.isspace() for c in value):
        return [f"{path}: {value[:60]!r}"]
    return []


async def _walk() -> tuple[dict[str, list[str]], set[str]]:
    found: dict[str, list[str]] = {}
    answered: set[str] = set()
    asked = [(q["household"], q["answer"]) for q in questions() if "answer" in q]
    for household in HOUSEHOLDS:
        salli = Salli(household)
        listed = await salli._server.list_tools()  # pyright: ignore[reportPrivateUsage]
        names = [
            t.name
            for t in listed
            if t.annotations and t.annotations.readOnlyHint and t.name not in OWN_DOCUMENTS
        ]
        calls = [(n, {}) for n in names] + [
            (a["tool"], a.get("args", {})) for h, a in asked if h == household
        ]
        entries = await salli.call("search_entries", {"limit": 1})
        calls.append(("get_entry", {"entry_id": entries["entries"][0]["id"]}))
        for tool, args in calls:
            result = await salli.call(tool, args)
            if isinstance(result, dict) and "error" in result:
                continue
            answered.add(tool)
            if raw := _raw(result):
                found[f"{household} {tool}"] = raw
    return found, answered


def test_every_read_tool_answers_its_free_text_fenced():
    found, answered = asyncio.run(_walk())
    assert found == {}
    # Enough of the tools answered on the households for this to mean something.
    assert len(answered) >= 25, sorted(answered)
    assert {"search_entries", "get_entry", "get_accounts", "get_baseline"} <= answered
