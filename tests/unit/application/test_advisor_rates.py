"""The advisor researches current deposit rates where the user is, not in Sri
Lanka for everyone."""

from __future__ import annotations

import sys
import types

import pytest

from salli.application.services.advisor_service import AdvisorService


@pytest.fixture
def searches(monkeypatch) -> list[str]:
    asked: list[str] = []

    class _Search:
        def __init__(self, **kwargs) -> None:
            pass

        async def ainvoke(self, query: str):
            asked.append(query)
            return [{"content": "rates"}]

    module = types.ModuleType("langchain_community.tools.tavily_search")
    module.TavilySearchResults = _Search  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langchain_community.tools.tavily_search", module)
    return asked


async def test_rates_are_researched_where_the_user_is_taxed(searches):
    svc = AdvisorService(None, None, None)
    assert await svc._research_rates("LK", "LKR") == "rates"
    assert await svc._research_rates("GB", "GBP") == "rates"
    assert searches == [
        "current fixed deposit and treasury bill interest rates in Sri Lanka",
        "current fixed deposit and treasury bill interest rates in the United Kingdom",
    ]


async def test_with_no_residency_the_currency_says_whose_rates(searches):
    svc = AdvisorService(None, None, None)
    await svc._research_rates(None, "LKR")
    assert searches == ["current fixed deposit and treasury bill interest rates for LKR savings"]
    # With neither, nothing is searched for.
    assert await svc._research_rates(None, None) == ""
    assert len(searches) == 1
