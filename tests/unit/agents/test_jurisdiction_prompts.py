"""
The agents' prompts come from the user's profile and the tax packs.

Every conversational prompt is a fixed text that knows no country, followed by
a section about the user: today's date, their base currency, where they are
taxed and the tax year they are in. A Sri Lankan resident hears what they
always did (the IRD, APIT and AIT, the pack's relief and bands); a user with no
residency hears no country's tax at all; a user taxed where Salli has no pack is
told it cannot compute their tax.
"""

from __future__ import annotations

import datetime
import importlib
import pathlib
import re
from typing import Any

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from salli.domain.agents.jurisdiction import (
    UserContext,
    context_section,
    market_notes,
    set_user_context,
    tax_specialist_section,
    user_context,
)
from salli.domain.agents.prompting import dynamic_prompt
from salli.domain.tax.packs import registry

TODAY = datetime.date(2026, 10, 9)


@pytest.fixture(autouse=True)
def _no_context_leaks_between_tests():
    """A sync test sets the context in the thread's own context, which the next
    test would otherwise inherit."""
    from salli.domain.agents import jurisdiction

    token = jurisdiction._context.set(None)
    yield
    jurisdiction._context.reset(token)


#: What only a Sri Lankan should hear about.
SRI_LANKAN = ("Sri Lanka", "LKR", "IRD", "Inland Revenue", "APIT", "AIT", "RAMIS", "FSI")


def _context(base: str | None, residency: str | None) -> UserContext:
    country = residency or (registry.country_for_currency(base) if base else None)
    return UserContext(
        today=TODAY,
        base_currency=base,
        tax_residency=residency,
        tax_country=country,
        current=registry.current_tax_year(country, TODAY),
    )


SRI_LANKAN_USER = _context("LKR", "LK")
NOBODY_KNOWS = _context("USD", None)
RUPEES_NO_RESIDENCY = _context("LKR", None)
AMERICAN = _context("USD", "US")


def _says(text: str, *words: str) -> list[str]:
    return [w for w in words if re.search(rf"\b{re.escape(w)}\b", text)]


def test_a_sri_lankan_resident_hears_what_they_always_did():
    section = tax_specialist_section(SRI_LANKAN_USER)
    for expected in (
        "Today's date is Friday, 9 October 2026",
        "base currency is LKR",
        "tax resident in Sri Lanka (LK)",
        "Inland Revenue Department (IRD)",
        "Inland Revenue Act No. 24 of 2017",
        "current Year of Assessment is 2026/27 (1 April 2026 to 31 March 2027)",
        "The latest year it can compute is 2025/26",
        "APIT (Advance Personal Income Tax",
        "AIT (Advance Income Tax",
        "personal relief LKR 1,800,000",
        "progressive bands 6/18/24/30/36%",
        "foreign service income remitted through a bank: 15% final tax",
    ):
        assert expected in section, expected


def test_a_user_with_no_residency_hears_no_countrys_tax():
    for ctx in (NOBODY_KNOWS, RUPEES_NO_RESIDENCY):
        section = tax_specialist_section(ctx)
        assert "has not said where they are tax resident" in section
        assert _says(section, *SRI_LANKAN) == ([] if ctx is NOBODY_KNOWS else ["LKR"])


def test_the_tools_fallback_is_named_without_naming_a_country():
    """A rupee ledger is still computed with Sri Lanka's pack until its owner
    sets a residency: the model is told to confirm before relying on it."""
    section = context_section(RUPEES_NO_RESIDENCY)
    assert "pack for their base currency" in section
    assert "Sri Lanka" not in section


def test_a_country_without_a_pack_is_told_so():
    section = tax_specialist_section(AMERICAN)
    assert "tax resident in the United States (US)" in section
    assert "no tax pack for the United States yet" in section
    assert _says(section, *SRI_LANKAN) == []


def test_no_section_uses_an_em_dash():
    for ctx in (SRI_LANKAN_USER, NOBODY_KNOWS, RUPEES_NO_RESIDENCY, AMERICAN):
        assert "—" not in tax_specialist_section(ctx)
    for residency in ("LK", "DE", None):
        assert "—" not in market_notes(residency)


# ── The fixed prompts know no country ────────────────────────────────────────

AGENTS_DIR = pathlib.Path(__file__).resolve().parents[3] / "src" / "salli" / "domain" / "agents"
PROMPT_RE = re.compile(r"^([A-Z_]*PROMPT)\s*=\s*", re.M)


def _prompt_constants() -> list[tuple[str, str]]:
    found = []
    for path in sorted(AGENTS_DIR.glob("*.py")):
        for name in PROMPT_RE.findall(path.read_text()):
            module = importlib.import_module(f"salli.domain.agents.{path.stem}")
            found.append((f"{path.stem}.{name}", getattr(module, name)))
    return found


def test_no_fixed_prompt_assumes_sri_lanka():
    constants = _prompt_constants()
    assert len(constants) >= 7
    offenders = {name: _says(text, *SRI_LANKAN, "2025/26") for name, text in constants}
    assert {name: words for name, words in offenders.items() if words} == {}


# ── Every conversational agent ends with this user's section ────────────────


