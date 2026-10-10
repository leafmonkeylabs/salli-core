"""The first-run flow every surface shares (the API, which `salli onboarding` calls, and `salli-server setup`)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from salli.application.services.onboarding_service import (
    BASE_ACCOUNTS,
    SYSTEM_NEED_TAGS,
    OnboardingService,
    starter_chart,
)

EVERY_SOURCE = ["employment", "freelance", "rental", "interest", "foreign", "dividends"]

#: Everyone's: their income sources, and nothing about anyone's tax.
NEUTRAL_CHART = [
    ("1100", "Cash", "asset", None),
    ("1200", "Bank Account", "asset", None),
    ("3000", "Opening Equity", "equity", None),
    ("5000", "General Expenses", "expense", None),
    ("4100", "Employment Income", "income", None),
    ("4200", "Freelance / Business Income", "income", None),
    ("5100", "Business Expenses", "expense", None),
    ("4300", "Rental Income", "income", None),
    ("5200", "Property & Maintenance Expenses", "expense", None),
    ("4400", "Interest Income", "income", None),
    ("1300", "Foreign Currency Account", "asset", None),
    ("4500", "Foreign Income", "income", None),
    ("4600", "Dividend Income", "income", None),
]


def _service(existing_codes=(), residency: str | None = None):
    documents, fi, ledger, profile = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    ledger.list_accounts.return_value = [SimpleNamespace(code=c) for c in existing_codes]
    profile.get_tax_residency.return_value = residency
    return OnboardingService(documents, fi, ledger, profile), documents, fi, ledger


def _opened(ledger) -> list[tuple]:
    return [
        (c.kwargs["code"], c.kwargs["name"], c.kwargs["type"], c.kwargs["tax_role"])
        for c in ledger.add_account.await_args_list
    ]


async def test_a_name_alone_gets_the_base_ledger_and_need_tags():
    svc, documents, fi, ledger = _service()

    result = await svc.complete("u1", {"name": "Asha"})

    assert _opened(ledger) == [tuple(seed) for seed in BASE_ACCOUNTS]
    ledger.ensure_system_tags.assert_awaited_once_with("u1", SYSTEM_NEED_TAGS)
    fi.create_goal.assert_not_awaited()
    assert result["memories_saved"] == ["onboarding_complete", "user_name", "residency_status"]


async def test_every_resident_gets_the_same_neutral_chart():
    """Tax accounts come from the user's own rule sets once they have some
    (`suggested_accounts`), never from where they live: Salli knows no
    country's tax."""
    for residency in ("LK", "US", None):
        svc, _, _, ledger = _service(residency=residency)

        await svc.complete("u1", {"name": "Asha", "income_sources": EVERY_SOURCE})

        assert _opened(ledger) == NEUTRAL_CHART, residency
        assert {role for *_, role in _opened(ledger)} == {None}


async def test_rerunning_skips_accounts_that_exist():
    svc, _, _, ledger = _service(existing_codes=[code for code, *_ in BASE_ACCOUNTS])

    result = await svc.complete("u1", {"name": "Asha"})

    ledger.add_account.assert_not_awaited()
    assert result["accounts_created"] == []


async def test_a_concrete_target_seeds_a_first_goal():
    svc, _, fi, _ = _service()

    await svc.complete(
        "u1",
        {
            "name": "Asha",
            "primary_goal": "home",
            "goal_target_amount": 25_000_000,
            "goal_target_year": "2030",
        },
    )

    goal = fi.create_goal.await_args.args[1]
    assert goal["name"] == "Buy a home"
    assert goal["target_date"] == "2030-12-31"


async def test_status_reads_the_completion_memory():
    svc, documents, _, _ = _service()
    documents.get_memory.return_value = None
    assert not await svc.is_complete("u1")
    documents.get_memory.return_value = {"value": "true"}
    assert await svc.is_complete("u1")


def test_the_starter_chart_is_the_base_and_the_income_sources():
    chart = starter_chart(["foreign"])
    assert chart == [*BASE_ACCOUNTS, *[s for s in chart if s.code in ("1300", "4500")]]
    assert ("4500", "Foreign Income", "income", None) in chart


async def test_a_source_given_twice_opens_its_accounts_once():
    svc, _, _, ledger = _service()

    await svc.complete("u1", {"name": "Asha", "income_sources": ["employment", "employment"]})

    assert [opened[0] for opened in _opened(ledger)].count("4100") == 1
