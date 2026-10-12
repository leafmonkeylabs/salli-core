"""
The guardrail on securities, as decision lab 3b reworded it (decision 21):
an agent may refer to the person's own holdings as they named them, but
never suggests buying or selling any security (theirs or another), never
compares holdings as investments, and points to a licensed professional for
choosing investments. The MCP prompts' guardrails, the CLI skill and
docs/ai-clients.md all say so; this keeps them saying it.
"""

from __future__ import annotations

from pathlib import Path

from salli.interfaces.api.mcp_server import GUARDRAILS

ROOT = Path(__file__).resolve().parents[2]


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_the_prompts_allow_the_persons_holdings_and_forbid_suggesting_or_comparing():
    text = _flat(GUARDRAILS)
    assert "Never name a specific product, provider, fund or security of your own" in text
    assert "You may refer to my own holdings as I named them" in text
    assert "never suggest buying or selling any security, mine or another" in text
    assert "never compare my holdings as investments" in text
    assert "choosing investments), say so and suggest a licensed professional there" in text


def test_the_skill_says_the_same():
    text = _flat((ROOT / "packages/cli/skills/salli-cli/SKILL.md").read_text())
    assert "Never name a specific product, provider, fund or security of your own." in text
    assert "You may refer to the user's own holdings as they named them" in text
    assert "never suggest buying or selling any security, theirs or another" in text
    assert "never compare their holdings as investments" in text
    # The bundled copy the CLI installs is the same text.
    bundled = (ROOT / "packages/cli/src/skills/bundled.ts").read_text()
    assert "never compare their holdings as investments" in _flat(bundled.replace("\\n", " "))


def test_the_docs_say_the_same():
    text = _flat((ROOT / "docs/ai-clients.md").read_text())
    assert "It never names a specific product, provider, fund or security of its own." in text
    assert "may refer to your own holdings as you named them" in text
    assert "never suggests buying or selling any security, yours or another" in text
    assert "never compares your holdings as investments" in text