def _builders() -> list[tuple[str, str, Any]]:
    from salli.domain.agents.buddy_agent import BUDDY_SYSTEM_PROMPT
    from salli.domain.agents.finance_worker import FINANCE_WORKER_PROMPT
    from salli.domain.agents.manager_agent import MANAGER_SYSTEM_PROMPT
    from salli.domain.agents.tax_agent import TAX_AGENT_SYSTEM_PROMPT
    from salli.domain.agents.tax_worker import TAX_WORKER_PROMPT

    return [
        ("scrooge", MANAGER_SYSTEM_PROMPT, context_section),
        ("buddy", BUDDY_SYSTEM_PROMPT, context_section),
        ("finance", FINANCE_WORKER_PROMPT, context_section),
        ("tax worker", TAX_WORKER_PROMPT, tax_specialist_section),
        ("tax agent", TAX_AGENT_SYSTEM_PROMPT, tax_specialist_section),
    ]


@pytest.mark.parametrize(("ctx", "may_say"), [(NOBODY_KNOWS, []), (AMERICAN, [])])
def test_no_assembled_prompt_frames_a_user_with_another_countrys_tax(ctx, may_say):
    set_user_context(ctx)
    for name, static, section in _builders():
        [system, *_] = dynamic_prompt(static, section)({"messages": []})
        assert _says(system.content, *SRI_LANKAN) == may_say, name


def test_a_sri_lankan_residents_assembled_prompts_carry_their_tax():
    set_user_context(SRI_LANKAN_USER)
    for name, static, section in _builders():
        [system, *_] = dynamic_prompt(static, section)({"messages": []})
        assert "Sri Lanka (LK)" in system.content, name
        assert "2026/27" in system.content, name


def test_the_prompt_reads_the_user_of_the_run_in_progress():
    """One compiled graph serves every user: the prompt is built per call."""
    prompt = dynamic_prompt("Fixed text.", context_section)
    question = HumanMessage("What do I owe?")

    set_user_context(SRI_LANKAN_USER)
    first = prompt({"messages": [question]})
    set_user_context(NOBODY_KNOWS)
    second = prompt({"messages": [question]})

    assert isinstance(first[0], SystemMessage) and first[1:] == [question]
    assert first[0].content.startswith("Fixed text.\n\nAbout this user:")
    assert "Sri Lanka" in first[0].content
    assert "Sri Lanka" not in second[0].content


def test_without_a_context_the_prompt_knows_only_the_date():
    from salli.domain.agents import jurisdiction

    token = jurisdiction._context.set(None)
    try:
        ctx = user_context()
    finally:
        jurisdiction._context.reset(token)
    assert ctx == UserContext(today=datetime.date.today())


# ── The FIRE strategy suggests what is available where the user is ──────────


def test_market_notes_follow_the_residency():
    assert "CSE index funds" in market_notes("LK")
    assert "Germany (DE)" in market_notes("DE")
    neutral = market_notes(None)
    assert "assume no country" in neutral
    assert _says(neutral, *SRI_LANKAN) == []


async def test_the_fire_strategy_is_asked_with_the_users_market():
    from salli.domain.agents import fire_strategy
    from salli.domain.llm import LLMUnreadableAnswer
    from tests.fakes import FakeLLM

    llm = FakeLLM("{}")  # no strategy: only the prompt matters here
    for residency in ("LK", None):
        with pytest.raises(LLMUnreadableAnswer):
            await fire_strategy.generate_strategy({"tax_residency": residency}, llm=llm)

    lk, unknown = (request["instructions"] for request in llm.requests)
    assert "CSE index funds" in lk
    assert "assume no country" in unknown and "Sri Lanka" not in unknown


# ── The agent service sets the context each turn ─────────────────────────────


class _Tax:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def current_tax_year(self, user_id, today):
        if self.fail:
            raise LookupError("no profile")
        from salli.application.services.tax_service import TaxJurisdiction

        return (
            TaxJurisdiction("LK", "tax_residency", "LK", "LKR"),
            registry.current_tax_year("LK", today),
        )


async def test_the_service_gathers_the_users_context():
    from salli.application.services.agent_service import AgentService

    ctx = await AgentService(None, _Tax()).user_context("u1")
    assert (ctx.base_currency, ctx.tax_residency, ctx.tax_country) == ("LKR", "LK", "LK")
    assert ctx.current is not None and ctx.current.latest is not None

    # A context it cannot gather never stops the conversation.
    neutral = await AgentService(None, _Tax(fail=True)).user_context("u1")
    assert neutral == UserContext(today=datetime.date.today())


async def test_each_turn_runs_with_its_users_context(monkeypatch):
    from salli.application.services.agent_service import AgentService

    seen: list[UserContext] = []

    class _Agent:
        async def astream_events(self, input_, config, version):
            seen.append(user_context())
            return
            yield  # an async generator that emits nothing

        async def aget_state(self, config):
            return type("State", (), {"interrupts": [], "tasks": []})()

    svc = AgentService(None, _Tax())
    monkeypatch.setattr(svc, "_get_agent", lambda *args, **kwargs: _Agent())
    async for _ in svc.stream_chat("u1", "hello", thread_id="t1", api_key="k"):
        pass

    assert [c.tax_residency for c in seen] == ["LK"]
