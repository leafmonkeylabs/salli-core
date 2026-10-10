"""
The agents' prompts come from the user's profile and their own tax rules.

Every conversational prompt is a fixed text that knows no country, followed by
a section about the user: today's date, their base currency, where they are
taxed, and which of their own rule sets is active for the tax year they are in.
A user with no residency hears no country's tax at all; a user with no active
rules is told Salli can't compute their tax and how to add rules; a user with
active rules hears their year, version and sources, and never a figure: those
reach the user only through the engine.
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
    TaxRulesContext,
    UserContext,
    context_section,
    market_notes,
    set_user_context,
    tax_specialist_section,
    user_context,
)
from salli.domain.agents.prompting import dynamic_prompt

TODAY = datetime.date(2031, 10, 9)


@pytest.fixture(autouse=True)
def _no_context_leaks_between_tests():
    """A sync test sets the context in the thread's own context, which the next
    test would otherwise inherit."""
    from salli.domain.agents import jurisdiction

    token = jurisdiction._context.set(None)
    yield
    jurisdiction._context.reset(token)


#: Words that would mean a country's law crept into a prompt.
COUNTRY_SPECIFIC = ("Sri Lanka", "LKR", "IRD", "Inland Revenue", "APIT", "AIT", "RAMIS", "FSI")

REMITLAND_2031 = TaxRulesContext(
    country="GB",
    region=None,
    year="2031/32",
    start=datetime.date(2031, 4, 6),
    end=datetime.date(2032, 4, 5),
    version=3,
    sources=("Income Tax Act (fictional)",),
    roles=(("salary", "Salary", "income"), ("tax_withheld", "Tax withheld", "withholding")),
)
LAST_YEAR = TaxRulesContext(
    country="GB",
    region=None,
    year="2030/31",
    start=datetime.date(2030, 4, 6),
    end=datetime.date(2031, 4, 5),
    version=1,
)

WITH_RULES = UserContext(
    today=TODAY,
    base_currency="GBP",
    tax_residency="GB",
    current=REMITLAND_2031,
    latest=REMITLAND_2031,
)
BETWEEN_YEARS = UserContext(
    today=TODAY, base_currency="GBP", tax_residency="GB", current=None, latest=LAST_YEAR
)
NOBODY_KNOWS = UserContext(today=TODAY, base_currency="USD")
NO_RULES = UserContext(today=TODAY, base_currency="USD", tax_residency="US")


def _says(text: str, *words: str) -> list[str]:
    return [w for w in words if re.search(rf"\b{re.escape(w)}\b", text)]


def test_a_user_with_active_rules_hears_their_year_version_and_sources():
    section = tax_specialist_section(WITH_RULES)
    for expected in (
        "Today's date is Thursday, 9 October 2031",
        "base currency is GBP",
        "tax resident in the United Kingdom (GB)",
        "Their current tax year is 2031/32 (6 April 2031 to 5 April 2032)",
        "computed from their own rule set for GB (version 3, citing Income Tax Act (fictional))",
        "doesn't vouch for the law",
        "salary (Salary, income); tax_withheld (Tax withheld, withholding)",
    ):
        assert expected in section, expected


def test_between_years_the_latest_computable_year_is_named():
    section = context_section(BETWEEN_YEARS)
    assert "falls in no tax year their active rules cover" in section
    assert "The latest year they can compute is 2030/31" in section
    assert "use it unless asked for another" in section


def test_a_user_with_no_residency_hears_no_countrys_tax():
    section = tax_specialist_section(NOBODY_KNOWS)
    assert "has not said where they are tax resident" in section
    assert "assume no country's tax rules" in section
    assert _says(section, *COUNTRY_SPECIFIC) == []


def test_a_user_with_no_active_rules_is_told_so_and_how_to_add_them():
    section = tax_specialist_section(NO_RULES)
    assert "tax resident in the United States (US)" in section
    assert "no active tax rules for the United States" in section
    assert "Salli can't compute their tax" in section
    assert "research_tax_rules" in section and "only the user can activate them" in section
    assert _says(section, *COUNTRY_SPECIFIC) == []


def test_no_section_uses_an_em_dash():
    for ctx in (WITH_RULES, BETWEEN_YEARS, NOBODY_KNOWS, NO_RULES):
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


def test_no_fixed_prompt_assumes_a_country():
    constants = _prompt_constants()
    assert len(constants) >= 7
    offenders = {name: _says(text, *COUNTRY_SPECIFIC, "2025/26") for name, text in constants}
    assert {name: words for name, words in offenders.items() if words} == {}


def test_the_tax_prompts_send_the_model_to_the_rules_and_the_engine():
    from salli.domain.agents.tax_agent import TAX_AGENT_SYSTEM_PROMPT
    from salli.domain.agents.tax_worker import TAX_WORKER_PROMPT

    for prompt in (TAX_AGENT_SYSTEM_PROMPT, TAX_WORKER_PROMPT):
        assert "explain_tax_line" in prompt
        assert "own" in prompt and "rules" in prompt
        assert "tax pack" not in prompt and "band_index" not in prompt


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


@pytest.mark.parametrize("ctx", [NOBODY_KNOWS, NO_RULES, WITH_RULES])
def test_no_assembled_prompt_frames_a_user_with_a_countrys_law(ctx):
    set_user_context(ctx)
    for name, static, section in _builders():
        [system, *_] = dynamic_prompt(static, section)({"messages": []})
        assert _says(system.content, *COUNTRY_SPECIFIC) == [], name


def test_a_users_assembled_prompts_carry_their_rules():
    set_user_context(WITH_RULES)
    for name, static, section in _builders():
        [system, *_] = dynamic_prompt(static, section)({"messages": []})
        assert "the United Kingdom (GB)" in system.content, name
        assert "2031/32" in system.content, name


def test_the_prompt_reads_the_user_of_the_run_in_progress():
    """One compiled graph serves every user: the prompt is built per call."""
    prompt = dynamic_prompt("Fixed text.", context_section)
    question = HumanMessage("What do I owe?")

    set_user_context(WITH_RULES)
    first = prompt({"messages": [question]})
    set_user_context(NOBODY_KNOWS)
    second = prompt({"messages": [question]})

    assert isinstance(first[0], SystemMessage) and first[1:] == [question]
    assert first[0].content.startswith("Fixed text.\n\nAbout this user:")
    assert "United Kingdom" in first[0].content
    assert "United Kingdom" not in second[0].content


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
    assert _says(neutral, *COUNTRY_SPECIFIC) == []


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


class _Rules:
    """TaxService's ActiveRules, as far as the agent service reads it."""

    def __init__(self) -> None:
        from salli.domain.taxrules.schema import RuleSet
        from tests.taxrules.documents import minimal

        self.document = RuleSet.model_validate(minimal())
        self.country, self.region, self.year = "XZ", None, "2031"
        self.start, self.end = datetime.date(2031, 1, 1), datetime.date(2031, 12, 31)
        self.version = {"id": "v1", "version": 2}


class _Tax:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def status(self, user_id, *, today=None):
        if self.fail:
            raise LookupError("no profile")
        from salli.application.services.tax_service import TaxJurisdiction, TaxYearStatus

        rules = _Rules()
        return TaxYearStatus(
            TaxJurisdiction("GB", None, "tax_residency", "GB", "GBP"), rules, rules
        )


async def test_the_service_gathers_the_users_context():
    from salli.application.services.agent_service import AgentService

    ctx = await AgentService(None, _Tax()).user_context("u1")
    assert (ctx.base_currency, ctx.tax_residency) == ("GBP", "GB")
    assert ctx.current is not None and ctx.current.version == 2
    assert ctx.current.sources == ("A fictional law",)
    assert ("income", "Income", "income") in ctx.current.roles

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

    assert [c.tax_residency for c in seen] == ["GB"]
