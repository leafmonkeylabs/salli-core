"""
The judge: a model asked one fixed question of an answer the figure checks
passed, whether it stands by its headline as a whole. Word lists can't tell
"No correction is needed." from "Don't rely on that figure."; a reader can.

The judge sees the answer and the headline as the answer wrote it, never the
key. Its verdicts are cached by a hash of the prompt, headline and answer
(JUDGE_CACHE), so a rerun on the same answers scores the same.
docs/benchmark.md publishes the prompt.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path

#: The judge's whole prompt; {headline} and {answer} are filled in.
JUDGE_PROMPT = (
    "You check one answer an AI assistant gave about someone's money.\n\n"
    "Answer:\n<<<\n{answer}\n>>>\n\n"
    "Headline figure: {headline}\n\n"
    "Does the answer, taken as a whole, assert the headline figure as correct "
    "without retracting, disowning or adjusting it? Explanations, context and "
    "caveats about what the figure covers do not count against it; calling it "
    "wrong, unreliable or made up, or changing it, does. Reply with one word: yes or no."
)
#: Where verdicts are kept between runs (not committed).
JUDGE_CACHE = Path(__file__).resolve().parent / ".judge-cache.json"

Judge = Callable[[str, str], Awaitable[bool]]


def _key(headline: str, answer: str) -> str:
    return hashlib.sha256(f"{JUDGE_PROMPT}\0{headline}\0{answer}".encode()).hexdigest()


def _verdict(reply: str) -> bool:
    return reply.strip().strip(".!\"'`*").lower().startswith("yes")


def cached(ask: Callable[[str], Awaitable[str]], path: Path = JUDGE_CACHE) -> Judge:
    """A judge that asks `ask` the prompt once per (headline, answer)."""
    verdicts: dict[str, bool] = json.loads(path.read_text()) if path.exists() else {}

    async def judge(headline: str, answer: str) -> bool:
        key = _key(headline, answer)
        if key not in verdicts:
            reply = await ask(JUDGE_PROMPT.format(headline=headline, answer=answer))
            verdicts[key] = _verdict(reply)
            path.write_text(json.dumps(verdicts, indent=1, sort_keys=True))
        return verdicts[key]

    return judge


def claude_judge(model: str | None = None, command: str = "claude", **kw: Path) -> Judge:
    """The judge through Claude Code headless (`claude -p`), with no tools."""

    async def ask(prompt: str) -> str:
        argv = [command, "-p", prompt, "--output-format", "json", "--tools", ""]
        if model:
            argv += ["--model", model]
        done = await asyncio.to_thread(
            subprocess.run, argv, capture_output=True, text=True, check=False
        )
        try:
            out = json.loads(done.stdout)
        except json.JSONDecodeError:
            out = {"is_error": True, "result": done.stderr.strip()}
        if out.get("is_error"):
            # never cached: a failed call is no verdict
            raise RuntimeError(f"The judge failed: {str(out.get('result'))[:200]}")
        return str(out.get("result") or "")

    return cached(ask, **kw)


def api_judge(chat_model: object, **kw: Path) -> Judge:
    """The judge through a LangChain chat model (benchmark.run.chat_model)."""
    from langchain_core.messages import HumanMessage

    async def ask(prompt: str) -> str:
        reply = await chat_model.ainvoke([HumanMessage(content=prompt)])  # type: ignore[attr-defined]
        content = reply.content
        return content if isinstance(content, str) else json.dumps(content)

    return cached(ask, **kw)
