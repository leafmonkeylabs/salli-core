"""
Every prompt a user reads shares one writing style.

The rule this guards is the one that keeps drifting: a style instruction pasted
into seven prompts is seven things to forget. `domain/agents/style.py` holds it
once, and these tests fail when a new prompt is added without it.
"""

from __future__ import annotations

import pathlib
import re

from salli.domain.agents.style import WRITING_STYLE

EM_DASH = "—"

#: Every prompt constant whose text an end user sees, directly or through a
#: report. Discovered from the source rather than listed, so a new prompt is
#: covered the moment it is written.
AGENTS_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "salli" / "domain" / "agents"
PROMPT_RE = re.compile(r"^([A-Z_]*PROMPT)\s*=\s*", re.M)


def _prompt_constants() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(AGENTS_DIR.glob("*.py")):
        for name in PROMPT_RE.findall(path.read_text()):
            module = __import__(f"salli.domain.agents.{path.stem}", fromlist=[name])
            found.append((f"{path.stem}.{name}", getattr(module, name)))
    return found


class TestWritingStyle:
    def test_prompts_were_actually_discovered(self):
        """A regex that silently matches nothing would make every test below
        pass without checking anything."""
        assert len(_prompt_constants()) >= 7

    def test_every_prompt_carries_the_shared_style(self):
        missing = [n for n, text in _prompt_constants() if WRITING_STYLE not in text]
        assert not missing, f"prompts without WRITING_STYLE: {missing}"

    def test_no_prompt_uses_an_em_dash(self):
        """Not pedantry: a model takes its register from the text it is given,
        so an em dash in the prompt teaches the habit the prompt forbids."""
        offenders = [n for n, text in _prompt_constants() if EM_DASH in text]
        assert not offenders, f"prompts containing an em dash: {offenders}"

    def test_the_style_block_forbids_em_dashes_and_permits_emoji(self):
        """The block is prose, so assert on what it means rather than on its
        exact wording."""
        assert "em dash" in WRITING_STYLE
        assert EM_DASH not in WRITING_STYLE
        assert "emoji" in WRITING_STYLE.lower()
        assert "do not use emoji" not in WRITING_STYLE.lower()
